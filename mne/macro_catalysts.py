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


def get_macro_calendar_status(
    calendar_path: str | Path,
    events: list[dict] | None,
    load_error: str | None = None,
) -> dict:
    calendar_path = Path(calendar_path)
    base_status = {
        "macro_calendar_path": str(calendar_path),
        "macro_calendar_event_count": 0,
        "macro_calendar_latest_event_date": None,
        "macro_calendar_warning": True,
    }

    if load_error == "missing_file":
        return {
            **base_status,
            "macro_calendar_status": "missing_file",
            "macro_calendar_message": "Macro calendar file is missing.",
        }

    if load_error == "invalid_json":
        return {
            **base_status,
            "macro_calendar_status": "invalid_json",
            "macro_calendar_message": "Macro calendar file could not be parsed.",
        }

    if events is not None:
        event_dates = []
        for event in events:
            if not isinstance(event, dict) or not event.get("date"):
                continue
            try:
                event_dates.append(date.fromisoformat(str(event["date"])))
            except (TypeError, ValueError):
                continue

        if not events or not event_dates:
            return {
                **base_status,
                "macro_calendar_status": "loaded_empty",
                "macro_calendar_message": "Macro calendar loaded but contains no events.",
            }

        latest_event_date = max(event_dates).isoformat()
        if all(event_date < date.today() for event_date in event_dates):
            return {
                **base_status,
                "macro_calendar_status": "stale_calendar",
                "macro_calendar_message": (
                    "Macro calendar appears stale. All events are historical."
                ),
                "macro_calendar_event_count": len(events),
                "macro_calendar_latest_event_date": latest_event_date,
            }

        if any(event_date >= date.today() for event_date in event_dates):
            return {
                **base_status,
                "macro_calendar_status": "loaded_with_events",
                "macro_calendar_message": (
                    f"Macro calendar loaded with {len(events)} event(s)."
                ),
                "macro_calendar_event_count": len(events),
                "macro_calendar_latest_event_date": latest_event_date,
                "macro_calendar_warning": False,
            }

    return {
        **base_status,
        "macro_calendar_status": "unknown",
        "macro_calendar_message": "Macro calendar status could not be determined.",
    }


def _load_macro_calendar(calendar_file, metadata=None):
    calendar_file = Path(calendar_file)
    if not calendar_file.exists():
        status = get_macro_calendar_status(
            calendar_file,
            events=None,
            load_error="missing_file",
        )
        if metadata is not None:
            metadata["macro_calendar_status"] = status
        logger.warning("Macro calendar file is missing: %s", calendar_file)
        return []

    try:
        raw_text = calendar_file.read_text(encoding="utf-8-sig")
    except OSError as error:
        logger.warning("Unable to read macro calendar %s: %s", calendar_file, error)
        if metadata is not None:
            metadata["macro_calendar_status"] = get_macro_calendar_status(
                calendar_file,
                events=None,
            )
        return []

    try:
        events = json.loads(raw_text)
    except json.JSONDecodeError:
        status = get_macro_calendar_status(
            calendar_file,
            events=None,
            load_error="invalid_json",
        )
        if metadata is not None:
            metadata["macro_calendar_status"] = status
        logger.warning("Macro calendar contains invalid JSON: %s", calendar_file)
        return []

    if not isinstance(events, list):
        logger.warning("Macro calendar must contain a JSON array: %s", calendar_file)
        if metadata is not None:
            metadata["macro_calendar_status"] = get_macro_calendar_status(
                calendar_file,
                events=None,
            )
        return []

    if metadata is not None:
        metadata["macro_calendar_status"] = get_macro_calendar_status(
            calendar_file,
            events=events,
        )
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
    metadata=None,
):
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    end_date = as_of + timedelta(days=lookahead_days)
    catalysts = []

    for event in _load_macro_calendar(calendar_file, metadata=metadata):
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
