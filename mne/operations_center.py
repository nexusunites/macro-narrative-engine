from collections import Counter


EXCELLENT = "EXCELLENT"
GOOD = "GOOD"
LIMITED = "LIMITED"
DEGRADED = "DEGRADED"
WARNING = "WARNING"
CRITICAL = "CRITICAL"
OFFLINE = "OFFLINE"

HIGH = "HIGH"
MODERATE = "MODERATE"
LOW = "LOW"
UNKNOWN = "UNKNOWN"

NO_ACTION = "No action needed."

COMPONENT_ORDER = (
    "configuration",
    "pipeline",
    "evidence_network",
    "source_confidence",
    "source_reliability",
    "coverage_intelligence",
    "freshness_feed_health",
)

COMPONENT_TITLES = {
    "configuration": "Configuration",
    "pipeline": "Pipeline / Platform Observability",
    "evidence_network": "Evidence Network",
    "source_confidence": "Source Confidence",
    "source_reliability": "Source Reliability",
    "coverage_intelligence": "Coverage Intelligence",
    "freshness_feed_health": "Freshness / Feed Health",
}

COMPONENT_DETAIL_ANCHORS = {
    "configuration": "configuration-diagnostics",
    "pipeline": "platform-observability",
    "evidence_network": "evidence-network",
    "source_confidence": "evidence-network",
    "source_reliability": "evidence-network",
    "coverage_intelligence": "coverage-intelligence",
    "freshness_feed_health": "source-health",
}

STATUS_SEVERITY = {
    EXCELLENT: 0,
    GOOD: 1,
    LIMITED: 2,
    WARNING: 3,
    DEGRADED: 4,
    OFFLINE: 5,
    CRITICAL: 6,
}

CONFIDENCE_SEVERITY = {
    HIGH: 0,
    MODERATE: 1,
    LOW: 2,
    UNKNOWN: 3,
}

SOURCE_CONFIDENCE_STATUS = {
    "HIGH": EXCELLENT,
    "MODERATE": LIMITED,
    "LOW": DEGRADED,
    "UNKNOWN": WARNING,
}

NETWORK_HEALTH_STATUS = {
    "NETWORK_HEALTHY": GOOD,
    "NETWORK_PARTIAL": LIMITED,
    "NETWORK_DEGRADED": DEGRADED,
    "NETWORK_CRITICAL": CRITICAL,
}

CORE_PIPELINE_STAGES = {
    "RSS_FETCH",
    "EVIDENCE_NORMALIZATION",
    "NARRATIVE_INTELLIGENCE",
    "RUN_PERSISTENCE",
}

HEALTHY_FEED_SEVERITIES = {"INFO"}
FRESH_STATUSES = {"FRESH"}


def build_operations_center(run_data, registry):
    source_intelligence = (run_data or {}).get("source_intelligence") or {}
    details = {
        "configuration_report": (registry or {}).get("configuration_report") or {},
        "source_registry": (registry or {}).get("source_registry") or {},
        "source_intelligence": source_intelligence,
        "platform_observability": (run_data or {}).get("platform_observability") or {},
    }
    components = [
        evaluate_component_status(component_key, run_data, registry)
        for component_key in COMPONENT_ORDER
    ]
    overall_status, contributing_components = rollup_overall_status(components)
    overall_confidence = rollup_overall_confidence(contributing_components)
    recommendations = build_recommendations(components, details)
    reason = build_overall_reason(overall_status, contributing_components)
    overall_recommendation = _dominant_recommendation(contributing_components, recommendations)

    return {
        "overall": {
            "status": overall_status,
            "confidence": overall_confidence,
            "reason": reason,
            "recommendation": overall_recommendation,
        },
        "recommendations": recommendations,
        "working": summarize_working_components(components),
        "needs_attention": summarize_problem_components(components),
        "components": components,
    }


def evaluate_component_status(component_key, run_data=None, registry=None):
    evaluators = {
        "configuration": _evaluate_configuration,
        "pipeline": _evaluate_pipeline,
        "evidence_network": _evaluate_evidence_network,
        "source_confidence": _evaluate_source_confidence,
        "source_reliability": _evaluate_source_reliability,
        "coverage_intelligence": _evaluate_coverage_intelligence,
        "freshness_feed_health": _evaluate_freshness_feed_health,
    }
    if component_key not in evaluators:
        raise ValueError(f"Unknown operations component: {component_key}")
    return evaluators[component_key](run_data or {}, registry or {})


