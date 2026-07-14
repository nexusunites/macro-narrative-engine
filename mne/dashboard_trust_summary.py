STRONG = "Strong evidence base"
USABLE = "Usable evidence base"
LIMITED = "Limited evidence base"
THIN = "Thin evidence base"
UNAVAILABLE = "Data unavailable"

HIGH = "High"
MODERATE = "Moderate"
LOW = "Low"

REASON_BY_STATE = {
    STRONG: "Today's read is based on a broad evidence set with healthy source collection.",
    USABLE: (
        "Today's read is usable, with enough evidence to support the current "
        "environment summary."
    ),
    LIMITED: "Today's read is usable, but evidence coverage is thinner than normal.",
    THIN: (
        "Today's read is thin because accepted fresh evidence or matched narrative "
        "coverage was low."
    ),
    UNAVAILABLE: "Today's evidence quality could not be verified from the latest run data.",
}

NETWORK_CONFIDENCE_REASON_BY_STATE = {
    STRONG: "Today's read is supported by a strong evidence network.",
    USABLE: "Today's read is usable, though the evidence network has some limitations.",
    LIMITED: "Today's read is limited because the evidence network has meaningful constraints.",
    THIN: "Today's read is thin because the evidence network is highly limited.",
}

FALLBACK_REASON = (
    "The dashboard is showing the latest meaningful run because the latest run did "
    "not produce enough narrative signal."
)

DEFAULT_ACCEPTED_EVIDENCE_FLOOR = 10
VERY_LOW_ACCEPTED_EVIDENCE = 2
NETWORK_CONFIDENCE_SOURCE = "network_confidence"
LEGACY_SOURCE = "legacy"

NETWORK_CONFIDENCE_STATE_TO_DASHBOARD_STATE = {
    "HIGH": STRONG,
    "MODERATE": USABLE,
    "LOW": LIMITED,
    "VERY_LOW": THIN,
}

NETWORK_CONFIDENCE_FACT_LABELS = {
    "HIGH": "Strong",
    "MODERATE": "Moderate",
    "LOW": "Limited",
    "VERY_LOW": "Thin",
    "UNKNOWN": "Unknown",
}

NETWORK_LABELS = {
    "NETWORK_HEALTHY": "Healthy",
    "NETWORK_PARTIAL": "Partial",
    "NETWORK_DEGRADED": "Limited",
    "NETWORK_CRITICAL": "Limited",
    "HEALTHY": "Healthy",
    "PARTIAL": "Partial",
    "DEGRADED": "Limited",
    "CRITICAL": "Limited",
}

SOURCE_CONFIDENCE_LABELS = {
    "HIGH": "High",
    "MODERATE": "Moderate",
    "LOW": "Low",
    "UNKNOWN": "Unknown",
}

COVERAGE_LABELS = {
    "EXTENSIVE": "Broad",
    "BROAD": "Broad",
    "MODERATE": "Moderate",
    "LIMITED": "Limited",
    "MINIMAL": "Thin",
}


def build_dashboard_trust_summary(run_data, latest_meaningful_fallback_active=False):
    facts = summarize_dashboard_trust_facts(
        run_data,
        latest_meaningful_fallback_active=latest_meaningful_fallback_active,
    )
    state, confidence, classification_source = classify_dashboard_data_quality(
        facts,
        latest_meaningful_fallback_active=latest_meaningful_fallback_active,
    )
    return {
        "state": state,
        "confidence": confidence,
        "reason": build_dashboard_trust_reason(
            state,
            classification_source=classification_source,
            latest_meaningful_fallback_active=latest_meaningful_fallback_active,
        ),
        "facts": _display_facts(facts),
        "admin_link_visible": True,
    }


