import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from mne_test_utils import temporary_mne_data_dir
from mne.source_registry import SourceRegistryError, load_source_registry


REUTERS_URL = "https://feeds.reuters.com/reuters/businessNews"


def valid_registry_data():
    return {
        "registry_version": "1.0.0",
        "network_thresholds": {
            "concentration_threshold": 0.40,
            "evidence_floor": 5,
        },
        "source_confidence_thresholds": {
            "accepted_evidence_floor": 10,
            "low_fetch_ratio": 0.50,
            "low_contribution_ratio": 0.40,
            "high_fetch_ratio": 0.85,
            "high_freshness_ratio": 0.80,
            "high_contribution_ratio": 0.70,
        },
        "source_reliability_thresholds": {
            "source_reliability_window_runs": 5,
            "minimum_required_runs": 3,
            "repeated_failure_ratio": 0.50,
            "quarantine_ratio": 0.80,
        },
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
        "sources": [
            {
                "source_id": "reuters-business-news",
                "display_name": "Reuters Business News",
                "provider": "Reuters",
                "category": "General Business",
                "priority": "TIER_1",
                "ingestion_type": "RSS",
                "supported_evidence_types": ["Headline"],
                "url": REUTERS_URL,
                "status": "ACTIVE",
                "freshness_threshold_minutes": 120,
                "expected_update_frequency_minutes": 45,
                "supported_narratives": ["Macro", "Companies"],
                "supported_groups": ["Macro", "Companies"],
                "notes": None,
            }
        ],
        "evidence_types": [{"evidence_type": "Headline", "status": "active"}],
        "categories": [{"category": "General Business", "description": "Business news."}],
        "priority_tiers": [{"tier": "TIER_1", "description": "Core narrative sources."}],
    }


class SourceRegistryTests(unittest.TestCase):
    def write_registry(self, data):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "source_registry.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.addCleanup(tmpdir.cleanup)
        return path

    def test_loads_valid_registry_and_active_urls(self):
        registry = load_source_registry(self.write_registry(valid_registry_data()))

        self.assertEqual(registry.registry_version, "1.0.0")
        self.assertEqual(
            registry.network_thresholds,
            {"concentration_threshold": 0.40, "evidence_floor": 5},
        )
        self.assertEqual(
            registry.source_confidence_thresholds,
            {
                "accepted_evidence_floor": 10,
                "low_fetch_ratio": 0.50,
                "low_contribution_ratio": 0.40,
                "high_fetch_ratio": 0.85,
                "high_freshness_ratio": 0.80,
                "high_contribution_ratio": 0.70,
            },
        )
        self.assertEqual(
            registry.source_reliability_thresholds,
            {
                "source_reliability_window_runs": 5,
                "minimum_required_runs": 3,
                "repeated_failure_ratio": 0.50,
                "quarantine_ratio": 0.80,
            },
        )
        self.assertEqual(registry.active_rss_urls, [REUTERS_URL])
        self.assertEqual(
            registry.source_by_url(REUTERS_URL)["display_name"],
            "Reuters Business News",
        )

    def test_invalid_semver_fails_loudly(self):
        data = valid_registry_data()
        data["registry_version"] = "1"

        with self.assertRaisesRegex(SourceRegistryError, "semantic version"):
            load_source_registry(self.write_registry(data))

    def test_missing_source_field_fails_loudly(self):
        data = valid_registry_data()
        del data["sources"][0]["supported_groups"]

        with self.assertRaisesRegex(SourceRegistryError, "missing fields: supported_groups"):
            load_source_registry(self.write_registry(data))

    def test_invalid_status_fails_loudly(self):
        data = valid_registry_data()
        data["sources"][0]["status"] = "PAUSED"

        with self.assertRaisesRegex(SourceRegistryError, "invalid status"):
            load_source_registry(self.write_registry(data))

    def test_invalid_network_thresholds_fail_loudly(self):
        data = valid_registry_data()
        data["network_thresholds"]["concentration_threshold"] = 1.5

        with self.assertRaisesRegex(SourceRegistryError, "concentration_threshold"):
            load_source_registry(self.write_registry(data))

    def test_invalid_source_confidence_thresholds_fail_loudly(self):
        data = valid_registry_data()
        data["source_confidence_thresholds"]["high_fetch_ratio"] = 1.5

        with self.assertRaisesRegex(
            SourceRegistryError,
            "source_confidence_thresholds.high_fetch_ratio",
        ):
            load_source_registry(self.write_registry(data))

    def test_invalid_source_reliability_thresholds_fail_loudly(self):
        data = valid_registry_data()
        data["source_reliability_thresholds"]["quarantine_ratio"] = 1.5

        with self.assertRaisesRegex(
            SourceRegistryError,
            "source_reliability_thresholds.quarantine_ratio",
        ):
            load_source_registry(self.write_registry(data))

    def test_only_active_sources_are_sent_to_fetch(self):
        data = valid_registry_data()
        for status in ("DISABLED", "DEPRECATED", "PLANNED"):
            source = copy.deepcopy(data["sources"][0])
            source["source_id"] = f"test-{status.lower()}"
            source["display_name"] = f"Test {status}"
            source["url"] = f"https://example.com/{status.lower()}.rss"
            source["status"] = status
            data["sources"].append(source)
        registry = load_source_registry(self.write_registry(data))

        with (
            temporary_mne_data_dir(),
            patch.object(main, "load_source_registry", return_value=registry),
            patch.object(
                main,
                "fetch_headlines_from_rss",
                return_value={
                    "entries": [],
                    "source_health": [
                        {
                            "source_id": "reuters-business-news",
                            "source_name": "Reuters Business News",
                            "state": "EMPTY",
                            "severity": "WARNING",
                            "reason": "Zero entries present in feed",
                            "recommended_action": "Confirm whether the source is expected to publish entries.",
                            "http_status": 200,
                            "entries_seen": 0,
                            "entries_parsed": 0,
                            "fetch_error": None,
                            "checked_at": "2026-07-06T12:00:00+00:00",
                        }
                    ],
                },
            ) as fetch,
            patch.object(
                main,
                "save_run_json",
                return_value=(Path("/tmp"), Path("/tmp/run.json")),
            ) as save_run_json,
        ):
            main.main([])

        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], [REUTERS_URL])
        persisted_run = save_run_json.call_args.args[0]
        source_intelligence = persisted_run["source_intelligence"]
        self.assertEqual(len(source_intelligence["source_health"]), 1)
        self.assertIn("network_health", source_intelligence)
        self.assertIn("source_confidence", source_intelligence)
        self.assertEqual(
            source_intelligence["network_health"]["thresholds_used"],
            {"concentration_threshold": 0.40, "evidence_floor": 5},
        )


if __name__ == "__main__":
    unittest.main()
