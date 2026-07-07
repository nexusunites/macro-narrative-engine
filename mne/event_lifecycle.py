import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import EVENT_LIFECYCLE_EVENTS_FILE


LOGGER = logging.getLogger(__name__)
ENGINE_VERSION = "1.0.0"

UPCOMING = "Upcoming"
PRE_POSITIONING = "Pre-Positioning"
IMMEDIATE_PRE_EVENT = "Immediate Pre-Event"
ACTIVE_RELEASE = "Active Release"
INITIAL_DIGESTION = "Initial Digestion"
NARRATIVE_REPRICING = "Narrative Repricing"
COMPLETE = "Complete"

IMPORTANCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

DEFAULT_WINDOWS = {
    "HIGH": {
        "pre_positioning_window_minutes": 120,
        "immediate_pre_event_window_minutes": 15,
        "active_release_window_minutes": 15,
        "digestion_window_minutes": 90,
        "repricing_window_minutes": None,
    },
    "MEDIUM": {
        "pre_positioning_window_minutes": 60,
        "immediate_pre_event_window_minutes": 10,
        "active_release_window_minutes": 10,
        "digestion_window_minutes": 45,
        "repricing_window_minutes": None,
    },
    "LOW": {
        "pre_positioning_window_minutes": 30,
        "immediate_pre_event_window_minutes": 5,
        "active_release_window_minutes": 5,
        "digestion_window_minutes": 20,
        "repricing_window_minutes": None,
    },
}

WINDOW_FIELDS = tuple(next(iter(DEFAULT_WINDOWS.values())).keys())
END_OF_TRADING_DAY_TIME = "16:00"
END_OF_TRADING_DAY_TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class EventTiming:
    event_date: date
    release_at_utc: datetime
    pre_positioning_start_utc: datetime
    immediate_pre_start_utc: datetime
    active_release_end_utc: datetime
    digestion_end_utc: datetime
    repricing_end_utc: datetime
    event_day_start_utc: datetime
    windows: dict
    used_defaults: bool


def load_event_definitions(path: str | Path = EVENT_LIFECYCLE_EVENTS_FILE) -> list[dict]:
    path = Path(path)
    if not path.exists():
        LOGGER.info("Event lifecycle file is missing: %s", path)
        return []

    try:
        events = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning("Unable to load event lifecycle file %s: %s", path, error)
        return []

    if not isinstance(events, list):
        LOGGER.warning("Event lifecycle file must contain a JSON array: %s", path)
        return []

    return [event for event in events if isinstance(event, dict)]


