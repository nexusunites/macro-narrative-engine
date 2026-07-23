import json
from datetime import datetime, timezone
from pathlib import Path

import config
from mne.evidence_summary import (
    build_evidence_reader_summary,
    normalize_evidence_reader_metadata,
)
from mne.historical_replay_admin import (
    build_replay_warning_messages,
    is_valid_replay_id,
    normalize_replay_display_path,
    sorted_scores,
)


class HistoricalResearchError(Exception):
    message = "The selected replay artifact could not be loaded."


class InvalidReplayIdentifier(HistoricalResearchError):
    message = "The replay identifier is invalid."


class ReplayArtifactNotFound(HistoricalResearchError):
    message = "Historical replay not found."


class ReplayArtifactLoadError(HistoricalResearchError):
    message = "The selected replay artifact could not be loaded."


class ReplayArtifactUnsupported(HistoricalResearchError):
    message = "This replay does not contain enough data for a historical research view."


def default_replay_dir():
    return config.get_data_dir() / "replays"


def validate_replay_id(replay_id):
    value = str(replay_id or "").strip()
    if not value or len(value) > 160 or not is_valid_replay_id(value):
        raise InvalidReplayIdentifier()
    return value


def resolve_replay_artifact_path(replay_id, replay_dir=None):
    normalized_id = validate_replay_id(replay_id)
    base_dir = Path(replay_dir) if replay_dir is not None else default_replay_dir()
    try:
        resolved_base = base_dir.resolve()
        candidate = (resolved_base / f"{normalized_id}.json").resolve()
    except OSError as error:
        raise ReplayArtifactLoadError() from error

    if candidate.parent != resolved_base:
        raise InvalidReplayIdentifier()
    if not candidate.exists() or not candidate.is_file():
        raise ReplayArtifactNotFound()
    return candidate


def load_replay_for_historical_research(replay_id, replay_dir=None):
    replay_path = resolve_replay_artifact_path(replay_id, replay_dir=replay_dir)
    try:
        with open(replay_path, "r", encoding="utf-8") as fh:
            artifact = json.load(fh)
    except json.JSONDecodeError as error:
        raise ReplayArtifactLoadError() from error
    except OSError as error:
        raise ReplayArtifactLoadError() from error

    if not isinstance(artifact, dict):
        raise ReplayArtifactLoadError()
    if artifact.get("replay_id") and artifact.get("replay_id") != validate_replay_id(replay_id):
        raise ReplayArtifactUnsupported()
    return artifact, replay_path


def build_historical_research_context(replay_artifact, replay_path=None, replay_dir=None):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    if not artifact.get("replay_id") and not artifact.get("replay_date"):
        raise ReplayArtifactUnsupported()

    metadata = artifact.get("replay_metadata") if isinstance(artifact.get("replay_metadata"), dict) else {}
    narratives = build_historical_narrative_list(artifact)
    selected_narrative = _selected_narrative(artifact, narratives)
    evidence = build_historical_evidence_context(artifact, selected_narrative=selected_narrative)
    warnings = build_historical_research_warnings(artifact, evidence)
    replay = build_historical_replay_snapshot(artifact, replay_path, replay_dir)

    return {
        "is_historical": True,
        "is_admin_view": True,
        "read_only": True,
        "replay": replay,
        "snapshot": {
            "dominant_theme": artifact.get("dominant_theme"),
            "dominant_group": artifact.get("dominant_group"),
            "evidence_count": artifact.get("evidence_count"),
            "accepted_evidence_count": _accepted_evidence_count(artifact),
            "source_count": artifact.get("source_count"),
            "warnings": warnings,
        },
        "historical_read": {
            "dominant_narrative": (
                artifact.get("dominant_group")
                or artifact.get("dominant_theme")
                or "Unavailable"
            ),
            "theme_scores": sorted_scores(artifact.get("theme_scores")),
            "group_scores": sorted_scores(artifact.get("group_scores")),
        },
        "narratives": narratives,
        "selected_narrative": selected_narrative,
        "evidence": evidence,
        "temporal_integrity": build_temporal_integrity_context(artifact),
        "metadata": build_safe_replay_metadata_context(artifact),
    }


def build_historical_replay_snapshot(replay_artifact, replay_path=None, replay_dir=None):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    metadata = artifact.get("replay_metadata") if isinstance(artifact.get("replay_metadata"), dict) else {}
    artifact_filename = Path(replay_path).name if replay_path else _artifact_filename(artifact)
    return {
        "replay_id": artifact.get("replay_id"),
        "replay_date": artifact.get("replay_date"),
        "evidence_cutoff": artifact.get("evidence_cutoff"),
        "generated_at": artifact.get("generated_at"),
        "mode": artifact.get("mode") or _display_mode(metadata),
        "status": artifact.get("status") or "completed",
        "artifact_filename": artifact_filename,
        "artifact_display_path": (
            normalize_replay_display_path(replay_path, replay_dir)
            if replay_path
            else _artifact_display_path(artifact_filename)
        ),
    }


