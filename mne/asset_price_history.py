"""Validated, deterministic daily OHLC persistence for registry assets."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yfinance as yf

from config import DATA_DIR


LOGGER = logging.getLogger(__name__)
ASSET_PRICES_DIR = DATA_DIR / "asset_prices"
STORE_VERSION = "1.0.0"
BACKFILL_PERIOD = "6mo"
SOURCE = "yfinance"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_CANDLE_FIELDS = ("open", "high", "low", "close")


class AssetPriceHistoryError(ValueError):
    """Raised when persisted asset price history is unavailable or invalid."""


@dataclass(frozen=True)
class Candle:
    date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class AssetPriceHistory:
    ticker: str
    version: str
    candles: tuple[Candle, ...]
    source: str | None = None
    backfill_period: str | None = None


def _validate_date(value: Any, location: str) -> str:
    if not isinstance(value, str):
        raise AssetPriceHistoryError(f"{location}.date must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AssetPriceHistoryError(f"{location}.date must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise AssetPriceHistoryError(f"{location}.date must use YYYY-MM-DD")
    return value


def validate_asset_price_history(data: Any) -> AssetPriceHistory:
    if not isinstance(data, dict):
        raise AssetPriceHistoryError("asset price history must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise AssetPriceHistoryError("version must use MAJOR.MINOR.PATCH semantic versioning")
    ticker = data.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise AssetPriceHistoryError("ticker must be a non-empty string")
    raw_candles = data.get("candles")
    if not isinstance(raw_candles, dict):
        raise AssetPriceHistoryError("candles must be an object")

    candles = []
    for candle_date, raw_candle in raw_candles.items():
        location = f"candles[{candle_date}]"
        _validate_date(candle_date, location)
        if not isinstance(raw_candle, dict):
            raise AssetPriceHistoryError(f"{location} must be an object")
        if set(raw_candle) != set(_CANDLE_FIELDS):
            missing = next((field for field in _CANDLE_FIELDS if field not in raw_candle), None)
            field = missing or next(iter(sorted(set(raw_candle) - set(_CANDLE_FIELDS))))
            raise AssetPriceHistoryError(f"{location}.{field} is not an exact candle field")
        for field in _CANDLE_FIELDS:
            if not isinstance(raw_candle[field], float):
                raise AssetPriceHistoryError(f"{location}.{field} must be a float")
        if raw_candle["high"] < raw_candle["low"]:
            raise AssetPriceHistoryError(f"{location}.high must be greater than or equal to low")
        candles.append(Candle(date=candle_date, **raw_candle))

    source = data.get("source")
    if source is not None and (not isinstance(source, str) or not source.strip()):
        raise AssetPriceHistoryError("source must be a non-empty string")
    backfill_period = data.get("backfill_period")
    if backfill_period is not None and (
        not isinstance(backfill_period, str) or not backfill_period.strip()
    ):
        raise AssetPriceHistoryError("backfill_period must be a non-empty string")
    return AssetPriceHistory(
        ticker=ticker.strip(),
        version=version,
        candles=tuple(sorted(candles, key=lambda candle: candle.date)),
        source=source,
        backfill_period=backfill_period,
    )


def load_asset_price_history(
    ticker: str,
    path: str | Path | None = None,
) -> AssetPriceHistory:
    """Load a required ticker file; missing, unreadable, and corrupt files fail closed."""
    price_path = Path(path) if path is not None else ASSET_PRICES_DIR / f"{ticker}.json"
    try:
        with price_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetPriceHistoryError(f"unable to load asset price history: {exc}") from exc
    history = validate_asset_price_history(data)
    if history.ticker != ticker:
        raise AssetPriceHistoryError("ticker does not match requested asset")
    return history


def load_asset_price_history_or_empty(
    ticker: str,
    path: str | Path | None = None,
) -> AssetPriceHistory:
    """Load history, treating only a missing file as an honest empty store."""
    price_path = Path(path) if path is not None else ASSET_PRICES_DIR / f"{ticker}.json"
    if not price_path.exists():
        return AssetPriceHistory(ticker=ticker, version=STORE_VERSION, candles=())
    return load_asset_price_history(ticker, price_path)


def _serialize(history: AssetPriceHistory) -> dict:
    data = {
        "ticker": history.ticker,
        "version": history.version,
        "candles": {
            candle.date: {
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
            }
            for candle in sorted(history.candles, key=lambda item: item.date)
        },
    }
    if history.source is not None:
        data["source"] = history.source
    if history.backfill_period is not None:
        data["backfill_period"] = history.backfill_period
    return data


def _write(history: AssetPriceHistory, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_serialize(history), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def upsert_daily_candle(
    ticker: str,
    candle: Candle,
    path: str | Path | None = None,
) -> None:
    price_path = Path(path) if path is not None else ASSET_PRICES_DIR / f"{ticker}.json"
    current = load_asset_price_history_or_empty(ticker, price_path)
    candles = {item.date: item for item in current.candles}
    candles[candle.date] = candle
    _write(
        AssetPriceHistory(
            ticker=ticker,
            version=STORE_VERSION,
            candles=tuple(candles.values()),
            source=current.source or SOURCE,
            backfill_period=current.backfill_period,
        ),
        price_path,
    )


def backfill_daily_candles(
    tickers: dict[str, str],
    prices_dir: str | Path = ASSET_PRICES_DIR,
) -> tuple[int, int]:
    """Backfill six months once per ticker without replacing captured dates."""
    created = 0
    skipped = 0
    prices_dir = Path(prices_dir)
    for ticker in sorted(set(tickers.values())):
        path = prices_dir / f"{ticker}.json"
        current = load_asset_price_history_or_empty(ticker, path)
        candles = {item.date: item for item in current.candles}
        try:
            data = yf.Ticker(ticker).history(period=BACKFILL_PERIOD)
        except Exception as exc:
            LOGGER.warning("Unable to backfill daily candles for %s: %s", ticker, exc)
            continue
        if data is None or getattr(data, "empty", True):
            continue
        for index, row in data.iterrows():
            candle_date = index.date().isoformat()
            if candle_date in candles:
                skipped += 1
                LOGGER.info("Skipped existing daily candle: %s %s", ticker, candle_date)
                continue
            try:
                candle = Candle(
                    date=candle_date,
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                )
            except (KeyError, TypeError, ValueError):
                continue
            candles[candle_date] = candle
            created += 1
            LOGGER.info("Created daily candle: %s %s", ticker, candle_date)
        _write(
            AssetPriceHistory(
                ticker=ticker,
                version=STORE_VERSION,
                candles=tuple(candles.values()),
                source=SOURCE,
                backfill_period=BACKFILL_PERIOD,
            ),
            path,
        )
    return created, skipped
