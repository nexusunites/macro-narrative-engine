import logging
from datetime import date, datetime, timedelta


logger = logging.getLogger(__name__)

MAJOR_COMPANY_CATALYSTS = {
    "NVDA": "red",
    "AAPL": "red",
    "MSFT": "red",
    "GOOGL": "red",
    "META": "red",
    "AMZN": "red",
    "AMD": "orange",
    "TSM": "orange",
    "AVGO": "orange",
    "TSLA": "orange",
}

AUTO_COMPANY_EARNINGS_SOURCE = "auto_company_earnings"
AUTO_COMPANY_EARNINGS_LOOKAHEAD_DAYS = 7


def _coerce_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _next_date_on_or_after(dates, as_of):
    upcoming_dates = [value for value in dates if value is not None and value >= as_of]
    return min(upcoming_dates) if upcoming_dates else None


def _first_earnings_date_from_get_earnings_dates(ticker, as_of):
    try:
        earnings_dates = ticker.get_earnings_dates()
    except Exception as error:
        logger.debug("Unable to fetch earnings dates: %s", error)
        return None

    if earnings_dates is None or getattr(earnings_dates, "empty", False):
        return None

    dates = []
    for value in getattr(earnings_dates, "index", []):
        parsed = _coerce_date(value)
        if parsed is not None:
            dates.append(parsed)

    return _next_date_on_or_after(dates, as_of)


def _calendar_values(calendar):
    if calendar is None:
        return []

    if isinstance(calendar, dict):
        values = []
        for key, value in calendar.items():
            if "earnings" in str(key).lower():
                if isinstance(value, (list, tuple)):
                    values.extend(value)
                else:
                    values.append(value)
        return values

    values = []
    try:
        columns = getattr(calendar, "columns", [])
        for column in columns:
            if "earnings" in str(column).lower():
                values.extend(calendar[column].dropna().tolist())
    except Exception:
        pass

    try:
        index = getattr(calendar, "index", [])
        for label in index:
            if "earnings" in str(label).lower():
                row = calendar.loc[label]
                if hasattr(row, "dropna"):
                    values.extend(row.dropna().tolist())
                else:
                    values.append(row)
    except Exception:
        pass

    return values


def _first_earnings_date_from_calendar(ticker, as_of):
    try:
        calendar = ticker.calendar
    except Exception as error:
        logger.debug("Unable to fetch earnings calendar: %s", error)
        return None

    dates = [_coerce_date(value) for value in _calendar_values(calendar)]
    return _next_date_on_or_after(dates, as_of)


def _next_earnings_date(symbol, as_of):
    try:
        import yfinance as yf
    except ImportError as error:
        logger.debug("yfinance is unavailable for auto company catalysts: %s", error)
        return None

    try:
        ticker = yf.Ticker(symbol)
    except Exception as error:
        logger.debug("Unable to initialize yfinance ticker %s: %s", symbol, error)
        return None

    earnings_date = _first_earnings_date_from_get_earnings_dates(ticker, as_of)
    if earnings_date is not None:
        return earnings_date

    return _first_earnings_date_from_calendar(ticker, as_of)


def get_auto_company_earnings_catalysts(
    as_of=None,
    lookahead_days=AUTO_COMPANY_EARNINGS_LOOKAHEAD_DAYS,
    watchlist=MAJOR_COMPANY_CATALYSTS,
):
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    end_date = as_of + timedelta(days=lookahead_days)
    catalysts = []

    for symbol, importance in watchlist.items():
        earnings_date = _next_earnings_date(symbol, as_of)
        if earnings_date is None:
            continue
        if not as_of <= earnings_date <= end_date:
            continue

        catalysts.append(
            {
                "date": earnings_date.isoformat(),
                "name": f"{symbol} Earnings",
                "importance": importance,
                "source": AUTO_COMPANY_EARNINGS_SOURCE,
                "ticker": symbol,
            }
        )

    return catalysts
