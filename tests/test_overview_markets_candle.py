import unittest
from unittest.mock import patch

import dashboard
from main import ASSET_EXPANSION_TICKERS
from mne.asset_price_history import AssetPriceHistory, Candle


class OverviewMarketsCandleTests(unittest.TestCase):
    def setUp(self):
        self.instruments = (
            {"asset": "VIX", "label": "Volatility", "role": "primary"},
            {"asset": "QQQ", "label": "Nasdaq 100", "role": "offset"},
        )
        self.history = AssetPriceHistory(
            ticker="^VIX",
            version="1.0.0",
            candles=(
                Candle(date="2026-08-13", open=15.0, high=17.0, low=14.0, close=16.0),
                Candle(date="2026-08-14", open=16.0, high=16.5, low=13.0, close=14.0),
            ),
        )

    @patch("dashboard.load_asset_price_history_or_empty")
    def test_investigation_output_is_exact_after_shared_helper_extraction(self, load):
        load.return_value = self.history

        result = dashboard._build_lead_instrument_candle(
            {"market_expression": {"instruments": self.instruments}},
            "group:Macro Pressure",
        )

        self.assertEqual(load.call_args.args, ("^VIX",))
        self.assertEqual(
            result,
            {
                "ticker": "VIX",
                "label": "Volatility",
                "symbol": "^VIX",
                "available": True,
                "href": "/research/group:Macro Pressure/sectors",
                "candles": (
                    {"x": 124.0, "wick_y": 8.0, "wick_height": 93.0, "body_x": 66.0, "body_y": 39.0, "body_width": 116.0, "body_height": 31.0, "direction": "up"},
                    {"x": 356.0, "wick_y": 23.5, "wick_height": 108.5, "body_x": 298.0, "body_y": 39.0, "body_width": 116.0, "body_height": 62.0, "direction": "down"},
                ),
            },
        )

    @patch("dashboard.load_asset_price_history_or_empty")
    def test_overview_uses_primary_instrument_and_dominant_drill_path(self, load):
        load.return_value = self.history

        result = dashboard.build_overview_markets_candle(
            self.instruments, "group:Macro Pressure"
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["ticker"], "VIX")
        self.assertEqual(result["symbol"], "^VIX")
        self.assertEqual(result["href"], "/research/group:Macro Pressure/sectors")

    @patch("dashboard.load_asset_price_history_or_empty")
    def test_overview_preserves_honest_missing_series(self, load):
        load.return_value = AssetPriceHistory(
            ticker="^VIX", version="1.0.0", candles=()
        )

        result = dashboard.build_overview_markets_candle(
            self.instruments, "group:Macro Pressure"
        )

        self.assertFalse(result["available"])
        self.assertEqual(result["candles"], ())

    def test_volatility_and_dollar_index_have_real_store_symbols(self):
        self.assertEqual(ASSET_EXPANSION_TICKERS["VIX"], "^VIX")
        self.assertEqual(ASSET_EXPANSION_TICKERS["DXY"], "DX-Y.NYB")


if __name__ == "__main__":
    unittest.main()
