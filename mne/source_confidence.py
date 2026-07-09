from collections import Counter

from mne.feed_health import HEALTHY, PARTIAL, REDIRECTED


HIGH = "HIGH"
MODERATE = "MODERATE"
LOW = "LOW"
UNKNOWN = "UNKNOWN"

SUCCESSFUL_FETCH_STATES = {HEALTHY, PARTIAL, REDIRECTED}

ACTION_BY_STATE_AND_FACTOR = {
    (HIGH, "healthy"): "No action needed.",
    (MODERATE, "fetch_success"): "Review weakened sources in Feed Health diagnostics.",
    (MODERATE, "freshness"): "Review stale and unknown-timestamp evidence in freshness diagnostics.",
    (MODERATE, "contribution"): "Review active sources that produced no accepted evidence.",
    (LOW, "accepted_count"): "Review evidence collection volume before relying on this run.",
    (LOW, "fetch_success"): "Review failing sources in Feed Health diagnostics.",
    (LOW, "contribution"): "Review active sources that did not contribute accepted evidence.",
    (UNKNOWN, "missing_diagnostics"): "Investigate why source diagnostics are missing for this run.",
    (UNKNOWN, "active_sources"): "Investigate why no active sources were available for this run.",
}


def build_source_confidence(registry, source_intelligence):
    thresholds = dict(registry.source_confidence_thresholds)
    diagnostics = source_intelligence or {}
    missing = missing_required_diagnostics(diagnostics)
    if missing:
        return unknown_confidence(thresholds, missing)

    metrics = derive_metrics(registry, diagnostics)
    state, dominant_factor = evaluate_confidence_state(metrics, thresholds)
    return {
        "confidence_state": state,
        "confidence_level": None,
        "reason": build_reason(state, dominant_factor, metrics),
        "contributing_factors": build_contributing_factors(metrics, thresholds),
        "recommended_action": recommended_action(state, dominant_factor),
        "thresholds_used": thresholds,
    }


def missing_required_diagnostics(source_intelligence):
    missing = []
    if not source_intelligence.get("source_health"):
        missing.append("source_health")
    if not source_intelligence.get("source_freshness"):
        missing.append("source_freshness")
    if not source_intelligence.get("evidence_funnel"):
        missing.append("evidence_funnel")
    return missing


def unknown_confidence(thresholds, missing):
    missing_text = ", ".join(missing)
    return {
        "confidence_state": UNKNOWN,
        "confidence_level": None,
        "reason": f"Source confidence could not be evaluated because {missing_text} diagnostics were missing.",
        "contributing_factors": [
            f"Missing required diagnostic: {name}" for name in missing
        ],
        "recommended_action": recommended_action(UNKNOWN, "missing_diagnostics"),
        "thresholds_used": thresholds,
    }


def derive_metrics(registry, source_intelligence):
    active_sources = list(registry.active_sources)
    active_source_ids = {source["source_id"] for source in active_sources}
    source_names = {
        source["source_id"]: source.get("display_name") or source["source_id"]
        for source in active_sources
    }
    health_by_source_id = _index_by_source_id(source_intelligence.get("source_health"))
    freshness_by_source_id = _index_by_source_id(source_intelligence.get("source_freshness"))
    accepted_evidence = source_intelligence.get("accepted_evidence") or []
    evidence_by_source = Counter(
        evidence.get("source_id")
        for evidence in accepted_evidence
        if isinstance(evidence, dict)
        and evidence.get("source_id") in active_source_ids
    )
    contributing_source_ids = {
        source_id for source_id, count in evidence_by_source.items() if count > 0
    }
    successful_fetch_ids = {
        source_id
        for source_id, health in health_by_source_id.items()
        if source_id in active_source_ids
        and health.get("state") in SUCCESSFUL_FETCH_STATES
    } | contributing_source_ids
    funnel = source_intelligence.get("evidence_funnel") or {}
    accepted_fresh = _as_int(funnel.get("accepted_fresh"))
    rejected_stale = _as_int(funnel.get("rejected_stale"))
    rejected_unknown = _as_int(funnel.get("rejected_unknown_timestamp"))
    freshness_denominator = accepted_fresh + rejected_stale + rejected_unknown

    active_count = len(active_sources)
    fetch_success_count = len(successful_fetch_ids)
    contributing_count = len(contributing_source_ids)
    return {
        "active_count": active_count,
        "fetch_success_count": fetch_success_count,
        "fetch_success_ratio": _ratio(fetch_success_count, active_count),
        "contributing_count": contributing_count,
        "contribution_ratio": _ratio(contributing_count, active_count),
        "freshness_ratio": _ratio(accepted_fresh, freshness_denominator),
        "freshness_denominator": freshness_denominator,
        "accepted_count": _as_int(source_intelligence.get("accepted_count")),
        "funnel": {
            "accepted_fresh": accepted_fresh,
            "rejected_stale": rejected_stale,
            "rejected_duplicate": _as_int(funnel.get("rejected_duplicate")),
            "rejected_unknown_timestamp": rejected_unknown,
            "analyzer_input_count": _as_int(funnel.get("analyzer_input_count")),
            "fetched": _as_int(funnel.get("fetched")),
        },
        "blocked_sources": _sources_with_state(health_by_source_id, source_names, "BLOCKED"),
        "weak_sources": _weak_sources(health_by_source_id, source_names, active_source_ids),
        "stale_source_count": sum(
            1 for row in freshness_by_source_id.values() if row.get("status") == "STALE"
        ),
        "unknown_freshness_source_count": sum(
            1 for row in freshness_by_source_id.values() if row.get("status") == "UNKNOWN"
        ),
        "non_contributing_sources": [
            source_names[source_id]
            for source_id in sorted(active_source_ids - contributing_source_ids)
        ],
    }


