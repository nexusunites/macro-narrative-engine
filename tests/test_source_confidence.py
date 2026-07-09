import unittest
from copy import deepcopy

from mne.source_confidence import (
    HIGH,
    LOW,
    MODERATE,
    UNKNOWN,
    build_source_confidence,
    derive_metrics,
)
from mne.source_registry import SourceRegistry


THRESHOLDS = {
    "accepted_evidence_floor": 10,
    "low_fetch_ratio": 0.50,
    "low_contribution_ratio": 0.40,
    "high_fetch_ratio": 0.85,
    "high_freshness_ratio": 0.80,
    "high_contribution_ratio": 0.70,
}


def source(source_id, status="ACTIVE"):
    return {
        "source_id": source_id,
        "display_name": f"Source {source_id}",
        "provider": f"Provider {source_id}",
        "category": "General Business",
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


def registry(count=4):
    return SourceRegistry(
        registry_version="1.3.0",
        sources=tuple(source(f"s{index}") for index in range(1, count + 1)),
        evidence_types=({"evidence_type": "Headline", "status": "active"},),
        categories=({"category": "General Business", "description": "Business news."},),
        priority_tiers=({"tier": "TIER_1", "description": "Core sources."},),
        coverage_thresholds={},
        network_thresholds={"concentration_threshold": 0.40, "evidence_floor": 5},
        source_confidence_thresholds=THRESHOLDS,
    )


def health(source_id, state="HEALTHY"):
    severity = "INFO" if state == "HEALTHY" else "CRITICAL"
    return {
        "source_id": source_id,
        "source_name": f"Source {source_id}",
        "state": state,
        "severity": severity,
    }


def freshness(source_id, status="FRESH"):
    return {
        "source_id": source_id,
        "source_name": f"Source {source_id}",
        "status": status,
    }


def accepted_evidence(source_ids, total):
    rows = []
    for index in range(total):
        source_id = source_ids[index % len(source_ids)]
        rows.append(
            {
                "evidence_id": f"{source_id}-{index}",
                "source_id": source_id,
                "title": f"Headline {index}",
            }
        )
    return rows


def source_intelligence(
    accepted_count=12,
    contributing_source_ids=None,
    health_states=None,
    freshness_statuses=None,
    rejected_stale=0,
    rejected_duplicate=0,
    rejected_unknown_timestamp=0,
):
    contributing_source_ids = contributing_source_ids or ["s1", "s2", "s3"]
    health_states = health_states or {
        "s1": "HEALTHY",
        "s2": "HEALTHY",
        "s3": "HEALTHY",
        "s4": "HEALTHY",
    }
    freshness_statuses = freshness_statuses or {
        "s1": "FRESH",
        "s2": "FRESH",
        "s3": "FRESH",
        "s4": "QUIET",
    }
    return {
        "accepted_count": accepted_count,
        "source_health": [
            health(source_id, state) for source_id, state in health_states.items()
        ],
        "source_freshness": [
            freshness(source_id, status)
            for source_id, status in freshness_statuses.items()
        ],
        "accepted_evidence": accepted_evidence(contributing_source_ids, accepted_count),
        "evidence_funnel": {
            "fetched": accepted_count + rejected_stale + rejected_duplicate + rejected_unknown_timestamp,
            "accepted_fresh": accepted_count,
            "rejected_stale": rejected_stale,
            "rejected_duplicate": rejected_duplicate,
            "rejected_unknown_timestamp": rejected_unknown_timestamp,
            "analyzer_input_count": accepted_count,
        },
    }


class SourceConfidenceTests(unittest.TestCase):
    def test_high_confidence_fixture(self):
        block = build_source_confidence(registry(), source_intelligence())

        self.assertEqual(block["confidence_state"], HIGH)
        self.assertIn("4 of 4 active sources", block["reason"])
        self.assertIn("Fetch success ratio: 4/4 = 1.00", block["contributing_factors"])
        self.assertEqual(block["recommended_action"], "No action needed.")
        self.assertEqual(block["thresholds_used"], THRESHOLDS)
        self.assertIsNone(block["confidence_level"])

    def test_moderate_confidence_fixture_for_fetch_ratio(self):
        block = build_source_confidence(
            registry(),
            source_intelligence(
                health_states={
                    "s1": "HEALTHY",
                    "s2": "HEALTHY",
                    "s3": "HEALTHY",
                    "s4": "OFFLINE",
                }
            ),
        )

        self.assertEqual(block["confidence_state"], MODERATE)
        self.assertIn("3 of 4 active sources", block["reason"])
        self.assertEqual(
            block["recommended_action"],
            "Review weakened sources in Feed Health diagnostics.",
        )

    def test_low_confidence_fixture_for_accepted_floor(self):
        block = build_source_confidence(registry(), source_intelligence(accepted_count=9))

        self.assertEqual(block["confidence_state"], LOW)
        self.assertIn("Only 9 accepted evidence objects", block["reason"])
        self.assertEqual(
            block["recommended_action"],
            "Review evidence collection volume before relying on this run.",
        )

    def test_unknown_requires_missing_diagnostics_not_bad_numbers(self):
        missing = source_intelligence()
        del missing["source_health"]
        unknown_block = build_source_confidence(registry(), missing)

        bad_numbers = source_intelligence(
            accepted_count=0,
            contributing_source_ids=["s1"],
            health_states={
                "s1": "BLOCKED",
                "s2": "BLOCKED",
                "s3": "BLOCKED",
                "s4": "BLOCKED",
            },
        )
        low_block = build_source_confidence(registry(), bad_numbers)

        self.assertEqual(unknown_block["confidence_state"], UNKNOWN)
        self.assertIn("Missing required diagnostic: source_health", unknown_block["contributing_factors"])
        self.assertEqual(low_block["confidence_state"], LOW)

    def test_stale_heavy_run_depresses_freshness_ratio_but_duplicates_do_not(self):
        stale_heavy = build_source_confidence(
            registry(),
            source_intelligence(rejected_stale=5),
        )
        duplicate_heavy = build_source_confidence(
            registry(),
            source_intelligence(rejected_duplicate=20),
        )
        duplicate_metrics = derive_metrics(registry(), source_intelligence(rejected_duplicate=20))

        self.assertEqual(stale_heavy["confidence_state"], MODERATE)
        self.assertIn("71% of freshness-evaluated", stale_heavy["reason"])
        self.assertEqual(duplicate_heavy["confidence_state"], HIGH)
        self.assertEqual(duplicate_metrics["freshness_ratio"], 1.0)

    def test_blocked_source_heavy_run_names_blocked_sources(self):
        block = build_source_confidence(
            registry(),
            source_intelligence(
                contributing_source_ids=["s1"],
                health_states={
                    "s1": "HEALTHY",
                    "s2": "BLOCKED",
                    "s3": "BLOCKED",
                    "s4": "BLOCKED",
                },
            ),
        )

        self.assertEqual(block["confidence_state"], LOW)
        self.assertIn("Source s2: BLOCKED", block["contributing_factors"])
        self.assertIn("Source s3: BLOCKED", block["contributing_factors"])
        self.assertIn("Source s4: BLOCKED", block["contributing_factors"])

    def test_accepted_evidence_thin_run_forces_low_with_healthy_ratios(self):
        block = build_source_confidence(
            registry(),
            source_intelligence(
                accepted_count=9,
                contributing_source_ids=["s1", "s2", "s3", "s4"],
            ),
        )

        self.assertEqual(block["confidence_state"], LOW)
        self.assertIn("Accepted evidence count: 9 (floor 10)", block["contributing_factors"])

    def test_threshold_boundaries_are_strictly_less_than(self):
        exactly_high_fetch = build_source_confidence(
            registry(count=20),
            source_intelligence(
                accepted_count=20,
                contributing_source_ids=[f"s{index}" for index in range(1, 15)],
                health_states={
                    f"s{index}": "HEALTHY" if index <= 17 else "OFFLINE"
                    for index in range(1, 21)
                },
                freshness_statuses={f"s{index}": "FRESH" for index in range(1, 21)},
            ),
        )
        just_below_high_fetch = build_source_confidence(
            registry(count=20),
            source_intelligence(
                accepted_count=20,
                contributing_source_ids=[f"s{index}" for index in range(1, 14)],
                health_states={
                    f"s{index}": "HEALTHY" if index <= 16 else "OFFLINE"
                    for index in range(1, 21)
                },
                freshness_statuses={f"s{index}": "FRESH" for index in range(1, 21)},
            ),
        )

        self.assertEqual(exactly_high_fetch["confidence_state"], HIGH)
        self.assertEqual(just_below_high_fetch["confidence_state"], MODERATE)

    def test_building_confidence_does_not_mutate_source_intelligence(self):
        diagnostics = source_intelligence()
        before = deepcopy(diagnostics)

        build_source_confidence(registry(), diagnostics)

        self.assertEqual(diagnostics, before)


if __name__ == "__main__":
    unittest.main()
