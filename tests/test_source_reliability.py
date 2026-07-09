import json
import tempfile
import unittest
from pathlib import Path

from mne.source_registry import SourceRegistry, load_source_registry
from mne.source_reliability import (
    QUARANTINE_RECOMMENDED,
    REPEATED_FAILURE,
    STABLE,
    UNKNOWN_STATE,
    WATCH,
    build_source_reliability_from_runs,
    load_recent_source_intelligence_runs,
    source_reliability_state,
)


THRESHOLDS = {
    "source_reliability_window_runs": 5,
    "minimum_required_runs": 3,
    "repeated_failure_ratio": 0.50,
    "quarantine_ratio": 0.80,
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


def registry(*sources):
    return SourceRegistry(
        registry_version="1.4.0",
        sources=tuple(sources),
        evidence_types=({"evidence_type": "Headline", "status": "active"},),
        categories=({"category": "General Business", "description": "Business news."},),
        priority_tiers=({"tier": "TIER_1", "description": "Core sources."},),
        coverage_thresholds={},
        network_thresholds={"concentration_threshold": 0.40, "evidence_floor": 5},
        source_confidence_thresholds={},
        source_reliability_thresholds=THRESHOLDS,
    )


def run(timestamp, source_id, health_state="HEALTHY", freshness_status="FRESH", contributed=True):
    severity = "INFO" if health_state == "HEALTHY" else "CRITICAL"
    accepted = (
        [{"source_id": source_id, "evidence_id": f"{source_id}-{timestamp}"}]
        if contributed
        else []
    )
    return {
        "timestamp": timestamp,
        "source_intelligence": {
            "source_health": [
                {
                    "source_id": source_id,
                    "source_name": f"Source {source_id}",
                    "state": health_state,
                    "severity": severity,
                }
            ],
            "source_freshness": [
                {
                    "source_id": source_id,
                    "source_name": f"Source {source_id}",
                    "status": freshness_status,
                }
            ],
            "accepted_evidence": accepted,
            "evidence_funnel": {"fetched": len(accepted)},
        },
    }


def reliability_for(history, source_status="ACTIVE"):
    block = build_source_reliability_from_runs(
        registry(source("s1", status=source_status)),
        history,
        THRESHOLDS,
    )
    return block["sources"][0], block


class SourceReliabilityTests(unittest.TestCase):
    def test_stable_healthy_contributing_across_window(self):
        row, block = reliability_for([run(str(index), "s1") for index in range(5)])

        self.assertEqual(row["reliability_state"], STABLE)
        self.assertEqual(row["healthy_runs"], 5)
        self.assertEqual(row["contributing_runs"], 5)
        self.assertEqual(block["summary"]["stable_count"], 1)

    def test_watch_for_one_weak_run(self):
        history = [run("1", "s1", freshness_status="STALE", contributed=False)]
        history += [run(str(index), "s1") for index in range(2, 6)]

        row, _block = reliability_for(history)

        self.assertEqual(row["reliability_state"], WATCH)
        self.assertEqual(row["stale_runs"], 1)
        self.assertIn("Stale in 1 of 5 observed runs", row["reason"])

    def test_repeated_failure_at_exact_half_threshold(self):
        history = [
            run("1", "s1", freshness_status="STALE", contributed=False),
            run("2", "s1", freshness_status="STALE", contributed=False),
            run("3", "s1"),
            run("4", "s1"),
        ]

        row, _block = reliability_for(history)

        self.assertEqual(row["reliability_state"], REPEATED_FAILURE)

    def test_quarantine_recommended_at_exact_threshold(self):
        history = [
            run("1", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("2", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("3", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("4", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("5", "s1"),
        ]

        row, _block = reliability_for(history)

        self.assertEqual(row["reliability_state"], QUARANTINE_RECOMMENDED)
        self.assertEqual(row["blocked_runs"], 4)
        self.assertIn("Blocked in 4 of 5 observed runs", row["reason"])
        self.assertIn("Review for disabling or replacement", row["recommended_action"])

    def test_unknown_when_observed_runs_below_minimum(self):
        row, _block = reliability_for([run("1", "s1"), run("2", "s1")])

        self.assertEqual(row["reliability_state"], UNKNOWN_STATE)
        self.assertIn("Only 2 observed run", row["reason"])

    def test_just_added_source_with_zero_history_is_unknown(self):
        block = build_source_reliability_from_runs(
            registry(source("new-source")),
            [run("1", "other-source") for _index in range(5)],
            THRESHOLDS,
        )

        row = block["sources"][0]
        self.assertEqual(row["runs_observed"], 0)
        self.assertEqual(row["reliability_state"], UNKNOWN_STATE)

    def test_stale_repeated_source_matches_wsj_pattern(self):
        history = [
            run(str(index), "s1", freshness_status="STALE", contributed=False)
            for index in range(1, 5)
        ] + [run("5", "s1")]

        row, _block = reliability_for(history, source_status="DISABLED")

        self.assertEqual(row["registry_status"], "DISABLED")
        self.assertEqual(row["reliability_state"], QUARANTINE_RECOMMENDED)
        self.assertEqual(row["stale_runs"], 4)
        self.assertIn("source appears persistently stale", row["recommended_action"])

    def test_empty_repeated_source_counts_empty_runs(self):
        history = [
            run(str(index), "s1", health_state="EMPTY", freshness_status="QUIET", contributed=False)
            for index in range(1, 5)
        ] + [run("5", "s1")]

        row, _block = reliability_for(history)

        self.assertEqual(row["reliability_state"], QUARANTINE_RECOMMENDED)
        self.assertEqual(row["empty_runs"], 4)

    def test_healthy_non_contributing_runs_drive_weakness(self):
        history = [
            run(str(index), "s1", contributed=False)
            for index in range(1, 6)
        ]

        row, _block = reliability_for(history)

        self.assertEqual(row["healthy_runs"], 5)
        self.assertEqual(row["contributing_runs"], 0)
        self.assertEqual(row["non_contributing_runs"], 5)
        self.assertEqual(row["reliability_state"], QUARANTINE_RECOMMENDED)
        self.assertIn("zero accepted evidence in 5 of 5", row["reason"])

    def test_mixed_recovering_source_classified_by_window_numbers(self):
        history = [
            run("1", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("2", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("3", "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False),
            run("4", "s1"),
            run("5", "s1"),
        ]

        row, _block = reliability_for(history)

        self.assertEqual(row["reliability_state"], REPEATED_FAILURE)
        self.assertEqual(row["latest_state"], "HEALTHY")
        self.assertEqual(row["blocked_runs"], 3)

    def test_persistence_block_reconciles_summary_and_window(self):
        history = [run(str(index), "s1") for index in range(1, 6)]
        _row, block = reliability_for(history)

        self.assertEqual(
            block["evaluation_window"],
            {
                "window_runs_configured": 5,
                "runs_evaluated": 5,
                "oldest_run_timestamp": "1",
                "newest_run_timestamp": "5",
            },
        )
        self.assertEqual(block["thresholds_used"], THRESHOLDS)
        self.assertEqual(sum(block["summary"].values()), len(block["sources"]))

    def test_state_threshold_boundaries_are_inclusive(self):
        self.assertEqual(source_reliability_state(4, 2, THRESHOLDS), REPEATED_FAILURE)
        self.assertEqual(source_reliability_state(5, 4, THRESHOLDS), QUARANTINE_RECOMMENDED)

    def test_malformed_historical_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir)
            (results_dir / "bad.json").write_text("{", encoding="utf-8")
            (results_dir / "good.json").write_text(
                json.dumps(run("2026-07-09_120000", "s1")),
                encoding="utf-8",
            )

            loaded = load_recent_source_intelligence_runs(results_dir, 5)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["timestamp"], "2026-07-09_120000")

    def test_evaluation_does_not_change_registry_statuses(self):
        data = {
            "registry_version": "1.4.0",
            "network_thresholds": {"concentration_threshold": 0.40, "evidence_floor": 5},
            "source_confidence_thresholds": {
                "accepted_evidence_floor": 10,
                "low_fetch_ratio": 0.50,
                "low_contribution_ratio": 0.40,
                "high_fetch_ratio": 0.85,
                "high_freshness_ratio": 0.80,
                "high_contribution_ratio": 0.70,
            },
            "source_reliability_thresholds": THRESHOLDS,
            "coverage_thresholds": {
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
            },
            "sources": [source("s1", status="ACTIVE")],
            "evidence_types": [{"evidence_type": "Headline", "status": "active"}],
            "categories": [{"category": "General Business", "description": "Business news."}],
            "priority_tiers": [{"tier": "TIER_1", "description": "Core sources."}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "source_registry.json"
            registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            before = registry_path.read_text(encoding="utf-8")
            loaded_registry = load_source_registry(registry_path)
            history = [
                run(str(index), "s1", health_state="BLOCKED", freshness_status="UNKNOWN", contributed=False)
                for index in range(1, 6)
            ]

            block = build_source_reliability_from_runs(loaded_registry, history, THRESHOLDS)
            after = registry_path.read_text(encoding="utf-8")

        self.assertEqual(block["sources"][0]["reliability_state"], QUARANTINE_RECOMMENDED)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
