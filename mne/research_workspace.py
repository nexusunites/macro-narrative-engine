from dataclasses import dataclass
from typing import Optional

from mne.narrative_signals import NARRATIVE_GROUPS, compute_group_scores


@dataclass(frozen=True)
class RunSelection:
    run: Optional[dict]
    path: Optional[object]
    latest_path: Optional[object] = None

    @property
    def notice(self):
        if self.run is None or self.path is None or self.latest_path is None:
            return None
        if self.path == self.latest_path:
            return None
        return (
            "Latest run had no narrative signal; showing latest meaningful run: "
            f"{self.path.name}."
        )


def narrative_key(narrative_level, narrative_id):
    return f"{narrative_level}:{narrative_id}"


def split_narrative_key(value):
    if not value or ":" not in str(value):
        return None, None
    level, narrative_id = str(value).split(":", 1)
    if level not in {"theme", "group"} or not narrative_id:
        return None, None
    return level, narrative_id


def _has_narrative_data(run):
    theme_scores = run.get("theme_scores") or run.get("theme_counts") or {}
    group_scores = run.get("group_scores") or {}
    if not isinstance(theme_scores, dict):
        theme_scores = {}
    if not isinstance(group_scores, dict):
        group_scores = {}
    return any(
        isinstance(v, (int, float)) and v > 0 for v in theme_scores.values()
    ) or any(
        isinstance(v, (int, float)) and v > 0 for v in group_scores.values()
    )


def _score_sort_value(item):
    value = item[1]
    if isinstance(value, (int, float)):
        return -value
    return 0


def select_latest_meaningful_run(files, load_result):
    latest_path = None
    for path in files:
        try:
            run = load_result(path)
        except Exception:
            continue
        if not isinstance(run, dict):
            continue
        if latest_path is None:
            latest_path = path
        if _has_narrative_data(run):
            return RunSelection(run=run, path=path, latest_path=latest_path)
    return RunSelection(run=None, path=None, latest_path=latest_path)


def latest_completed_run(files, load_result):
    selection = select_latest_meaningful_run(files, load_result)
    return selection.run, selection.path


def build_narrative_selector(run):
    run = run if isinstance(run, dict) else {}
    narratives = []
    theme_scores = run.get("theme_scores") or run.get("theme_counts") or {}
    group_scores = run.get("group_scores") or {}

    if not group_scores and isinstance(theme_scores, dict):
        group_scores = compute_group_scores(theme_scores)

    if isinstance(group_scores, dict):
        for narrative_id, score in sorted(
            group_scores.items(), key=_score_sort_value
        ):
            if not (isinstance(score, (int, float)) and score > 0):
                continue
            narratives.append(
                {
                    "narrative_level": "group",
                    "narrative_id": narrative_id,
                    "display_name": narrative_id,
                    "score": score,
                    "key": narrative_key("group", narrative_id),
                }
            )

    if isinstance(theme_scores, dict):
        for narrative_id, score in sorted(
            theme_scores.items(), key=_score_sort_value
        ):
            if not (isinstance(score, (int, float)) and score > 0):
                continue
            narratives.append(
                {
                    "narrative_level": "theme",
                    "narrative_id": narrative_id,
                    "display_name": narrative_id.replace("_", " ").title(),
                    "score": score,
                    "key": narrative_key("theme", narrative_id),
                }
            )

    return narratives


def build_narrative_investigation(
    run,
    narrative_level,
    narrative_id,
    admin=False,
    event_definitions=None,
):
    run = run if isinstance(run, dict) else {}
    source_intelligence = (
        run.get("source_intelligence") if isinstance(run.get("source_intelligence"), dict) else {}
    )
    coverage_record = _coverage_record(source_intelligence, narrative_level, narrative_id)
    return {
        "narrative_level": narrative_level,
        "narrative_id": narrative_id,
        "display_name": _display_name(narrative_level, narrative_id),
        "overview": _overview(run, narrative_level, narrative_id),
        "brief": _brief(run, narrative_level, narrative_id),
        "supporting_evidence": _supporting_evidence(
            source_intelligence,
            narrative_level,
            narrative_id,
        ),
        "coverage": coverage_record,
        "source_summary": _source_summary(source_intelligence, coverage_record),
        "events": _events(
            run.get("event_lifecycle"),
            narrative_level,
            narrative_id,
            event_definitions=event_definitions,
        ),
        "platform_observability": (
            _platform_observability(run.get("platform_observability")) if admin else None
        ),
    }


