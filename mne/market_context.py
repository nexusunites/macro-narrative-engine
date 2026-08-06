from datetime import date

import yfinance as yf


def latest_daily_candle(data, today=None):
    """Return the latest complete OHLC row, rounded for persistence."""
    if data is None or getattr(data, "empty", True) or len(data) < 2:
        return None

    try:
        if data.index[-1].date() != (today or date.today()):
            return None
        row = data.iloc[-1]
        values = {field: round(float(row[column]), 2) for field, column in (
            ("open", "Open"),
            ("high", "High"),
            ("low", "Low"),
            ("close", "Close"),
        )}
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        return None
    return values


def get_market_snapshot(tickers, observed_at=None, today=None):
    snapshot = {}

    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period="5d")
        except Exception:
            snapshot[name] = None
            continue

        if data.empty or len(data) < 2:
            snapshot[name] = None
            continue

        latest_close = data["Close"].iloc[-1]
        previous_close = data["Close"].iloc[-2]

        pct_change = ((latest_close - previous_close) / previous_close) * 100

        snapshot[name] = {
            "ticker": ticker,
            "latest_close": round(float(latest_close), 2),
            "pct_change": round(float(pct_change), 2),
            "observed_at": observed_at,
        }
        candle = latest_daily_candle(data, today=today)
        if candle is not None:
            snapshot[name]["candle"] = candle

    return snapshot


def classify_market_move(pct_change):
    if pct_change is None:
        return "UNKNOWN"

    if pct_change >= 1.0:
        return "STRONG UP"
    elif pct_change >= 0.25:
        return "UP"
    elif pct_change <= -1.0:
        return "STRONG DOWN"
    elif pct_change <= -0.25:
        return "DOWN"
    else:
        return "FLAT"