def build_historical_narrative_list(replay_artifact):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    rows = []
    dominant_group = artifact.get("dominant_group")
    dominant_theme = artifact.get("dominant_theme")

    for key, score in sorted_scores(artifact.get("group_scores")):
        if not _positive_score(score):
            continue
        rows.append(
            {
                "key": f"group:{key}",
                "label": key,
                "level": "group",
                "score": score,
                "group": key,
                "evidence_count": _evidence_count_for_narrative(artifact, "group", key),
                "selected": key == dominant_group,
                "dominant": key == dominant_group,
            }
        )

    for key, score in sorted_scores(artifact.get("theme_scores")):
        if not _positive_score(score):
            continue
        rows.append(
            {
                "key": f"theme:{key}",
                "label": str(key).replace("_", " ").title(),
                "level": "theme",
                "score": score,
                "group": _group_for_theme(artifact, key),
                "evidence_count": _evidence_count_for_narrative(artifact, "theme", key),
                "selected": key == dominant_theme and not dominant_group,
                "dominant": key == dominant_theme,
            }
        )
    return rows


def build_historical_evidence_context(replay_artifact, selected_narrative=None):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    cutoff = _parse_datetime(artifact.get("evidence_cutoff"))
    evidence_rows = []
    for evidence in _artifact_evidence(artifact):
        if not isinstance(evidence, dict):
            continue
        published_at = _evidence_timestamp(evidence)
        parsed_published_at = _parse_datetime(published_at)
        if cutoff is not None and parsed_published_at is not None and parsed_published_at > cutoff:
            continue
        evidence_rows.append(
            _display_evidence(evidence, selected_narrative=selected_narrative)
        )
    return evidence_rows


def build_temporal_integrity_context(replay_artifact):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    metadata = artifact.get("replay_metadata") if isinstance(artifact.get("replay_metadata"), dict) else {}
    return {
        "persisted_evidence_only": metadata.get("live_run_source") is False,
        "future_evidence_excluded": metadata.get("future_evidence_excluded"),
        "live_fetch_performed": metadata.get("live_fetch_performed", False),
        "selection_rule": metadata.get("evidence_selection_rule"),
        "knowledge_boundary": metadata.get("knowledge_boundary"),
        "publication_cutoff": artifact.get("evidence_cutoff"),
        "message": (
            "This replay uses persisted evidence available at the selected cutoff. "
            "Future evidence was excluded."
        ),
    }


def build_historical_research_warnings(replay_artifact, evidence_rows=None):
    warnings = build_replay_warning_messages(replay_artifact)
    evidence_rows = evidence_rows if isinstance(evidence_rows, list) else []
    evidence_count = _int_or_none((replay_artifact or {}).get("evidence_count"))
    source_count = _int_or_none((replay_artifact or {}).get("source_count"))

    if evidence_count is not None and evidence_count < 5:
        warnings.append("Historical evidence was limited for this replay.")
    if source_count is not None and 0 < source_count < 2:
        warnings.append("Interpret this reconstruction with caution because historical source coverage was thin.")
    if evidence_count and not evidence_rows:
        warnings.append("The replay scores are available, but individual historical evidence records were not stored in this artifact.")
    return _dedupe(warnings)


def build_safe_replay_metadata_context(replay_artifact):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    metadata = artifact.get("replay_metadata") if isinstance(artifact.get("replay_metadata"), dict) else {}
    return {
        "taxonomy_version": artifact.get("taxonomy_version"),
        "registry_version": artifact.get("registry_version"),
        "replay_engine_version": metadata.get("replay_engine_version"),
        "replay_mode": metadata.get("replay_mode"),
        "evidence_selection_rule": metadata.get("evidence_selection_rule"),
        "future_evidence_excluded": metadata.get("future_evidence_excluded"),
        "live_run_source": metadata.get("live_run_source"),
        "warnings": list(metadata.get("warnings") or []),
        "coverage_intelligence": build_historical_coverage_display_context(artifact),
    }