def classify_dashboard_data_quality(
    facts,
    latest_meaningful_fallback_active=False,
):
    if not facts.get("has_run"):
        return UNAVAILABLE, LOW, LEGACY_SOURCE

    has_diagnostics = facts.get("has_source_intelligence") and (
        facts.get("source_confidence_state")
        or facts.get("network_status")
        or facts.get("accepted_count") is not None
    )
    if not has_diagnostics and not facts.get("has_fallback_facts"):
        return UNAVAILABLE, LOW, LEGACY_SOURCE

    accepted_count = facts.get("accepted_count")
    matched_headlines = facts.get("matched_headlines")
    has_narratives = facts.get("has_narratives")
    source_confidence = facts.get("source_confidence_state")
    network_status = facts.get("network_status")
    coverage_strength = facts.get("coverage_strength")
    network_confidence_state = facts.get("network_confidence_state")
    accepted_floor = facts.get("accepted_evidence_floor") or DEFAULT_ACCEPTED_EVIDENCE_FLOOR

    if latest_meaningful_fallback_active:
        return THIN, LOW, LEGACY_SOURCE

    if accepted_count is not None and accepted_count <= VERY_LOW_ACCEPTED_EVIDENCE:
        return THIN, _confidence_for_missing(facts, low_when_missing=True), LEGACY_SOURCE
    if matched_headlines is not None and matched_headlines <= 0 and not has_narratives:
        return THIN, _confidence_for_missing(facts, low_when_missing=True), LEGACY_SOURCE

    if network_confidence_state and network_confidence_state != "UNKNOWN":
        network_state = NETWORK_CONFIDENCE_STATE_TO_DASHBOARD_STATE.get(
            network_confidence_state
        )
        if network_state:
            return network_state, HIGH, NETWORK_CONFIDENCE_SOURCE

    if source_confidence == "LOW" or network_status in {"NETWORK_DEGRADED", "NETWORK_CRITICAL"}:
        return LIMITED, _confidence_for_missing(facts), LEGACY_SOURCE
    if (
        accepted_count is not None
        and 0 < accepted_count < accepted_floor
        and has_narratives
    ):
        return LIMITED, _confidence_for_missing(facts), LEGACY_SOURCE
    if coverage_strength in {"MINIMAL", "LIMITED"} and has_narratives:
        return LIMITED, _confidence_for_missing(facts), LEGACY_SOURCE

    if (
        source_confidence == "HIGH"
        and network_status == "NETWORK_HEALTHY"
        and accepted_count is not None
        and accepted_count >= accepted_floor
        and coverage_strength in {"BROAD", "EXTENSIVE"}
    ):
        return STRONG, _confidence_for_agreement(facts), LEGACY_SOURCE

    if (
        source_confidence in {"HIGH", "MODERATE"}
        or network_status in {"NETWORK_HEALTHY", "NETWORK_PARTIAL"}
        or (accepted_count is not None and accepted_count >= accepted_floor)
    ) and has_narratives:
        return USABLE, _confidence_for_missing(facts), LEGACY_SOURCE

    if has_narratives:
        return LIMITED, LOW, LEGACY_SOURCE
    return UNAVAILABLE, LOW, LEGACY_SOURCE


def build_dashboard_trust_reason(
    state,
    classification_source=LEGACY_SOURCE,
    latest_meaningful_fallback_active=False,
):
    reason_source = (
        NETWORK_CONFIDENCE_REASON_BY_STATE
        if classification_source == NETWORK_CONFIDENCE_SOURCE
        else REASON_BY_STATE
    )
    reason = reason_source.get(state, REASON_BY_STATE[UNAVAILABLE])
    if latest_meaningful_fallback_active:
        return f"{reason} {FALLBACK_REASON}"
    return reason


def summarize_dashboard_trust_facts(
    run_data,
    latest_meaningful_fallback_active=False,
):
    run = run_data if isinstance(run_data, dict) else {}
    source_intelligence = run.get("source_intelligence")
    source_intelligence = source_intelligence if isinstance(source_intelligence, dict) else {}
    source_confidence = source_intelligence.get("source_confidence")
    source_confidence = source_confidence if isinstance(source_confidence, dict) else {}
    network_health = source_intelligence.get("network_health")
    network_health = network_health if isinstance(network_health, dict) else {}
    network_confidence = source_intelligence.get("network_confidence")
    network_confidence = network_confidence if isinstance(network_confidence, dict) else {}
    coverage = source_intelligence.get("coverage_intelligence")
    coverage = coverage if isinstance(coverage, dict) else {}

    accepted_count = _int_or_none(source_intelligence.get("accepted_count"))
    if accepted_count is None:
        accepted_count = _accepted_count_from_fallbacks(source_intelligence, network_health)

    coverage_strength = _coverage_strength(coverage)
    provider_count = _provider_count(source_intelligence, network_health, coverage)
    source_count = _source_count(source_intelligence, network_health, coverage)

    return {
        "has_run": bool(run_data),
        "has_source_intelligence": bool(source_intelligence),
        "has_fallback_facts": any(
            value is not None
            for value in (
                accepted_count,
                run.get("matched_headlines"),
                run.get("headline_count"),
            )
        ),
        "accepted_count": accepted_count,
        "matched_headlines": _int_or_none(run.get("matched_headlines")),
        "has_narratives": _has_narratives(run),
        "source_confidence_state": _normalize_key(
            source_confidence.get("confidence_state")
            or source_confidence.get("confidence_level")
        ),
        "network_status": _normalize_key(network_health.get("network_status")),
        "network_confidence": network_confidence,
        "network_confidence_state": _normalize_key(
            network_confidence.get("network_confidence_state")
        ),
        "coverage_strength": coverage_strength,
        "provider_count": provider_count,
        "source_count": source_count,
        "accepted_evidence_floor": _int_or_none(
            (source_confidence.get("thresholds_used") or {}).get("accepted_evidence_floor")
        ),
        "has_evidence_funnel": isinstance(source_intelligence.get("evidence_funnel"), dict),
        "has_coverage_intelligence": bool(coverage),
        "latest_meaningful_fallback_active": latest_meaningful_fallback_active,
    }


def normalize_user_facing_network_state(network_status):
    key = _normalize_key(network_status)
    if not key:
        return None
    return NETWORK_LABELS.get(key, _title_label(key))


def normalize_user_facing_source_confidence(confidence_state):
    key = _normalize_key(confidence_state)
    if not key:
        return None
    return SOURCE_CONFIDENCE_LABELS.get(key, _title_label(key))


