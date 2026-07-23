import unittest

from mne.coverage_intelligence import (
    accepted_deduped_evidence,
    assign_breadth_state,
    assign_coverage_state,
    build_coverage_intelligence,
    build_coverage_source_records,
    build_historical_coverage_limitations,
    build_historical_source_record_from_evidence,
    build_replay_coverage_intelligence,
    partition_evidence_by_origin,
)
from mne.evidence import EvidenceObject
from mne.source_registry import SourceRegistry, SourceRegistryError


THRESHOLDS = {
    "LIMITED": {
        "min_evidence_count": 2,
        "max_evidence_count": 4,
        "min_unique_source_count": 2,
        "min_unique_provider_count": 0,
    },
    "MODERATE": {
        "min_evidence_count": 5,
        "max_evidence_count": 9,
        "min_unique_source_count": 3,
        "min_unique_provider_count": 2,
    },
    "BROAD": {
        "min_evidence_count": 10,
        "max_evidence_count": 19,
        "min_unique_source_count": 5,
        "min_unique_provider_count": 3,
    },
    "EXTENSIVE": {
        "min_evidence_count": 20,
        "max_evidence_count": None,
        "min_unique_source_count": 7,
        "min_unique_provider_count": 4,
    },
}


def make_registry():
    sources = []
    providers = {
        "s1": "Shared Provider",
        "s2": "Shared Provider",
        "s3": "Provider 3",
        "s4": "Provider 4",
        "s5": "Provider 5",
        "s6": "Provider 6",
        "s7": "Provider 7",
    }
    for source_id, provider in providers.items():
        sources.append(
            {
                "source_id": source_id,
                "display_name": f"Source {source_id}",
                "provider": provider,
                "category": "General Business",
                "priority": "TIER_1",
                "ingestion_type": "RSS",
                "supported_evidence_types": ["Headline"],
                "url": f"https://example.com/{source_id}.xml",
                "status": "ACTIVE",
                "freshness_threshold_minutes": 120,
                "expected_update_frequency_minutes": 60,
                "supported_narratives": ["ai", "rates"],
                "supported_groups": ["AI / Tech Growth", "Macro Pressure"],
                "notes": None,
            }
        )
    return SourceRegistry(
        registry_version="1.0.0",
        sources=tuple(sources),
        evidence_types=({"evidence_type": "Headline", "status": "active"},),
        categories=({"category": "General Business", "description": "Business news."},),
        priority_tiers=({"tier": "TIER_1", "description": "Core sources."},),
        coverage_thresholds=THRESHOLDS,
    )


def make_live_row(evidence_id, source_id, provider=None):
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "provider": provider,
        "accepted": True,
    }


def make_historical_row(evidence_id, source_id, provider, category, backfill_id="backfill_1"):
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "provider": provider,
        "category": category,
        "connector_source_id": source_id,
        "evidence_origin": "HISTORICAL_BACKFILL",
        "backfill_id": backfill_id,
        "accepted": True,
    }


def make_evidence(index, source_id="s1", accepted=True, rejection_reason=None, title=None):
    return EvidenceObject(
        evidence_id=f"e{index}",
        source_id=source_id,
        source_name=f"Source {source_id}",
        evidence_type="Headline",
        timestamp="2026-07-06T12:00:00+00:00",
        title=title or f"AI headline {index}",
        summary=None,
        url=f"https://example.com/{index}",
        accepted=accepted,
        rejection_reason=rejection_reason,
        freshness_state="FRESH" if accepted else "STALE",
    )