def evaluate_event_lifecycle_run(
    events: list[dict] | None = None,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = _normalize_utc(now_utc or datetime.now(timezone.utc))
    evaluated_events = []

    for event in events if events is not None else load_event_definitions():
        try:
            evaluated_events.append(evaluate_event_lifecycle(event, now_utc))
        except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
            LOGGER.warning(
                "Skipping malformed event lifecycle entry %s: %s",
                event.get("event_id") if isinstance(event, dict) else None,
                error,
            )

    return {
        "run_timestamp_utc": now_utc.isoformat().replace("+00:00", "Z"),
        "current_event": select_current_event(evaluated_events),
        "events": evaluated_events,
    }


def evaluate_event_lifecycle(event: dict, now_utc: datetime) -> dict:
    now_utc = _normalize_utc(now_utc)
    timing = calculate_event_timing(event)
    state = classify_lifecycle_state(event, timing, now_utc)
    next_transition = _next_transition(state, timing, now_utc)

    release_at = timing.release_at_utc
    minutes_until_release = None
    minutes_since_release = None
    if now_utc < release_at:
        minutes_until_release = _whole_minutes(release_at - now_utc)
    else:
        minutes_since_release = _whole_minutes(now_utc - release_at)

    if state == COMPLETE:
        minutes_until_release = None
        minutes_since_release = None

    return {
        "event_id": str(event["event_id"]),
        "event_name": str(event["event_name"]),
        "event_importance": _importance(event),
        "lifecycle_state": state,
        "minutes_until_release": minutes_until_release,
        "minutes_since_release": minutes_since_release,
        "next_transition": next_transition,
        "confidence": "MEDIUM" if timing.used_defaults else "HIGH",
        "reason": _reason(state, timing, now_utc),
    }


def calculate_event_timing(event: dict) -> EventTiming:
    event_date = date.fromisoformat(str(event["date"]))
    release_zone = ZoneInfo(str(event["release_timezone"]))
    release_hour, release_minute = _parse_hhmm(str(event["release_time"]))
    release_local = datetime.combine(
        event_date,
        time(release_hour, release_minute),
        tzinfo=release_zone,
    )
    release_at_utc = release_local.astimezone(timezone.utc)

    event_day_start_utc = datetime.combine(
        event_date,
        time(0, 0),
        tzinfo=release_zone,
    ).astimezone(timezone.utc)

    windows, used_defaults = _resolve_windows(event)
    active_release_end = release_at_utc + timedelta(
        minutes=windows["active_release_window_minutes"]
    )
    digestion_end = active_release_end + timedelta(
        minutes=windows["digestion_window_minutes"]
    )
    repricing_minutes = windows["repricing_window_minutes"]
    if repricing_minutes is None:
        repricing_end = _end_of_trading_day_utc(event_date)
    else:
        repricing_end = min(
            digestion_end + timedelta(minutes=repricing_minutes),
            _end_of_trading_day_utc(event_date),
        )

    return EventTiming(
        event_date=event_date,
        release_at_utc=release_at_utc,
        pre_positioning_start_utc=release_at_utc
        - timedelta(minutes=windows["pre_positioning_window_minutes"]),
        immediate_pre_start_utc=release_at_utc
        - timedelta(minutes=windows["immediate_pre_event_window_minutes"]),
        active_release_end_utc=active_release_end,
        digestion_end_utc=digestion_end,
        repricing_end_utc=repricing_end,
        event_day_start_utc=event_day_start_utc,
        windows=windows,
        used_defaults=used_defaults,
    )


def classify_lifecycle_state(event: dict, timing: EventTiming, now_utc: datetime) -> str:
    now_utc = _normalize_utc(now_utc)
    event_zone = ZoneInfo(str(event["release_timezone"]))
    local_now_date = now_utc.astimezone(event_zone).date()

    if local_now_date > timing.event_date:
        return COMPLETE
    if local_now_date < timing.event_date:
        return UPCOMING
    if now_utc >= timing.repricing_end_utc:
        return COMPLETE
    if timing.digestion_end_utc <= now_utc < timing.repricing_end_utc:
        return NARRATIVE_REPRICING
    if timing.active_release_end_utc <= now_utc < timing.digestion_end_utc:
        return INITIAL_DIGESTION
    if timing.release_at_utc <= now_utc < timing.active_release_end_utc:
        return ACTIVE_RELEASE
    if timing.immediate_pre_start_utc <= now_utc < timing.release_at_utc:
        return IMMEDIATE_PRE_EVENT
    if timing.pre_positioning_start_utc <= now_utc < timing.immediate_pre_start_utc:
        return PRE_POSITIONING
    return UPCOMING


def select_current_event(evaluated_events: list[dict]) -> str | None:
    active_events = [
        event
        for event in evaluated_events
        if event.get("lifecycle_state") not in {UPCOMING, COMPLETE}
    ]
    if not active_events:
        return None

    selected = sorted(
        active_events,
        key=lambda event: (
            -IMPORTANCE_ORDER.get(str(event.get("event_importance")), 0),
            event.get("minutes_until_release")
            if event.get("minutes_until_release") is not None
            else event.get("minutes_since_release", 0),
            str(event.get("event_id")),
        ),
    )[0]
    return selected.get("event_id")


def _resolve_windows(event: dict) -> tuple[dict, bool]:
    importance = _importance(event)
    defaults = DEFAULT_WINDOWS[importance]
    windows = {}
    used_defaults = False

    for field in WINDOW_FIELDS:
        value = event.get(field)
        if value is None:
            windows[field] = defaults[field]
            used_defaults = True
            continue
        value = int(value)
        if value < 0:
            raise ValueError(f"{field} must not be negative")
        windows[field] = value

    if (
        windows["immediate_pre_event_window_minutes"]
        > windows["pre_positioning_window_minutes"]
    ):
        raise ValueError(
            "immediate_pre_event_window_minutes must be less than or equal to "
            "pre_positioning_window_minutes"
        )

    return windows, used_defaults


def _next_transition(state: str, timing: EventTiming, now_utc: datetime) -> dict:
    transitions = {
        UPCOMING: (
            PRE_POSITIONING,
            max(timing.pre_positioning_start_utc, timing.event_day_start_utc),
        ),
        PRE_POSITIONING: (IMMEDIATE_PRE_EVENT, timing.immediate_pre_start_utc),
        IMMEDIATE_PRE_EVENT: (ACTIVE_RELEASE, timing.release_at_utc),
        ACTIVE_RELEASE: (INITIAL_DIGESTION, timing.active_release_end_utc),
        INITIAL_DIGESTION: (NARRATIVE_REPRICING, timing.digestion_end_utc),
        NARRATIVE_REPRICING: (COMPLETE, timing.repricing_end_utc),
    }
    next_state, at_utc = transitions.get(state, (None, None))
    if next_state is None or at_utc is None or at_utc <= now_utc:
        return {"next_state": None, "at_utc": None, "minutes_away": None}

    return {
        "next_state": next_state,
        "at_utc": at_utc.isoformat().replace("+00:00", "Z"),
        "minutes_away": _whole_minutes(at_utc - now_utc),
    }


def _reason(state: str, timing: EventTiming, now_utc: datetime) -> str:
    if state == COMPLETE:
        return "Event lifecycle is complete for this run timestamp."
    if state == UPCOMING:
        minutes = _whole_minutes(timing.release_at_utc - now_utc)
        return (
            f"{minutes} minutes before release, outside pre-positioning window "
            f"({timing.windows['pre_positioning_window_minutes']} min)."
        )
    if state == PRE_POSITIONING:
        minutes = _whole_minutes(timing.release_at_utc - now_utc)
        return (
            f"{minutes} minutes before release, inside pre-positioning window "
            f"({timing.windows['pre_positioning_window_minutes']} min)."
        )
    if state == IMMEDIATE_PRE_EVENT:
        minutes = _whole_minutes(timing.release_at_utc - now_utc)
        return (
            f"{minutes} minutes before release, inside immediate pre-event window "
            f"({timing.windows['immediate_pre_event_window_minutes']} min)."
        )
    if state == ACTIVE_RELEASE:
        minutes = _whole_minutes(now_utc - timing.release_at_utc)
        return (
            f"{minutes} minutes since release, inside active release window "
            f"({timing.windows['active_release_window_minutes']} min)."
        )
    if state == INITIAL_DIGESTION:
        minutes = _whole_minutes(now_utc - timing.release_at_utc)
        return (
            f"{minutes} minutes since release, inside initial digestion window "
            f"({timing.windows['digestion_window_minutes']} min)."
        )
    minutes = _whole_minutes(now_utc - timing.release_at_utc)
    return (
        f"{minutes} minutes since release, inside narrative repricing window "
        "through end of trading day."
    )


def _end_of_trading_day_utc(event_date: date) -> datetime:
    hour, minute = _parse_hhmm(END_OF_TRADING_DAY_TIME)
    local = datetime.combine(
        event_date,
        time(hour, minute),
        tzinfo=ZoneInfo(END_OF_TRADING_DAY_TIMEZONE),
    )
    return local.astimezone(timezone.utc)


def _importance(event: dict) -> str:
    importance = str(event["importance"]).upper()
    if importance not in DEFAULT_WINDOWS:
        raise ValueError(f"Unsupported event importance: {importance}")
    return importance


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"Invalid HH:MM time: {value}")
    return hour, minute


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _whole_minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)
