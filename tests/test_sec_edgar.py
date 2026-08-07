import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from mne.sec_edgar import (
    GENERIC_TITLE,
    SecEdgarError,
    build_filing_url,
    fetch_8k_filings,
    load_sec_edgar_map,
    parse_submissions,
    title_for_items,
    validate_sec_edgar_map,
)


def submissions(*, accessions=("0001045810-26-000060","other"), forms=("8-K","10-Q")):
    count = len(accessions)
    return {"name":"Fixture Corp","tickers":["FIX"],"filings":{"recent":{
        "accessionNumber":list(accessions),
        "filingDate":["2026-06-28"] * count,
        "reportDate":["2026-06-27"] * count,
        "form":list(forms),
        "items":["8.01,9.01"] * count,
        "primaryDocument":["fixture.htm"] * count,
        "primaryDocDescription":["Current report"] * count,
    }}}


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class SecEdgarTests(unittest.TestCase):
    def test_parse_filters_forms_and_keeps_parallel_rows(self):
        records = parse_submissions(submissions(), "1045810")
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(("8.01","9.01"), record.items)
        self.assertEqual("0001045810-26-000060", record.accession)
        self.assertEqual("Other events; Financial statements and exhibits", record.title)

    def test_parse_shape_fails_closed_but_bad_row_is_skipped(self):
        with self.assertRaises(SecEdgarError): parse_submissions(None, "1")
        with self.assertRaises(SecEdgarError): parse_submissions({}, "1")
        mismatch = submissions(); mismatch["filings"]["recent"]["items"].pop()
        with self.assertRaises(SecEdgarError): parse_submissions(mismatch, "1")
        bad_row = submissions(accessions=("", "valid"), forms=("8-K","8-K"))
        self.assertEqual(("valid",), tuple(item.accession for item in parse_submissions(bad_row, "1")))

    def test_titles_and_archive_url_are_exact(self):
        self.assertEqual("Results of operations and financial condition", title_for_items(("2.02",)))
        self.assertEqual("Other events; Financial statements and exhibits", title_for_items(("8.01","9.01")))
        self.assertEqual(GENERIC_TITLE, title_for_items(("6.99",)))
        self.assertEqual(
            "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000060/nvda-20260628.htm",
            build_filing_url("1045810", "0001045810-26-000060", "nvda-20260628.htm"),
        )

    def test_fetch_merges_ciks_dedupes_accessions_and_sends_headers(self):
        first = submissions(accessions=("shared","legacy"), forms=("8-K","8-K"))
        second = submissions(accessions=("shared","new"), forms=("8-K","8-K"))
        session = Session((Response(first),Response(second)))
        records = fetch_8k_filings(("34088","2115436"), contact="MNE test test@example.com", session=session, as_of=date(2026,8,6), since=date(2026,1,1))
        self.assertEqual({"shared","legacy","new"}, {item.accession for item in records})
        self.assertEqual("MNE test test@example.com", session.calls[0][1]["headers"]["User-Agent"])
        self.assertEqual("gzip, deflate", session.calls[0][1]["headers"]["Accept-Encoding"])
        self.assertIn("CIK0000034088.json", session.calls[0][0])

    def test_config_loader_and_validation_fail_closed(self):
        valid = {"version":"1.0.0","contact":"MNE test test@example.com","ciks":{"XOM":["34088","2115436"]}}
        self.assertEqual(("34088","2115436"), validate_sec_edgar_map(valid).as_dict()["XOM"])
        cases = (
            {**valid,"version":"one"},
            {"version":"1.0.0","ciks":valid["ciks"]},
            {**valid,"ciks":{"XOM":"34088"}},
            {**valid,"ciks":{"XOM":[]}},
            {**valid,"ciks":{"XOM":[34088]}},
        )
        for fixture in cases:
            with self.subTest(fixture=fixture), self.assertRaises(SecEdgarError): validate_sec_edgar_map(fixture)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SecEdgarError): load_sec_edgar_map(Path(directory) / "missing.json")

    def test_fetch_failure_is_honest_empty(self):
        session = Session((RuntimeError("network unavailable"),))
        self.assertEqual((), fetch_8k_filings(("1045810",), contact="MNE test test@example.com", session=session))


if __name__ == "__main__":
    unittest.main()
