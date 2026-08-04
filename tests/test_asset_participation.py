import unittest
from datetime import datetime, timedelta, timezone

from mne.asset_exploration import load_asset_registry, load_narrative_asset_map
from mne.asset_participation import classify_assets_for_run


NOW = datetime(2026, 8, 4, 16, tzinfo=timezone.utc)


def record(change, observed_at=None):
    return {"pct_change": change, "observed_at": (observed_at or NOW - timedelta(hours=1)).isoformat()}


class AssetParticipationTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_asset_registry()
        self.asset_map = load_narrative_asset_map(registry=self.registry)

    def classify(self, ticker, change, narrative="AI / Tech Growth"):
        result = classify_assets_for_run({"market_snapshot": {ticker: record(change)}}, self.asset_map, self.registry, narrative, now=NOW)
        return result["assets"][ticker]

    def test_all_six_states_are_hand_derivable(self):
        cases = (("NVDA", 1.0, "STRONG"), ("NVDA", .25, "PARTICIPATING"), ("NVDA", .1, "EMERGING"), ("NVDA", 0, "MUTED"), ("NVDA", -.25, "CONTRADICTING"))
        for ticker, change, expected in cases:
            with self.subTest(expected=expected): self.assertEqual(expected, self.classify(ticker, change)["participation_state"])
        self.assertEqual("UNAVAILABLE", classify_assets_for_run({"market_snapshot": {}}, self.asset_map, self.registry, "AI / Tech Growth", now=NOW)["assets"]["NVDA"]["participation_state"])

    def test_offset_role_can_reach_strong_using_its_expected_direction(self):
        row = self.classify("VIX", -1.2)
        self.assertEqual("STRONG", row["participation_state"])

    def test_macro_pressure_expected_directions_are_explicit(self):
        snapshot = {"VIX": record(1.1), "DXY": record(.5), "QQQ": record(-.5), "NVDA": record(.5)}
        rows = classify_assets_for_run({"market_snapshot": snapshot}, self.asset_map, self.registry, "Macro Pressure", now=NOW)["assets"]
        self.assertEqual(("STRONG", "PARTICIPATING", "PARTICIPATING", "CONTRADICTING"), tuple(rows[key]["participation_state"] for key in ("VIX", "DXY", "QQQ", "NVDA")))

    def test_missing_stale_malformed_and_unsupported_fail_closed(self):
        stale = NOW - timedelta(days=5)
        snapshots = ({}, {"NVDA": record(2, stale)}, {"NVDA": record("bad")}, {"NVDA": {"pct_change": 2}}, {"SPY": record(5)})
        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot):
                rows = classify_assets_for_run({"market_snapshot": snapshot}, self.asset_map, self.registry, "AI / Tech Growth", now=NOW)["assets"]
                self.assertEqual("UNAVAILABLE", rows["NVDA"]["participation_state"])

    def test_classifier_uses_shared_calendar_without_fetching(self):
        source = __import__("pathlib").Path("mne/asset_participation.py").read_text()
        self.assertIn("from mne.market_calendar import classify_session_freshness", source)
        self.assertNotIn("yfinance", source)
        self.assertNotIn("requests", source)

    def test_sector_etf_falls_back_to_persisted_sector_slug(self):
        mapping_type = type(next(iter(dict(self.asset_map.narratives).values()))[0])
        direct_sector_map = type(self.asset_map)(self.asset_map.version, (("AI / Tech Growth", (mapping_type("XLK", "PRIMARY", "Technology sector.", True, "UP"),)),))
        rows = classify_assets_for_run({"market_snapshot": {"technology": record(.5)}}, direct_sector_map, self.registry, "AI / Tech Growth", now=NOW)["assets"]
        self.assertEqual("PARTICIPATING", rows["XLK"]["participation_state"])

    def test_company_assets_do_not_reuse_sector_slug_records(self):
        rows = classify_assets_for_run({"market_snapshot": {"technology": record(1.5)}}, self.asset_map, self.registry, "AI / Tech Growth", now=NOW)["assets"]
        self.assertEqual("UNAVAILABLE", rows["MSFT"]["participation_state"])

    def test_new_tickers_use_only_their_own_persisted_records(self):
        fixtures = {
            "AI / Tech Growth": {"MSFT": record(.5)},
            "Energy / Commodities": {"XOM": record(.5), "CVX": record(.5), "SLB": record(.5)},
            "Macro Pressure": {"TLT": record(-.5), "HYG": record(-.5)},
        }
        for narrative, snapshot in fixtures.items():
            with self.subTest(narrative=narrative):
                rows = classify_assets_for_run({"market_snapshot": snapshot}, self.asset_map, self.registry, narrative, now=NOW)["assets"]
                for ticker in snapshot:
                    self.assertEqual("PARTICIPATING", rows[ticker]["participation_state"])

    def test_old_snapshot_keeps_all_six_new_assets_unavailable(self):
        for narrative, tickers in {
            "AI / Tech Growth": ("MSFT",),
            "Energy / Commodities": ("XOM", "CVX", "SLB"),
            "Macro Pressure": ("TLT", "HYG"),
        }.items():
            rows = classify_assets_for_run({"market_snapshot": {}}, self.asset_map, self.registry, narrative, now=NOW)["assets"]
            self.assertTrue(all(rows[ticker]["participation_state"] == "UNAVAILABLE" for ticker in tickers))


if __name__ == "__main__": unittest.main()
