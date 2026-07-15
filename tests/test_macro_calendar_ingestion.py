import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from mne.calendar_sources.base import SourceResult
from mne.calendar_sources.bls import BLS_CALENDAR_URL, BLS_ICS_URL, fetch_events as fetch_bls_events, parse_bls_ics
from mne.calendar_sources.fred import (
    FRED_API_KEY_ENV_VAR,
    FRED_BLS_RELEASES,
    FRED_RELEASE_DATES_URL,
    FRED_TARGETED_RELEASE_DATES_URL,
    TARGETED_SOURCE_VARIANT,
    get_fred_bls_calendar_events,
    parse_fred_release_dates,
)
from mne.calendar_sources.bea import parse_bea_schedule_html
from mne.calendar_sources.eia import parse_eia_natural_gas_html, parse_eia_petroleum_html
from mne.calendar_sources.federal_reserve import parse_fomc_html
from mne.macro_calendar_ingestion import (
    auto_refresh_macro_calendar_enabled,
    refresh_macro_calendar,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} test response")


class ExplodingGet:
    def __call__(self, *_args, **_kwargs):
        raise TimeoutError("timed out")


class MacroCalendarIngestionTests(unittest.TestCase):
    def test_bls_full_ics_supported_mappings_and_unsupported_ignored(self):
        events = parse_bls_ics(fixture("calendar_bls_full.ics"))
        event_types = {event["event_type"] for event in events}
        self.assertEqual(
            event_types,
            {
                "cpi",
                "ppi",
                "employment_situation",
                "jolts",
                "employment_cost_index",
                "import_export_prices",
            },
        )
        self.assertNotIn("state_employment", event_types)

    def test_bls_cpi_regression_and_deduplication(self):
        events = parse_bls_ics(fixture("calendar_bls.ics"))
        cpi = [event for event in events if event["event_type"] == "cpi"]
        self.assertEqual(len(cpi), 1)
        self.assertEqual(cpi[0]["date"], "2026-07-14")
        self.assertEqual(cpi[0]["time"], "08:30")
        self.assertEqual(cpi[0]["importance"], "red")
        self.assertEqual(cpi[0]["name"], "Consumer Price Index")

    def test_bls_critical_cpi_regression_from_ical_suffix(self):
        events = parse_bls_ics(fixture("calendar_bls_full.ics"))
        cpi = [event for event in events if event["event_type"] == "cpi"][0]
        self.assertEqual(cpi["date"], "2026-07-14")
        self.assertEqual(cpi["time"], "08:30")
        self.assertEqual(cpi["timezone"], "America/New_York")
        self.assertEqual(cpi["event_type"], "cpi")
        self.assertEqual(cpi["importance"], "red")
        self.assertEqual(cpi["source_uid"], "bls-cpi-20260714@example")
        self.assertIn("Consumer Price Index", cpi["source_description"])

    def test_bls_folded_ical_lines(self):
        events = parse_bls_ics(fixture("calendar_bls_folded.ics"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "cpi")
        self.assertEqual(events[0]["date"], "2026-07-14")

    def test_bls_date_only_event_does_not_invent_time(self):
        events = parse_bls_ics(fixture("calendar_bls_date_only.ics"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "ppi")
        self.assertEqual(events[0]["date"], "2026-07-15")
        self.assertTrue(events[0]["time_missing"])
        self.assertNotIn("time", events[0])

    def test_bls_empty_or_invalid_ics_does_not_parse_events(self):
        self.assertEqual(parse_bls_ics(fixture("calendar_bls_empty.ics")), [])
        self.assertEqual(parse_bls_ics("not a calendar"), [])

    def test_bls_ical_success_avoids_html_fallback(self):
        calls = []

        def get(url, **_kwargs):
            calls.append(url)
            return FakeResponse(fixture("calendar_bls_full.ics"))

        result = fetch_bls_events(get=get, loaded_at="2026-07-14T00:00:00-04:00")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_variant, "official_ical")
        self.assertEqual(calls, [BLS_ICS_URL])
        self.assertGreaterEqual(len(result.events), 6)

    def test_bls_ical_failure_invokes_html_fallback(self):
        calls = []

        def get(url, **_kwargs):
            calls.append(url)
            if url == BLS_ICS_URL:
                return FakeResponse("", status_code=403)
            return FakeResponse(fixture("calendar_bls_html.html"))

        result = fetch_bls_events(get=get, loaded_at="2026-07-14T00:00:00-04:00")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_variant, "official_html_fallback")
        self.assertEqual(calls, [BLS_ICS_URL, BLS_ICS_URL, BLS_CALENDAR_URL])
        self.assertTrue(any(event["event_type"] == "cpi" for event in result.events))

    def test_bls_both_sources_fail_records_attempts(self):
        def get(_url, **_kwargs):
            return FakeResponse("", status_code=403)

        with patch.dict("os.environ", {}, clear=True):
            result = fetch_bls_events(get=get, loaded_at="2026-07-14T00:00:00-04:00")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.events, [])
        self.assertEqual(
            [attempt["source_variant"] for attempt in result.attempts],
            ["official_ical", "official_html", TARGETED_SOURCE_VARIANT],
        )
        self.assertEqual(
            [attempt["status"] for attempt in result.attempts],
            ["failed", "failed", "skipped"],
        )

    def test_bls_repeated_refresh_has_stable_ids_without_duplicates(self):
        first = parse_bls_ics(fixture("calendar_bls_full.ics"))
        second = parse_bls_ics(fixture("calendar_bls_full.ics"))
        first_ids = [event["event_id"] for event in first]
        second_ids = [event["event_id"] for event in second]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

    def test_fred_valid_response_supported_mappings_and_unsupported_ignored(self):
        events = parse_fred_release_dates(fixture("calendar_fred_bls.json"))
        event_types = {event["event_type"] for event in events}
        self.assertEqual(
            event_types,
            {
                "cpi",
                "ppi",
                "employment_situation",
                "jolts",
                "employment_cost_index",
                "import_export_prices",
            },
        )
        self.assertEqual(len(events), 6)

    def test_fred_cpi_regression_date_only(self):
        events = parse_fred_release_dates(
            json.dumps(
                {
                    "release_dates": [
                        {
                            "release_id": 10,
                            "release_name": "Consumer Price Index",
                            "date": "2026-07-14",
                        }
                    ]
                }
            )
        )
        self.assertEqual(events[0]["date"], "2026-07-14")
        self.assertEqual(events[0]["event_type"], "cpi")
        self.assertEqual(events[0]["importance"], "red")
        self.assertEqual(events[0]["source_agency"], "BLS")
        self.assertEqual(events[0]["source_family"], "fred_release_dates_fallback")
        self.assertIsNone(events[0]["time"])
        self.assertIsNone(events[0]["scheduled_at"])
        self.assertEqual(events[0]["time_precision"], "date_only")
        self.assertEqual(events[0]["event_id"], "fred:cpi:2026-07-14")

    def test_fred_missing_api_key_is_skipped(self):
        result = get_fred_bls_calendar_events(env={})
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.events, [])
        self.assertEqual(result.source_variant, TARGETED_SOURCE_VARIANT)
        self.assertEqual(result.attempts[0]["status"], "skipped")

    def test_fred_invalid_key_and_rate_limit_are_failures_without_secret(self):
        key = "secret-test-key"

        def get(_url, **_kwargs):
            return FakeResponse(f"bad key {key}", status_code=400)

        result = get_fred_bls_calendar_events(api_key=key, get=get)

        self.assertEqual(result.status, "failed")
        self.assertNotIn(key, result.error)
        self.assertNotIn(key, json.dumps(result.to_metadata()))

        def limited(_url, **_kwargs):
            return FakeResponse("rate limited", status_code=429)

        limited_result = get_fred_bls_calendar_events(api_key=key, get=limited)
        self.assertEqual(limited_result.status, "failed")

    def test_fred_timeout_malformed_and_empty_are_failures(self):
        self.assertEqual(
            get_fred_bls_calendar_events(api_key="fake", get=ExplodingGet()).status,
            "failed",
        )

        malformed = lambda *_args, **_kwargs: FakeResponse("{not json")
        self.assertEqual(
            get_fred_bls_calendar_events(api_key="fake", get=malformed).status,
            "failed",
        )

        empty = lambda *_args, **_kwargs: FakeResponse(fixture("calendar_fred_empty.json"))
        self.assertEqual(
            get_fred_bls_calendar_events(api_key="fake", get=empty).status,
            "failed",
        )

    def test_fred_targeted_cpi_release_response(self):
        result = get_fred_bls_calendar_events(
            api_key="fake",
            get=self.targeted_fred_get({"cpi": ["2026-07-14"]}),
            loaded_at="2026-07-14T00:00:00-04:00",
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_url, FRED_TARGETED_RELEASE_DATES_URL)
        cpi = [event for event in result.events if event["event_type"] == "cpi"]
        self.assertEqual(len(cpi), 1)
        self.assertEqual(cpi[0]["date"], "2026-07-14")
        self.assertIsNone(cpi[0]["time"])
        self.assertIsNone(cpi[0]["scheduled_at"])
        self.assertEqual(cpi[0]["time_precision"], "date_only")

    def test_fred_all_six_targeted_requests_succeed(self):
        calls = []
        result = get_fred_bls_calendar_events(
            api_key="fake",
            get=self.targeted_fred_get(self.all_targeted_dates(), calls=calls),
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.events), 6)
        self.assertEqual(
            {event["event_type"] for event in result.events},
            {config["event_type"] for config in FRED_BLS_RELEASES.values()},
        )
        self.assertEqual(
            [call["release_id"] for call in calls],
            [str(config["release_id"]) for config in FRED_BLS_RELEASES.values()],
        )

    def test_fred_one_targeted_request_times_out(self):
        def get(url, **kwargs):
            release_id = kwargs["params"]["release_id"]
            key = self.release_key_for_id(release_id)
            if key == "jolts":
                raise TimeoutError("Read timed out")
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)

        self.assertEqual(result.status, "partial")
        release_results = result.attempts[0]["release_results"]
        self.assertEqual(release_results["jolts"]["status"], "failed")
        self.assertGreater(len(result.events), 0)
        self.assertFalse(any(event["event_type"] == "jolts" for event in result.events))

    def test_fred_one_targeted_request_returns_malformed_json(self):
        def get(url, **kwargs):
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            if key == "ppi":
                return FakeResponse("{not json")
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.attempts[0]["release_results"]["ppi"]["status"], "failed")
        self.assertTrue(any(event["event_type"] == "cpi" for event in result.events))

    def test_fred_unexpected_release_name_fails_family_safely(self):
        def get(url, **kwargs):
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            if key == "cpi":
                payload = {
                    "release_dates": [
                        {
                            "release_id": FRED_BLS_RELEASES[key]["release_id"],
                            "release_name": "Regional Manufacturing Survey",
                            "date": "2026-07-14",
                        }
                    ]
                }
                return FakeResponse(json.dumps(payload))
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.attempts[0]["release_results"]["cpi"]["status"], "failed")
        self.assertFalse(any(event["event_type"] == "cpi" for event in result.events))

    def test_fred_invalid_key_stops_without_retrying_other_families(self):
        calls = []

        def get(url, **kwargs):
            calls.append(kwargs["params"]["release_id"])
            return FakeResponse("invalid api key", status_code=400)

        result = get_fred_bls_calendar_events(api_key="secret", get=get)

        self.assertEqual(result.status, "failed")
        self.assertEqual(calls, [str(FRED_BLS_RELEASES["cpi"]["release_id"])])
        self.assertEqual(result.attempts[0]["release_results"]["cpi"]["status"], "failed")

    def test_fred_retry_succeeds_after_one_timeout(self):
        attempts = {"cpi": 0}

        def get(url, **kwargs):
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            if key == "cpi":
                attempts["cpi"] += 1
                if attempts["cpi"] == 1:
                    raise TimeoutError("Read timed out")
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)

        self.assertEqual(result.status, "success")
        self.assertEqual(attempts["cpi"], 2)
        self.assertEqual(result.attempts[0]["release_results"]["cpi"]["status"], "success")

    def test_fred_retry_exhaustion_records_failed_family(self):
        attempts = {"cpi": 0}

        def get(url, **kwargs):
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            if key == "cpi":
                attempts["cpi"] += 1
                raise TimeoutError("Read timed out")
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)

        self.assertEqual(result.status, "partial")
        self.assertEqual(attempts["cpi"], 2)
        self.assertEqual(result.attempts[0]["release_results"]["cpi"]["status"], "failed")

    def test_fred_partial_targeted_success_preserves_successful_events(self):
        def get(url, **kwargs):
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            if key == "jolts":
                raise TimeoutError("Read timed out")
            return self.targeted_response(key, self.all_targeted_dates()[key])

        result = get_fred_bls_calendar_events(api_key="fake", get=get)
        event_types = {event["event_type"] for event in result.events}

        self.assertEqual(result.status, "partial")
        self.assertIn("cpi", event_types)
        self.assertIn("ppi", event_types)
        self.assertNotIn("jolts", event_types)

    def test_fred_targeted_output_ordering_is_deterministic(self):
        dates = self.all_targeted_dates()
        first = get_fred_bls_calendar_events(api_key="fake", get=self.targeted_fred_get(dates))
        second = get_fred_bls_calendar_events(api_key="fake", get=self.targeted_fred_get(dates))

        self.assertEqual(
            [event["event_id"] for event in first.events],
            [event["event_id"] for event in second.events],
        )
        self.assertEqual(
            [event["event_type"] for event in first.events],
            [
                "cpi",
                "ppi",
                "import_export_prices",
                "employment_cost_index",
                "jolts",
                "employment_situation",
            ],
        )

    def test_bls_preferred_live_path_does_not_call_broad_fred_releases(self):
        calls = []

        def get(url, **kwargs):
            calls.append(url)
            if url in {BLS_ICS_URL, BLS_CALENDAR_URL}:
                return FakeResponse("", status_code=403)
            if url == FRED_RELEASE_DATES_URL:
                self.fail("Broad FRED release-date catalog should not be called")
            key = self.release_key_for_id(kwargs["params"]["release_id"])
            return self.targeted_response(key, self.all_targeted_dates()[key])

        with patch.dict("os.environ", {FRED_API_KEY_ENV_VAR: "fake-key"}):
            result = fetch_bls_events(get=get)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_url, FRED_TARGETED_RELEASE_DATES_URL)
        self.assertNotIn(FRED_RELEASE_DATES_URL, calls)

    def test_fred_api_key_absent_from_diagnostics(self):
        key = "secret-test-key"

        def get(_url, **_kwargs):
            raise TimeoutError(f"Read timed out with {key}")

        result = get_fred_bls_calendar_events(api_key=key, get=get)

        self.assertEqual(result.status, "failed")
        self.assertNotIn(key, result.error)
        self.assertNotIn(key, json.dumps(result.to_metadata()))

    def test_fred_pagination_and_deterministic_ordering(self):
        calls = []

        def get(_url, **kwargs):
            calls.append(kwargs["params"]["offset"])
            offset = int(kwargs["params"]["offset"])
            if offset == 0:
                return FakeResponse(
                    json.dumps(
                        {
                            "count": 2,
                            "offset": 0,
                            "limit": 1,
                            "release_dates": [
                                {
                                    "release_name": "Producer Price Index",
                                    "date": "2026-07-15",
                                }
                            ],
                        }
                    )
                )
            return FakeResponse(
                json.dumps(
                    {
                        "count": 2,
                        "offset": 1,
                        "limit": 1,
                        "release_dates": [
                            {
                                "release_name": "Consumer Price Index",
                                "date": "2026-07-14",
                            }
                        ],
                    }
                )
            )

        events = []
        offset = 0
        while True:
            payload = get(FRED_RELEASE_DATES_URL, params={"offset": str(offset)}).text
            page_events = parse_fred_release_dates(payload)
            events.extend(page_events)
            data = json.loads(payload)
            offset += len(data.get("release_dates", []))
            if offset >= data.get("count", 0):
                break

        self.assertEqual(calls, ["0", "1"])
        events = sorted(events, key=lambda event: event["date"])
        self.assertEqual([event["event_type"] for event in events], ["cpi", "ppi"])

    def test_bls_direct_ical_success_prevents_fred_call(self):
        calls = []

        def get(url, **_kwargs):
            calls.append(url)
            if url in {FRED_RELEASE_DATES_URL, FRED_TARGETED_RELEASE_DATES_URL}:
                self.fail("FRED should not be called when BLS iCalendar succeeds")
            return FakeResponse(fixture("calendar_bls_full.ics"))

        result = fetch_bls_events(get=get)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_variant, "official_ical")
        self.assertEqual(calls, [BLS_ICS_URL])

    def test_bls_direct_html_success_prevents_fred_call(self):
        calls = []

        def get(url, **_kwargs):
            calls.append(url)
            if url == BLS_ICS_URL:
                return FakeResponse("", status_code=403)
            if url in {FRED_RELEASE_DATES_URL, FRED_TARGETED_RELEASE_DATES_URL}:
                self.fail("FRED should not be called when BLS HTML succeeds")
            return FakeResponse(fixture("calendar_bls_html.html"))

        result = fetch_bls_events(get=get)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_variant, "official_html_fallback")

    def test_bls_direct_failures_trigger_fred_success(self):
        calls = []

        def get(url, **_kwargs):
            calls.append(url)
            if url in {BLS_ICS_URL, BLS_CALENDAR_URL}:
                return FakeResponse("", status_code=403)
            key = self.release_key_for_id(_kwargs["params"]["release_id"])
            return self.targeted_response(key, self.all_targeted_dates()[key])

        with patch.dict("os.environ", {FRED_API_KEY_ENV_VAR: "fake-key"}):
            result = fetch_bls_events(get=get)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.source_variant, TARGETED_SOURCE_VARIANT)
        self.assertEqual(result.source_url, FRED_TARGETED_RELEASE_DATES_URL)
        self.assertTrue(any(event["event_type"] == "cpi" for event in result.events))
        self.assertIn(FRED_TARGETED_RELEASE_DATES_URL, calls)
        self.assertNotIn(FRED_RELEASE_DATES_URL, calls)
        self.assertEqual(
            [attempt["source_variant"] for attempt in result.attempts],
            ["official_ical", "official_html", TARGETED_SOURCE_VARIANT],
        )

    def test_fred_date_only_dedupes_against_precise_bls_event(self):
        precise = parse_bls_ics(fixture("calendar_bls_full.ics"))
        fred = parse_fred_release_dates(
            json.dumps(
                {
                    "release_dates": [
                        {
                            "release_name": "Consumer Price Index",
                            "date": "2026-07-14",
                        }
                    ]
                }
            )
        )
        merged = self._dedupe_prefer_precise(precise + fred)
        cpi = [event for event in merged if event["event_type"] == "cpi"]
        self.assertEqual(len(cpi), 1)
        self.assertEqual(cpi[0]["source_agency"], "BLS")
        self.assertIn("scheduled_at", cpi[0])

    def test_bea_personal_income_regression(self):
        events = parse_bea_schedule_html(fixture("calendar_bea.html"), year=2026)
        pce = [event for event in events if event["event_type"] == "personal_income_outlays"]
        self.assertEqual(len(pce), 1)
        self.assertEqual(pce[0]["date"], "2026-07-30")
        self.assertEqual(pce[0]["time"], "08:30")
        self.assertEqual(pce[0]["importance"], "red")

    def test_federal_reserve_fomc_events(self):
        events = parse_fomc_html(fixture("calendar_fomc.html"))
        event_types = {event["event_type"] for event in events}
        self.assertIn("fomc_policy_decision", event_types)
        self.assertIn("fomc_press_conference", event_types)
        self.assertIn("fomc_minutes", event_types)

    def test_eia_weekly_events(self):
        petroleum = parse_eia_petroleum_html(
            fixture("calendar_eia_petroleum.html"),
            as_of=date(2026, 7, 14),
        )
        natural_gas = parse_eia_natural_gas_html(
            fixture("calendar_empty.html"),
            as_of=date(2026, 7, 14),
        )
        self.assertTrue(
            any(event["event_type"] == "eia_weekly_petroleum_status" for event in petroleum)
        )
        self.assertTrue(
            any(
                event["event_type"] == "eia_weekly_natural_gas_storage"
                for event in natural_gas
            )
        )

    def test_empty_and_malformed_fixtures_do_not_parse_as_successful_events(self):
        self.assertEqual(parse_bls_ics(fixture("calendar_malformed.html")), [])
        self.assertEqual(parse_bea_schedule_html(fixture("calendar_empty.html")), [])
        self.assertEqual(parse_fomc_html(fixture("calendar_malformed.html")), [])

    def test_refresh_all_sources_succeed_writes_calendar_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "macro_calendar.json"
            metadata_path = Path(tmpdir) / "macro_calendar_metadata.json"
            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=calendar_path,
                metadata_path=metadata_path,
                source_fetchers={
                    "bls": self.success_fetcher("bls", "cpi", "Consumer Price Index"),
                    "bea": self.success_fetcher("bea", "gdp", "Gross Domestic Product"),
                },
            )

            events = json.loads(calendar_path.read_text(encoding="utf-8"))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(events), 2)
        self.assertEqual(metadata["status"], "complete")
        self.assertFalse(metadata["partial"])

    def test_refresh_partial_persists_successful_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "macro_calendar.json"
            metadata_path = Path(tmpdir) / "macro_calendar_metadata.json"
            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=calendar_path,
                metadata_path=metadata_path,
                source_fetchers={
                    "bls": self.success_fetcher("bls", "cpi", "Consumer Price Index"),
                    "bea": self.failed_fetcher("bea"),
                },
            )
            events = json.loads(calendar_path.read_text(encoding="utf-8"))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(events), 1)
        self.assertIn("bea", metadata["failed_sources"])
        self.assertTrue(metadata["partial"])

    def test_total_failure_uses_last_good_calendar_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "macro_calendar.json"
            metadata_path = Path(tmpdir) / "macro_calendar_metadata.json"
            previous = [
                self.event("bls", "cpi", "Consumer Price Index", event_id="bls:cpi:previous")
            ]
            calendar_path.write_text(json.dumps(previous), encoding="utf-8")

            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=calendar_path,
                metadata_path=metadata_path,
                source_fetchers={
                    "bls": self.failed_fetcher("bls"),
                    "bea": self.failed_fetcher("bea"),
                },
            )
            events = json.loads(calendar_path.read_text(encoding="utf-8"))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "stale_fallback")
        self.assertEqual(events, previous)
        self.assertTrue(metadata["used_previous_calendar"])

    def test_total_failure_without_last_good_does_not_create_empty_calendar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "macro_calendar.json"
            metadata_path = Path(tmpdir) / "macro_calendar_metadata.json"
            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=calendar_path,
                metadata_path=metadata_path,
                source_fetchers={"bls": self.failed_fetcher("bls")},
            )
            metadata_exists = metadata_path.exists()

        self.assertEqual(result["status"], "failed")
        self.assertFalse(calendar_path.exists())
        self.assertTrue(metadata_exists)

    def test_duplicate_events_are_stably_ordered(self):
        event = self.event("bls", "cpi", "Consumer Price Index")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=Path(tmpdir) / "macro_calendar.json",
                metadata_path=Path(tmpdir) / "macro_calendar_metadata.json",
                source_fetchers={
                    "bls": lambda **_: SourceResult(
                        "bls", "success", [event, dict(event)], "2026-07-14T00:00:00-04:00", ""
                    )
                },
            )
            events = json.loads(
                (Path(tmpdir) / "macro_calendar.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["event_count"], 1)
        self.assertEqual(len(events), 1)

    def test_all_three_bls_paths_fail_preserves_last_good_calendar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "macro_calendar.json"
            metadata_path = Path(tmpdir) / "macro_calendar_metadata.json"
            previous = [
                self.event("bls", "cpi", "Consumer Price Index", event_id="bls:cpi:previous")
            ]
            calendar_path.write_text(json.dumps(previous), encoding="utf-8")

            result = refresh_macro_calendar(
                as_of=date(2026, 7, 14),
                calendar_path=calendar_path,
                metadata_path=metadata_path,
                source_fetchers={
                    "bls": lambda **_: fetch_bls_events(
                        get=lambda *_a, **_k: FakeResponse("", status_code=403)
                    )
                },
            )
            events = json.loads(calendar_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "stale_fallback")
        self.assertEqual(events, previous)

    def test_auto_refresh_configuration_switch(self):
        with patch.dict("os.environ", {"MNE_AUTO_REFRESH_MACRO_CALENDAR": "0"}):
            self.assertFalse(auto_refresh_macro_calendar_enabled())
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(auto_refresh_macro_calendar_enabled())

    def success_fetcher(self, source, event_type, name):
        def fetcher(**kwargs):
            loaded_at = kwargs.get("loaded_at") or "2026-07-14T00:00:00-04:00"
            return SourceResult(
                source,
                "success",
                [self.event(source, event_type, name, loaded_at=loaded_at)],
                loaded_at,
                f"https://example.gov/{source}",
            )

        return fetcher

    def failed_fetcher(self, source):
        return lambda **kwargs: SourceResult(
            source,
            "failed",
            [],
            kwargs.get("loaded_at") or "2026-07-14T00:00:00-04:00",
            f"https://example.gov/{source}",
            "failed",
        )

    def event(
        self,
        source,
        event_type,
        name,
        *,
        event_id=None,
        loaded_at="2026-07-14T00:00:00-04:00",
    ):
        return {
            "event_id": event_id or f"{source}:{event_type}:2026-07-14T08:30:00-04:00",
            "date": "2026-07-14",
            "time": "08:30",
            "timezone": "America/New_York",
            "scheduled_at": "2026-07-14T08:30:00-04:00",
            "name": name,
            "event_type": event_type,
            "importance": "red",
            "source": "official_macro_calendar",
            "source_agency": source.upper(),
            "source_family": f"{source}_fixture",
            "source_url": f"https://example.gov/{source}",
            "loaded_at": loaded_at,
        }

    def all_targeted_dates(self):
        return {
            "cpi": ["2026-07-14"],
            "ppi": ["2026-07-15"],
            "employment_situation": ["2026-08-07"],
            "jolts": ["2026-08-04"],
            "employment_cost_index": ["2026-07-31"],
            "import_export_prices": ["2026-07-17"],
        }

    def release_key_for_id(self, release_id):
        release_id = int(release_id)
        for key, config in FRED_BLS_RELEASES.items():
            if config["release_id"] == release_id:
                return key
        raise AssertionError(f"Unexpected release_id {release_id}")

    def targeted_response(self, release_key, dates):
        config = FRED_BLS_RELEASES[release_key]
        return FakeResponse(
            json.dumps(
                {
                    "release_dates": [
                        {
                            "release_id": config["release_id"],
                            "release_name": config["expected_name"],
                            "date": event_date,
                        }
                        for event_date in dates
                    ]
                }
            )
        )

    def targeted_fred_get(self, date_map, *, calls=None):
        def get(url, **kwargs):
            if url == FRED_RELEASE_DATES_URL:
                raise AssertionError("Broad FRED release-date catalog should not be called")
            self.assertEqual(url, FRED_TARGETED_RELEASE_DATES_URL)
            params = kwargs["params"]
            if calls is not None:
                calls.append(dict(params))
            key = self.release_key_for_id(params["release_id"])
            dates = date_map.get(key, [])
            return self.targeted_response(key, dates)

        return get

    def _dedupe_prefer_precise(self, events):
        by_key = {}
        for event in events:
            key = (event["event_type"], event["date"])
            existing = by_key.get(key)
            if existing is None or (
                existing.get("time_precision") == "date_only"
                and event.get("time_precision") != "date_only"
            ):
                by_key[key] = event
        return sorted(by_key.values(), key=lambda event: event["event_id"])


if __name__ == "__main__":
    unittest.main()