class CoverageIntelligenceTests(unittest.TestCase):
    def test_accepted_deduped_evidence_excludes_rejected_and_headline_duplicates(self):
        evidence = [
            make_evidence(1, "s1", title="AI growth accelerates"),
            make_evidence(2, "s2", accepted=False, rejection_reason="duplicate"),
            make_evidence(3, "s3", accepted=False, rejection_reason="stale"),
            make_evidence(4, "s4", accepted=False, rejection_reason="unknown_timestamp"),
            make_evidence(5, "s2", title="ai growth accelerates!"),
            make_evidence(6, "s2", title="Rates move higher"),
        ]

        selected = accepted_deduped_evidence(evidence)

        self.assertEqual([item.evidence_id for item in selected], ["e1", "e6"])

    def test_provider_diversity_counts_shared_provider_once(self):
        registry = make_registry()
        evidence = [
            make_evidence(1, "s1"),
            make_evidence(2, "s2"),
        ]
        coverage = build_coverage_intelligence(
            evidence,
            [{"themes": ["ai"]}, {"themes": ["ai"]}],
            registry,
        )

        ai = coverage["per_narrative"][0]
        self.assertEqual(ai["narrative_level"], "group")
        theme = [item for item in coverage["per_narrative"] if item["narrative_level"] == "theme"][0]
        self.assertEqual(theme["unique_source_count"], 2)
        self.assertEqual(theme["unique_provider_count"], 1)
        self.assertEqual(theme["provider_list"], ["Shared Provider"])

    def test_concentration_ratio_and_breakdown_are_deterministic(self):
        registry = make_registry()
        evidence = [
            *[make_evidence(index, "s1") for index in range(1, 15)],
            *[make_evidence(index, "s2") for index in range(15, 20)],
        ]
        coverage = build_coverage_intelligence(
            evidence,
            [{"themes": ["ai"]} for _ in evidence],
            registry,
        )

        theme = [item for item in coverage["per_narrative"] if item["narrative_level"] == "theme"][0]
        self.assertEqual(theme["evidence_count"], 19)
        self.assertEqual(theme["concentration_ratio"], 0.74)
        self.assertEqual(theme["source_contribution_breakdown"][0]["source_id"], "s1")
        self.assertEqual(sum(row["evidence_count"] for row in theme["source_contribution_breakdown"]), 19)

    def test_coverage_state_thresholds(self):
        cases = [
            (1, 1, 1, "MINIMAL"),
            (4, 2, 1, "LIMITED"),
            (9, 3, 2, "MODERATE"),
            (19, 5, 3, "BROAD"),
            (20, 7, 4, "EXTENSIVE"),
        ]

        for evidence_count, source_count, provider_count, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    assign_coverage_state(
                        evidence_count,
                        source_count,
                        provider_count,
                        THRESHOLDS,
                    ),
                    expected,
                )

    def test_group_coverage_uses_union_of_attributed_theme_evidence(self):
        registry = make_registry()
        evidence = [
            make_evidence(1, "s1"),
            make_evidence(2, "s2"),
            make_evidence(3, "s3"),
        ]
        coverage = build_coverage_intelligence(
            evidence,
            [{"themes": ["ai"]}, {"themes": ["semiconductors"]}, {"themes": ["rates"]}],
            registry,
        )

        records = {
            (item["narrative_level"], item["narrative_id"]): item
            for item in coverage["per_narrative"]
        }
        self.assertEqual(records[("group", "AI / Tech Growth")]["evidence_count"], 2)
        self.assertEqual(records[("group", "Macro Pressure")]["evidence_count"], 1)
        self.assertEqual(records[("theme", "ai")]["evidence_count"], 1)

    def test_overall_summary_reconciles_with_per_narrative_records(self):
        registry = make_registry()
        evidence = [
            make_evidence(1, "s1"),
            make_evidence(2, "s2"),
            make_evidence(3, "s3"),
        ]
        coverage = build_coverage_intelligence(
            evidence,
            [{"themes": ["ai"]}, {"themes": ["ai"]}, {"themes": ["rates"]}],
            registry,
        )

        self.assertEqual(
            coverage["overall"]["source_diversity"]["unique_source_count"],
            3,
        )
        self.assertEqual(
            coverage["overall"]["provider_diversity"]["provider_list"],
            ["Provider 3", "Shared Provider"],
        )
        summary_total = sum(coverage["overall"]["coverage_summary"].values())
        self.assertEqual(summary_total, len(coverage["per_narrative"]))

    def test_partition_evidence_by_origin_splits_on_evidence_origin_key(self):
        rows = [
            make_live_row("e1", "s1", "Shared Provider"),
            make_historical_row("e2", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
        ]
        live_rows, historical_rows = partition_evidence_by_origin(rows)
        self.assertEqual([row["evidence_id"] for row in live_rows], ["e1"])
        self.assertEqual([row["evidence_id"] for row in historical_rows], ["e2"])

    def test_build_historical_source_record_from_evidence_uses_persisted_fields_only(self):
        row = make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications")
        record = build_historical_source_record_from_evidence(row)
        self.assertEqual(record["source_id"], "fed_fomc")
        self.assertEqual(record["provider"], "Federal Reserve")
        self.assertEqual(record["category"], "Central Bank Communications")
        self.assertEqual(record["connector_source_id"], "fed_fomc")
        self.assertEqual(record["backfill_id"], "backfill_1")

    def test_build_coverage_source_records_accepts_historical_source_without_registry_membership(self):
        registry = make_registry()
        rows = [make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications")]
        with self.assertRaises(SourceRegistryError):
            registry.source_by_id("fed_fomc")
        records = build_coverage_source_records(rows, registry)
        self.assertEqual(records[0]["source_id"], "fed_fomc")
        self.assertEqual(records[0]["origin"], "historical_backfill")

    def test_build_coverage_source_records_resolves_live_rows_via_registry(self):
        registry = make_registry()
        rows = [make_live_row("e1", "s1")]
        records = build_coverage_source_records(rows, registry)
        self.assertEqual(records[0]["provider"], "Shared Provider")
        self.assertEqual(records[0]["category"], "General Business")
        self.assertEqual(records[0]["origin"], "live_persisted")

    def test_build_replay_coverage_intelligence_historical_only_reconciles_counts(self):
        registry = make_registry()
        rows = [
            make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
            make_historical_row("e2", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
            make_historical_row("e3", "bls_cpi", "BLS", "Inflation / Economic Data"),
        ]
        coverage = build_replay_coverage_intelligence(rows, registry)
        self.assertEqual(coverage["accepted_evidence_count"], 3)
        self.assertEqual(coverage["contributing_source_count"], 2)
        self.assertEqual(coverage["contributing_provider_count"], 2)
        self.assertEqual(coverage["contributing_category_count"], 2)
        self.assertEqual(coverage["evidence_count_by_source"], {"bls_cpi": 1, "fed_fomc": 2})
        self.assertEqual(sum(coverage["evidence_count_by_source"].values()), coverage["accepted_evidence_count"])
        self.assertEqual(sum(coverage["evidence_count_by_provider"].values()), coverage["accepted_evidence_count"])
        self.assertEqual(sum(coverage["evidence_count_by_category"].values()), coverage["accepted_evidence_count"])
        self.assertEqual(coverage["evidence_origins_used"], ["historical_backfill"])

    def test_build_replay_coverage_intelligence_reconciles_fed_fomc_bls_cpi_bea_gdp_pce_eia_energy(self):
        registry = make_registry()
        rows = [
            make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
            make_historical_row("e2", "bls_cpi", "BLS", "Inflation / Economic Data"),
            make_historical_row("e3", "bea_gdp_pce", "BEA", "Economic Data / Growth / Inflation"),
            make_historical_row("e4", "eia_energy", "EIA", "Energy / Commodities"),
        ]
        coverage = build_replay_coverage_intelligence(rows, registry)
        self.assertEqual(coverage["evidence_count_by_source"]["fed_fomc"], 1)
        self.assertEqual(coverage["evidence_count_by_source"]["bls_cpi"], 1)
        self.assertEqual(coverage["evidence_count_by_source"]["bea_gdp_pce"], 1)
        self.assertEqual(coverage["evidence_count_by_source"]["eia_energy"], 1)
        self.assertEqual(coverage["contributing_source_count"], 4)
        self.assertEqual(coverage["breadth_state"], "BROAD")

    def test_build_replay_coverage_intelligence_mixed_live_and_historical_reconciles(self):
        registry = make_registry()
        rows = [
            make_live_row("e1", "s1"),
            make_live_row("e2", "s2"),
            make_historical_row("e3", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
        ]
        coverage = build_replay_coverage_intelligence(rows, registry)
        self.assertEqual(coverage["accepted_evidence_count"], 3)
        self.assertEqual(coverage["contributing_source_count"], 3)
        self.assertEqual(sorted(coverage["evidence_origins_used"]), ["historical_backfill", "live_persisted"])
        self.assertEqual(
            sum(coverage["evidence_count_by_source"].values()),
            coverage["accepted_evidence_count"],
        )

    def test_concentration_metrics_are_deterministic(self):
        registry = make_registry()
        rows = [
            make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
            make_historical_row("e2", "fed_fomc", "Federal Reserve", "Central Bank Communications"),
            make_historical_row("e3", "bls_cpi", "BLS", "Inflation / Economic Data"),
        ]
        first = build_replay_coverage_intelligence(rows, registry)
        second = build_replay_coverage_intelligence(list(reversed(rows)), registry)
        self.assertEqual(first["source_concentration"], round(2 / 3, 2))
        self.assertEqual(first["provider_concentration"], round(2 / 3, 2))
        self.assertEqual(first["category_concentration"], round(2 / 3, 2))
        self.assertEqual(first["source_concentration"], second["source_concentration"])
        self.assertEqual(first["evidence_count_by_source"], second["evidence_count_by_source"])

    def test_breadth_state_fixtures(self):
        registry = make_registry()
        cases = [
            (0, "UNKNOWN"),
            (1, "MINIMAL"),
            (2, "LIMITED"),
            (3, "MODERATE"),
            (4, "BROAD"),
        ]
        sources = [
            ("fed_fomc", "Federal Reserve", "Central Bank Communications"),
            ("bls_cpi", "BLS", "Inflation / Economic Data"),
            ("bea_gdp_pce", "BEA", "Economic Data / Growth / Inflation"),
            ("eia_energy", "EIA", "Energy / Commodities"),
        ]
        for source_count, expected_state in cases:
            with self.subTest(expected=expected_state):
                rows = [
                    make_historical_row(f"e{index}", *sources[index])
                    for index in range(source_count)
                ]
                coverage = build_replay_coverage_intelligence(rows, registry)
                self.assertEqual(coverage["breadth_state"], expected_state)

    def test_assign_breadth_state_matches_named_thresholds(self):
        self.assertEqual(assign_breadth_state(0, 0), "UNKNOWN")
        self.assertEqual(assign_breadth_state(1, 1), "MINIMAL")
        self.assertEqual(assign_breadth_state(2, 2), "LIMITED")
        self.assertEqual(assign_breadth_state(3, 3), "MODERATE")
        self.assertEqual(assign_breadth_state(4, 3), "BROAD")
        # Four sources but insufficient category diversity does not qualify as BROAD.
        self.assertEqual(assign_breadth_state(4, 1), "MODERATE")

    def test_historical_limitations_copy_present_and_no_complete_coverage_claim(self):
        limitations = build_historical_coverage_limitations(["historical_backfill"])
        self.assertIn("Historical coverage reflects supported backfill sources only.", limitations)
        self.assertIn("This is not complete historical market-news coverage.", limitations)
        self.assertIn("Coverage breadth is measured within the evidence available to this replay.", limitations)
        for message in limitations:
            if "complete" in message.lower():
                self.assertIn("not", message.lower())

    def test_historical_limitations_note_mixed_origins_when_both_present(self):
        historical_only = build_historical_coverage_limitations(["historical_backfill"])
        mixed = build_historical_coverage_limitations(["historical_backfill", "live_persisted"])
        self.assertEqual(len(mixed), len(historical_only) + 1)

    def test_live_source_registry_untouched_by_historical_evidence(self):
        registry = make_registry()
        source_ids_before = {source["source_id"] for source in registry.sources}
        rows = [make_historical_row("e1", "fed_fomc", "Federal Reserve", "Central Bank Communications")]
        build_replay_coverage_intelligence(rows, registry)
        source_ids_after = {source["source_id"] for source in registry.sources}
        self.assertEqual(source_ids_before, source_ids_after)
        self.assertNotIn("fed_fomc", source_ids_after)


if __name__ == "__main__":
    unittest.main()
