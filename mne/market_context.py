import yfinance as yf


def get_market_snapshot(tickers, observed_at=None):
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
