import unittest
from unittest.mock import patch

from mne.market_context import get_market_snapshot
from main import ASSET_EXPANSION_TICKERS


class _Series:
    def __init__(self, values): self.values = values
    @property
    def iloc(self): return self
    def __getitem__(self, index): return self.values[index]


class _History:
    def __init__(self, values): self.values = values; self.empty = not values
    def __len__(self): return len(self.values)
    def __getitem__(self, key): return _Series(self.values)


class MarketContextTests(unittest.TestCase):
    @patch("mne.market_context.yf.Ticker")
    def test_existing_and_sector_instruments_share_fetch_and_timestamp(self, ticker):
        ticker.return_value.history.return_value = _History([100, 102])
        result = get_market_snapshot({"QQQ": "QQQ", "technology": "XLK"}, observed_at="2026-08-04_120000")
        self.assertEqual({"QQQ", "technology"}, set(result))
        self.assertEqual("QQQ", result["QQQ"]["ticker"])
        self.assertEqual("XLK", result["technology"]["ticker"])
        self.assertEqual("2026-08-04_120000", result["technology"]["observed_at"])
        self.assertEqual(2, ticker.call_count)

    @patch("mne.market_context.yf.Ticker")
    def test_one_sector_failure_does_not_fail_snapshot(self, ticker):
        ticker.side_effect = [RuntimeError("missing"), type("T", (), {"history": lambda self, period: _History([100, 101])})()]
        result = get_market_snapshot({"technology": "XLK", "energy": "XLE"}, observed_at="stamp")
        self.assertIsNone(result["technology"])
        self.assertEqual(1.0, result["energy"]["pct_change"])

    @patch("mne.market_context.yf.Ticker")
    def test_expansion_fetch_order_timestamp_and_failure_isolation(self, ticker):
        class GoodTicker:
            def history(self, period): return _History([100, 101])
        ticker.side_effect = [GoodTicker(), RuntimeError("missing"), GoodTicker(), GoodTicker(), GoodTicker(), GoodTicker()]
        result = get_market_snapshot(ASSET_EXPANSION_TICKERS, observed_at="stamp")
        self.assertEqual(list(ASSET_EXPANSION_TICKERS), list(result))
        self.assertIsNone(result["XOM"])
        self.assertTrue(all(record["observed_at"] == "stamp" for record in result.values() if record))


if __name__ == "__main__":
    unittest.main()
