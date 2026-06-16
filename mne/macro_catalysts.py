import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from config import DATA_DIR


logger = logging.getLogger(__name__)

MACRO_CALENDAR_FILE = DATA_DIR / "config" / "macro_calendar.json"
AUTO_MACRO_CALENDAR_SOURCE = "auto_macro_calendar"
AUTO_MACRO_CALENDAR_LOOKAHEAD_DAYS = 7

RED_IMPORTANCE = "red"
ORANGE_IMPORTANCE = "orange"

RED_EVENT_KEYWORDS = [
    "cpi",
    "core cpi",
    "fomc rate decision",
    "fed chair press conference",
    "nonfarm payrolls",
    "non-farm payrolls",
    "nfp",
    "core pce",
    "gdp advance release",
]

ORANGE_EVENT_KEYWORDS = [
    "ppi",
    "retail sales",
    "consumer confidence",
    "jobless claims",
    "ism",
    "fed speakers",
    "fed speaker",
    "fomc minutes",
]


def _ensure_macro_calendar_file(calendar_file):
    calendar_file = Path(calendar_file)
    if calendar_file.exists():
        return True

    try:
        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text("[]\n", encoding="utf-8")
        return True
    except OSError as error:
        logger.warning("Unable to create macro calendar %s: %s", calendar_file, error)
        return False


def _repair_macro_calendar_file(calendar_file):
    try:
        Path(calendar_file).write_text("[]\n", encoding="utf-8")
    except OSError as error:
        logger.warning("Unable to repair macro calendar %s: %s", calendar_file, error)


def _load_macro_calendar(calendar_file):
    calendar_file = Path(calendar_file)
    if not _ensure_macro_calendar_file(calendar_file):
        return []

    try:
        raw_text = calendar_file.read_text(encoding="utf-8-sig")
    except OSError as error:
        logger.warning("Unable to read macro calendar %s: %s", calendar_file, error)
        return []

    if not raw_text.strip():
        logger.warning("Macro calendar is empty; repairing %s", calendar_file)
        _repair_macro_calendar_file(calendar_file)
        return []

    try:
        events = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Macro calendar contains invalid JSON; repairing %s", calendar_file)
        _repair_macro_calendar_file(calendar_file)
        return []

    if not isinstance(events, list):
        logger.warning("Macro calendar must contain a JSON array; repairing %s", calendar_file)
        _repair_macro_calendar_file(calendar_file)
        return []

    return events


def _coerce_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _classify_macro_importance(event):
    importance = (event.get("importance") or "").strip().lower()
    if importance in {RED_IMPORTANCE, ORANGE_IMPORTANCE}:
        return importance

    name = (event.get("name") or "").strip().lower()
    if any(keyword in name for keyword in RED_EVENT_KEYWORDS):
        return RED_IMPORTANCE
    if any(keyword in name for keyword in ORANGE_EVENT_KEYWORDS):
        return ORANGE_IMPORTANCE

    return None


def get_auto_macro_calendar_catalysts(
    as_of=None,
    lookahead_days=AUTO_MACRO_CALENDAR_LOOKAHEAD_DAYS,
    calendar_file=MACRO_CALENDAR_FILE,
):
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    end_date = as_of + timedelta(days=lookahead_days)
    catalysts = []

    for event in _load_macro_calendar(calendar_file):
        if not isinstance(event, dict):
            logger.warning("Skipping malformed macro calendar entry in %s", calendar_file)
            continue

        event_date = _coerce_date(event.get("date"))
        name = (event.get("name") or "").strip()
        importance = _classify_macro_importance(event)

        if event_date is None or not name or importance is None:
            logger.warning("Skipping incomplete macro calendar entry in %s", calendar_file)
            continue

        if not as_of <= event_date <= end_date:
            continue

        catalysts.append(
            {
                "date": event_date.isoformat(),
                "name": name,
                "importance": importance,
                "source": AUTO_MACRO_CALENDAR_SOURCE,
            }
        )

    return catalysts
