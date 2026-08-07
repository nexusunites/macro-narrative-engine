import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from mne.asset_events import (
    AssetEvent,
    AssetEventsError,
    load_asset_events,
    load_asset_events_or_empty,
    refresh_asset_event_feeds,
    select_upcoming_asset_catalysts,
    validate_asset_event_feed,
    write_asset_events,
)
from mne.company_catalysts import _historical_earnings_dates_from_get_earnings_dates


class FakeFrame:
    empty = False

    def __init__(self, index):
        self.index = index


class AssetEventTests(unittest.TestCase):
    def test_fail_closed_triad_and_exact_no_news_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            self.assertEqual((), load_asset_events_or_empty("NVDA", path).events)
            with self.assertRaises(AssetEventsError):
                load_asset_events("NVDA", path)
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(AssetEventsError):
                load_asset_events_or_empty("NVDA", path)
        valid = {"ticker":"NVDA","version":"1.0.0","events":[]}
        for event_type in ("news", "NEWS", ""):
            fixture = {**valid, "events":[{"date":"2026-08-05","type":event_type,"title":"Title","blurb":"Blurb","detail":"Detail","source":"Source"}]}
            with self.subTest(event_type=event_type), self.assertRaises(AssetEventsError):
                validate_asset_event_feed(fixture)

    def test_write_load_is_deterministic_and_ticker_checked(self):
        events = [
            AssetEvent("2026-08-05","macro","CPI","B","D","S"),
            AssetEvent("2026-07-01","earnings","NVDA Earnings","B","D","S"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            write_asset_events("NVDA", events, path)
            first = path.read_bytes()
            write_asset_events("NVDA", list(reversed(events)), path)
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(("2026-07-01","2026-08-05"), tuple(item.date for item in load_asset_events("NVDA", path).events))
            with self.assertRaises(AssetEventsError):
                load_asset_events("MSFT", path)

    def test_historical_earnings_extractor_keeps_only_past_unique_dates(self):
        ticker = SimpleNamespace(get_earnings_dates=lambda: FakeFrame([
            "2026-08-07", "2026-08-05", "2026-08-05", "2026-07-01"
        ]))
        self.assertEqual(
            (date(2026,7,1), date(2026,8,5)),
            _historical_earnings_dates_from_get_earnings_dates(ticker, date(2026,8,6)),
        )

    def test_refresh_persists_earnings_and_only_story_relevant_macro(self):
        asset_map = SimpleNamespace(narratives=(("AI / Tech Growth", (SimpleNamespace(ticker="NVDA"),)),))
        stories = SimpleNamespace(stories=(SimpleNamespace(group="AI / Tech Growth", catalyst_names=("CPI",)),))
        calendar = [
            {"date":"2026-07-14","scheduled_at":"2026-07-14T08:30:00-04:00","name":"CPI report","source_agency":"BLS","source_url":"https://example.test/cpi"},
            {"date":"2026-07-15","scheduled_at":"2026-07-15T08:30:00-04:00","name":"Retail Sales","source":"Calendar"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            calendar_path = Path(directory) / "macro.json"
            calendar_path.write_text(json.dumps(calendar), encoding="utf-8")
            written = refresh_asset_event_feeds(
                {"NVDA":"NVDA"}, asset_map, stories, as_of=date(2026,8,6),
                calendar_file=calendar_path, events_dir=directory,
                earnings_loader=lambda symbol, as_of: (date(2026,5,20),),
            )
            feed = load_asset_events("NVDA", Path(directory) / "NVDA.json")
        self.assertEqual(1, written)
        self.assertEqual(("earnings","macro"), tuple(item.type for item in feed.events))
        self.assertNotIn("Retail Sales", {item.title for item in feed.events})

    def test_upcoming_selection_preserves_real_macro_timestamp(self):
        stories = SimpleNamespace(stories=(SimpleNamespace(group="Macro Pressure", catalyst_names=("FOMC",)),))
        calendar = [{"date":"2026-08-08","scheduled_at":"2026-08-08T14:00:00-04:00","name":"FOMC Decision"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro.json"; path.write_text(json.dumps(calendar), encoding="utf-8")
            selected = select_upcoming_asset_catalysts(
                [{"date":"2026-08-08","name":"FOMC Decision","days_until":2}],
                "Macro Pressure", "TLT", stories, calendar_file=path,
            )
        self.assertEqual("2026-08-08T14:00:00-04:00", selected[0]["scheduled_at"])
        self.assertEqual("macro", selected[0]["type"])


if __name__ == "__main__":
    unittest.main()