def build_historical_coverage_display_context(replay_artifact):
    artifact = replay_artifact if isinstance(replay_artifact, dict) else {}
    source_intelligence = artifact.get("source_intelligence")
    coverage = (
        source_intelligence.get("coverage_intelligence")
        if isinstance(source_intelligence, dict)
        else None
    )
    if not isinstance(coverage, dict):
        return None
    return {
        "breadth_state": coverage.get("breadth_state"),
        "evidence_origins_used": list(coverage.get("evidence_origins_used") or []),
        "coverage_limitations": list(coverage.get("coverage_limitations") or []),
        "contributing_source_count": coverage.get("contributing_source_count"),
        "contributing_provider_count": coverage.get("contributing_provider_count"),
        "contributing_category_count": coverage.get("contributing_category_count"),
    }


def _artifact_evidence(artifact):
    source_intelligence = artifact.get("source_intelligence") if isinstance(artifact.get("source_intelligence"), dict) else {}
    evidence = source_intelligence.get("accepted_evidence")
    if not isinstance(evidence, list):
        evidence = source_intelligence.get("evidence_objects")
    if isinstance(evidence, list):
        return [
            row
            for row in evidence
            if isinstance(row, dict)
            and row.get("accepted", True) is True
            and not row.get("rejection_state")
            and not row.get("rejection_reason")
        ]
    direct_evidence = artifact.get("evidence")
    return direct_evidence if isinstance(direct_evidence, list) else []


def _display_evidence(evidence, selected_narrative=None):
    narrative = selected_narrative or {}
    reader_narrative = {
        "narrative_level": narrative.get("level") or narrative.get("narrative_level"),
        "narrative_id": narrative.get("label") or narrative.get("narrative_id"),
        "display_name": narrative.get("label") or narrative.get("display_name"),
    }
    metadata = normalize_evidence_reader_metadata(evidence, reader_narrative)
    return {
        "title": metadata["title"],
        "source_name": metadata["source"],
        "provider": metadata["provider"],
        "published_at": metadata["published_at"],
        "timestamp": metadata["published_at"],
        "url": metadata["article_url"],
        "article_link_available": metadata["article_link_available"],
        "matched_theme": metadata["theme"],
        "matched_group": metadata["group"],
        "evidence_type": metadata["evidence_type"],
        "reader_summary": build_evidence_reader_summary(evidence, reader_narrative),
    }


def _selected_narrative(artifact, narratives):
    for row in narratives:
        if row.get("selected"):
            return row
    for row in narratives:
        if row.get("dominant"):
            return row
    if artifact.get("dominant_group"):
        return {
            "key": f"group:{artifact.get('dominant_group')}",
            "label": artifact.get("dominant_group"),
            "level": "group",
            "score": None,
            "group": artifact.get("dominant_group"),
        }
    if artifact.get("dominant_theme"):
        return {
            "key": f"theme:{artifact.get('dominant_theme')}",
            "label": str(artifact.get("dominant_theme")).replace("_", " ").title(),
            "level": "theme",
            "score": None,
            "group": None,
        }
    return None


def _evidence_count_for_narrative(artifact, level, value):
    count = 0
    for evidence in _artifact_evidence(artifact):
        if _evidence_matches(evidence, level, value):
            count += 1
    return count if count else None


def _evidence_matches(evidence, level, value):
    values = []
    if level == "theme":
        values.extend(_list_values(evidence.get("themes")))
        metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
        values.extend(_list_values(metadata.get("themes")))
    if level == "group":
        values.extend(_list_values(evidence.get("groups")))
        values.extend(_list_values(evidence.get("narrative_groups")))
        metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
        values.extend(_list_values(metadata.get("groups")))
    return str(value) in values


def _group_for_theme(artifact, theme):
    for evidence in _artifact_evidence(artifact):
        if _evidence_matches(evidence, "theme", theme):
            groups = _list_values(evidence.get("groups")) or _list_values(evidence.get("narrative_groups"))
            if groups:
                return groups[0]
    return None


def _list_values(value):
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value:
        return [str(value)]
    return []


def _evidence_timestamp(evidence):
    return evidence.get("timestamp") or evidence.get("published_at")


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _accepted_evidence_count(artifact):
    source_intelligence = artifact.get("source_intelligence") if isinstance(artifact.get("source_intelligence"), dict) else None
    if isinstance(source_intelligence, dict):
        return source_intelligence.get("accepted_evidence_count")
    return artifact.get("evidence_count")


def _display_mode(metadata):
    if metadata.get("replay_mode") == "HISTORICAL_REPLAY":
        return "macro"
    return "Unavailable"


def _artifact_filename(artifact):
    replay_id = artifact.get("replay_id") if isinstance(artifact, dict) else None
    return f"{replay_id}.json" if replay_id else None


def _artifact_display_path(filename):
    return f"replays/{filename}" if filename else None


def _positive_score(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
