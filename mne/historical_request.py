"""User-safe historical reconstruction request state and orchestration.

This module owns the product-category boundary and persisted request record.
Backfill and replay behavior remains in the existing historical workflow.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import config
from mne import historical_workflow
from mne.historical_replay_admin import is_valid_replay_id


MAX_REQUEST_DAYS = 92
CATEGORY_SOURCES = {
    "monetary_policy": "fed_fomc",
    "inflation": "bls_cpi",
    "growth_consumer": "bea_gdp_pce",
    "energy_commodities": "eia_energy",
}
CATEGORY_ORDER = tuple(CATEGORY_SOURCES)
REQUEST_ID_PATTERN = re.compile(r"^request_[a-f0-9]{24}$")
FORM_FIELDS = frozenset({"start_date", "end_date", "category"})


class HistoricalRequestValidationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_request(start_date, end_date, categories) -> dict:
    try:
        start = date.fromisoformat(str(start_date or "").strip())
        end = date.fromisoformat(str(end_date or "").strip())
    except ValueError as error:
        raise HistoricalRequestValidationError("invalid_dates") from error
    if end < start:
        raise HistoricalRequestValidationError("invalid_dates")
    if (end - start).days + 1 > MAX_REQUEST_DAYS:
        raise HistoricalRequestValidationError("range_too_large")

    submitted = [str(value or "").strip() for value in categories or ()]
    if not submitted:
        raise HistoricalRequestValidationError("empty_categories")
    if any(value not in CATEGORY_SOURCES for value in submitted):
        raise HistoricalRequestValidationError("invalid_categories")
    selected = set(submitted)
    ordered = [token for token in CATEGORY_ORDER if token in selected]
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "categories": ordered,
        "sources": [CATEGORY_SOURCES[token] for token in ordered],
    }


def validate_form_fields(field_names) -> None:
    if any(str(name) not in FORM_FIELDS for name in field_names):
        raise HistoricalRequestValidationError("invalid_submission")


def build_request_id(start_date: str, end_date: str, categories) -> str:
    identity = json.dumps(
        {
            "categories": sorted(categories),
            "end_date": end_date,
            "start_date": start_date,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"request_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"


def is_valid_request_id(value) -> bool:
    return bool(REQUEST_ID_PATTERN.fullmatch(str(value or "")))


def load_request(request_id, data_dir=None) -> dict | None:
    path = _request_path(request_id, data_dir)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        record = json.load(fh)
    if not isinstance(record, dict) or record.get("request_id") != request_id:
        raise ValueError("Historical request record is invalid.")
    return record


def execute_request(
    start_date,
    end_date,
    categories,
    *,
    run_backfills: Callable,
    run_replay: Callable,
    data_dir=None,
) -> dict:
    validated = validate_request(start_date, end_date, categories)
    request_id = build_request_id(
        validated["start_date"], validated["end_date"], validated["categories"]
    )
    existing = load_request(request_id, data_dir=data_dir)
    if existing and existing.get("state") == "COMPLETE":
        return {"request_id": request_id, "reused": True}

    now = _format_utc_now()
    record = {
        "request_id": request_id,
        "requested_period": {
            "start_date": validated["start_date"],
            "end_date": validated["end_date"],
        },
        "requested_product_categories": validated["categories"],
        "category_outcomes": [],
        "state": "REQUESTED",
        "resulting_replay_reference": None,
        "requested_at": (existing or {}).get("requested_at") or now,
        "started_at": None,
        "completed_at": None,
        "updated_at": now,
    }
    _write_request(record, data_dir)
    record["state"] = "RUNNING"
    record["started_at"] = _format_utc_now()
    record["updated_at"] = record["started_at"]
    _write_request(record, data_dir)

    try:
        backfill_result = run_backfills(
            validated["sources"],
            validated["end_date"],
            validated["start_date"],
            validated["end_date"],
        )
        workflow_id = backfill_result.get("workflow_id")
        if not workflow_id:
            raise RuntimeError("Historical workflow could not start.")
        manifest = historical_workflow.load_workflow_manifest(
            workflow_id, data_dir=data_dir
        )
        if not manifest:
            raise RuntimeError("Historical workflow result is unavailable.")
        record["category_outcomes"] = _build_category_outcomes(
            validated["categories"], manifest.get("source_outcomes")
        )
        replay_result = run_replay(workflow_id, "run_replay")
        replay_id = replay_result.get("replay_id")
        if not is_valid_replay_id(replay_id):
            record["state"] = "FAILED"
        else:
            record["resulting_replay_reference"] = replay_id
            record["state"] = (
                "COMPLETE"
                if all(
                    item["outcome"] == "RECONSTRUCTED"
                    for item in record["category_outcomes"]
                )
                else "PARTIAL"
            )
    except Exception:
        record["state"] = "FAILED"
        if not record["category_outcomes"]:
            record["category_outcomes"] = [
                {"category": token, "outcome": "FAILED", "record_count": 0}
                for token in validated["categories"]
            ]

    record["completed_at"] = _format_utc_now()
    record["updated_at"] = record["completed_at"]
    _write_request(record, data_dir)
    return {"request_id": request_id, "reused": False}


def build_user_request_view(record) -> dict:
    """Whitelist persisted request fields for the user status surface."""
    data = record if isinstance(record, dict) else {}
    period = data.get("requested_period") or {}
    outcomes = []
    for item in data.get("category_outcomes") or ():
        category = item.get("category")
        outcome = item.get("outcome")
        if category not in CATEGORY_SOURCES or outcome not in {
            "RECONSTRUCTED",
            "NO_RECORDS",
            "FAILED",
        }:
            continue
        outcomes.append(
            {
                "category": category,
                "outcome": outcome,
                "record_count": max(0, int(item.get("record_count") or 0)),
            }
        )
    replay_id = data.get("resulting_replay_reference")
    return {
        "state": data.get("state")
        if data.get("state") in {"REQUESTED", "RUNNING", "COMPLETE", "PARTIAL", "FAILED"}
        else "FAILED",
        "start_date": period.get("start_date"),
        "end_date": period.get("end_date"),
        "categories": [
            token
            for token in data.get("requested_product_categories") or ()
            if token in CATEGORY_SOURCES
        ],
        "outcomes": outcomes,
        "investigation_url": f"/history/{replay_id}"
        if is_valid_replay_id(replay_id)
        else None,
        "comparison_url": "/studio/compare",
    }


def _build_category_outcomes(categories, source_outcomes) -> list[dict]:
    by_source = {
        item.get("source"): item
        for item in source_outcomes or ()
        if isinstance(item, dict)
    }
    outcome_names = {
        "COMPLETE": "RECONSTRUCTED",
        "EMPTY": "NO_RECORDS",
        "FAILED": "FAILED",
    }
    rows = []
    for token in categories:
        item = by_source.get(CATEGORY_SOURCES[token]) or {}
        rows.append(
            {
                "category": token,
                "outcome": outcome_names.get(item.get("status"), "FAILED"),
                "record_count": max(0, int(item.get("evidence_count") or 0)),
            }
        )
    return rows


def _request_root(data_dir=None) -> Path:
    base = Path(data_dir) if data_dir is not None else config.get_data_dir()
    return base / "historical_requests"


def _request_path(request_id, data_dir=None) -> Path:
    if not is_valid_request_id(request_id):
        raise ValueError("Unknown historical request identifier.")
    root = _request_root(data_dir).resolve()
    candidate = (root / request_id).resolve()
    if candidate.parent != root:
        raise ValueError("Unknown historical request identifier.")
    return candidate / "request.json"


def _write_request(record, data_dir=None) -> Path:
    path = _request_path(record.get("request_id"), data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, sort_keys=True)
    temporary.replace(path)
    return path


def _format_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
