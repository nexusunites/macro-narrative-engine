import json
import re
from datetime import date

from mne.calendar_sources.base import (
    CalendarSourceError,
    SourceResult,
    dedupe_events,
    fetch_text,
    html_lines,
    normalized_event,
    now_iso,
    parse_month_day,
)


BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
SOURCE_FAMILY = "bea_release_schedule"

BEA_EVENT_MAP = {
    "gdp": ("Gross Domestic Product", "gdp", "red"),
    "personal income and outlays": ("Personal Income and Outlays", "personal_income_outlays", "red"),
    "u.s. international trade in goods and services": (
        "U.S. International Trade in Goods and Services",
        "international_trade",
        "orange",
    ),
}


def _match_event(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    lowered = text.lower()
    for prefix, mapping in BEA_EVENT_MAP.items():
        if lowered.startswith(prefix):
            return mapping
    return None


def parse_bea_json(payload: str, *, source_url=BEA_SCHEDULE_URL, loaded_at=None) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    data = json.loads(payload)
    rows = data if isinstance(data, list) else data.get("releases") or data.get("results") or []
    events = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = row.get("name") or row.get("title") or row.get("ReleaseName")
        mapping = _match_event(title)
        date_text = row.get("date") or row.get("ReleaseDate") or row.get("release_date")
        time_text = row.get("time") or row.get("ReleaseTime") or row.get("release_time")
        year = int(str(row.get("year") or date.today().year))
        event_date = _parse_bea_date(date_text, year)
        if mapping and event_date:
            name, event_type, importance = mapping
            events.append(
                normalized_event(
                    source_agency="BEA",
                    source_family=SOURCE_FAMILY,
                    source_url=source_url,
                    name=name,
                    event_type=event_type,
                    importance=importance,
                    day=event_date,
                    time_text=time_text,
                    loaded_at=loaded_at,
                )
            )
    return dedupe_events(events)


def parse_bea_schedule_html(
    payload: str,
    *,
    year: int | None = None,
    source_url=BEA_SCHEDULE_URL,
    loaded_at=None,
) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    lines = html_lines(payload)
    year = year or _year_from_lines(lines) or date.today().year
    events = []
    for index, line in enumerate(lines):
        event_date = _parse_bea_date(line, year)
        if event_date is None or index + 2 >= len(lines):
            continue
        time_text = _next_time(lines, index + 1)
        title, mapping = _next_matching_title(lines, index + 1)
        if not mapping:
            continue
        name, event_type, importance = mapping
        events.append(
            normalized_event(
                source_agency="BEA",
                source_family=SOURCE_FAMILY,
                source_url=source_url,
                name=name,
                event_type=event_type,
                importance=importance,
                day=event_date,
                time_text=time_text,
                loaded_at=loaded_at,
            )
        )
    return dedupe_events(events)


def _next_time(lines, start):
    for line in lines[start : start + 4]:
        if re.search(r"\d{1,2}:\d{2}\s*[AP]M", line, re.IGNORECASE):
            return line
    return None


def _next_matching_title(lines, start):
    for line in lines[start : start + 10]:
        mapping = _match_event(line)
        if mapping:
            return line, mapping
    return None, None


def _parse_bea_date(value, year):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}", text):
        return parse_month_day(text, year)
    if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, 20\d{2}", text):
        return parse_month_day(text, year)
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _year_from_lines(lines):
    for line in lines:
        match = re.search(r"Year\s+(20\d{2})", line)
        if match:
            return int(match.group(1))
    return None


def fetch_events(as_of=None, get=None, loaded_at=None) -> SourceResult:
    loaded_at = loaded_at or now_iso()
    try:
        payload = fetch_text(BEA_SCHEDULE_URL, get=get)
        events = parse_bea_schedule_html(payload, loaded_at=loaded_at)
        if not events:
            raise CalendarSourceError("BEA schedule produced no recognized events")
        return SourceResult("bea", "success", events, loaded_at, BEA_SCHEDULE_URL)
    except Exception as error:
        return SourceResult("bea", "failed", [], loaded_at, BEA_SCHEDULE_URL, str(error))