def rollup_overall_status(component_statuses):
    components = list(component_statuses or [])
    if not components:
        return UNKNOWN, []
    worst_score = max(STATUS_SEVERITY.get(component.get("status"), 0) for component in components)
    contributing = [
        component
        for component in components
        if STATUS_SEVERITY.get(component.get("status"), 0) == worst_score
    ]
    status = contributing[0]["status"]
    if any(
        component.get("key") == "configuration" and component.get("status") == CRITICAL
        for component in components
    ):
        status = CRITICAL
        contributing = [
            component
            for component in components
            if component.get("key") == "configuration"
            and component.get("status") == CRITICAL
        ]
    return status, contributing


def build_recommendations(component_statuses, details=None):
    details = details or {}
    recommendations = []
    by_key = {component.get("key"): component for component in component_statuses or []}

    configuration = by_key.get("configuration") or {}
    if configuration.get("status") == CRITICAL:
        recommendations.append("Fix registry/configuration errors; see Configuration diagnostics.")

    source_intelligence = details.get("source_intelligence") or {}
    source_health = source_intelligence.get("source_health") or []
    source_freshness = source_intelligence.get("source_freshness") or []
    if _stale_or_degraded_sources(source_health, source_freshness):
        recommendations.append("Review stale sources in Feed Health.")

    reliability = source_intelligence.get("source_reliability") or {}
    reliability_summary = reliability.get("summary") or {}
    if int(reliability_summary.get("quarantine_recommended_count") or 0) > 0:
        recommendations.append(
            "Review sources recommended for quarantine in Source Reliability."
        )
    if int(reliability_summary.get("repeated_failure_count") or 0) > 0:
        recommendations.append("Review sources with repeated failures in Source Reliability.")
    if int(reliability_summary.get("watch_count") or 0) > 0:
        recommendations.append("Review sources marked WATCH in Source Reliability.")

    network_health = source_intelligence.get("network_health") or {}
    categories = network_health.get("categories") or []
    network_status = network_health.get("network_status")
    if any(category.get("category_state") == "UNCOVERED" for category in categories):
        recommendations.append("Review Evidence Network categories marked UNCOVERED.")
    elif network_status == "NETWORK_PARTIAL":
        recommendations.append("Review Evidence Network dependencies and concentration.")
    elif network_status == "NETWORK_DEGRADED":
        recommendations.append("Review Evidence Network dependencies and concentration.")

    source_confidence = source_intelligence.get("source_confidence") or {}
    if source_confidence.get("confidence_state") == "UNKNOWN":
        recommendations.append("Investigate missing source diagnostics.")

    if not recommendations:
        recommendations.append(NO_ACTION)
    return _dedupe(recommendations)


def summarize_working_components(component_statuses):
    return [
        f"{component['title']}: {component['reason']}"
        for component in component_statuses or []
        if component.get("status") in {EXCELLENT, GOOD}
    ]


def summarize_problem_components(component_statuses):
    return [
        f"{component['title']} is {component['status']}: {component['reason']}"
        for component in component_statuses or []
        if component.get("status") not in {EXCELLENT, GOOD}
    ]


def rollup_overall_confidence(contributing_components):
    if not contributing_components:
        return UNKNOWN
    return max(
        (component.get("confidence") or UNKNOWN for component in contributing_components),
        key=lambda confidence: CONFIDENCE_SEVERITY.get(confidence, CONFIDENCE_SEVERITY[UNKNOWN]),
    )


def build_overall_reason(overall_status, contributing_components):
    if not contributing_components:
        return "Operations Center could not evaluate the selected run."
    if overall_status == EXCELLENT:
        return "All components are operating at EXCELLENT."
    if len(contributing_components) == 1:
        component = contributing_components[0]
        return f"{component['title']} is {component['status']}: {component['reason']}"
    names = ", ".join(component["title"] for component in contributing_components)
    return f"{names} are {overall_status}; review the component summaries for specifics."


def _dominant_recommendation(contributing_components, recommendations):
    for component in contributing_components or []:
        recommendation = component.get("recommendation")
        if recommendation and recommendation != NO_ACTION:
            return recommendation
    return recommendations[0] if recommendations else NO_ACTION


