import unittest

from mne.network_health import (
    build_network_health,
    category_rollups,
    evaluate_network_status,
    provider_concentration,
    provider_rollups,
)
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


def source(
    source_id,
    provider,
    category="General Business",
    status="ACTIVE",
):
    return {
        "source_id": source_id,
        "display_name": f"Source {source_id}",
        "provider": provider,
        "category": category,
        "priority": "TIER_1",
        "ingestion_type": "RSS",
        "supported_evidence_types": ["Headline"],
        "url": f"https://example.com/{source_id}.xml",
        "status": status,
        "freshness_threshold_minutes": 120,
        "expected_update_frequency_minutes": 60,
        "supported_narratives": ["Macro"],
        "supported_groups": ["Macro"],
        "notes": None,
    }


def registry(sources, categories=None, network_thresholds=None):
    category_names = categories or sorted({item["category"] for item in sources})
    return SourceRegistry(
        registry_version="1.2.0",
        sources=tuple(sources),
        evidence_types=({"evidence_type": "Headline", "status": "active"},),
        categories=tuple(
            {"category": category, "description": f"{category} sources."}
            for category in category_names
        ),
        priority_tiers=({"tier": "TIER_1", "description": "Core sources."},),
        coverage_thresholds=THRESHOLDS,
        network_thresholds=network_thresholds
        or {"concentration_threshold": 0.40, "evidence_floor": 5},
    )


def health(source_id, severity="INFO"):
    return {
        "source_id": source_id,
        "source_name": f"Source {source_id}",
        "state": "HEALTHY" if severity == "INFO" else "EMPTY",
        "severity": severity,
    }


def freshness(source_id, status="FRESH"):
    return {
        "source_id": source_id,
        "source_name": f"Source {source_id}",
        "status": status,
    }


def evidence(source_id, count):
    return [
        {
            "evidence_id": f"{source_id}-{index}",
            "source_id": source_id,
            "title": f"{source_id} headline {index}",
        }
        for index in range(count)
    ]


