import hashlib
import importlib
import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from mne import historical_backfill


def directory_digest(path):
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


@contextmanager
def temporary_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "mne-data"
        with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
            import config

            importlib.reload(config)
            importlib.reload(historical_backfill.config)
            try:
                yield data_dir
            finally:
                importlib.reload(config)
                importlib.reload(historical_backfill.config)


def fomc_record(published_at="2020-01-29T19:00:00Z"):
    return {
        "title": "Federal Reserve issues FOMC statement",
        "published_at": published_at,
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200129a.htm",
        "raw_id": "monetary20200129a",
        "retrieval_timestamp": "2026-07-15T00:00:00Z",
    }


class HistoricalBackfillTests(unittest.TestCase):
    def test_build_backfill_request_accepts_single_date_and_range(self):
        single = historical_backfill.build_backfill_request(requested_date="2020-01-29")
        ranged = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))

        self.assertEqual(single.requested_date, "2020-01-29")
        self.assertEqual(single.requested_range, ("2020-01-29", "2020-01-29"))
        self.assertEqual(single.narrative_mode, "macro")
        self.assertEqual(single.source_categories, ("fed_fomc",))
        self.assertEqual(ranged.requested_range, ("2020-01-01", "2020-01-31"))
        self.assertEqual(
            ranged.backfill_id,
            "backfill_2020-01-01_2020-01-31_macro_fed_fomc",
        )

    def test_invalid_date_and_invalid_range_are_rejected(self):
        with self.assertRaises(ValueError):
            historical_backfill.build_backfill_request(requested_date="January 29")
        with self.assertRaises(ValueError):
            historical_backfill.build_backfill_request(requested_range=("2020-02-01", "2020-01-01"))
        with self.assertRaises(ValueError):
            historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"), source_categories=("news",))

    def test_backfill_id_is_deterministic(self):
        first = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
        second = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))

        self.assertEqual(first.backfill_id, second.backfill_id)

    def test_storage_paths_use_mne_data_dir_and_persist_manifest_and_evidence(self):
        with temporary_data_dir() as data_dir:
            request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
            result = historical_backfill.run_historical_backfill(
                request,
                connector=lambda start, end, get=None: [fomc_record()],
            )
            path = historical_backfill.persist_backfill_result(
                result["request"],
                result["evidence_objects"],
                result["manifest"],
            )

            self.assertEqual(
                path.resolve(),
                (data_dir / "historical_evidence" / request.backfill_id).resolve(),
            )
            self.assertTrue((path / "manifest.json").exists())
            self.assertTrue((path / "evidence.json").exists())
            self.assertEqual(historical_backfill.load_backfill_manifest(request.backfill_id)["backfill_id"], request.backfill_id)
            self.assertEqual(len(historical_backfill.load_backfilled_evidence(request.backfill_id)), 1)

    def test_empty_connector_result_produces_warned_non_replay_ready_manifest(self):
        request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))

        result = historical_backfill.run_historical_backfill(
            request,
            connector=lambda start, end, get=None: [],
        )
        manifest = result["manifest"]

        self.assertEqual(manifest["records_found"], 0)
        self.assertEqual(manifest["evidence_count"], 0)
        self.assertEqual(manifest["status"], "PARTIAL")
        self.assertFalse(manifest["replay_ready"])
        self.assertGreater(len(manifest["warnings"]), 0)

    def test_replay_ready_requires_evidence_and_no_unresolved_errors(self):
        request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
        good = historical_backfill.run_historical_backfill(
            request,
            connector=lambda start, end, get=None: [fomc_record()],
        )
        bad = historical_backfill.run_historical_backfill(
            request,
            connector=lambda start, end, get=None: [{"title": "missing published_at"}],
        )

        self.assertTrue(good["manifest"]["replay_ready"])
        self.assertFalse(bad["manifest"]["replay_ready"])
        self.assertTrue(any("could not be normalized" in warning for warning in bad["manifest"]["warnings"]))

    def test_no_live_results_or_replay_artifacts_are_modified(self):
        with temporary_data_dir() as data_dir:
            results_dir = data_dir / "results"
            replays_dir = data_dir / "replays"
            results_dir.mkdir(parents=True)
            replays_dir.mkdir(parents=True)
            (results_dir / "existing.json").write_text(json.dumps({"live": True}), encoding="utf-8")
            (replays_dir / "existing.json").write_text(json.dumps({"replay": True}), encoding="utf-8")
            before_results = directory_digest(results_dir)
            before_replays = directory_digest(replays_dir)

            request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
            result = historical_backfill.run_historical_backfill(
                request,
                connector=lambda start, end, get=None: [fomc_record()],
            )
            historical_backfill.persist_backfill_result(
                result["request"],
                result["evidence_objects"],
                result["manifest"],
            )

            self.assertEqual(before_results, directory_digest(results_dir))
            self.assertEqual(before_replays, directory_digest(replays_dir))

    def test_config_portability_writes_only_under_temp_data_dir(self):
        with temporary_data_dir() as data_dir:
            default_dir = Path.home() / ".mne" / "data"
            before_default = directory_digest(default_dir)
            request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
            result = historical_backfill.run_historical_backfill(
                request,
                connector=lambda start, end, get=None: [fomc_record()],
            )

            historical_backfill.persist_backfill_result(
                result["request"],
                result["evidence_objects"],
                result["manifest"],
            )

            self.assertTrue((data_dir / "historical_evidence" / request.backfill_id).exists())
            self.assertEqual(before_default, directory_digest(default_dir))

    def test_warning_strings_are_verbatim(self):
        request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
        result = historical_backfill.run_historical_backfill(
            request,
            connector=lambda start, end, get=None: [fomc_record()],
        )

        warnings = result["manifest"]["warnings"]
        self.assertIn("Fed/FOMC backfill covers only Federal Reserve communications.", warnings)
        self.assertIn("This is partial historical coverage, not complete market news reconstruction.", warnings)
        self.assertIn("No live sources were fetched.", warnings)
        self.assertIn("No paywalled news was accessed.", warnings)

    def test_load_backfilled_evidence_resolves_by_requested_date(self):
        with temporary_data_dir():
            request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
            result = historical_backfill.run_historical_backfill(
                request,
                connector=lambda start, end, get=None: [fomc_record()],
            )
            historical_backfill.persist_backfill_result(
                result["request"],
                result["evidence_objects"],
                result["manifest"],
            )

            evidence = historical_backfill.load_backfilled_evidence(requested_date="2020-01-29")

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["metadata"]["evidence_origin"], "HISTORICAL_BACKFILL")


if __name__ == "__main__":
    unittest.main()
