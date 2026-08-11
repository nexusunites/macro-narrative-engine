from dataclasses import dataclass
from typing import Optional

from mne.evidence_summary import (
    build_evidence_reader_summary,
    normalize_evidence_reader_metadata,
)
from mne.narrative_signals import NARRATIVE_GROUPS, compute_group_scores
from mne.explanation_layer import explain_market_expression, explain_narrative_snapshot
from mne.market_expression import build_market_expression_for_run
from mne.presentation_language import (
    attention_cloud_direction,
    attention_direction_from_share_delta,
)
from mne.story_registry import load_story_registry


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
                    "type_label": "Group narrative",
                    "context": "Investigation candidate from the selected run.",
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
                    "type_label": "Theme signal",
                    "context": "Theme-level evidence trail from the selected run.",
                    "score": score,
                    "key": narrative_key("theme", narrative_id),
                }
            )

    return narratives


def build_research_index(run, followed_narratives=(), story_registry=None):
    """Build the deterministic group-and-story read model for the Research finder."""
    run = run if isinstance(run, dict) else {}
    theme_scores = run.get("theme_scores") or run.get("theme_counts") or {}
    group_scores = run.get("group_scores") or {}
    if not group_scores and isinstance(theme_scores, dict):
        group_scores = compute_group_scores(theme_scores)
    group_scores = group_scores if isinstance(group_scores, dict) else {}

    registry = story_registry or load_story_registry()
    registry_stories = tuple(registry.stories)
    extraction = run.get("story_extraction")
    extracted_stories = (
        extraction.get("stories")
        if isinstance(extraction, dict) and isinstance(extraction.get("stories"), dict)
        else {}
    )
    followed = {
        (item.get("narrative_level"), item.get("narrative_key"))
        for item in followed_narratives
        if isinstance(item, dict)
    }
    positive_total = sum(
        score for score in group_scores.values()
        if isinstance(score, (int, float)) and score > 0
    )

    stories = {}
    stories_by_group = {group: [] for group in NARRATIVE_GROUPS}
    for story in registry_stories:
        extracted = extracted_stories.get(story.slug)
        direction = attention_direction_from_share_delta(
            extracted.get("share_delta") if isinstance(extracted, dict) else None
        )
        keyword_values = [
            story.display_name,
            *story.keywords.strong,
            *story.keywords.medium,
            *story.keywords.weak,
            *story.driving_sectors,
            *story.catalyst_names,
        ]
        item = {
            "slug": story.slug,
            "display_name": story.display_name,
            "group": story.group,
            "themes": list(story.themes),
            "theme": story.themes[0],
            "direction": direction["direction"],
            "direction_label": direction["label"],
            "search_text": " ".join(keyword_values).lower(),
        }
        stories[story.slug] = item
        stories_by_group[story.group].append(item)

    narratives = []
    for narrative_id, group_themes in NARRATIVE_GROUPS.items():
        score = group_scores.get(narrative_id)
        scored = isinstance(score, (int, float)) and score > 0
        group_stories = stories_by_group.get(narrative_id, []) if scored else []
        direction = _research_group_direction(run, narrative_id)
        narratives.append(
            {
                "narrative_level": "group",
                "narrative_id": narrative_id,
                "name": narrative_id,
                "key": narrative_key("group", narrative_id),
                "scored": scored,
                "score": score if scored else None,
                "share": round((score / positive_total) * 100, 1)
                if scored and positive_total
                else None,
                "direction": direction["direction"] if scored else "steady",
                "direction_label": direction["label"] if scored else None,
                "themes": [
                    theme for theme in group_themes
                    if isinstance(theme_scores, dict) and theme in theme_scores
                ],
                "stories": group_stories,
                "search_text": " ".join((narrative_id, *group_themes)).lower(),
                "followed": ("group", narrative_id) in followed,
            }
        )
    return {"narratives": narratives, "stories": stories}


