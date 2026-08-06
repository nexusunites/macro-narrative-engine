import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from mne.asset_price_history import (
    AssetPriceHistoryError,
    Candle,
    backfill_daily_candles,
    load_asset_price_history,
    load_asset_price_history_or_empty,
    upsert_daily_candle,
    validate_asset_price_history,
)
from mne.market_context import get_market_snapshot, latest_daily_candle


class _ILoc:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, index):
        return self.rows[index]


class _Series:
    def __init__(self, values):
        self.iloc = _ILoc(values)


class FakeFrame:
    def __init__(self, rows, dates=None):
        self.rows = rows
        self.empty = not rows
        self.iloc = _ILoc(rows)
        self.dates = dates or []
        self.index = self.dates

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, key):
        return _Series([row[key] for row in self.rows])

    def iterrows(self):
        return iter(zip(self.dates, self.rows))


def valid_history(**overrides):
    data = {
        "ticker": "NVDA",
        "version": "1.0.0",
        "candles": {
            "2026-08-05": {"open": 1.0, "high": 3.0, "low": 0.5, "close": 2.0}
        },
    }
    data.update(overrides)
    return data


class AssetPriceHistoryTests(unittest.TestCase):
    def test_loads_frozen_records_and_missing_is_honestly_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            path.write_text(json.dumps(valid_history()), encoding="utf-8")
            history = load_asset_price_history("NVDA", path)
            self.assertEqual(history.candles[0].close, 2.0)
            with self.assertRaises(FrozenInstanceError):
                history.candles[0].close = 4.0
            empty = load_asset_price_history_or_empty("NVDA", Path(directory) / "missing.json")
            self.assertEqual(empty.candles, ())

    def test_schema_failures_are_closed(self):
        base_candle = {"open": 1.0, "high": 3.0, "low": 0.5, "close": 2.0}
        cases = [
            (valid_history(version="v1"), "version"),
            (valid_history(candles=[]), "candles"),
            (valid_history(candles={"08/05/2026": base_candle}), r"candles\[08/05/2026\].date"),
            (valid_history(candles={"2026-08-05": {"open": 1.0}}), r"candles\[2026-08-05\].high"),
            (valid_history(candles={"2026-08-05": {**base_candle, "extra": 1.0}}), r"candles\[2026-08-05\].extra"),
            (valid_history(candles={"2026-08-05": {**base_candle, "open": 1}}), r"candles\[2026-08-05\].open"),
            (valid_history(candles={"2026-08-05": {**base_candle, "high": 0.1}}), r"candles\[2026-08-05\].high"),
        ]
        for data, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(AssetPriceHistoryError, message):
                validate_asset_price_history(data)

    def test_loader_wraps_io_and_json_errors(self):
        with self.assertRaises(AssetPriceHistoryError):
            load_asset_price_history("NVDA", "/definitely/missing/NVDA.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(AssetPriceHistoryError):
                load_asset_price_history("NVDA", path)

    def test_upsert_is_idempotent_sorted_and_byte_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            upsert_daily_candle("NVDA", Candle("2026-08-06", 1.0, 2.0, 0.5, 1.5), path)
            upsert_daily_candle("NVDA", Candle("2026-08-05", 3.0, 4.0, 2.0, 3.5), path)
            upsert_daily_candle("NVDA", Candle("2026-08-06", 5.0, 6.0, 4.0, 5.5), path)
            first = path.read_bytes()
            history = load_asset_price_history("NVDA", path)
            self.assertEqual([item.date for item in history.candles], ["2026-08-05", "2026-08-06"])
            self.assertEqual(history.candles[-1].open, 5.0)
            upsert_daily_candle("NVDA", history.candles[-1], path)
            self.assertEqual(path.read_bytes(), first)

    def test_extracts_rounded_candle_and_preserves_snapshot_shape(self):
        rows = [
            {"Open": 1.111, "High": 2.222, "Low": 0.555, "Close": 1.5},
            {"Open": 2.345, "High": 3.456, "Low": 1.234, "Close": 3.001},
        ]
        today = date(2026, 8, 6)
        frame = FakeFrame(rows, [datetime(2026, 8, 5), datetime(2026, 8, 6)])
        self.assertEqual(
            latest_daily_candle(frame, today=today),
            {"open": 2.35, "high": 3.46, "low": 1.23, "close": 3.0},
        )
        self.assertIsNone(latest_daily_candle(FakeFrame([])))
        self.assertIsNone(latest_daily_candle(FakeFrame(rows[:1])))
        with patch("mne.market_context.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = frame
            snapshot = get_market_snapshot(
                {"NVDA": "NVDA"}, observed_at="stamp", today=today
            )["NVDA"]
        self.assertEqual(
            set(snapshot),
            {"ticker", "latest_close", "pct_change", "observed_at", "candle"},
        )

    def test_snapshot_omits_candle_when_latest_session_is_not_today(self):
        today = date(2026, 8, 6)
        frame = FakeFrame(
            [
                {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5},
                {"Open": 2.0, "High": 3.0, "Low": 1.5, "Close": 2.5},
            ],
            [datetime(2026, 8, 4), datetime(2026, 8, 5)],
        )
        with patch("mne.market_context.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = frame
            snapshot = get_market_snapshot(
                {"NVDA": "NVDA"}, observed_at="stamp", today=today
            )["NVDA"]
        self.assertEqual(
            set(snapshot),
            {"ticker", "latest_close", "pct_change", "observed_at"},
        )

    @patch("mne.asset_price_history.yf.Ticker")
    def test_backfill_skips_existing_and_records_provenance(self, ticker):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NVDA.json"
            upsert_daily_candle("NVDA", Candle("2026-08-05", 9.0, 10.0, 8.0, 9.5), path)
            ticker.return_value.history.return_value = FakeFrame(
                [
                    {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5},
                    {"Open": 3.0, "High": 4.0, "Low": 2.0, "Close": 3.5},
                ],
                [datetime(2026, 8, 5), datetime(2026, 8, 6)],
            )
            self.assertEqual(backfill_daily_candles({"NVDA": "NVDA"}, directory), (1, 1))
            ticker.return_value.history.assert_called_once_with(period="6mo")
            history = load_asset_price_history("NVDA", path)
            self.assertEqual(history.candles[0].open, 9.0)
            self.assertEqual(history.source, "yfinance")
            self.assertEqual(history.backfill_period, "6mo")


if __name__ == "__main__":
    unittest.main()