def _component(key, status, confidence, reason, recommendation=NO_ACTION, facts=None):
    return {
        "key": key,
        "title": COMPONENT_TITLES[key],
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "recommendation": recommendation,
        "detail_anchor": COMPONENT_DETAIL_ANCHORS[key],
        "facts": facts or {},
    }


def _evaluate_configuration(_run_data, registry):
    report = (registry or {}).get("configuration_report") or {}
    source_registry = (registry or {}).get("source_registry") or {}
    error = report.get("registry_error") or source_registry.get("error")
    if error:
        return _component(
            "configuration",
            CRITICAL,
            HIGH,
            f"Registry/configuration validation failed: {error}",
            "Fix registry/configuration errors; see Configuration diagnostics.",
        )
    if not report:
        return _component(
            "configuration",
            WARNING,
            UNKNOWN,
            "Configuration diagnostics were not available for this render.",
            "Review Configuration diagnostics.",
        )
    missing = [
        label
        for label, value in (
            ("active data directory", report.get("active_data_dir")),
            ("results directory", report.get("results_dir")),
            ("headlines directory", report.get("headlines_dir")),
            ("registry version", report.get("registry_version")),
        )
        if not value
    ]
    if missing:
        return _component(
            "configuration",
            CRITICAL,
            MODERATE,
            f"Configuration diagnostics are missing {', '.join(missing)}.",
            "Fix registry/configuration errors; see Configuration diagnostics.",
        )
    return _component(
        "configuration",
        EXCELLENT,
        HIGH,
        (
            f"Registry {report.get('registry_version')} loaded and data directory resolved; "
            "required registry threshold sections validated."
        ),
    )


def _evaluate_pipeline(run_data, _registry):
    observability = (run_data or {}).get("platform_observability") or {}
    stages = list(observability.get("stages") or [])
    if not observability or not stages:
        return _component(
            "pipeline",
            OFFLINE,
            UNKNOWN,
            "No Platform Observability block was persisted for this run.",
            "Investigate missing platform observability diagnostics.",
        )
    statuses = Counter(stage.get("status") or "UNKNOWN" for stage in stages)
    failed = [stage for stage in stages if stage.get("status") == "FAILED"]
    partial = [stage for stage in stages if stage.get("status") == "PARTIAL"]
    skipped = [stage for stage in stages if stage.get("status") == "SKIPPED"]
    if failed:
        core_failed = [
            stage for stage in failed if stage.get("stage_name") in CORE_PIPELINE_STAGES
        ]
        status = CRITICAL if core_failed else DEGRADED
        names = _stage_names(core_failed or failed)
        return _component(
            "pipeline",
            status,
            HIGH,
            f"Failed stage(s): {names}.",
            f"Investigate failed pipeline stage(s): {names}.",
            {"stage_status_counts": dict(statuses)},
        )
    if len(partial) > 1:
        names = _stage_names(partial)
        return _component(
            "pipeline",
            LIMITED,
            HIGH,
            f"Multiple partial stage(s): {names}.",
            f"Review partial pipeline stage(s): {names}.",
            {"stage_status_counts": dict(statuses)},
        )
    if partial:
        names = _stage_names(partial)
        return _component(
            "pipeline",
            GOOD,
            HIGH,
            f"One partial stage: {names}; remaining stages completed or were intentionally skipped.",
            f"Review partial pipeline stage: {names}.",
            {"stage_status_counts": dict(statuses)},
        )
    if skipped:
        names = _stage_names(skipped)
        return _component(
            "pipeline",
            GOOD,
            HIGH,
            f"No failed or partial stages; skipped stage(s): {names}.",
            "Review skipped stage rationale in Platform Observability.",
            {"stage_status_counts": dict(statuses)},
        )
    return _component(
        "pipeline",
        EXCELLENT,
        HIGH,
        f"All {len(stages)} persisted pipeline stage(s) completed successfully.",
        facts={"stage_status_counts": dict(statuses)},
    )


