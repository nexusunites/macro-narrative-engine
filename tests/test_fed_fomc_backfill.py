import unittest
from pathlib import Path
from unittest.mock import patch

from mne import historical_backfill
from mne.backfill_sources import fed_fomc


FIXTURE = Path(__file__).parent / "fixtures" / "fed_fomc_historical_2020.html"


class FedFomcBackfillConnectorTests(unittest.TestCase):
    def test_parse_fed_fomc_records_extracts_statement_links_without_network(self):
        records = fed_fomc.parse_fed_fomc_records(FIXTURE.read_text(encoding="utf-8"), 2020)

        self.assertEqual([record["raw_id"] for record in records], ["monetary20200129a", "monetary20200315a"])
        self.assertEqual(records[0]["title"], "Federal Reserve issues FOMC statement")
        self.assertEqual(records[0]["published_date"], "2020-01-29")
        self.assertEqual(
            records[0]["url"],
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200129a.htm",
        )

    def test_normalize_fed_fomc_record_maps_connector_contract(self):
        raw = {
            "title": "Federal Reserve issues FOMC statement",
            "published_at": "2020-01-29T19:00:00Z",
            "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200129a.htm",
            "raw_id": "monetary20200129a",
        }

        normalized = fed_fomc.normalize_fed_fomc_record(
            raw,
            retrieval_timestamp="2026-07-15T00:00:00Z",
        )

        self.assertEqual(normalized["title"], "Federal Reserve issues FOMC statement")
        self.assertEqual(normalized["source"], "Federal Reserve")
        self.assertEqual(normalized["provider"], "Federal Reserve")
        self.assertEqual(normalized["published_at"], "2020-01-29T19:00:00Z")
        self.assertEqual(normalized["source_type"], "official_central_bank_statement")
        self.assertEqual(normalized["category"], "Central Bank Communications")
        self.assertEqual(normalized["raw_id"], "monetary20200129a")
        self.assertEqual(normalized["retrieval_timestamp"], "2026-07-15T00:00:00Z")
        self.assertEqual(normalized["usage_storage_rights"], "NORMALIZED_EVIDENCE")

    def test_normalized_fomc_record_becomes_historical_backfill_evidence(self):
        request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))
        record = fed_fomc.normalize_fed_fomc_record(
            {
                "title": "Federal Reserve issues FOMC statement",
                "published_at": "2020-01-29T19:00:00Z",
                "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200129a.htm",
                "raw_id": "monetary20200129a",
                "retrieval_timestamp": "2026-07-15T00:00:00Z",
            }
        )

        evidence = historical_backfill.normalize_backfill_record(record, request.backfill_id)

        self.assertEqual(evidence.metadata["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(evidence.metadata["backfill_id"], request.backfill_id)
        self.assertEqual(evidence.timestamp, "2020-01-29T19:00:00Z")
        self.assertEqual(evidence.source_id, "fed_fomc")
        self.assertEqual(evidence.source_name, "Federal Reserve")
        self.assertEqual(evidence.metadata["category"], "Central Bank Communications")

    def test_duplicate_records_are_deduped_by_shared_evidence_id(self):
        raw = {
            "title": "Federal Reserve issues FOMC statement",
            "published_at": "2020-01-29T19:00:00Z",
            "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200129a.htm",
            "raw_id": "monetary20200129a",
            "retrieval_timestamp": "2026-07-15T00:00:00Z",
        }
        request = historical_backfill.build_backfill_request(requested_range=("2020-01-01", "2020-01-31"))

        result = historical_backfill.run_historical_backfill(
            request,
            connector=lambda start, end, get=None: [raw, dict(raw)],
        )

        self.assertEqual(len(result["evidence_objects"]), 1)
        self.assertEqual(result["manifest"]["records_found"], 2)
        self.assertEqual(result["manifest"]["evidence_count"], 1)

    def test_fetch_and_parse_are_independently_testable_and_fetch_is_isolated(self):
        class Response:
            text = FIXTURE.read_text(encoding="utf-8")

            def raise_for_status(self):
                return None

        calls = []

        def fake_get(url, timeout, headers):
            calls.append(url)
            return Response()

        records = fed_fomc.fetch_fed_fomc_records("2020-01-01", "2020-01-31", get=fake_get)

        self.assertEqual(len(calls), 1)
        self.assertEqual(records[0]["raw_id"], "monetary20200129a")

        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            parsed = fed_fomc.parse_fed_fomc_records(FIXTURE.read_text(encoding="utf-8"), 2020)
        self.assertEqual(len(parsed), 2)


if __name__ == "__main__":
    unittest.main()

