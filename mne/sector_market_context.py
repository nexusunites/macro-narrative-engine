"""Deterministic sector ETF registry and persisted participation classifier."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mne.sector_isolation import SECTOR_KEYS, SectorMapConfig


DEFAULT_SECTOR_INSTRUMENTS_PATH = Path(__file__).resolve().parents[1] / "config" / "sector_instruments.json"
SECTOR_STALE_MAX_AGE = timedelta(hours=36)
STRONG_MOVE_PCT = 1.0
MEANINGFUL_MOVE_PCT = 0.25
DETACHED_MOVE_EPSILON = 0.01
DATA_FRESHNESS_STATES = frozenset({"FRESH", "STALE", "UNAVAILABLE"})
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class NarrativeSectorInstrumentError(ValueError):
    """Raised when the curated sector instrument registry is invalid."""


def _required_text(record: dict, key: str, location: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NarrativeSectorInstrumentError(f"{location}.{key} must be a non-empty string")
    return value.strip()


def validate_sector_instruments(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise NarrativeSectorInstrumentError("sector instruments must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise NarrativeSectorInstrumentError("version must use MAJOR.MINOR.PATCH semantic versioning")
    raw_sectors = data.get("sectors")
    if not isinstance(raw_sectors, dict):
        raise NarrativeSectorInstrumentError("sectors must be an object")
    sectors, seen = {}, set()
    for sector_key in sorted(raw_sectors):
        if sector_key not in SECTOR_KEYS:
            raise NarrativeSectorInstrumentError(f"unknown sector key: {sector_key}")
        record = raw_sectors[sector_key]
        if not isinstance(record, dict):
            raise NarrativeSectorInstrumentError(f"sectors.{sector_key} must be an object")
        location = f"sectors.{sector_key}"
        display_name = _required_text(record, "display_name", location)
        instrument = _required_text(record, "instrument", location).upper()
        instrument_type = _required_text(record, "instrument_type", location)
        display_enabled = record.get("display_enabled")
        if not isinstance(display_enabled, bool):
            raise NarrativeSectorInstrumentError(f"{location}.display_enabled must be boolean")
        if instrument in seen:
            raise NarrativeSectorInstrumentError(f"duplicate instrument: {instrument}")
        seen.add(instrument)
        sectors[sector_key] = {"display_name": display_name, "instrument": instrument, "instrument_type": instrument_type, "display_enabled": display_enabled}
    return {"version": version, "sectors": sectors}


def load_sector_instruments(path: str | Path = DEFAULT_SECTOR_INSTRUMENTS_PATH) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NarrativeSectorInstrumentError(f"unable to load sector instruments: {exc}") from exc
    return validate_sector_instruments(data)


def build_sector_ticker_map(config: dict[str, Any] | None = None) -> dict[str, str]:
    registry = config or load_sector_instruments()
    return {key: item["instrument"] for key, item in registry["sectors"].items() if item["display_enabled"]}


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d_%H%M%S", "%Y%m%d_%H%M%S"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc))


def _freshness(record: dict[str, Any] | None, now: Any) -> str:
    if not isinstance(record, dict):
        return "UNAVAILABLE"
    observed = _parse_timestamp(record.get("observed_at"))
    reference = _parse_timestamp(now) if now is not None else datetime.now(timezone.utc)
    if observed is None or reference is None:
        return "UNAVAILABLE"
    return "STALE" if reference - observed > SECTOR_STALE_MAX_AGE else "FRESH"


def classify_sector_participation(mapping: Any, record: dict[str, Any] | None, instrument: dict[str, Any] | None, *, now: Any = None) -> dict[str, Any]:
    freshness = _freshness(record, now)
    ticker = instrument.get("instrument") if isinstance(instrument, dict) and instrument.get("display_enabled") else None
    base = {"participation_state": "UNAVAILABLE", "data_freshness": freshness, "instrument": ticker, "pct_change": None}
    if ticker is None or not isinstance(record, dict) or freshness != "FRESH" or not getattr(mapping, "expected_expression", None):
        return base
    try:
        change = float(record.get("pct_change"))
    except (TypeError, ValueError):
        return base
    absolute = abs(change)
    role = mapping.role
    aligned = (change > 0 and mapping.expected_expression == "UP") or (change < 0 and mapping.expected_expression == "DOWN")
    if absolute < DETACHED_MOVE_EPSILON:
        state = "DETACHED"
    elif role == "EMERGING":
        state = "EMERGING" if aligned else "DETACHED"
    elif not aligned and absolute >= MEANINGFUL_MOVE_PCT and role in {"PRIMARY", "SECONDARY"}:
        state = "CONTRADICTING"
    elif aligned and absolute >= STRONG_MOVE_PCT and role in {"PRIMARY", "SECONDARY"}:
        state = "STRONG"
    elif aligned and absolute >= MEANINGFUL_MOVE_PCT:
        state = "PARTICIPATING"
    elif aligned and absolute > 0:
        state = "EMERGING"
    else:
        state = "DETACHED"
    return {**base, "participation_state": state, "pct_change": round(change, 4)}


def _participation_breadth(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fresh = [row for row in rows.values() if row["data_freshness"] == "FRESH" and row["participation_state"] != "UNAVAILABLE"]
    confirming = sum(row["participation_state"] in {"STRONG", "PARTICIPATING"} for row in fresh)
    if any(row["participation_state"] == "CONTRADICTING" for row in fresh):
        state = "CONTRADICTED"
    elif confirming >= 3:
        state = "BROAD"
    elif confirming == 2:
        state = "MODERATE"
    elif confirming == 1:
        state = "CONCENTRATED"
    elif any(row["participation_state"] == "EMERGING" for row in fresh):
        state = "LIMITED"
    else:
        state = "UNAVAILABLE"
    return {"state": state, "fresh_count": len(fresh), "confirming_count": confirming}


def classify_sectors_for_run(run: dict[str, Any], sector_map: SectorMapConfig, narrative: str, *, now: Any = None, instrument_config: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = instrument_config or load_sector_instruments()
    snapshot = run.get("market_snapshot") if isinstance(run, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    mappings = dict(sector_map.narratives).get(narrative, ())
    rows = {}
    for mapping in mappings:
        instrument = registry["sectors"].get(mapping.sector)
        result = classify_sector_participation(mapping, snapshot.get(mapping.sector), instrument, now=now)
        state = result["participation_state"]
        freshness = result["data_freshness"]
        result.update({"participation_label_key": f"participation_{state}", "participation_explanation_key": f"participation_explanation_{state}", "freshness_label_key": f"freshness_{freshness}"})
        rows[mapping.sector] = result
    return {"sectors": rows, "participation_breadth": _participation_breadth(rows)}
