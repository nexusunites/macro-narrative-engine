from collections import Counter, defaultdict

from mne.headline_deduplication import normalize_headline_for_deduplication
from mne.narrative_signals import NARRATIVE_GROUPS


COVERAGE_STATES = ("MINIMAL", "LIMITED", "MODERATE", "BROAD", "EXTENSIVE")
THRESHOLD_EVALUATION_ORDER = ("EXTENSIVE", "BROAD", "MODERATE", "LIMITED")
ENGINE_VERSION = "1.0.0"


def accepted_deduped_evidence(evidence_objects):
    selected = []
    seen = set()

    for evidence in evidence_objects:
        if not _evidence_value(evidence, "accepted"):
            continue
        title = _evidence_value(evidence, "title")
        normalized = normalize_headline_for_deduplication(title or "")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(evidence)

    return selected


def evidence_titles(evidence_objects):
    return [_evidence_value(evidence, "title") for evidence in evidence_objects]


def build_coverage_intelligence(
    scored_evidence,
    theme_attribution,
    registry,
    narrative_groups=None,
):
    narrative_groups = narrative_groups or NARRATIVE_GROUPS
    attributed = _build_narrative_attribution(scored_evidence, theme_attribution, narrative_groups)
    per_narrative = [
        _build_narrative_record(level, narrative_id, evidence, registry)
        for (level, narrative_id), evidence in sorted(attributed.items())
        if evidence
    ]

    return {
        "per_narrative": per_narrative,
        "overall": _build_overall_summary(per_narrative),
    }


def assign_coverage_state(
    evidence_count,
    unique_source_count,
    unique_provider_count,
    thresholds,
):
    for state in THRESHOLD_EVALUATION_ORDER:
        config = thresholds[state]
        if _threshold_matches(
            config,
            evidence_count,
            unique_source_count,
            unique_provider_count,
        ):
            return state
    return "MINIMAL"


def _build_narrative_attribution(scored_evidence, theme_attribution, narrative_groups):
    attributed = defaultdict(list)
    theme_to_groups = defaultdict(list)
    for group, themes in narrative_groups.items():
        for theme in themes:
            theme_to_groups[theme].append(group)

    for evidence, attribution in zip(scored_evidence, theme_attribution):
        if not _evidence_value(evidence, "accepted"):
            continue
        themes = attribution.get("themes", []) if isinstance(attribution, dict) else []
        for theme in themes:
            attributed[("theme", theme)].append(evidence)
        for group in sorted({group for theme in themes for group in theme_to_groups.get(theme, [])}):
            attributed[("group", group)].append(evidence)

    return attributed


def _build_narrative_record(narrative_level, narrative_id, evidence_items, registry):
    source_counts = Counter(_evidence_value(evidence, "source_id") for evidence in evidence_items)
    source_rows = []
    providers = set()

    for source_id in sorted(source_counts):
        source = registry.source_by_id(source_id)
        providers.add(source["provider"])
        source_rows.append(
            {
                "source_id": source_id,
                "source_name": source["display_name"],
            }
        )

    breakdown = [
        {
            "source_id": source_id,
            "source_name": registry.source_by_id(source_id)["display_name"],
            "evidence_count": count,
        }
        for source_id, count in sorted(
            source_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    evidence_count = len(evidence_items)
    max_source_count = breakdown[0]["evidence_count"] if breakdown else 0
    concentration_ratio = round(max_source_count / evidence_count, 2) if evidence_count else 0.0

    return {
        "narrative_level": narrative_level,
        "narrative_id": narrative_id,
        "evidence_count": evidence_count,
        "unique_source_count": len(source_counts),
        "unique_provider_count": len(providers),
        "provider_list": sorted(providers),
        "source_list": source_rows,
        "source_contribution_breakdown": breakdown,
        "concentration_ratio": concentration_ratio,
        "coverage_state": assign_coverage_state(
            evidence_count,
            len(source_counts),
            len(providers),
            registry.coverage_thresholds,
        ),
    }


def _build_overall_summary(per_narrative):
    providers = set()
    sources = set()
    coverage_counts = {state.lower() + "_count": 0 for state in COVERAGE_STATES}
    highest_id = None
    highest_ratio = None

    for record in per_narrative:
        providers.update(record["provider_list"])
        sources.update(source["source_id"] for source in record["source_list"])
        coverage_counts[record["coverage_state"].lower() + "_count"] += 1
        ratio = record["concentration_ratio"]
        if highest_ratio is None or ratio > highest_ratio:
            highest_ratio = ratio
            highest_id = record["narrative_id"]

    return {
        "provider_diversity": {
            "unique_provider_count": len(providers),
            "provider_list": sorted(providers),
        },
        "source_diversity": {
            "unique_source_count": len(sources),
        },
        "concentration_summary": {
            "highest_concentration_narrative_id": highest_id,
            "highest_concentration_ratio": highest_ratio,
        },
        "coverage_summary": coverage_counts,
    }


def _threshold_matches(
    config,
    evidence_count,
    unique_source_count,
    unique_provider_count,
):
    if evidence_count < config["min_evidence_count"]:
        return False
    max_evidence_count = config.get("max_evidence_count")
    if max_evidence_count is not None and evidence_count > max_evidence_count:
        return False
    return (
        unique_source_count >= config["min_unique_source_count"]
        and unique_provider_count >= config["min_unique_provider_count"]
    )


def _evidence_value(evidence, field):
    if isinstance(evidence, dict):
        return evidence.get(field)
    return getattr(evidence, field)
