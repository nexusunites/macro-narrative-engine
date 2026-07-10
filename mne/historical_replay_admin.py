import json
import logging
import re
from pathlib import Path


LOGGER = logging.getLogger(__name__)
RECENT_REPLAY_LIMIT = 10
REPLAY_ID_PATTERN = re.compile(r"^replay_\d{4}-\d{2}-\d{2}_[a-z0-9_-]+$")


def is_valid_replay_id(value):
    return bool(REPLAY_ID_PATTERN.fullmatch(str(value or "")))


def sorted_scores(scores):
    if not isinstance(scores, dict):
        return []
    return sorted(scores.items(), key=lambda item: _score_sort_value(item[1]), reverse=True)


def build_replay_admin_summary(replay_output, replay_path=None, replay_dir=None):
    output = replay_output if isinstance(replay_output, dict) else {}
    metadata = output.get("replay_metadata") if isinstance(output.get("replay_metadata"), dict) else {}
    artifact_filename = Path(replay_path).name if replay_path else _artifact_filename(output)

    return {
        "status": "completed",
        "message": "Historical replay completed successfully.",
        "replay_id": output.get("replay_id"),
        "replay_date": output.get("replay_date"),
        "evidence_cutoff": output.get("evidence_cutoff"),
        "generated_at": output.get("generated_at"),
        "mode": _display_mode(output, metadata),
        "evidence_count": output.get("evidence_count"),
        "accepted_evidence_count": _accepted_evidence_count(output),
        "source_count": output.get("source_count"),
        "dominant_theme": output.get("dominant_theme"),
        "dominant_group": output.get("dominant_group"),
        "theme_scores": sorted_scores(output.get("theme_scores")),
        "group_scores": sorted_scores(output.get("group_scores")),
        "warnings": build_replay_warning_messages(output),
        "artifact_filename": artifact_filename,
        "artifact_display_path": normalize_replay_display_path(replay_path, replay_dir)
        if replay_path
        else _artifact_display_path(artifact_filename),
    }


def build_replay_warning_messages(replay_output):
    output = replay_output if isinstance(replay_output, dict) else {}
    metadata = output.get("replay_metadata") if isinstance(output.get("replay_metadata"), dict) else {}
    warnings = list(metadata.get("warnings") or [])

    evidence_count = _int_or_none(output.get("evidence_count"))
    source_count = _int_or_none(output.get("source_count"))
    if evidence_count == 0 and not _contains_text(warnings, "No accepted evidence"):
        warnings.append("No eligible historical evidence was available for this date.")
    elif evidence_count is not None and evidence_count < 5 and not _contains_text(warnings, "Only"):
        warnings.append("Replay completed with a thin evidence base.")
    if source_count is not None and 0 < source_count < 2:
        warnings.append("The replay completed, but source coverage was limited.")
    if not output.get("dominant_theme"):
        warnings.append("No dominant narrative theme was identified from the available evidence.")
    if not output.get("dominant_group"):
        warnings.append("No dominant narrative group was identified from the available evidence.")

    return _dedupe(warnings)


def list_recent_replay_summaries(replay_dir, limit=RECENT_REPLAY_LIMIT):
    replay_path = Path(replay_dir)
    if not replay_path.exists():
        return []

    files = sorted(
        replay_path.glob("*.json"),
        key=lambda item: _safe_mtime(item),
        reverse=True,
    )[:limit]
    rows = []
    for path in files:
        row = {
            "filename": path.name,
            "artifact_display_path": _artifact_display_path(path.name),
            "replay_id": path.stem if is_valid_replay_id(path.stem) else None,
            "replay_date": None,
            "generated_at": None,
            "evidence_count": None,
            "source_count": None,
            "dominant_theme": None,
            "dominant_group": None,
            "status": "Unreadable",
            "unreadable": True,
            "error": "Replay summary could not be read.",
        }
        try:
            data = _read_replay_json(path)
            row.update(
                {
                    "replay_id": data.get("replay_id") if is_valid_replay_id(data.get("replay_id")) else row["replay_id"],
                    "replay_date": data.get("replay_date"),
                    "generated_at": data.get("generated_at"),
                    "evidence_count": data.get("evidence_count"),
                    "source_count": data.get("source_count"),
                    "dominant_theme": data.get("dominant_theme"),
                    "dominant_group": data.get("dominant_group"),
                    "status": "Completed",
                    "unreadable": False,
                    "error": None,
                }
            )
        except (OSError, json.JSONDecodeError, ValueError) as error:
            LOGGER.warning("Could not read historical replay summary %s: %s", path.name, error)
        rows.append(row)
    return rows


def load_replay_summary_by_id(replay_dir, replay_id):
    if not is_valid_replay_id(replay_id):
        raise ValueError("Unknown replay identifier.")

    replay_path = Path(replay_dir).resolve()
    candidate = (replay_path / f"{replay_id}.json").resolve()
    if candidate.parent != replay_path:
        raise ValueError("Unknown replay identifier.")
    if not candidate.exists():
        raise FileNotFoundError("Replay artifact was not found.")
    output = _read_replay_json(candidate)
    return build_replay_admin_summary(output, candidate, replay_path)


def normalize_replay_display_path(replay_path, replay_dir=None):
    filename = Path(replay_path).name
    if replay_dir is not None:
        try:
            base = Path(replay_dir).resolve()
            candidate = Path(replay_path).resolve()
            if candidate.parent != base:
                return _artifact_display_path(filename)
        except OSError:
            pass
    return _artifact_display_path(filename)


def build_replay_error_context(error):
    LOGGER.warning("Historical replay admin operation failed: %s", error, exc_info=True)
    return {
        "status": "failed",
        "message": "The replay could not be completed. Review the replay diagnostics and try again.",
    }


def _read_replay_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("Replay file did not contain a JSON object.")
    return data


def _artifact_filename(output):
    replay_id = output.get("replay_id") if isinstance(output, dict) else None
    return f"{replay_id}.json" if replay_id else None


def _artifact_display_path(filename):
    return f"replays/{filename}" if filename else None


def _display_mode(output, metadata):
    mode = output.get("mode") if isinstance(output, dict) else None
    if mode:
        return mode
    replay_mode = metadata.get("replay_mode")
    if replay_mode == "HISTORICAL_REPLAY":
        return "macro"
    return "macro"


def _accepted_evidence_count(output):
    source_intelligence = output.get("source_intelligence") if isinstance(output, dict) else None
    if isinstance(source_intelligence, dict):
        return source_intelligence.get("accepted_evidence_count")
    return output.get("evidence_count") if isinstance(output, dict) else None


def _score_sort_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _contains_text(messages, text):
    needle = text.lower()
    return any(needle in str(message).lower() for message in messages)


def _dedupe(messages):
    seen = set()
    result = []
    for message in messages:
        text = str(message)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_mtime(path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0
