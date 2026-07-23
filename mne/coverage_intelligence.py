from collections import Counter, defaultdict

from mne.headline_deduplication import normalize_headline_for_deduplication
from mne.narrative_signals import NARRATIVE_GROUPS


COVERAGE_STATES = ("MINIMAL", "LIMITED", "MODERATE", "BROAD", "EXTENSIVE")
THRESHOLD_EVALUATION_ORDER = ("EXTENSIVE", "BROAD", "MODERATE", "LIMITED")
ENGINE_VERSION = "1.0.0"

HISTORICAL_EVIDENCE_ORIGIN = "HISTORICAL_BACKFILL"
LIVE_EVIDENCE_ORIGIN_LABEL = "live_persisted"
HISTORICAL_EVIDENCE_ORIGIN_LABEL = "historical_backfill"

# Replay-level breadth states for source-agnostic (live + historical backfill)
# Coverage Intelligence. Deliberately excludes EXTENSIVE: the backfill source
# set is small and finite today, and claiming "extensive" coverage from a
# 4-connector ceiling would overclaim.
HISTORICAL_BREADTH_STATES = ("UNKNOWN", "MINIMAL", "LIMITED", "MODERATE", "BROAD")
HISTORICAL_BREADTH_EVALUATION_ORDER = ("BROAD", "MODERATE", "LIMITED")
HISTORICAL_BREADTH_THRESHOLDS = {
    "BROAD": {"min_source_count": 4, "min_category_count": 3},
    "MODERATE": {"min_source_count": 3, "min_category_count": 0},
    "LIMITED": {"min_source_count": 2, "min_category_count": 0},
}

HISTORICAL_COVERAGE_LIMITATIONS = (
    "Historical coverage reflects supported backfill sources only.",
    "This is not complete historical market-news coverage.",
    "Coverage breadth is measured within the evidence available to this replay.",
)
MIXED_ORIGIN_COVERAGE_LIMITATION = (
    "This replay mixes live-persisted and historical backfill evidence; "
    "counts are shown by origin."
)


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


def partition_evidence_by_origin(accepted_evidence):
    """Splits unified accepted_evidence rows (as persisted on a replay's
    source_intelligence.accepted_evidence) into (live_rows, historical_rows).

    Live rows never carry an evidence_origin key; historical/backfilled rows
    always set it to HISTORICAL_EVIDENCE_ORIGIN. Absence of the key is treated
    as the live signal rather than requiring an explicit "LIVE" sentinel."""
    live_rows = []
    historical_rows = []
    for row in accepted_evidence or []:
        if not isinstance(row, dict):
            continue
        if row.get("evidence_origin") == HISTORICAL_EVIDENCE_ORIGIN:
            historical_rows.append(row)
        else:
            live_rows.append(row)
    return live_rows, historical_rows


def build_historical_source_record_from_evidence(evidence_row):
    """Derives a source record for a historical/backfilled accepted_evidence
    row from its own persisted fields, without consulting the live Source
    Registry."""
    return {
        "source_id": evidence_row.get("source_id"),
        "provider": evidence_row.get("provider"),
        "category": evidence_row.get("category"),
        "connector_source_id": evidence_row.get("connector_source_id"),
        "backfill_id": evidence_row.get("backfill_id"),
        "origin": HISTORICAL_EVIDENCE_ORIGIN_LABEL,
    }


def build_coverage_source_records(accepted_evidence, registry):
    """Builds one uniform source record per accepted_evidence row, resolving
    live rows via the live Source Registry and historical rows via their own
    persisted metadata. Never calls registry.source_by_id for a historical
    row, and never registers a historical source_id anywhere."""
    live_rows, historical_rows = partition_evidence_by_origin(accepted_evidence)
    records = []

    for row in live_rows:
        source_id = row.get("source_id")
        if not source_id:
            continue
        source = registry.source_by_id(source_id)
        records.append(
            {
                "source_id": source_id,
                "provider": row.get("provider") or source.get("provider"),
                "category": source.get("category"),
                "origin": LIVE_EVIDENCE_ORIGIN_LABEL,
            }
        )

    for row in historical_rows:
        if not row.get("source_id"):
            continue
        records.append(build_historical_source_record_from_evidence(row))

    return records


def assign_breadth_state(contributing_source_count, contributing_category_count):
    if contributing_source_count <= 0:
        return "UNKNOWN"
    for state in HISTORICAL_BREADTH_EVALUATION_ORDER:
        config = HISTORICAL_BREADTH_THRESHOLDS[state]
        if (
            contributing_source_count >= config["min_source_count"]
            and contributing_category_count >= config["min_category_count"]
        ):
            return state
    return "MINIMAL"


def build_historical_coverage_limitations(evidence_origins_used):
    limitations = list(HISTORICAL_COVERAGE_LIMITATIONS)
    origins = set(evidence_origins_used or [])
    if LIVE_EVIDENCE_ORIGIN_LABEL in origins and HISTORICAL_EVIDENCE_ORIGIN_LABEL in origins:
        limitations.append(MIXED_ORIGIN_COVERAGE_LIMITATION)
    return limitations


def build_replay_coverage_intelligence(accepted_evidence, registry):
    """Builds a replay-level, source-agnostic breadth summary spanning live
    and historical backfilled evidence together. This is separate from the
    per-narrative, live-registry-bound coverage built by
    build_coverage_intelligence, and is safe to call on evidence sets that
    include historical source ids not present in the live Source Registry."""
    source_records = build_coverage_source_records(accepted_evidence, registry)
    accepted_evidence_count = len(source_records)

    source_counts = Counter(record["source_id"] for record in source_records if record.get("source_id"))
    provider_counts = Counter(record["provider"] for record in source_records if record.get("provider"))
    category_counts = Counter(record["category"] for record in source_records if record.get("category"))
    origins_used = sorted({record["origin"] for record in source_records})

    return {
        "accepted_evidence_count": accepted_evidence_count,
        "contributing_source_count": len(source_counts),
        "contributing_provider_count": len(provider_counts),
        "contributing_category_count": len(category_counts),
        "evidence_count_by_source": dict(sorted(source_counts.items())),
        "evidence_count_by_provider": dict(sorted(provider_counts.items())),
        "evidence_count_by_category": dict(sorted(category_counts.items())),
        "source_concentration": _replay_concentration_ratio(source_counts, accepted_evidence_count),
        "provider_concentration": _replay_concentration_ratio(provider_counts, accepted_evidence_count),
        "category_concentration": _replay_concentration_ratio(category_counts, accepted_evidence_count),
        "breadth_state": assign_breadth_state(len(source_counts), len(category_counts)),
        "evidence_origins_used": origins_used,
        "coverage_limitations": build_historical_coverage_limitations(origins_used),
    }


def _replay_concentration_ratio(counter, total):
    if not counter or not total:
        return 0.0
    return round(max(counter.values()) / total, 2)


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
