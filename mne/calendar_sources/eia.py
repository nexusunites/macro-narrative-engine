import re
from datetime import date, timedelta

from mne.calendar_sources.base import (
    SourceResult,
    dedupe_events,
    fetch_text,
    future_weekdays,
    html_lines,
    normalized_event,
    now_iso,
    parse_month_day,
    parse_time,
)


EIA_PETROLEUM_URL = "https://www.eia.gov/petroleum/supply/weekly/schedule.php"
EIA_NATURAL_GAS_URL = "https://www.eia.gov/naturalgas/storage/dashboard/"
SOURCE_FAMILY = "eia_weekly_release_schedule"


def parse_eia_petroleum_html(
    payload: str,
    *,
    as_of=None,
    source_url=EIA_PETROLEUM_URL,
    loaded_at=None,
) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    as_of = as_of or date.today()
    end = as_of + timedelta(days=120)
    exceptions = _parse_exception_dates(payload, as_of.year)
    events = {}
    for day in future_weekdays(as_of, end, 2):
        events[day.isoformat()] = ("10:30", day)
    for release_day, release_time in exceptions.items():
        if as_of <= release_day <= end:
            events[release_day.isoformat()] = (release_time, release_day)
    return dedupe_events(
        [
            normalized_event(
                source_agency="EIA",
                source_family=SOURCE_FAMILY,
                source_url=source_url,
                name="EIA Weekly Petroleum Status Report",
                event_type="eia_weekly_petroleum_status",
                importance="orange",
                day=day,
                time_text=time_text,
                loaded_at=loaded_at,
            )
            for time_text, day in events.values()
        ]
    )


def parse_eia_natural_gas_html(
    payload: str,
    *,
    as_of=None,
    source_url=EIA_NATURAL_GAS_URL,
    loaded_at=None,
) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    as_of = as_of or date.today()
    end = as_of + timedelta(days=120)
    return dedupe_events(
        [
            normalized_event(
                source_agency="EIA",
                source_family=SOURCE_FAMILY,
                source_url=source_url,
                name="EIA Weekly Natural Gas Storage Report",
                event_type="eia_weekly_natural_gas_storage",
                importance="orange",
                day=day,
                time_text="10:30",
                loaded_at=loaded_at,
            )
            for day in future_weekdays(as_of, end, 3)
        ]
    )


def _parse_exception_dates(payload, year):
    lines = html_lines(payload)
    exceptions = {}
    for index, line in enumerate(lines):
        if not re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, 20\d{2}", line):
            continue
        if index + 3 >= len(lines):
            continue
        release_day = parse_month_day(lines[index + 1], year)
        release_time = parse_time(lines[index + 3])
        if release_day and release_time:
            exceptions[release_day] = release_time
    return exceptions


def fetch_events(as_of=None, get=None, loaded_at=None) -> SourceResult:
    loaded_at = loaded_at or now_iso()
    events = []
    errors = []
    try:
        payload = fetch_text(EIA_PETROLEUM_URL, get=get)
        events.extend(parse_eia_petroleum_html(payload, as_of=as_of, loaded_at=loaded_at))
    except Exception as error:
        errors.append(f"petroleum: {error}")
    try:
        payload = fetch_text(EIA_NATURAL_GAS_URL, get=get)
        events.extend(parse_eia_natural_gas_html(payload, as_of=as_of, loaded_at=loaded_at))
    except Exception as error:
        errors.append(f"natural_gas: {error}")
        events.extend(parse_eia_natural_gas_html("", as_of=as_of, loaded_at=loaded_at))
    events = dedupe_events(events)
    status = "success" if events and not errors else "partial" if events else "failed"
    return SourceResult(
        "eia",
        status,
        events,
        loaded_at,
        EIA_PETROLEUM_URL,
        "; ".join(errors) if errors else None,
    )
