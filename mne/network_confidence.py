HIGH = "HIGH"
MODERATE = "MODERATE"
LOW = "LOW"
VERY_LOW = "VERY_LOW"
UNKNOWN = "UNKNOWN"

NETWORK_HEALTHY = "NETWORK_HEALTHY"
NETWORK_PARTIAL = "NETWORK_PARTIAL"
NETWORK_DEGRADED = "NETWORK_DEGRADED"
NETWORK_CRITICAL = "NETWORK_CRITICAL"

SOURCE_CONFIDENCE_HIGH = "HIGH"
SOURCE_CONFIDENCE_MODERATE = "MODERATE"
SOURCE_CONFIDENCE_LOW = "LOW"
SOURCE_CONFIDENCE_UNKNOWN = "UNKNOWN"

RELIABILITY_WATCH_COUNT_THRESHOLD = 2
RELIABILITY_REPEATED_FAILURE_COUNT_THRESHOLD = 1
RELIABILITY_QUARANTINE_RECOMMENDED_COUNT_THRESHOLD = 1
MIN_BROAD_COVERAGE_COUNT = 1
MAX_MINIMAL_COVERAGE_COUNT_FOR_MODERATE = 0

ACTION_BY_STATE = {
    HIGH: "No action needed.",
    MODERATE: "Monitor evidence-network diagnostics before relying on broad conclusions.",
    LOW: "Review network health, source reliability, and coverage limits before relying on this run.",
    VERY_LOW: "Do not rely on this run until evidence-network diagnostics are reviewed.",
    UNKNOWN: "Investigate why required evidence-network diagnostics are missing for this run.",
}

THRESHOLDS_USED = {
    "reliability_watch_count_threshold": RELIABILITY_WATCH_COUNT_THRESHOLD,
    "reliability_repeated_failure_count_threshold": RELIABILITY_REPEATED_FAILURE_COUNT_THRESHOLD,
    "reliability_quarantine_recommended_count_threshold": (
        RELIABILITY_QUARANTINE_RECOMMENDED_COUNT_THRESHOLD
    ),
    "min_broad_coverage_count": MIN_BROAD_COVERAGE_COUNT,
    "max_minimal_coverage_count_for_moderate": MAX_MINIMAL_COVERAGE_COUNT_FOR_MODERATE,
}

REQUIRED_BLOCKS = (
    "network_health",
    "source_confidence",
    "source_reliability",
    "coverage_intelligence",
)


def build_network_confidence(source_intelligence):
    diagnostics = source_intelligence or {}
    missing = missing_required_blocks(diagnostics)
    if missing:
        return _unknown(missing)

    facts = derive_network_confidence_facts(diagnostics)
    state, rule = evaluate_network_confidence_state(facts)
    return {
        "network_confidence_state": state,
        "confidence_level": None,
        "reason": build_reason(state, rule, facts),
        "recommended_action": ACTION_BY_STATE[state],
        "supporting_factors": build_supporting_factors(facts),
        "limiting_factors": build_limiting_factors(facts),
        "thresholds_used": dict(THRESHOLDS_USED),
        "inputs": {
            "network_status": facts["network_status"],
            "source_confidence_state": facts["source_confidence_state"],
            "reliability_summary": dict(facts["reliability_summary"]),
            "coverage_summary": dict(facts["coverage_summary"]),
        },
    }


def missing_required_blocks(source_intelligence):
    return [
        block
        for block in REQUIRED_BLOCKS
        if not isinstance(source_intelligence.get(block), dict)
        or not source_intelligence.get(block)
    ]


def derive_network_confidence_facts(source_intelligence):
    network_health = source_intelligence.get("network_health") or {}
    source_confidence = source_intelligence.get("source_confidence") or {}
    source_reliability = source_intelligence.get("source_reliability") or {}
    coverage_intelligence = source_intelligence.get("coverage_intelligence") or {}
    coverage_summary = (coverage_intelligence.get("overall") or {}).get("coverage_summary") or {}
    reliability_summary = source_reliability.get("summary") or {}

    return {
        "network_status": network_health.get("network_status") or UNKNOWN,
        "source_confidence_state": source_confidence.get("confidence_state") or UNKNOWN,
        "reliability_summary": {
            "stable_count": _as_int(reliability_summary.get("stable_count")),
            "watch_count": _as_int(reliability_summary.get("watch_count")),
            "repeated_failure_count": _as_int(
                reliability_summary.get("repeated_failure_count")
            ),
            "quarantine_recommended_count": _as_int(
                reliability_summary.get("quarantine_recommended_count")
            ),
            "unknown_count": _as_int(reliability_summary.get("unknown_count")),
        },
        "coverage_summary": {
            "minimal_count": _as_int(coverage_summary.get("minimal_count")),
            "limited_count": _as_int(coverage_summary.get("limited_count")),
            "moderate_count": _as_int(coverage_summary.get("moderate_count")),
            "broad_count": _as_int(coverage_summary.get("broad_count")),
            "extensive_count": _as_int(coverage_summary.get("extensive_count")),
        },
    }