def _evaluate_evidence_network(run_data, _registry):
    network_health = (
        ((run_data or {}).get("source_intelligence") or {}).get("network_health") or {}
    )
    if not network_health:
        return _component(
            "evidence_network",
            OFFLINE,
            UNKNOWN,
            "No Evidence Network block was persisted for this run.",
            "Review Evidence Network diagnostics.",
        )
    network_status = network_health.get("network_status") or "UNKNOWN"
    categories = network_health.get("categories") or []
    concentration = network_health.get("concentration") or {}
    single_provider = [
        category.get("category")
        for category in categories
        if category.get("single_provider_dependency")
    ]
    uncovered = [
        category.get("category")
        for category in categories
        if category.get("category_state") == "UNCOVERED"
    ]
    concentration_flag = bool(concentration.get("concentration_flag"))
    status = NETWORK_HEALTH_STATUS.get(network_status, WARNING)
    if (
        network_status == "NETWORK_HEALTHY"
        and not concentration_flag
        and not single_provider
    ):
        status = EXCELLENT
    reason_parts = [f"Network health persisted {network_status}."]
    if concentration_flag and concentration.get("top_provider"):
        reason_parts.append(
            f"{concentration.get('top_provider')} contributed "
            f"{concentration.get('top_provider_share')} of accepted evidence."
        )
    if single_provider:
        reason_parts.append(
            f"Single-provider dependencies: {', '.join(single_provider[:4])}."
        )
    if uncovered:
        reason_parts.append(f"Uncovered categories: {', '.join(uncovered[:4])}.")
    if len(reason_parts) == 1:
        reason_parts.append(f"{len(categories)} categories evaluated.")
    recommendation = (
        "Review Evidence Network categories marked UNCOVERED."
        if uncovered
        else (
            "Review Evidence Network dependencies and concentration."
            if status in {LIMITED, DEGRADED, CRITICAL}
            else NO_ACTION
        )
    )
    return _component(
        "evidence_network",
        status,
        HIGH,
        " ".join(reason_parts),
        recommendation,
        {
            "network_status": network_status,
            "single_provider_dependencies": single_provider,
            "uncovered_categories": uncovered,
            "concentration_flag": concentration_flag,
        },
    )


def _evaluate_source_confidence(run_data, _registry):
    source_confidence = (
        ((run_data or {}).get("source_intelligence") or {}).get("source_confidence") or {}
    )
    if not source_confidence:
        return _component(
            "source_confidence",
            WARNING,
            UNKNOWN,
            "No Source Confidence block was persisted for this run.",
            "Investigate missing source diagnostics.",
        )
    state = source_confidence.get("confidence_state") or "UNKNOWN"
    status = SOURCE_CONFIDENCE_STATUS.get(state, WARNING)
    confidence = UNKNOWN if state == "UNKNOWN" else HIGH
    recommendation = (
        "Investigate missing source diagnostics."
        if state == "UNKNOWN"
        else source_confidence.get("recommended_action") or NO_ACTION
    )
    return _component(
        "source_confidence",
        status,
        confidence,
        source_confidence.get("reason") or f"Source Confidence persisted {state}.",
        recommendation,
        {"confidence_state": state},
    )


def _evaluate_source_reliability(run_data, _registry):
    source_reliability = (
        ((run_data or {}).get("source_intelligence") or {}).get("source_reliability") or {}
    )
    if not source_reliability:
        return _component(
            "source_reliability",
            WARNING,
            UNKNOWN,
            "No Source Reliability block was persisted for this run.",
            "Review Source Reliability diagnostics.",
        )
    summary = source_reliability.get("summary") or {}
    stable = int(summary.get("stable_count") or 0)
    watch = int(summary.get("watch_count") or 0)
    repeated = int(summary.get("repeated_failure_count") or 0)
    quarantine = int(summary.get("quarantine_recommended_count") or 0)
    unknown = int(summary.get("unknown_count") or 0)
    total = stable + watch + repeated + quarantine + unknown
    if quarantine > 0:
        status = WARNING
        recommendation = "Review sources recommended for quarantine in Source Reliability."
    elif repeated > 0:
        status = WARNING
        recommendation = "Review sources with repeated failures in Source Reliability."
    elif watch > 0:
        status = GOOD
        recommendation = "Review sources marked WATCH in Source Reliability."
    else:
        status = EXCELLENT
        recommendation = NO_ACTION

    if total <= 0:
        confidence = UNKNOWN
    elif unknown > total / 2:
        confidence = LOW
    elif unknown > 0:
        confidence = MODERATE
    else:
        confidence = HIGH

    reason = (
        f"{stable} stable, {watch} watch, {repeated} repeated failure, "
        f"{quarantine} quarantine recommended, {unknown} unknown source(s)."
    )
    return _component(
        "source_reliability",
        status,
        confidence,
        reason,
        recommendation,
        {
            "stable_count": stable,
            "watch_count": watch,
            "repeated_failure_count": repeated,
            "quarantine_recommended_count": quarantine,
            "unknown_count": unknown,
        },
    )


