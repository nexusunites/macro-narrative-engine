import json
import logging
import re
from pathlib import Path

from mne import historical_backfill


LOGGER = logging.getLogger(__name__)
RECENT_BACKFILL_LIMIT = 10
BACKFILL_ID_PATTERN = re.compile(
    r"^backfill_\d{4}-\d{2}-\d{2}(?:_\d{4}-\d{2}-\d{2})?_[a-z0-9]+_[a-z0-9_]+$"
)


def is_valid_backfill_id(value):
    return bool(BACKFILL_ID_PATTERN.fullmatch(str(value or "")))


def normalize_backfill_display_path(backfill_id):
    if not is_valid_backfill_id(backfill_id):
        return None
    return f"historical_evidence/{backfill_id}/"


def build_backfill_admin_summary(manifest):
    data = manifest if isinstance(manifest, dict) else {}
    backfill_id = data.get("backfill_id")
    return {
        "backfill_id": backfill_id,
        "source": data.get("source_id"),
        "provider": data.get("provider"),
        "category": data.get("category"),
        "requested_start_date": data.get("requested_start_date"),
        "requested_end_date": data.get("requested_end_date"),
        "records_found": data.get("records_found"),
        "evidence_count": data.get("evidence_count"),
        "replay_ready": data.get("replay_ready"),
        "warnings": list(data.get("warnings") or []),
        "limitations": list(data.get("limitations") or []),
        "artifact_display_path": normalize_backfill_display_path(backfill_id),
        "generated_at": data.get("generated_at"),
    }


def list_recent_backfill_summaries(data_dir=None, limit=RECENT_BACKFILL_LIMIT):
    root = historical_backfill._historical_evidence_root(data_dir=data_dir)
    if not root.exists():
        return []

    manifests = sorted(
        root.glob("*/manifest.json"),
        key=_safe_mtime,
        reverse=True,
    )[: max(0, limit)]
    rows = []
    for path in manifests:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            if not isinstance(manifest, dict):
                raise ValueError("Backfill manifest did not contain a JSON object.")
            summary = build_backfill_admin_summary(manifest)
            if not is_valid_backfill_id(summary.get("backfill_id")):
                raise ValueError("Backfill manifest contained an invalid identifier.")
            rows.append(summary)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            LOGGER.warning("Could not read historical backfill summary %s: %s", path, error)
    return rows


def load_backfill_summary_by_id(backfill_id, data_dir=None):
    if not is_valid_backfill_id(backfill_id):
        raise ValueError("Unknown backfill identifier.")

    root = historical_backfill._historical_evidence_root(data_dir=data_dir).resolve()
    candidate = (root / backfill_id).resolve()
    if candidate.parent != root:
        raise ValueError("Unknown backfill identifier.")
    manifest = historical_backfill.load_backfill_manifest(backfill_id, data_dir=data_dir)
    if manifest is None:
        raise FileNotFoundError("Backfill manifest was not found.")
    return build_backfill_admin_summary(manifest)


def build_backfill_error_context(error):
    LOGGER.warning("Historical backfill admin operation failed: %s", error, exc_info=True)
    return {
        "status": "failed",
        "message": "The backfill could not be completed. Review the backfill diagnostics and try again.",
    }


def _safe_mtime(path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0
