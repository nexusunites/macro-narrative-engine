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
from mne.sec_edgar import Edgar8K


class FakeFrame:
    empty = False

    def __init__(self, index):
        self.index = index


class AssetEventTests(unittest.TestCase):
    def test_fail_closed_triad_and_event_type_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            self.assertEqual((), load_asset_events_or_empty("NVDA", path).events)
            with self.assertRaises(AssetEventsError):
                load_asset_events("NVDA", path)
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(AssetEventsError):
                load_asset_events_or_empty("NVDA", path)
        valid = {"ticker":"NVDA","version":"1.0.0","events":[]}
        news = {**valid, "events":[{"date":"2026-08-05","type":"news","title":"Title","blurb":"Blurb","detail":"Detail","source":"Source"}]}
        self.assertEqual("news", validate_asset_event_feed(news).events[0].type)
        for event_type in ("NEWS", "", "rumor"):
            fixture = {**valid, "events":[{"date":"2026-08-05","type":event_type,"title":"Title","blurb":"Blurb","detail":"Detail","source":"Source"}]}
            with self.subTest(event_type=event_type), self.assertRaises(AssetEventsError):
                validate_asset_event_feed(fixture)

    def test_optional_url_is_strict_and_backward_compatible(self):
        base = {"ticker":"NVDA","version":"1.0.0","events":[{"date":"2026-08-05","type":"macro","title":"Title","blurb":"Blurb","detail":"Detail","source":"Source"}]}
        self.assertEqual("", validate_asset_event_feed(base).events[0].url)
        with_url = json.loads(json.dumps(base)); with_url["events"][0]["type"] = "news"; with_url["events"][0]["url"] = "https://www.sec.gov/filing"
        self.assertEqual("https://www.sec.gov/filing", validate_asset_event_feed(with_url).events[0].url)
        for extra in ({"url":" "}, {"unexpected":"value"}):
            fixture = json.loads(json.dumps(base)); fixture["events"][0].update(extra)
            with self.subTest(extra=extra), self.assertRaises(AssetEventsError):
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

    def test_news_url_round_trips_and_empty_urls_are_omitted(self):
        events = [
            AssetEvent("2026-08-05","macro","CPI","B","D","S"),
            AssetEvent("2026-08-06","news","Other events","B","D","SEC EDGAR","https://www.sec.gov/filing"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            write_asset_events("NVDA", events, path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            loaded = load_asset_events("NVDA", path)
        self.assertNotIn("url", raw["events"][0])
        self.assertEqual("https://www.sec.gov/filing", loaded.events[1].url)

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
                news_fetcher=lambda *args, **kwargs: (),
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

    def test_refresh_persists_windowed_news_for_non_earnings_ticker(self):
        asset_map = SimpleNamespace(narratives=(("Energy / Commodities", (SimpleNamespace(ticker="XOM"),)),))
        stories = SimpleNamespace(stories=())
        recent = Edgar8K("2026-07-01", ("8.01","9.01"), "acc-new", "new.htm", "https://www.sec.gov/new", "Other events; Financial statements and exhibits")
        old = Edgar8K("2025-12-01", ("8.01",), "acc-old", "old.htm", "https://www.sec.gov/old", "Other events")
        seen = {}
        def fetcher(ciks, **kwargs):
            seen.update({"ciks":ciks, **kwargs})
            return (old, recent)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "macro.json").write_text("[]", encoding="utf-8")
            (root / "sec.json").write_text(json.dumps({"version":"1.0.0","contact":"MNE test test@example.com","ciks":{"XOM":["34088","2115436"]}}), encoding="utf-8")
            refresh_asset_event_feeds(
                {"XOM":"XOM"}, asset_map, stories, as_of=date(2026,8,6),
                calendar_file=root / "macro.json", events_dir=root,
                earnings_loader=lambda *args, **kwargs: (), news_fetcher=fetcher,
                sec_edgar_map_file=root / "sec.json",
            )
            feed = load_asset_events("XOM", root / "XOM.json")
        self.assertEqual(("34088","2115436"), seen["ciks"])
        self.assertEqual(date(2026,2,4), seen["since"])
        self.assertEqual(1, len(feed.events))
        event = feed.events[0]
        self.assertEqual(("news","SEC EDGAR","https://www.sec.gov/new"), (event.type,event.source,event.url))
        self.assertIn("Accession acc-new", event.detail)
        self.assertNotIn(event.url, event.detail)

    def test_news_refresh_is_per_ticker_fail_soft_and_stacks_distinct_accessions(self):
        asset_map = SimpleNamespace(narratives=(("Energy / Commodities", (SimpleNamespace(ticker="XOM"),SimpleNamespace(ticker="CVX"))),))
        stories = SimpleNamespace(stories=())
        one = Edgar8K("2026-07-01", ("8.01",), "acc-one", "one.htm", "https://www.sec.gov/one", "Other events")
        duplicate = Edgar8K("2026-07-01", ("8.01",), "acc-one", "one.htm", "https://www.sec.gov/one", "Other events")
        two = Edgar8K("2026-07-01", ("8.01",), "acc-two", "two.htm", "https://www.sec.gov/two", "Other events")
        def fetcher(ciks, **kwargs):
            if ciks == ("93410",):
                raise RuntimeError("unavailable")
            return (one, duplicate, two)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "macro.json").write_text("[]", encoding="utf-8")
            (root / "sec.json").write_text(json.dumps({"version":"1.0.0","contact":"MNE test test@example.com","ciks":{"XOM":["34088"],"CVX":["93410"]}}), encoding="utf-8")
            refresh_asset_event_feeds(
                {"XOM":"XOM","CVX":"CVX"}, asset_map, stories, as_of=date(2026,8,6),
                calendar_file=root / "macro.json", events_dir=root,
                earnings_loader=lambda *args, **kwargs: (), news_fetcher=fetcher,
                sec_edgar_map_file=root / "sec.json",
            )
            xom = load_asset_events("XOM", root / "XOM.json")
            cvx = load_asset_events("CVX", root / "CVX.json")
        self.assertEqual(2, len(xom.events))
        self.assertEqual((), cvx.events)


if __name__ == "__main__":
    unittest.main()