def _research_group_direction(run, narrative_id):
    memory = run.get("narrative_memory")
    groups = memory.get("groups") if isinstance(memory, dict) else None
    if isinstance(groups, list):
        record = next(
            (
                item for item in groups
                if isinstance(item, dict)
                and (item.get("name") or item.get("narrative_name")) == narrative_id
            ),
            None,
        )
        if record:
            delta = record.get("share_delta")
            if not isinstance(delta, (int, float)):
                delta = record.get("score_delta")
            if isinstance(delta, (int, float)):
                return attention_direction_from_share_delta(delta)

    pulse = run.get("narrative_pulse")
    pulse_record = pulse.get(narrative_id) if isinstance(pulse, dict) else None
    dynamics = run.get("narrative_dynamics")
    dynamic_groups = dynamics.get("groups") if isinstance(dynamics, dict) else None
    dynamic_record = (
        dynamic_groups.get(narrative_id) if isinstance(dynamic_groups, dict) else None
    )
    return attention_cloud_direction(
        dynamic_record.get("acceleration") if isinstance(dynamic_record, dict) else None,
        pulse_record.get("pulse_state") if isinstance(pulse_record, dict) else None,
    )


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
    supporting_evidence = _supporting_evidence(
        source_intelligence,
        narrative_level,
        narrative_id,
    )
    source_summary = _source_summary(source_intelligence, coverage_record)
    context = {
        "narrative_level": narrative_level,
        "narrative_id": narrative_id,
        "display_name": _display_name(narrative_level, narrative_id),
        "overview": _overview(run, narrative_level, narrative_id),
        "brief": _brief(run, narrative_level, narrative_id),
        "supporting_evidence": supporting_evidence,
        "supporting_evidence_display": _supporting_evidence_display(
            supporting_evidence,
            narrative_level,
            narrative_id,
        ),
        "coverage": coverage_record,
        "coverage_explanation": _coverage_explanation(coverage_record),
        "source_summary": source_summary,
        "source_summary_display": _source_summary_display(source_summary),
        "memory": _narrative_memory_context(
            run.get("narrative_memory"),
            narrative_level,
            narrative_id,
        ),
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
    market_expression = build_market_expression_for_run(run, narrative_id)
    if market_expression:
        market_expression["explanation"] = explain_market_expression(market_expression)
    context["market_expression"] = market_expression
    context["explanation"] = explain_narrative_snapshot(context)
    return context


def _display_name(narrative_level, narrative_id):
    if narrative_level == "theme":
        return str(narrative_id).replace("_", " ").title()
    return narrative_id


def _narrative_memory_context(narrative_memory, narrative_level, narrative_id):
    if not isinstance(narrative_memory, dict):
        return None

    records_key = "themes" if narrative_level == "theme" else "groups"
    records = narrative_memory.get(records_key)
    if not isinstance(records, list):
        return None

    for record in records:
        if not (
            isinstance(record, dict)
            and record.get("narrative_level") == narrative_level
            and record.get("name") == narrative_id
        ):
            continue

        display_name = _display_name(narrative_level, narrative_id)
        summary = record.get("plain_language_summary")
        return {
            "display_name": display_name,
            "state": record.get("memory_state") or "Unavailable",
            "state_class": _memory_state_class(record.get("memory_state")),
            "summary": _display_memory_summary(summary, narrative_level, narrative_id),
            "appearances_in_window": record.get("appearances_in_window"),
            "runs_used": _memory_runs_used(narrative_memory),
            "dominance_count": record.get("dominance_count"),
            "streak_length": record.get("streak_length"),
            "momentum_label": record.get("momentum_label") or "Unavailable",
            "persistence_label": record.get("persistence_label") or "Unavailable",
            "score_delta": _format_delta(record.get("score_delta")),
            "share_delta": _format_delta(record.get("share_delta"), percent=True),
            "rank_delta": _format_delta(record.get("rank_delta"), invert=True),
        }

    return None


def _memory_runs_used(narrative_memory):
    window = narrative_memory.get("memory_window")
    if not isinstance(window, dict):
        return None
    return window.get("runs_used")


def _display_memory_summary(summary, narrative_level, narrative_id):
    if not summary:
        return None
    summary = str(summary)
    if narrative_level != "theme":
        return summary

    display_name = _display_name(narrative_level, narrative_id)
    return summary.replace(str(narrative_id), display_name, 1)


def _memory_state_class(state):
    if not state:
        return "memory-state-absent"
    return f"memory-state-{str(state).lower().replace('_', '-')}"


def _format_delta(value, percent=False, invert=False):
    if not isinstance(value, (int, float)):
        return "Unavailable"
    display_value = -value if invert else value
    if percent:
        display_value = display_value * 100
        suffix = " pts"
    else:
        suffix = ""
    sign = "+" if display_value > 0 else ""
    if percent:
        return f"{sign}{display_value:.1f}{suffix}"
    if isinstance(display_value, float) and not display_value.is_integer():
        return f"{sign}{display_value:.2f}"
    return f"{sign}{int(display_value)}"


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


def _supporting_evidence_display(evidence_rows, narrative_level, narrative_id):
    rows = []
    selected_narrative = {
        "narrative_level": narrative_level,
        "narrative_id": narrative_id,
        "display_name": _display_name(narrative_level, narrative_id),
    }
    for evidence in evidence_rows:
        if not isinstance(evidence, dict):
            continue
        metadata = normalize_evidence_reader_metadata(evidence, selected_narrative)
        summary = build_evidence_reader_summary(evidence, selected_narrative)
        rows.append(
            {
                "title": metadata["title"],
                "source_name": metadata["source"],
                "provider": metadata["provider"],
                "timestamp": metadata["published_at"],
                "url": metadata["article_url"],
                "article_link_available": metadata["article_link_available"],
                "matched_narrative": selected_narrative["display_name"],
                "matched_theme": metadata["theme"],
                "matched_group": metadata["group"],
                "evidence_type": metadata["evidence_type"],
                "reader_summary": summary,
            }
        )
    return rows


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


def _coverage_explanation(coverage_record):
    if not isinstance(coverage_record, dict):
        return None
    state = coverage_record.get("coverage_state") or "UNKNOWN"
    state_text = str(state).replace("_", " ").title()
    return (
        f"{state_text} evidence breadth describes how broad the supporting evidence is "
        "for this narrative in the selected run. It is not a judgment of narrative quality."
    )


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
                "provider": contribution.get("provider"),
                "evidence_count": contribution.get("evidence_count"),
                "health": health_by_source.get(source_id),
                "freshness": freshness_by_source.get(source_id),
            }
        )
    return rows


def _source_summary_display(source_summary):
    rows = []
    for source in source_summary:
        if not isinstance(source, dict):
            continue
        freshness = source.get("freshness") if isinstance(source.get("freshness"), dict) else {}
        health = source.get("health") if isinstance(source.get("health"), dict) else {}
        rows.append(
            {
                "source_name": source.get("source_name") or "Unknown source",
                "provider": source.get("provider"),
                "evidence_count": source.get("evidence_count"),
                "health_state": health.get("state") or "Unavailable",
                "freshness_state": (
                    freshness.get("freshness_state")
                    or freshness.get("status")
                    or "Unavailable"
                ),
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