def evaluate_confidence_state(metrics, thresholds):
    if metrics["active_count"] <= 0:
        return UNKNOWN, "active_sources"
    if metrics["accepted_count"] < thresholds["accepted_evidence_floor"]:
        return LOW, "accepted_count"
    if metrics["fetch_success_ratio"] < thresholds["low_fetch_ratio"]:
        return LOW, "fetch_success"
    if metrics["contribution_ratio"] < thresholds["low_contribution_ratio"]:
        return LOW, "contribution"
    if metrics["fetch_success_ratio"] < thresholds["high_fetch_ratio"]:
        return MODERATE, "fetch_success"
    if metrics["freshness_ratio"] < thresholds["high_freshness_ratio"]:
        return MODERATE, "freshness"
    if metrics["contribution_ratio"] < thresholds["high_contribution_ratio"]:
        return MODERATE, "contribution"
    return HIGH, "healthy"


def build_reason(state, dominant_factor, metrics):
    if state == UNKNOWN and dominant_factor == "active_sources":
        return "Source confidence could not be evaluated because no active sources were registered."
    if dominant_factor == "accepted_count":
        return (
            f"Only {metrics['accepted_count']} accepted evidence objects were collected "
            f"from {metrics['active_count']} active sources."
        )
    if dominant_factor == "fetch_success":
        return (
            f"{metrics['fetch_success_count']} of {metrics['active_count']} active sources "
            f"fetched successfully or contributed accepted evidence."
        )
    if dominant_factor == "freshness":
        return (
            f"{_percent(metrics['freshness_ratio'])} of freshness-evaluated non-duplicate "
            "evidence was fresh."
        )
    if dominant_factor == "contribution":
        return (
            f"Only {metrics['contributing_count']} of {metrics['active_count']} active sources "
            "contributed accepted evidence."
        )
    return (
        f"{metrics['fetch_success_count']} of {metrics['active_count']} active sources fetched "
        f"successfully or contributed evidence, and {_percent(metrics['freshness_ratio'])} "
        "of freshness-evaluated non-duplicate evidence was fresh."
    )


def build_contributing_factors(metrics, thresholds):
    factors = [
        (
            f"Accepted evidence count: {metrics['accepted_count']} "
            f"(floor {thresholds['accepted_evidence_floor']})"
        ),
        (
            f"Fetch success ratio: {metrics['fetch_success_count']}/{metrics['active_count']} "
            f"= {_format_ratio(metrics['fetch_success_ratio'])}"
        ),
        (
            f"Contribution ratio: {metrics['contributing_count']}/{metrics['active_count']} "
            f"= {_format_ratio(metrics['contribution_ratio'])}"
        ),
        (
            "Freshness ratio: "
            f"{metrics['funnel']['accepted_fresh']}/{metrics['freshness_denominator']} "
            f"= {_format_ratio(metrics['freshness_ratio'])}; duplicates excluded "
            f"({metrics['funnel']['rejected_duplicate']} duplicate rejection(s))"
        ),
        (
            "Funnel counts: "
            f"fetched {metrics['funnel']['fetched']}, "
            f"accepted_fresh {metrics['funnel']['accepted_fresh']}, "
            f"rejected_stale {metrics['funnel']['rejected_stale']}, "
            f"rejected_unknown_timestamp {metrics['funnel']['rejected_unknown_timestamp']}, "
            f"analyzer_input_count {metrics['funnel']['analyzer_input_count']}"
        ),
    ]
    factors.extend(f"{source}: BLOCKED" for source in metrics["blocked_sources"])
    factors.extend(
        f"{source}: {state}" for source, state in metrics["weak_sources"]
        if state != "BLOCKED"
    )
    if metrics["stale_source_count"]:
        factors.append(f"{metrics['stale_source_count']} source(s) produced only stale content.")
    if metrics["unknown_freshness_source_count"]:
        factors.append(
            f"{metrics['unknown_freshness_source_count']} source(s) had unknown freshness."
        )
    if metrics["non_contributing_sources"]:
        sample = ", ".join(metrics["non_contributing_sources"][:5])
        suffix = "..." if len(metrics["non_contributing_sources"]) > 5 else ""
        factors.append(
            f"Non-contributing active sources: {sample}{suffix}"
        )
    return factors


def recommended_action(state, dominant_factor):
    return ACTION_BY_STATE_AND_FACTOR.get(
        (state, dominant_factor),
        ACTION_BY_STATE_AND_FACTOR[(UNKNOWN, "missing_diagnostics")],
    )


def _index_by_source_id(rows):
    return {
        row.get("source_id"): row
        for row in rows or []
        if isinstance(row, dict) and row.get("source_id")
    }


def _sources_with_state(health_by_source_id, source_names, state):
    return [
        source_names.get(source_id, source_id)
        for source_id, row in sorted(health_by_source_id.items())
        if row.get("state") == state
    ]


def _weak_sources(health_by_source_id, source_names, active_source_ids):
    rows = []
    for source_id, health in sorted(health_by_source_id.items()):
        if source_id not in active_source_ids:
            continue
        state = health.get("state")
        if state not in SUCCESSFUL_FETCH_STATES:
            rows.append((source_names.get(source_id, source_id), state or "UNKNOWN"))
    return rows


def _ratio(numerator, denominator):
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _as_int(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _format_ratio(value):
    return f"{value:.2f}"


def _percent(value):
    return f"{round(value * 100)}%"