class NetworkHealthTests(unittest.TestCase):
    def test_provider_rollups_cover_all_states(self):
        reg = registry(
            [
                source("healthy-a", "Healthy Provider"),
                source("partial-a", "Partial Provider"),
                source("partial-b", "Partial Provider"),
                source("degraded-a", "Degraded Provider"),
                source("offline-a", "Offline Provider"),
            ]
        )
        rows = {
            row["provider"]: row
            for row in provider_rollups(
                reg,
                [
                    health("healthy-a"),
                    health("partial-a"),
                    health("partial-b", "WARNING"),
                    health("degraded-a"),
                    health("offline-a", "CRITICAL"),
                ],
                [
                    freshness("healthy-a"),
                    freshness("partial-a"),
                    freshness("partial-b", "STALE"),
                    freshness("degraded-a"),
                    freshness("offline-a", "UNKNOWN"),
                ],
                [
                    *evidence("healthy-a", 2),
                    *evidence("partial-a", 1),
                ],
            )
        }

        self.assertEqual(rows["Healthy Provider"]["provider_state"], "HEALTHY")
        self.assertEqual(rows["Partial Provider"]["provider_state"], "PARTIAL")
        self.assertEqual(rows["Degraded Provider"]["provider_state"], "DEGRADED")
        self.assertEqual(rows["Offline Provider"]["provider_state"], "OFFLINE")
        self.assertEqual(rows["Partial Provider"]["sources_healthy"], 1)
        self.assertEqual(rows["Partial Provider"]["sources_degraded"], 1)

    def test_category_rollups_cover_states_and_dependency_distinction(self):
        reg = registry(
            [
                source("healthy-a", "Provider A", "Healthy Cat"),
                source("healthy-b", "Provider B", "Healthy Cat"),
                source("partial-a", "Provider A", "Partial Cat"),
                source("partial-b", "Provider B", "Partial Cat"),
                source("degraded-a", "Provider A", "Degraded Cat"),
                source("offline-a", "Provider A", "Offline Cat"),
            ],
            categories=[
                "Healthy Cat",
                "Partial Cat",
                "Degraded Cat",
                "Offline Cat",
                "Uncovered Cat",
            ],
        )
        rows = {
            row["category"]: row
            for row in category_rollups(
                reg,
                [
                    health("healthy-a"),
                    health("healthy-b"),
                    health("partial-a"),
                    health("partial-b", "WARNING"),
                    health("degraded-a"),
                    health("offline-a", "CRITICAL"),
                ],
                [
                    freshness("healthy-a"),
                    freshness("healthy-b"),
                    freshness("partial-a"),
                    freshness("partial-b", "STALE"),
                    freshness("degraded-a"),
                    freshness("offline-a", "UNKNOWN"),
                ],
                [
                    *evidence("healthy-a", 1),
                    *evidence("healthy-b", 1),
                    *evidence("partial-a", 1),
                ],
            )
        }

        self.assertEqual(rows["Healthy Cat"]["category_state"], "HEALTHY")
        self.assertFalse(rows["Healthy Cat"]["single_provider_dependency"])
        self.assertEqual(rows["Partial Cat"]["category_state"], "PARTIAL")
        self.assertTrue(rows["Partial Cat"]["single_provider_dependency"])
        self.assertEqual(rows["Degraded Cat"]["category_state"], "DEGRADED")
        self.assertFalse(rows["Degraded Cat"]["single_provider_dependency"])
        self.assertEqual(rows["Offline Cat"]["category_state"], "OFFLINE")
        self.assertEqual(rows["Uncovered Cat"]["category_state"], "UNCOVERED")
        self.assertEqual(rows["Uncovered Cat"]["sources_total"], 0)

    def test_provider_concentration_rounding_sorting_and_flags(self):
        reg = registry(
            [
                source("a", "Provider A"),
                source("b", "Provider B"),
                source("c", "Provider C"),
            ]
        )

        below = provider_concentration(
            [*evidence("a", 26), *evidence("b", 20), *evidence("c", 20)],
            reg,
            0.40,
        )
        above = provider_concentration(
            [*evidence("a", 27), *evidence("b", 20), *evidence("c", 19)],
            reg,
            0.40,
        )
        tie = provider_concentration(
            [*evidence("b", 2), *evidence("a", 2)],
            reg,
            0.40,
        )
        zero = provider_concentration([], reg, 0.40)

        self.assertEqual(below["top_provider_share"], 0.39)
        self.assertFalse(below["concentration_flag"])
        self.assertEqual(above["top_provider_share"], 0.41)
        self.assertTrue(above["concentration_flag"])
        self.assertEqual([row["provider"] for row in tie["provider_shares"]], ["Provider A", "Provider B"])
        self.assertIsNone(zero["top_provider"])
        self.assertIsNone(zero["top_provider_share"])

    def test_overall_network_status_rule_table(self):
        concentration = {
            "total_accepted_evidence": 10,
            "concentration_flag": False,
        }
        healthy_categories = [
            {"category_state": "HEALTHY", "single_provider_dependency": False},
            {"category_state": "HEALTHY", "single_provider_dependency": False},
        ]

        self.assertEqual(
            evaluate_network_status(healthy_categories, concentration, 5),
            "NETWORK_HEALTHY",
        )
        self.assertEqual(
            evaluate_network_status(healthy_categories, {"total_accepted_evidence": 4}, 5),
            "NETWORK_CRITICAL",
        )
        self.assertEqual(
            evaluate_network_status(
                [{"category_state": "OFFLINE", "single_provider_dependency": False}],
                concentration,
                5,
            ),
            "NETWORK_CRITICAL",
        )
        self.assertEqual(
            evaluate_network_status(
                [
                    {"category_state": "DEGRADED", "single_provider_dependency": False},
                    {"category_state": "DEGRADED", "single_provider_dependency": False},
                    {"category_state": "HEALTHY", "single_provider_dependency": False},
                ],
                concentration,
                5,
            ),
            "NETWORK_DEGRADED",
        )
        self.assertEqual(
            evaluate_network_status(
                [{"category_state": "HEALTHY", "single_provider_dependency": True}],
                {"total_accepted_evidence": 10, "concentration_flag": True},
                5,
            ),
            "NETWORK_DEGRADED",
        )
        self.assertEqual(
            evaluate_network_status(
                [{"category_state": "HEALTHY", "single_provider_dependency": True}],
                concentration,
                5,
            ),
            "NETWORK_PARTIAL",
        )

    def test_build_network_health_persists_thresholds_and_reconciles_totals(self):
        reg = registry([source("a", "Provider A"), source("b", "Provider B")])
        block = build_network_health(
            reg,
            [health("a"), health("b")],
            [freshness("a"), freshness("b")],
            [*evidence("a", 3), *evidence("b", 2)],
        )

        self.assertEqual(
            block["thresholds_used"],
            {"concentration_threshold": 0.40, "evidence_floor": 5},
        )
        self.assertEqual(
            sum(row["evidence_contributed"] for row in block["providers"]),
            block["concentration"]["total_accepted_evidence"],
        )
        self.assertEqual(block["concentration"]["total_accepted_evidence"], 5)


if __name__ == "__main__":
    unittest.main()