def evaluate_network_confidence_state(facts):
    reliability = facts["reliability_summary"]
    coverage = facts["coverage_summary"]
    network_status = facts["network_status"]
    source_confidence = facts["source_confidence_state"]

    if network_status == UNKNOWN or source_confidence == SOURCE_CONFIDENCE_UNKNOWN:
        return UNKNOWN, "unknown_input_state"
    if network_status == NETWORK_CRITICAL:
        return VERY_LOW, "network_critical"
    if source_confidence == SOURCE_CONFIDENCE_LOW:
        return VERY_LOW, "source_confidence_low"
    if (
        reliability["quarantine_recommended_count"]
        >= RELIABILITY_QUARANTINE_RECOMMENDED_COUNT_THRESHOLD
    ):
        return LOW, "quarantine_recommended"
    if network_status == NETWORK_DEGRADED:
        return LOW, "network_degraded"
    if (
        reliability["repeated_failure_count"]
        >= RELIABILITY_REPEATED_FAILURE_COUNT_THRESHOLD
    ):
        return LOW, "repeated_failure"
    if coverage["minimal_count"] > MAX_MINIMAL_COVERAGE_COUNT_FOR_MODERATE:
        return LOW, "minimal_coverage"
    if network_status == NETWORK_PARTIAL:
        return MODERATE, "network_partial"
    if source_confidence == SOURCE_CONFIDENCE_MODERATE:
        return MODERATE, "source_confidence_moderate"
    if reliability["watch_count"] >= RELIABILITY_WATCH_COUNT_THRESHOLD:
        return MODERATE, "watch_sources"
    if (
        coverage["broad_count"] + coverage["extensive_count"]
        < MIN_BROAD_COVERAGE_COUNT
    ):
        return MODERATE, "no_broad_coverage"
    return HIGH, "healthy"


def build_reason(state, rule, facts):
    reliability = facts["reliability_summary"]
    coverage = facts["coverage_summary"]
    if rule == "unknown_input_state":
        return "Network confidence could not be evaluated because an input diagnostic state was UNKNOWN."
    if rule == "network_critical":
        return "Network Health persisted NETWORK_CRITICAL for this run."
    if rule == "source_confidence_low":
        return "Source Confidence persisted LOW for this run."
    if rule == "quarantine_recommended":
        return (
            f"{reliability['quarantine_recommended_count']} source(s) were marked "
            "QUARANTINE_RECOMMENDED."
        )
    if rule == "network_degraded":
        return "Network Health persisted NETWORK_DEGRADED for this run."
    if rule == "repeated_failure":
        return (
            f"{reliability['repeated_failure_count']} source(s) were marked "
            "REPEATED_FAILURE."
        )
    if rule == "minimal_coverage":
        return f"{coverage['minimal_count']} narrative coverage record(s) were MINIMAL."
    if rule == "network_partial":
        return "Network Health persisted NETWORK_PARTIAL for this run."
    if rule == "source_confidence_moderate":
        return "Source Confidence persisted MODERATE for this run."
    if rule == "watch_sources":
        return f"{reliability['watch_count']} source(s) were marked WATCH."
    if rule == "no_broad_coverage":
        return "Coverage Intelligence persisted no BROAD or EXTENSIVE coverage records."
    return "Evidence network inputs are healthy, reliable, and broadly covered."


def build_supporting_factors(facts):
    reliability = facts["reliability_summary"]
    coverage = facts["coverage_summary"]
    factors = []
    if facts["network_status"] == NETWORK_HEALTHY:
        factors.append("Network Health: NETWORK_HEALTHY")
    if facts["source_confidence_state"] == SOURCE_CONFIDENCE_HIGH:
        factors.append("Source Confidence: HIGH")
    if reliability["stable_count"]:
        factors.append(f"Stable sources: {reliability['stable_count']}")
    broad_total = coverage["broad_count"] + coverage["extensive_count"]
    if broad_total:
        factors.append(f"BROAD/EXTENSIVE coverage records: {broad_total}")
    return factors


def build_limiting_factors(facts):
    reliability = facts["reliability_summary"]
    coverage = facts["coverage_summary"]
    factors = []
    if facts["network_status"] != NETWORK_HEALTHY:
        factors.append(f"Network Health: {facts['network_status']}")
    if facts["source_confidence_state"] != SOURCE_CONFIDENCE_HIGH:
        factors.append(f"Source Confidence: {facts['source_confidence_state']}")
    if reliability["watch_count"]:
        factors.append(f"WATCH sources: {reliability['watch_count']}")
    if reliability["repeated_failure_count"]:
        factors.append(f"REPEATED_FAILURE sources: {reliability['repeated_failure_count']}")
    if reliability["quarantine_recommended_count"]:
        factors.append(
            "QUARANTINE_RECOMMENDED sources: "
            f"{reliability['quarantine_recommended_count']}"
        )
    if reliability["unknown_count"]:
        factors.append(f"UNKNOWN reliability sources: {reliability['unknown_count']}")
    if coverage["minimal_count"]:
        factors.append(f"MINIMAL coverage records: {coverage['minimal_count']}")
    if not coverage["broad_count"] and not coverage["extensive_count"]:
        factors.append("No BROAD or EXTENSIVE coverage records.")
    return factors


def _unknown(missing):
    missing_text = ", ".join(missing)
    return {
        "network_confidence_state": UNKNOWN,
        "confidence_level": None,
        "reason": (
            "Network confidence could not be evaluated because "
            f"{missing_text} diagnostic block(s) were missing."
        ),
        "recommended_action": ACTION_BY_STATE[UNKNOWN],
        "supporting_factors": [],
        "limiting_factors": [
            f"Missing required diagnostic: {block}" for block in missing
        ],
        "thresholds_used": dict(THRESHOLDS_USED),
        "inputs": {
            "missing_required_blocks": list(missing),
        },
    }


def _as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
