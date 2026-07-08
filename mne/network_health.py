from collections import Counter

from mne.freshness import FRESH


PROVIDER_STATES = ("HEALTHY", "PARTIAL", "DEGRADED", "OFFLINE")
CATEGORY_STATES = ("HEALTHY", "PARTIAL", "DEGRADED", "OFFLINE", "UNCOVERED")
NETWORK_HEALTHY = "NETWORK_HEALTHY"
NETWORK_PARTIAL = "NETWORK_PARTIAL"
NETWORK_DEGRADED = "NETWORK_DEGRADED"
NETWORK_CRITICAL = "NETWORK_CRITICAL"


def build_network_health(registry, source_health, source_freshness, accepted_evidence):
    thresholds = registry.network_thresholds
    providers = provider_rollups(
        registry,
        source_health,
        source_freshness,
        accepted_evidence,
    )
    categories = category_rollups(
        registry,
        source_health,
        source_freshness,
        accepted_evidence,
    )
    concentration = provider_concentration(
        accepted_evidence,
        registry,
        thresholds["concentration_threshold"],
    )
    return {
        "network_status": evaluate_network_status(
            categories,
            concentration,
            thresholds["evidence_floor"],
        ),
        "providers": providers,
        "categories": categories,
        "concentration": concentration,
        "thresholds_used": {
            "concentration_threshold": thresholds["concentration_threshold"],
            "evidence_floor": thresholds["evidence_floor"],
        },
    }


def provider_rollups(registry, source_health, source_freshness, accepted_evidence):
    health_by_source_id = _index_by_source_id(source_health)
    freshness_by_source_id = _index_by_source_id(source_freshness)
    evidence_by_provider = _evidence_counts_by_provider(accepted_evidence, registry)
    by_provider = {}

    for source in registry.active_sources:
        by_provider.setdefault(source["provider"], []).append(source)

    rows = []
    for provider, sources in sorted(by_provider.items()):
        healthy_count = sum(
            1
            for source in sources
            if _source_is_healthy(source["source_id"], health_by_source_id, freshness_by_source_id)
        )
        evidence_count = evidence_by_provider.get(provider, 0)
        rows.append(
            {
                "provider": provider,
                "sources_total": len(sources),
                "sources_healthy": healthy_count,
                "sources_degraded": len(sources) - healthy_count,
                "evidence_contributed": evidence_count,
                "provider_state": provider_state(
                    len(sources),
                    healthy_count,
                    evidence_count,
                ),
            }
        )
    return rows


def category_rollups(registry, source_health, source_freshness, accepted_evidence):
    health_by_source_id = _index_by_source_id(source_health)
    freshness_by_source_id = _index_by_source_id(source_freshness)
    evidence_by_source = _evidence_counts_by_source(accepted_evidence)
    rows = []

    for category in _registry_category_names(registry):
        sources = [
            source
            for source in registry.active_sources
            if source["category"] == category
        ]
        healthy_sources = [
            source
            for source in sources
            if _source_is_healthy(source["source_id"], health_by_source_id, freshness_by_source_id)
        ]
        evidence_count = sum(
            evidence_by_source.get(source["source_id"], 0)
            for source in sources
        )
        contributing_healthy_providers = {
            source["provider"]
            for source in healthy_sources
            if evidence_by_source.get(source["source_id"], 0) > 0
        }
        providers_total = len({source["provider"] for source in sources})
        providers_healthy = len(contributing_healthy_providers)

        rows.append(
            {
                "category": category,
                "providers_total": providers_total,
                "providers_healthy": providers_healthy,
                "sources_total": len(sources),
                "sources_healthy": len(healthy_sources),
                "evidence_contributed": evidence_count,
                "single_provider_dependency": providers_healthy == 1,
                "category_state": category_state(
                    len(sources),
                    len(healthy_sources),
                    evidence_count,
                    providers_healthy,
                ),
            }
        )
    return rows


def provider_concentration(accepted_evidence, registry, concentration_threshold):
    provider_counts = _evidence_counts_by_provider(accepted_evidence, registry)
    total = sum(provider_counts.values())
    provider_shares = []

    for provider, count in provider_counts.items():
        provider_shares.append(
            {
                "provider": provider,
                "evidence_count": count,
                "share": round(count / total, 2) if total else 0,
            }
        )
    provider_shares = sorted(
        provider_shares,
        key=lambda item: (-item["share"], item["provider"]),
    )
    top = provider_shares[0] if provider_shares and total else None

    return {
        "total_accepted_evidence": total,
        "provider_shares": provider_shares,
        "top_provider": top["provider"] if top else None,
        "top_provider_share": top["share"] if top else None,
        "concentration_flag": bool(
            top and top["share"] > concentration_threshold
        ),
    }


def evaluate_network_status(categories, concentration, evidence_floor):
    covered = [
        category
        for category in categories
        if category.get("category_state") != "UNCOVERED"
    ]
    total_accepted = concentration.get("total_accepted_evidence") or 0

    if total_accepted < evidence_floor or any(
        category.get("category_state") == "OFFLINE" for category in covered
    ):
        return NETWORK_CRITICAL

    degraded_or_offline = sum(
        1
        for category in covered
        if category.get("category_state") in {"DEGRADED", "OFFLINE"}
    )
    has_dependency = any(
        category.get("single_provider_dependency") for category in covered
    )
    concentration_flag = bool(concentration.get("concentration_flag"))

    if (
        covered
        and degraded_or_offline > len(covered) / 2
    ) or (concentration_flag and has_dependency):
        return NETWORK_DEGRADED

    if degraded_or_offline or has_dependency or concentration_flag:
        return NETWORK_PARTIAL

    return NETWORK_HEALTHY


def provider_state(sources_total, sources_healthy, evidence_contributed):
    if sources_healthy == 0 and evidence_contributed == 0:
        return "OFFLINE"
    if sources_healthy == sources_total and evidence_contributed > 0:
        return "HEALTHY"
    if sources_healthy > 0 and evidence_contributed > 0:
        return "PARTIAL"
    return "DEGRADED"


def category_state(sources_total, sources_healthy, evidence_contributed, providers_healthy):
    if sources_total == 0:
        return "UNCOVERED"
    if sources_healthy == 0 and evidence_contributed == 0:
        return "OFFLINE"
    if sources_healthy == sources_total and evidence_contributed > 0:
        return "HEALTHY"
    if providers_healthy > 0:
        return "PARTIAL"
    return "DEGRADED"


def _index_by_source_id(rows):
    return {
        row.get("source_id"): row
        for row in rows or []
        if isinstance(row, dict) and row.get("source_id")
    }


def _source_is_healthy(source_id, health_by_source_id, freshness_by_source_id):
    health = health_by_source_id.get(source_id) or {}
    freshness = freshness_by_source_id.get(source_id) or {}
    return health.get("severity") == "INFO" and freshness.get("status") == FRESH


def _evidence_counts_by_source(accepted_evidence):
    return Counter(
        row.get("source_id")
        for row in accepted_evidence or []
        if isinstance(row, dict) and row.get("source_id")
    )


def _evidence_counts_by_provider(accepted_evidence, registry):
    counts = Counter()
    for source_id, count in _evidence_counts_by_source(accepted_evidence).items():
        source = registry.source_by_id(source_id)
        counts[source["provider"]] += count
    return counts


def _registry_category_names(registry):
    return [
        category["category"]
        for category in registry.categories
        if isinstance(category, dict) and category.get("category")
    ]
