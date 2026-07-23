import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config
from mne import historical_backfill, historical_backfill_admin


SUPPORTED_MODE = historical_backfill.SUPPORTED_MODE
WORKFLOW_ID_PATTERN = re.compile(
    r"^workflow_\d{4}-\d{2}-\d{2}_[a-f0-9]{12}$"
)


def run_workflow_backfills(
    sources, start_date, end_date, data_dir=None
) -> list[dict]:
    requested_sources = _validate_sources(sources)
    # This public builder performs all range validation before any connector is
    # reached. One call is enough because the range is shared by every source.
    historical_backfill.build_backfill_request(
        requested_range=(start_date, end_date),
        source_categories=(requested_sources[0],),
    )

    outcomes = []
    for source in historical_backfill.SUPPORTED_SOURCES:
        if source not in requested_sources:
            continue
        try:
            _, result = historical_backfill.run_and_persist_historical_backfill(
                source, start_date, end_date, data_dir=data_dir
            )
            manifest = result["manifest"]
            replay_ready = manifest.get("replay_ready") is True
            outcomes.append(
                {
                    "source": source,
                    "status": "COMPLETE" if replay_ready else "EMPTY",
                    "backfill_id": manifest.get("backfill_id"),
                    "evidence_count": manifest.get("evidence_count", 0),
                    "replay_ready": replay_ready,
                    "warnings": list(manifest.get("warnings") or []),
                    "limitations": list(manifest.get("limitations") or []),
                    "error_message": None,
                }
            )
        except Exception as error:
            context = historical_backfill_admin.build_backfill_error_context(error)
            outcomes.append(
                {
                    "source": source,
                    "status": "FAILED",
                    "backfill_id": None,
                    "evidence_count": 0,
                    "replay_ready": False,
                    "warnings": [],
                    "limitations": [],
                    "error_message": context["message"],
                }
            )
    return outcomes


def build_workflow_manifest(
    replay_date,
    start_date,
    end_date,
    mode,
    requested_sources,
    source_outcomes,
) -> dict:
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode != SUPPORTED_MODE:
        raise ValueError("Unsupported historical workflow mode.")
    replay_request = _validate_replay_date(replay_date, normalized_mode)
    ordered_sources = _validate_sources(requested_sources)
    resolved_start = str(start_date or "").strip() or replay_request.replay_date
    resolved_end = str(end_date or "").strip() or replay_request.replay_date
    historical_backfill.build_backfill_request(
        requested_range=(resolved_start, resolved_end),
        source_categories=(ordered_sources[0],),
    )
    replay_day = replay_request.replay_date
    return {
        "workflow_id": f"workflow_{replay_day}_{uuid.uuid4().hex[:12]}",
        "generated_at": _format_utc_now(),
        "requested_replay_date": replay_day,
        "requested_start_date": resolved_start,
        "requested_end_date": resolved_end,
        "mode": normalized_mode,
        "requested_sources": ordered_sources,
        "source_outcomes": list(source_outcomes),
        "replay_id": None,
    }


def write_workflow_manifest(manifest, data_dir=None) -> Path:
    workflow_id = (manifest or {}).get("workflow_id")
    if not is_valid_workflow_id(workflow_id):
        raise ValueError("Unknown workflow identifier.")
    root = _workflow_root(data_dir)
    output_dir = root / workflow_id
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "manifest.json"
    _write_json(path, manifest)
    return path


def load_workflow_manifest(workflow_id, data_dir=None) -> dict | None:
    if not is_valid_workflow_id(workflow_id):
        raise ValueError("Unknown workflow identifier.")
    root = _workflow_root(data_dir).resolve()
    candidate = (root / workflow_id).resolve()
    if candidate.parent != root:
        raise ValueError("Unknown workflow identifier.")
    path = candidate / "manifest.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    if not isinstance(manifest, dict) or manifest.get("workflow_id") != workflow_id:
        raise ValueError("Workflow manifest contained an invalid identifier.")
    return manifest


def mark_workflow_replay(workflow_id, replay_id, data_dir=None) -> None:
    from mne.historical_replay_admin import is_valid_replay_id

    if not is_valid_replay_id(replay_id):
        raise ValueError("Unknown replay identifier.")
    manifest = load_workflow_manifest(workflow_id, data_dir=data_dir)
    if manifest is None:
        raise FileNotFoundError("Workflow manifest was not found.")
    manifest["replay_id"] = replay_id
    _write_json(_workflow_root(data_dir) / workflow_id / "manifest.json", manifest)


def is_valid_workflow_id(value) -> bool:
    return bool(WORKFLOW_ID_PATTERN.fullmatch(str(value or "")))


def _validate_sources(sources) -> list[str]:
    submitted = [str(source).strip() for source in (sources or ()) if str(source).strip()]
    if not submitted:
        raise ValueError("Select at least one supported source.")
    if any(source not in historical_backfill.SUPPORTED_SOURCES for source in submitted):
        raise ValueError("The selected source is not supported.")
    selected = set(submitted)
    return [
        source for source in historical_backfill.SUPPORTED_SOURCES if source in selected
    ]


def _validate_replay_date(replay_date, mode):
    # Local import avoids making the workflow module an alternate replay engine.
    from mne import historical_replay

    return historical_replay.build_replay_request(replay_date, mode=mode)


def _workflow_root(data_dir=None) -> Path:
    base_dir = Path(data_dir) if data_dir is not None else config.get_data_dir()
    return base_dir / "historical_workflows"


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)


def _format_utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