def _display_name(narrative_level, narrative_id):
    if narrative_level == "theme":
        return str(narrative_id).replace("_", " ").title()
    return narrative_id


def _overview(run, narrative_level, narrative_id):
    scores = {}
    if narrative_level == "group":
        scores = run.get("group_scores") if isinstance(run.get("group_scores"), dict) else {}
    elif narrative_level == "theme":
        scores = run.get("theme_scores") or run.get("theme_counts")
        scores = scores if isinstance(scores, dict) else {}

    narrative_pulse = run.get("narrative_pulse")
    pulse = None
    if narrative_level == "group" and isinstance(narrative_pulse, dict):
        pulse = narrative_pulse.get(narrative_id)

    return {
        "score": scores.get(narrative_id),
        "leadership": _leadership(run, narrative_level, narrative_id),
        "pulse": pulse if isinstance(pulse, dict) else None,
        "regime_alignment": run.get("regime_alignment")
        if isinstance(run.get("regime_alignment"), dict)
        else None,
    }


def _leadership(run, narrative_level, narrative_id):
    if narrative_level == "group" and run.get("dominant_group") == narrative_id:
        return "Current narrative leader"
    if narrative_level == "theme" and run.get("dominant_theme") == narrative_id:
        return "Current dominant theme"

    leadership = run.get("narrative_leadership")
    leaders = leadership.get("leaders") if isinstance(leadership, dict) else None
    if narrative_level == "group" and isinstance(leaders, list):
        for row in leaders:
            if isinstance(row, dict) and row.get("group") == narrative_id:
                return f"Rank {row.get('rank')}" if row.get("rank") is not None else None
    return None


def _brief(run, narrative_level, narrative_id):
    brief = run.get("narrative_brief")
    if not isinstance(brief, dict):
        return None

    sections = []
    for section in brief.get("sections", []):
        if not isinstance(section, dict):
            continue
        if _matches_narrative(section, narrative_level, narrative_id):
            sections.append(section)

    if not sections and _is_dominant_run_narrative(run, narrative_level, narrative_id):
        sections = [section for section in brief.get("sections", []) if isinstance(section, dict)]

    if not sections:
        return None

    return {
        "headline": brief.get("headline"),
        "confidence": brief.get("confidence"),
        "summary": brief.get("summary"),
        "sections": sections,
        "evidence_registry": brief.get("evidence_registry") or [],
    }


def _is_dominant_run_narrative(run, narrative_level, narrative_id):
    if narrative_level == "group":
        return run.get("dominant_group") == narrative_id
    if narrative_level == "theme":
        return run.get("dominant_theme") == narrative_id
    return False


def _supporting_evidence(source_intelligence, narrative_level, narrative_id):
    evidence_objects = source_intelligence.get("accepted_evidence")
    if not isinstance(evidence_objects, list):
        evidence_objects = source_intelligence.get("evidence_objects")
    if not isinstance(evidence_objects, list):
        return []

    return [
        evidence
        for evidence in evidence_objects
        if isinstance(evidence, dict)
        and evidence.get("accepted", True) is True
        and not evidence.get("rejection_state")
        and not evidence.get("rejection_reason")
        and _matches_narrative(evidence, narrative_level, narrative_id)
    ]


def _coverage_record(source_intelligence, narrative_level, narrative_id):
    coverage = source_intelligence.get("coverage_intelligence")
    per_narrative = coverage.get("per_narrative") if isinstance(coverage, dict) else None
    if not isinstance(per_narrative, list):
        return None

    for record in per_narrative:
        if (
            isinstance(record, dict)
            and record.get("narrative_level") == narrative_level
            and record.get("narrative_id") == narrative_id
        ):
            return record
    return None