def _display_facts(facts):
    rows = []
    if facts.get("accepted_count") is not None:
        rows.append(f"Accepted evidence: {facts['accepted_count']}")
    if facts.get("provider_count") is not None:
        rows.append(f"Providers: {facts['provider_count']}")
    network_confidence_state = facts.get("network_confidence_state")
    network_confidence = (
        NETWORK_CONFIDENCE_FACT_LABELS.get(network_confidence_state)
        if network_confidence_state and network_confidence_state != "UNKNOWN"
        else None
    )
    if network_confidence:
        rows.append(f"Evidence network: {network_confidence}")
    else:
        network = normalize_user_facing_network_state(facts.get("network_status"))
        if network:
            rows.append(f"Network status: {network}")
    source_confidence = normalize_user_facing_source_confidence(
        facts.get("source_confidence_state")
    )
    if source_confidence:
        rows.append(f"Source confidence: {source_confidence}")
    coverage = COVERAGE_LABELS.get(facts.get("coverage_strength"))
    if coverage:
        rows.append(f"Coverage: {coverage}")
    return rows


def _confidence_for_agreement(facts):
    required = (
        facts.get("source_confidence_state"),
        facts.get("network_status"),
        facts.get("accepted_count"),
        facts.get("coverage_strength"),
    )
    if all(value is not None for value in required):
        return HIGH
    return MODERATE


def _confidence_for_missing(facts, low_when_missing=False):
    required = (
        facts.get("source_confidence_state"),
        facts.get("network_status"),
        facts.get("accepted_count"),
    )
    missing = sum(1 for value in required if value is None)
    if missing >= 2:
        return LOW
    if missing == 1 or not facts.get("has_coverage_intelligence"):
        return LOW if low_when_missing else MODERATE
    return MODERATE


def _accepted_count_from_fallbacks(source_intelligence, network_health):
    count = _int_or_none(
        (network_health.get("concentration") or {}).get("total_accepted_evidence")
    )
    if count is not None:
        return count
    accepted = source_intelligence.get("accepted_evidence")
    if isinstance(accepted, list):
        return len(accepted)
    funnel = source_intelligence.get("evidence_funnel")
    if isinstance(funnel, dict):
        return _int_or_none(funnel.get("accepted_fresh"))
    return None


def _coverage_strength(coverage):
    overall = coverage.get("overall") if isinstance(coverage, dict) else None
    summary = overall.get("coverage_summary") if isinstance(overall, dict) else None
    if isinstance(summary, dict):
        if summary.get("extensive_count") or summary.get("broad_count"):
            return "BROAD"
        if summary.get("moderate_count"):
            return "MODERATE"
        if summary.get("limited_count"):
            return "LIMITED"
        if summary.get("minimal_count"):
            return "MINIMAL"

    states = [
        _normalize_key(row.get("coverage_state"))
        for row in coverage.get("per_narrative", [])
        if isinstance(row, dict)
    ]
    for state in ("EXTENSIVE", "BROAD", "MODERATE", "LIMITED", "MINIMAL"):
        if state in states:
            return state
    return None


def _provider_count(source_intelligence, network_health, coverage):
    providers = network_health.get("providers")
    if isinstance(providers, list) and providers:
        return len([row for row in providers if isinstance(row, dict)])

    overall = coverage.get("overall") if isinstance(coverage, dict) else None
    diversity = overall.get("provider_diversity") if isinstance(overall, dict) else None
    count = _int_or_none((diversity or {}).get("unique_provider_count"))
    if count is not None:
        return count

    provider_ids = {
        row.get("provider")
        for row in source_intelligence.get("accepted_evidence", [])
        if isinstance(row, dict) and row.get("provider")
    }
    return len(provider_ids) if provider_ids else None


def _source_count(source_intelligence, network_health, coverage):
    source_ids = {
        row.get("source_id")
        for row in source_intelligence.get("accepted_evidence", [])
        if isinstance(row, dict) and row.get("source_id")
    }
    if source_ids:
        return len(source_ids)

    providers = network_health.get("providers")
    if isinstance(providers, list):
        count = sum(_int_or_none(row.get("sources_total")) or 0 for row in providers if isinstance(row, dict))
        if count:
            return count

    overall = coverage.get("overall") if isinstance(coverage, dict) else None
    diversity = overall.get("source_diversity") if isinstance(overall, dict) else None
    return _int_or_none((diversity or {}).get("unique_source_count"))


def _has_narratives(run):
    for field in ("theme_scores", "theme_counts", "group_scores"):
        scores = run.get(field)
        if isinstance(scores, dict) and any((_numeric(value) or 0) > 0 for value in scores.values()):
            return True
    return bool(run.get("dominant_theme") or run.get("dominant_group"))


def _normalize_key(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper().replace("-", "_").replace(" ", "_")


def _title_label(value):
    return str(value).replace("_", " ").title()


def _int_or_none(value):
    number = _numeric(value)
    if number is None:
        return None
    return int(number)


def _numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
