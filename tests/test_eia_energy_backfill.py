import hashlib
import json
import shutil
import unittest
import uuid
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mne import historical_backfill
from mne.backfill_sources import eia_energy


WPSR_FIXTURE = Path(__file__).parent / "fixtures" / "eia_energy_historical_wpsr_2020.html"
NG_FIXTURE = Path(__file__).parent / "fixtures" / "eia_energy_historical_ngstorage_2020.html"


def fixture_record(published_at="2020-01-08T15:30:00Z"):
    return {
        "title": "Weekly Petroleum Status Report — Week Ending January 3, 2020",
        "published_at": published_at,
        "url": "https://www.eia.gov/petroleum/supply/weekly/archive/2020/2020_01_08/wpsr_2020_01_08.php",
        "raw_id": "wpsr_2020_01_08",
        "retrieval_timestamp": "2026-07-23T00:00:00Z",
    }


def directory_digest(path):
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        digest.update(child.read_bytes())
    return digest.hexdigest()


class EiaEnergyBackfillTests(unittest.TestCase):
    def test_source_accepted_by_backfill_request_and_cli_dispatch(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"),
            source_categories=("eia_energy",),
        )
        self.assertTrue(request.backfill_id.endswith("_eia_energy"))
        manifest = {"evidence_count": 4, "replay_ready": True}
        with patch.object(
            historical_backfill, "run_and_persist_historical_backfill",
            return_value=(Path("/tmp/eia-backfill"), {"manifest": manifest}),
        ) as runner, patch("sys.stdout", new_callable=StringIO):
            historical_backfill.main([
                "--source", "eia_energy", "--start", "2020-01-01", "--end", "2020-03-31"
            ])
        runner.assert_called_once_with("eia_energy", "2020-01-01", "2020-03-31")

    def test_invalid_source_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "fed_fomc, bls_cpi, bea_gdp_pce"):
            historical_backfill.run_and_persist_historical_backfill(
                "eia_electricity", "2020-01-01", "2020-03-31"
            )

    def test_parse_eia_energy_records_extracts_wpsr_and_ng_storage_only(self):
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            wpsr = eia_energy.parse_eia_energy_records(WPSR_FIXTURE.read_text(encoding="utf-8"), "wpsr")
            ng_storage = eia_energy.parse_eia_energy_records(NG_FIXTURE.read_text(encoding="utf-8"), "ng_storage")
        self.assertEqual([row["raw_id"] for row in wpsr], [
            "wpsr_2020_01_08",
            "wpsr_2020_01_15",
            "wpsr_2020_01_23",
            "wpsr_2020_01_29",
        ])
        self.assertEqual([row["raw_id"] for row in ng_storage], [
            "ng_storage_2020_01_02",
            "ng_storage_2020_01_09",
            "ng_storage_2020_01_16",
        ])
        self.assertEqual(wpsr[0]["published_at"], "2020-01-08T15:30:00Z")
        self.assertEqual(ng_storage[0]["published_at"], "2020-01-02T15:30:00Z")

    def test_non_scoped_rows_are_ignored(self):
        wpsr = eia_energy.parse_eia_energy_records(WPSR_FIXTURE.read_text(encoding="utf-8"), "wpsr")
        ng_storage = eia_energy.parse_eia_energy_records(NG_FIXTURE.read_text(encoding="utf-8"), "ng_storage")
        self.assertNotIn("ngwu_2020_01_23", [row["raw_id"] for row in ng_storage])
        self.assertTrue(all("/electricity/" not in row["url"] for row in wpsr))

    def test_normalize_eia_energy_record_maps_connector_contract(self):
        first = eia_energy.normalize_eia_energy_record(fixture_record())
        second = eia_energy.normalize_eia_energy_record(fixture_record())
        self.assertEqual(first, second)
        self.assertEqual(first["source"], "U.S. Energy Information Administration")
        self.assertEqual(first["provider"], "EIA")
        self.assertEqual(first["category"], "Energy / Commodities")
        self.assertEqual(first["published_at"], "2020-01-08T15:30:00Z")
        self.assertEqual(first["url"], fixture_record()["url"])
        self.assertEqual(first["raw_id"], "wpsr_2020_01_08")
        self.assertEqual(first["raw_id"], first["reference_id"])
        self.assertEqual(first["usage_storage_rights"], "NORMALIZED_EVIDENCE")

    def test_normalized_eia_record_becomes_historical_backfill_evidence(self):
        normalized = eia_energy.normalize_eia_energy_record(fixture_record())
        evidence = historical_backfill.normalize_backfill_record(
            normalized, "backfill_test", historical_source_id="eia_energy",
            provider="EIA", category="Energy / Commodities",
        )
        self.assertEqual((evidence.source_id, evidence.source_name), ("eia_energy", "EIA"))
        self.assertEqual(evidence.metadata["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(evidence.metadata["backfill_id"], "backfill_test")
        self.assertEqual(evidence.metadata["category"], "Energy / Commodities")

    def test_duplicate_records_are_deduped_by_shared_evidence_id(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"), source_categories=("eia_energy",)
        )
        raw = fixture_record()
        result = historical_backfill.run_historical_backfill(
            request, connector=lambda start, end, get=None: [raw, dict(raw)]
        )
        self.assertEqual(result["manifest"]["records_found"], 2)
        self.assertEqual(len(result["evidence_objects"]), 1)

    def test_persistence_writes_manifest_and_evidence_json(self):
        workspace_tmp = Path(".tmp_mne_data")
        workspace_tmp.mkdir(exist_ok=True)
        temp = workspace_tmp / f"eia_backfill_{uuid.uuid4().hex}"
        temp.mkdir()
        try:
            data_dir = temp
            other_source = data_dir / "historical_evidence" / "backfill_other_macro_bea_gdp_pce"
            other_source.mkdir(parents=True)
            (other_source / "manifest.json").write_text(json.dumps({"keep": True}), encoding="utf-8")
            before_other = directory_digest(other_source)
            request = historical_backfill.build_backfill_request(
                requested_range=("2020-01-01", "2020-03-31"), source_categories=("eia_energy",)
            )
            result = historical_backfill.run_historical_backfill(
                request, connector=lambda start, end, get=None: [fixture_record()]
            )
            path = historical_backfill.persist_backfill_result(
                request, result["evidence_objects"], result["manifest"], data_dir=data_dir
            )
            self.assertTrue((path / "manifest.json").exists())
            self.assertTrue((path / "evidence.json").exists())
            self.assertEqual(before_other, directory_digest(other_source))
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_empty_result_produces_valid_manifest_with_warnings(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"), source_categories=("eia_energy",)
        )
        result = historical_backfill.run_historical_backfill(
            request, connector=lambda start, end, get=None: []
        )
        manifest = result["manifest"]
        self.assertEqual((manifest["records_found"], manifest["evidence_count"]), (0, 0))
        self.assertFalse(manifest["replay_ready"])
        for warning in historical_backfill.EIA_WARNINGS:
            self.assertIn(warning, manifest["warnings"])
        self.assertIn("No EIA energy release evidence was found for the requested date range.", manifest["warnings"])

    def test_fetch_is_injectable_and_does_not_call_live_network(self):
        class Response:
            def __init__(self, text):
                self.text = text
            def raise_for_status(self):
                return None
        calls = []
        payloads = {
            eia_energy.WPSR_ARCHIVE_URL: WPSR_FIXTURE.read_text(encoding="utf-8"),
            eia_energy.NG_STORAGE_ARCHIVE_URL: NG_FIXTURE.read_text(encoding="utf-8"),
        }
        def fake_get(url, timeout, headers):
            calls.append(url)
            return Response(payloads[url])
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            records = eia_energy.fetch_eia_energy_records(
                "2020-01-08", "2020-01-09", get=fake_get
            )
        self.assertEqual(calls, [eia_energy.WPSR_ARCHIVE_URL, eia_energy.NG_STORAGE_ARCHIVE_URL])
        self.assertEqual([row["raw_id"] for row in records], ["wpsr_2020_01_08", "ng_storage_2020_01_09"])


if __name__ == "__main__":
    unittest.main()
