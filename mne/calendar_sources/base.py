import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests


EASTERN_TIMEZONE = "America/New_York"
EASTERN = ZoneInfo(EASTERN_TIMEZONE)
DEFAULT_USER_AGENT = "MacroNarrativeEngine/1.0 official-calendar-refresh"


class CalendarSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceResult:
    source: str
    status: str
    events: list[dict]
    loaded_at: str
    source_url: str
    error: str | None = None
    source_variant: str | None = None
    attempts: list[dict] | None = None

    def to_metadata(self):
        event_dates = [event["date"] for event in self.events if event.get("date")]
        return {
            "status": self.status,
            "source_variant": self.source_variant,
            "event_count": len(self.events),
            "loaded_at": self.loaded_at,
            "source_url": self.source_url,
            "coverage_start": min(event_dates) if event_dates else None,
            "coverage_end": max(event_dates) if event_dates else None,
            "error": self.error,
            "attempts": self.attempts or [],
        }


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "tr", "td", "th", "li", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return "\n".join(self.parts)


def html_lines(payload: str) -> list[str]:
    parser = TextExtractor()
    parser.feed(payload or "")
    return [line.strip() for line in parser.text().splitlines() if line.strip()]


def now_iso():
    return datetime.now(EASTERN).isoformat(timespec="seconds")


def parse_month_day(value: str, year: int) -> date | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip().replace(".", "")
    for fmt in ("%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return date(parsed.year if "%Y" in fmt else year, parsed.month, parsed.day)
        except ValueError:
            continue
    return None


def parse_time(value: str) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower().replace(".", "")
    text = text.replace("a m", "am").replace("p m", "pm")
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return datetime.strptime(text.upper(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None


def scheduled_at_for(day: date, time_text: str | None) -> str | None:
    parsed_time = parse_time(time_text) if time_text else None
    if parsed_time is None:
        return None
    hour, minute = [int(part) for part in parsed_time.split(":")]
    return datetime.combine(day, dt_time(hour, minute), tzinfo=EASTERN).isoformat(
        timespec="minutes"
    )


def stable_event_id(source_agency: str, event_type: str, day: date, time_text: str | None):
    timestamp = scheduled_at_for(day, time_text) or day.isoformat()
    return f"{source_agency.lower()}:{event_type}:{timestamp}"


def normalized_event(
    *,
    source_agency: str,
    source_family: str,
    source_url: str,
    name: str,
    event_type: str,
    importance: str,
    day: date,
    time_text: str | None,
    loaded_at: str,
    coverage_start: str | None = None,
    coverage_end: str | None = None,
) -> dict:
    parsed_time = parse_time(time_text) if time_text else None
    event = {
        "event_id": stable_event_id(source_agency, event_type, day, parsed_time),
        "date": day.isoformat(),
        "name": name,
        "event_type": event_type,
        "importance": importance,
        "source": "official_macro_calendar",
        "source_agency": source_agency,
        "source_family": source_family,
        "source_url": source_url,
        "loaded_at": loaded_at,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
    }
    if parsed_time:
        event["time"] = parsed_time
        event["timezone"] = EASTERN_TIMEZONE
        event["scheduled_at"] = scheduled_at_for(day, parsed_time)
    else:
        event["time_missing"] = True
    return event


def fetch_text(url: str, timeout=15, retries=1, get: Callable | None = None) -> str:
    getter = get or requests.get
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = getter(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(0.25)
    raise CalendarSourceError(str(last_error))


def absolute_url(base_url: str, href: str):
    return urljoin(base_url, href)


def dedupe_events(events: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for event in events:
        key = _dedupe_key(event)
        if key in seen:
            if _should_replace_existing(deduped, key, event):
                for index, existing in enumerate(deduped):
                    if _dedupe_key(existing) == key:
                        deduped[index] = event
                        break
            continue
        seen.add(key)
        deduped.append(event)
    return sorted(
        deduped,
        key=lambda event: (
            event.get("scheduled_at") or event.get("date") or "",
            event.get("source_agency") or "",
            event.get("event_type") or "",
        ),
    )


def _dedupe_key(event):
    if event.get("event_type") and event.get("date"):
        return (
            event.get("source_agency"),
            event.get("event_type"),
            event.get("date"),
        )
    return event.get("event_id") or (
        event.get("source_agency"),
        event.get("event_type"),
        event.get("scheduled_at") or event.get("date"),
    )


def _should_replace_existing(events, key, candidate):
    if candidate.get("time_precision") == "date_only":
        return False
    for existing in events:
        if _dedupe_key(existing) != key:
            continue
        return existing.get("time_precision") == "date_only"
    return False


def future_weekdays(start: date, end: date, weekday: int):
    current = start
    while current <= end:
        if current.weekday() == weekday:
            yield current
        current += timedelta(days=1)
