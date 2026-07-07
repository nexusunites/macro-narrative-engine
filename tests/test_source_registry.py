import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from mne.source_registry import SourceRegistryError, load_source_registry


REUTERS_URL = "https://feeds.reuters.com/reuters/businessNews"


def valid_registry_data():
    return {
        "registry_version": "1.0.0",
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
            patch.object(main, "load_source_registry", return_value=registry),
            patch.object(main, "fetch_headlines_from_rss", return_value=[]) as fetch,
            patch.object(main, "save_run_json", return_value=(Path("/tmp"), Path("/tmp/run.json"))),
        ):
            main.main([])

        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], [REUTERS_URL])


if __name__ == "__main__":
    unittest.main()