def _evaluate_coverage_intelligence(run_data, _registry):
    coverage = (
        ((run_data or {}).get("source_intelligence") or {}).get("coverage_intelligence")
        or {}
    )
    if not coverage:
        return _component(
            "coverage_intelligence",
            OFFLINE,
            UNKNOWN,
            "No Coverage Intelligence block was persisted for this run.",
            "Review Coverage Intelligence diagnostics.",
        )
    per_narrative = list(coverage.get("per_narrative") or [])
    if not per_narrative:
        return _component(
            "coverage_intelligence",
            WARNING,
            LOW,
            "Coverage Intelligence persisted but no per-narrative measurements were available.",
            "Review Coverage Intelligence diagnostics.",
        )
    states = [row.get("coverage_state") or "UNKNOWN" for row in per_narrative]
    broadest = _broadest_coverage_state(states)
    return _component(
        "coverage_intelligence",
        EXCELLENT,
        HIGH,
        f"{len(per_narrative)} narratives measured; broadest at {broadest}.",
        facts={"narratives_measured": len(per_narrative), "broadest": broadest},
    )


def _evaluate_freshness_feed_health(run_data, _registry):
    source_intelligence = (run_data or {}).get("source_intelligence") or {}
    source_health = list(source_intelligence.get("source_health") or [])
    source_freshness = list(source_intelligence.get("source_freshness") or [])
    if not source_health:
        return _component(
            "freshness_feed_health",
            OFFLINE,
            UNKNOWN,
            "No source health diagnostics were persisted for this run.",
            "Review Feed Health diagnostics.",
        )
    freshness_by_source = {
        row.get("source_id"): row
        for row in source_freshness
        if isinstance(row, dict) and row.get("source_id")
    }
    degraded = []
    for health in source_health:
        source_id = health.get("source_id")
        freshness = freshness_by_source.get(source_id) or {}
        if (
            health.get("severity") not in HEALTHY_FEED_SEVERITIES
            or freshness.get("status") not in FRESH_STATUSES
        ):
            degraded.append(
                {
                    "source_name": health.get("source_name") or source_id or "Unknown source",
                    "health_state": health.get("state") or "UNKNOWN",
                    "freshness_status": freshness.get("status") or "UNKNOWN",
                }
            )
    total = len(source_health)
    degraded_count = len(degraded)
    if degraded_count == 0:
        status = EXCELLENT
        recommendation = NO_ACTION
    else:
        ratio = degraded_count / total
        if ratio > 0.5:
            status = DEGRADED
        elif ratio >= 0.25:
            status = LIMITED
        else:
            status = GOOD
        recommendation = "Review stale sources in Feed Health."
    confidence = HIGH if source_freshness else MODERATE
    if degraded:
        sample = ", ".join(
            f"{row['source_name']} ({row['health_state']}/{row['freshness_status']})"
            for row in degraded[:4]
        )
        reason = f"{degraded_count} of {total} source(s) degraded or stale: {sample}."
    else:
        reason = f"All {total} source(s) reported healthy feed health and fresh evidence."
    return _component(
        "freshness_feed_health",
        status,
        confidence,
        reason,
        recommendation,
        {"degraded_count": degraded_count, "source_count": total},
    )


def _stage_names(stages):
    return ", ".join(stage.get("stage_name") or "UNKNOWN_STAGE" for stage in stages)


def _stale_or_degraded_sources(source_health, source_freshness):
    freshness_by_source = {
        row.get("source_id"): row
        for row in source_freshness or []
        if isinstance(row, dict) and row.get("source_id")
    }
    for health in source_health or []:
        freshness = freshness_by_source.get(health.get("source_id")) or {}
        if (
            health.get("severity") not in HEALTHY_FEED_SEVERITIES
            or freshness.get("status") not in FRESH_STATUSES
        ):
            return True
    return False


def _broadest_coverage_state(states):
    order = {
        "UNKNOWN": 0,
        "MINIMAL": 1,
        "LIMITED": 2,
        "MODERATE": 3,
        "BROAD": 4,
        "EXTENSIVE": 5,
    }
    return max(states or ["UNKNOWN"], key=lambda state: order.get(state, 0))


def _dedupe(items):
    seen = set()
    deduped = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