def _source_summary(source_intelligence, coverage_record):
    if not isinstance(coverage_record, dict):
        return []

    source_ids = [
        row.get("source_id")
        for row in coverage_record.get("source_contribution_breakdown", [])
        if isinstance(row, dict) and row.get("source_id")
    ]
    health_by_source = _index_by_source_id(source_intelligence.get("source_health"))
    freshness_by_source = _index_by_source_id(source_intelligence.get("source_freshness"))

    rows = []
    for contribution in coverage_record.get("source_contribution_breakdown", []):
        if not isinstance(contribution, dict):
            continue
        source_id = contribution.get("source_id")
        if source_id not in source_ids:
            continue
        rows.append(
            {
                "source_id": source_id,
                "source_name": contribution.get("source_name"),
                "evidence_count": contribution.get("evidence_count"),
                "health": health_by_source.get(source_id),
                "freshness": freshness_by_source.get(source_id),
            }
        )
    return rows


def _events(event_lifecycle, narrative_level, narrative_id, event_definitions=None):
    if not isinstance(event_lifecycle, dict):
        return []

    definition_index = _index_event_definitions(event_definitions)
    return [
        event
        for event in event_lifecycle.get("events", [])
        if isinstance(event, dict)
        and _event_matches_narrative(event, definition_index, narrative_level, narrative_id)
    ]


def _event_matches_narrative(event, definition_index, narrative_level, narrative_id):
    if _matches_direct_narrative(event, narrative_level, narrative_id):
        return True

    definition = definition_index.get(event.get("event_id"))
    return bool(
        isinstance(definition, dict)
        and _matches_direct_narrative(definition, narrative_level, narrative_id)
    )


def _index_event_definitions(event_definitions):
    if not isinstance(event_definitions, list):
        return {}
    return {
        str(event.get("event_id")): event
        for event in event_definitions
        if isinstance(event, dict) and event.get("event_id")
    }


def _platform_observability(platform_observability):
    if not isinstance(platform_observability, dict):
        return None
    run_metadata = platform_observability.get("run_metadata")
    if not isinstance(run_metadata, dict):
        return None
    return {
        "run_id": run_metadata.get("run_id"),
        "run_duration_ms": run_metadata.get("run_duration_ms"),
    }


def _index_by_source_id(rows):
    if not isinstance(rows, list):
        return {}
    return {
        row.get("source_id"): row
        for row in rows
        if isinstance(row, dict) and row.get("source_id")
    }


def _matches_narrative(item, narrative_level, narrative_id):
    if _matches_direct_narrative(item, narrative_level, narrative_id):
        return True

    if narrative_level == "group":
        metadata = item.get("metadata")
        themes = item.get("themes")
        if isinstance(themes, list) and _themes_include_group(themes, narrative_id):
            return True
        metadata_themes = metadata.get("themes") if isinstance(metadata, dict) else None
        if isinstance(metadata_themes, list) and _themes_include_group(metadata_themes, narrative_id):
            return True

    return False


def _matches_direct_narrative(item, narrative_level, narrative_id):
    if item.get("narrative_level") == narrative_level and item.get("narrative_id") == narrative_id:
        return True

    narrative_keys = item.get("narrative_keys")
    if isinstance(narrative_keys, list) and narrative_key(narrative_level, narrative_id) in narrative_keys:
        return True

    if narrative_level == "theme":
        themes = item.get("themes")
        if isinstance(themes, list) and narrative_id in themes:
            return True
        metadata = item.get("metadata")
        metadata_themes = metadata.get("themes") if isinstance(metadata, dict) else None
        if isinstance(metadata_themes, list) and narrative_id in metadata_themes:
            return True

    if narrative_level == "group":
        groups = item.get("groups") or item.get("narrative_groups")
        if isinstance(groups, list) and narrative_id in groups:
            return True
        metadata = item.get("metadata")
        metadata_groups = metadata.get("groups") if isinstance(metadata, dict) else None
        if isinstance(metadata_groups, list) and narrative_id in metadata_groups:
            return True

    return False


def _themes_include_group(themes, group):
    return any(theme in NARRATIVE_GROUPS.get(group, []) for theme in themes)
