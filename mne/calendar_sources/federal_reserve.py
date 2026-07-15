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


FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
SOURCE_FAMILY = "federal_reserve_fomc_calendar"
MONTHS = {
    "january": 1,
    "jan/feb": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "oct/nov": 10,
    "november": 11,
    "december": 12,
}


def parse_fomc_html(
    payload: str,
    *,
    year: int | None = None,
    source_url=FED_FOMC_URL,
    loaded_at=None,
) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    lines = html_lines(payload)
    events = []
    current_year = year
    current_month_label = None
    for index, line in enumerate(lines):
        year_match = re.search(r"(20\d{2}) FOMC Meetings", line)
        if year_match:
            current_year = int(year_match.group(1))
            continue
        lowered = line.lower()
        if lowered in MONTHS:
            current_month_label = lowered
            continue
        if current_year is None or current_month_label is None:
            continue
        if not re.fullmatch(r"\d{1,2}(?:-\d{1,2})?\*?", line):
            continue
        decision_date = _decision_date(current_year, current_month_label, line)
        if decision_date is None:
            continue
        events.append(
            normalized_event(
                source_agency="Federal Reserve",
                source_family=SOURCE_FAMILY,
                source_url=source_url,
                name="FOMC Policy Decision",
                event_type="fomc_policy_decision",
                importance="red",
                day=decision_date,
                time_text="14:00",
                loaded_at=loaded_at,
            )
        )
        following = " ".join(lines[index : index + 12]).lower()
        if "press conference" in following:
            events.append(
                normalized_event(
                    source_agency="Federal Reserve",
                    source_family=SOURCE_FAMILY,
                    source_url=source_url,
                    name="FOMC Press Conference",
                    event_type="fomc_press_conference",
                    importance="red",
                    day=decision_date,
                    time_text="14:30",
                    loaded_at=loaded_at,
                )
            )
        minutes_date = _minutes_date(lines[index : index + 16], current_year)
        if minutes_date:
            events.append(
                normalized_event(
                    source_agency="Federal Reserve",
                    source_family=SOURCE_FAMILY,
                    source_url=source_url,
                    name="FOMC Minutes",
                    event_type="fomc_minutes",
                    importance="orange",
                    day=minutes_date,
                    time_text="14:00",
                    loaded_at=loaded_at,
                )
            )
    return dedupe_events(events)


def _decision_date(year, month_label, day_range):
    clean = day_range.replace("*", "")
    end_day = int(clean.split("-")[-1])
    month = MONTHS[month_label]
    if month_label == "jan/feb" and "-" in clean:
        month = 2
    if month_label == "oct/nov" and "-" in clean:
        month = 11
    return date(year, month, end_day)


def _minutes_date(lines, year):
    text = " ".join(lines)
    match = re.search(r"Released\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})", text)
    if not match:
        return None
    return parse_month_day(match.group(1), year)


def fetch_events(as_of=None, get=None, loaded_at=None) -> SourceResult:
    loaded_at = loaded_at or now_iso()
    try:
        payload = fetch_text(FED_FOMC_URL, get=get)
        events = parse_fomc_html(payload, loaded_at=loaded_at)
        if not events:
            raise CalendarSourceError("Federal Reserve FOMC page produced no recognized events")
        return SourceResult("federal_reserve", "success", events, loaded_at, FED_FOMC_URL)
    except Exception as error:
        return SourceResult(
            "federal_reserve", "failed", [], loaded_at, FED_FOMC_URL, str(error)
        )

