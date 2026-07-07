import unittest

from mne.coverage_intelligence import (
    accepted_deduped_evidence,
    assign_coverage_state,
    build_coverage_intelligence,
)
from mne.evidence import EvidenceObject
from mne.source_registry import SourceRegistry


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


if __name__ == "__main__":
    unittest.main()
