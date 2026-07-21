import hashlib
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mne import historical_backfill, historical_replay
from mne.backfill_sources import bls_cpi


FIXTURE = Path(__file__).parent / "fixtures" / "bls_cpi_historical_2020.html"


def fixture_record(published_at="2020-06-10T12:30:00Z"):
    return {
        "title": "Consumer Price Index — May 2020",
        "published_at": published_at,
        "url": "https://www.bls.gov/news.release/archives/cpi_06102020.htm",
        "raw_id": "cpi_06102020",
        "retrieval_timestamp": "2026-07-21T12:00:00Z",
    }


def directory_digest(path):
    digest = hashlib.sha256()
    if path.exists():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(str(child.relative_to(path)).encode())
            digest.update(child.read_bytes())
    return digest.hexdigest()


class BlsCpiBackfillTests(unittest.TestCase):
    def test_request_and_dispatch_accept_bls_cpi_and_invalid_names_valid_options(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-06-01", "2020-06-30"),
            source_categories=("bls_cpi",),
        )
        self.assertEqual(request.source_categories, ("bls_cpi",))
        self.assertTrue(request.backfill_id.endswith("_bls_cpi"))
        with self.assertRaisesRegex(ValueError, "fed_fomc, bls_cpi"):
            historical_backfill.run_and_persist_historical_backfill(
                "ppi", "2020-01-01", "2020-01-31"
            )

    def test_cli_dispatch_accepts_bls_cpi(self):
        manifest = {"evidence_count": 1, "replay_ready": True}
        with patch.object(
            historical_backfill,
            "run_and_persist_historical_backfill",
            return_value=(Path("/tmp/bls-backfill"), {"manifest": manifest}),
        ) as runner, patch("sys.stdout", new_callable=StringIO) as output:
            historical_backfill.main([
                "--source", "bls_cpi", "--start", "2020-06-01", "--end", "2020-06-30"
            ])
        runner.assert_called_once_with("bls_cpi", "2020-06-01", "2020-06-30")
        self.assertIn("Evidence produced: 1", output.getvalue())

    def test_fixture_parses_only_cpi_and_dedupes_format_variants(self):
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            records = bls_cpi.parse_bls_cpi_records(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([row["raw_id"] for row in records], [
            "cpi_02132020", "cpi_03112020", "cpi_06102020"
        ])
        self.assertTrue(all("/cpi_" in row["url"] for row in records))
        self.assertEqual(records[-1]["title"], "Consumer Price Index — May 2020")
        self.assertEqual(records[-1]["published_at"], "2020-06-10T12:30:00Z")

    def test_fetch_is_injectable_bounded_and_does_not_call_live_network(self):
        class Response:
            text = FIXTURE.read_text(encoding="utf-8")
            def raise_for_status(self):
                return None
        calls = []
        def fake_get(url, timeout, headers):
            calls.append(url)
            return Response()
        records = bls_cpi.fetch_bls_cpi_records(
            "2020-06-01", "2020-06-30", get=fake_get
        )
        self.assertEqual(calls, [bls_cpi.ARCHIVE_URL])
        self.assertEqual([row["raw_id"] for row in records], ["cpi_06102020"])

    def test_connector_contract_and_identifier_are_deterministic(self):
        first = bls_cpi.normalize_bls_cpi_record(
            fixture_record(), retrieval_timestamp="2026-07-21T12:00:00Z"
        )
        second = bls_cpi.normalize_bls_cpi_record(
            fixture_record(), retrieval_timestamp="2026-07-21T12:00:00Z"
        )
        self.assertEqual(first, second)
        self.assertEqual(first["source"], "Bureau of Labor Statistics")
        self.assertEqual(first["provider"], "BLS")
        self.assertEqual(first["category"], "Inflation / Economic Data")
        self.assertEqual(first["source_type"], "official_release")
        self.assertEqual(first["published_at"], fixture_record()["published_at"])
        self.assertEqual(first["url"], fixture_record()["url"])
        self.assertEqual(first["raw_id"], first["reference_id"])

    def test_run_normalizes_provenance_dedupes_and_builds_bls_manifest(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-06-01", "2020-06-30"), source_categories=("bls_cpi",)
        )
        result = historical_backfill.run_historical_backfill(
            request, connector=lambda start, end, get=None: [fixture_record(), fixture_record()]
        )
        evidence = result["evidence_objects"][0]
        self.assertEqual(len(result["evidence_objects"]), 1)
        self.assertEqual((evidence.source_id, evidence.source_name), ("bls_cpi", "BLS"))
        self.assertEqual(evidence.timestamp, fixture_record()["published_at"])
        self.assertEqual(evidence.url, fixture_record()["url"])
        self.assertEqual(evidence.metadata["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(evidence.metadata["backfill_id"], request.backfill_id)
        self.assertEqual(evidence.metadata["provider"], "BLS")
        self.assertEqual(evidence.metadata["category"], "Inflation / Economic Data")
        self.assertEqual(result["manifest"]["records_found"], 2)
        self.assertEqual(result["manifest"]["evidence_count"], 1)
        self.assertEqual(result["manifest"]["date_range_covered"], {
            "start": "2020-06-10", "end": "2020-06-10"
        })

    def test_persistence_empty_manifest_and_unrelated_artifacts_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            results, replays = data_dir / "results", data_dir / "replays"
            results.mkdir(); replays.mkdir()
            (results / "live.json").write_text(json.dumps({"live": True}))
            (replays / "replay.json").write_text(json.dumps({"replay": True}))
            before = (directory_digest(results), directory_digest(replays))
            request = historical_backfill.build_backfill_request(
                requested_range=("2020-07-01", "2020-07-02"), source_categories=("bls_cpi",)
            )
            result = historical_backfill.run_historical_backfill(
                request, connector=lambda start, end, get=None: []
            )
            path = historical_backfill.persist_backfill_result(
                request, result["evidence_objects"], result["manifest"], data_dir=data_dir
            )
            self.assertTrue((path / "manifest.json").exists())
            self.assertTrue((path / "evidence.json").exists())
            self.assertEqual(result["manifest"]["records_found"], 0)
            self.assertFalse(result["manifest"]["replay_ready"])
            for warning in historical_backfill.BLS_WARNINGS:
                self.assertIn(warning, result["manifest"]["warnings"])
            self.assertEqual(before, (directory_digest(results), directory_digest(replays)))

    def test_replay_includes_bls_by_id_and_enforces_cutoff(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-06-01", "2020-07-31"), source_categories=("bls_cpi",)
        )
        rows = []
        for raw in [fixture_record(), fixture_record("2020-07-14T12:30:00Z")]:
            normalized = bls_cpi.normalize_bls_cpi_record(raw)
            rows.append(historical_backfill.normalize_backfill_record(
                normalized, request.backfill_id, historical_source_id="bls_cpi",
                provider="BLS", category="Inflation / Economic Data"
            ).to_dict())
        replay_request = historical_replay.build_replay_request(
            "2020-06-30", backfill_id=request.backfill_id
        )
        with patch.object(
            historical_replay.historical_backfill, "load_backfilled_evidence", return_value=rows
        ) as loader:
            output = historical_replay.run_historical_replay(replay_request, historical_records=[])
        loader.assert_called_once_with(backfill_id=request.backfill_id, requested_date=None)
        self.assertEqual(output["evidence_count"], 1)
        self.assertEqual(output["replay_metadata"]["backfill_ids_used"], [request.backfill_id])
        accepted = output["source_intelligence"]["accepted_evidence"][0]
        self.assertEqual(accepted["backfill_id"], request.backfill_id)
        self.assertEqual(accepted["evidence_origin"], "HISTORICAL_BACKFILL")


if __name__ == "__main__":
    unittest.main()
