import hashlib
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mne import historical_backfill
from mne.backfill_sources import bea_gdp_pce


FIXTURE = Path(__file__).parent / "fixtures" / "bea_gdp_pce_historical_2020.html"


def fixture_record(published_at="2020-01-30T13:30:00Z"):
    return {
        "title": "Gross Domestic Product, 4th Quarter and Annual 2019 (Advance Estimate)",
        "published_at": published_at,
        "url": "https://www.bea.gov/news/2020/gross-domestic-product-4th-quarter-and-annual-2019-advance-estimate",
        "raw_id": "gross-domestic-product-4th-quarter-and-annual-2019-advance-estimate",
        "retrieval_timestamp": "2026-07-21T00:00:00Z",
    }


def directory_digest(path):
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        digest.update(child.read_bytes())
    return digest.hexdigest()


class BeaGdpPceBackfillTests(unittest.TestCase):
    def test_source_accepted_by_backfill_request_and_cli_dispatch(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"),
            source_categories=("bea_gdp_pce",),
        )
        self.assertTrue(request.backfill_id.endswith("_bea_gdp_pce"))
        manifest = {"evidence_count": 4, "replay_ready": True}
        with patch.object(
            historical_backfill, "run_and_persist_historical_backfill",
            return_value=(Path("/tmp/bea-backfill"), {"manifest": manifest}),
        ) as runner, patch("sys.stdout", new_callable=StringIO):
            historical_backfill.main([
                "--source", "bea_gdp_pce", "--start", "2020-01-01", "--end", "2020-03-31"
            ])
        runner.assert_called_once_with("bea_gdp_pce", "2020-01-01", "2020-03-31")

    def test_invalid_source_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "fed_fomc, bls_cpi, bea_gdp_pce"):
            historical_backfill.run_and_persist_historical_backfill(
                "gdp_by_industry", "2020-01-01", "2020-03-31"
            )

    def test_parse_bea_gdp_pce_records_extracts_gdp_and_pce_only(self):
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            records = bea_gdp_pce.parse_bea_gdp_pce_records(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([row["raw_id"] for row in records], [
            "gross-domestic-product-4th-quarter-and-annual-2019-advance-estimate",
            "personal-income-and-outlays-december-2019",
            "gross-domestic-product-4th-quarter-and-annual-2019-second-estimate",
            "personal-income-and-outlays-january-2020",
        ])
        self.assertEqual(records[0]["published_at"], "2020-01-30T13:30:00Z")

    def test_normalize_bea_gdp_pce_record_maps_connector_contract(self):
        first = bea_gdp_pce.normalize_bea_gdp_pce_record(fixture_record())
        second = bea_gdp_pce.normalize_bea_gdp_pce_record(fixture_record())
        self.assertEqual(first, second)
        self.assertEqual(first["source"], "Bureau of Economic Analysis")
        self.assertEqual(first["provider"], "BEA")
        self.assertEqual(first["category"], "Economic Data / Growth / Inflation")
        self.assertEqual(first["source_type"], "official_release")
        self.assertEqual(first["raw_id"], first["reference_id"])
        self.assertEqual(first["usage_storage_rights"], "NORMALIZED_EVIDENCE")

    def test_normalized_bea_record_becomes_historical_backfill_evidence(self):
        normalized = bea_gdp_pce.normalize_bea_gdp_pce_record(fixture_record())
        evidence = historical_backfill.normalize_backfill_record(
            normalized, "backfill_test", historical_source_id="bea_gdp_pce",
            provider="BEA", category="Economic Data / Growth / Inflation",
        )
        self.assertEqual((evidence.source_id, evidence.source_name), ("bea_gdp_pce", "BEA"))
        self.assertEqual(evidence.metadata["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(evidence.metadata["backfill_id"], "backfill_test")
        self.assertEqual(evidence.metadata["category"], "Economic Data / Growth / Inflation")

    def test_duplicate_records_are_deduped_by_shared_evidence_id(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"), source_categories=("bea_gdp_pce",)
        )
        raw = fixture_record()
        result = historical_backfill.run_historical_backfill(
            request, connector=lambda start, end, get=None: [raw, dict(raw)]
        )
        self.assertEqual(result["manifest"]["records_found"], 2)
        self.assertEqual(len(result["evidence_objects"]), 1)

    def test_persistence_writes_manifest_and_evidence_json(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            unrelated = data_dir / "unrelated.json"
            unrelated.write_text(json.dumps({"keep": True}))
            before = directory_digest(data_dir)
            request = historical_backfill.build_backfill_request(
                requested_range=("2020-01-01", "2020-03-31"), source_categories=("bea_gdp_pce",)
            )
            result = historical_backfill.run_historical_backfill(
                request, connector=lambda start, end, get=None: [fixture_record()]
            )
            path = historical_backfill.persist_backfill_result(
                request, result["evidence_objects"], result["manifest"], data_dir=data_dir
            )
            self.assertTrue((path / "manifest.json").exists())
            self.assertTrue((path / "evidence.json").exists())
            self.assertEqual(json.loads(unrelated.read_text()), {"keep": True})
            self.assertNotEqual(before, directory_digest(data_dir))

    def test_empty_result_produces_valid_manifest_with_warnings(self):
        request = historical_backfill.build_backfill_request(
            requested_range=("2020-01-01", "2020-03-31"), source_categories=("bea_gdp_pce",)
        )
        result = historical_backfill.run_historical_backfill(
            request, connector=lambda start, end, get=None: []
        )
        manifest = result["manifest"]
        self.assertEqual((manifest["records_found"], manifest["evidence_count"]), (0, 0))
        self.assertFalse(manifest["replay_ready"])
        for warning in historical_backfill.BEA_WARNINGS:
            self.assertIn(warning, manifest["warnings"])
        self.assertIn("No BEA GDP/PCE release evidence was found for the requested date range.", manifest["warnings"])

    def test_fetch_is_injectable_and_does_not_call_live_network(self):
        class Response:
            text = FIXTURE.read_text(encoding="utf-8")
            def raise_for_status(self):
                return None
        calls = []
        def fake_get(url, timeout, headers):
            calls.append(url)
            return Response()
        records = bea_gdp_pce.fetch_bea_gdp_pce_records(
            "2020-01-30", "2020-01-31", get=fake_get
        )
        self.assertEqual(calls, [bea_gdp_pce.ARCHIVE_URL])
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
