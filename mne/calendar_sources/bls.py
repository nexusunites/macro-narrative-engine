import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from mne.calendar_sources.base import (
    CalendarSourceError,
    EASTERN,
    SourceResult,
    dedupe_events,
    fetch_text,
    html_lines,
    normalized_event,
    now_iso,
    parse_month_day,
)
from mne.calendar_sources.fred import (
    FRED_TARGETED_RELEASE_DATES_URL,
    TARGETED_SOURCE_VARIANT as FRED_TARGETED_SOURCE_VARIANT,
    get_fred_bls_calendar_events,
)


BLS_CALENDAR_URL = "https://www.bls.gov/schedule/news_release/"
BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
SOURCE_FAMILY = "bls_release_schedule"

BLS_EVENT_MAP = {
    "consumer price index": ("Consumer Price Index", "cpi", "red"),
    "producer price index": ("Producer Price Index", "ppi", "red"),
    "employment situation": ("Employment Situation", "employment_situation", "red"),
    "job openings and labor turnover survey": (
        "Job Openings and Labor Turnover Survey",
        "jolts",
        "orange",
    ),
    "job openings and labor turnover": (
        "Job Openings and Labor Turnover Survey",
        "jolts",
        "orange",
    ),
    "employment cost index": ("Employment Cost Index", "employment_cost_index", "orange"),
    "u.s. import and export price indexes": (
        "U.S. Import and Export Price Indexes",
        "import_export_prices",
        "orange",
    ),
    "u.s. export and import price indexes": (
        "U.S. Import and Export Price Indexes",
        "import_export_prices",
        "orange",
    ),
}


def _match_event_name(value):
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    lowered = name.lower()
    for prefix, mapping in BLS_EVENT_MAP.items():
        if lowered.startswith(prefix):
            return mapping
    return None


def _unfold_ical_lines(payload):
    lines = []
    for raw_line in (payload or "").splitlines():
        line = raw_line.rstrip("\r")
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _unescape_ical(value):
    return (
        str(value or "")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_property(line):
    if ":" not in line:
        return None, {}, None
    raw_key, value = line.split(":", 1)
    parts = raw_key.split(";")
    key = parts[0].upper()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            name, param_value = part.split("=", 1)
            params[name.upper()] = param_value
    return key, params, _unescape_ical(value)


def _parse_ics_datetime(value, params=None):
    params = params or {}
    text = str(value or "").strip()
    value_type = params.get("VALUE", "").upper()
    if value_type == "DATE" or re.fullmatch(r"\d{8}", text):
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8])), None
        except ValueError:
            return None, None

    match = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z)?", text)
    if not match:
        return None, None
    year, month, day, hour, minute, second, utc_marker = match.groups()
    try:
        naive = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
    except ValueError:
        return None, None

    if utc_marker:
        localized = naive.replace(tzinfo=timezone.utc).astimezone(EASTERN)
    else:
        timezone_name = params.get("TZID")
        tzinfo = ZoneInfo(timezone_name) if timezone_name else EASTERN
        localized = naive.replace(tzinfo=tzinfo).astimezone(EASTERN)

    return localized.date(), localized.strftime("%H:%M")


def parse_bls_ics(payload: str, *, source_url=BLS_ICS_URL, loaded_at=None) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    events = []
    current = {}
    current_params = {}
    for raw_line in _unfold_ical_lines(payload):
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
            current_params = {}
        elif line == "END:VEVENT":
            summary = current.get("SUMMARY")
            mapping = _match_event_name(summary)
            event_date, event_time = _parse_ics_datetime(
                current.get("DTSTART"),
                current_params.get("DTSTART"),
            )
            if mapping and event_date:
                name, event_type, importance = mapping
                event = normalized_event(
                    source_agency="BLS",
                    source_family=SOURCE_FAMILY,
                    source_url=source_url,
                    name=name,
                    event_type=event_type,
                    importance=importance,
                    day=event_date,
                    time_text=event_time,
                    loaded_at=loaded_at,
                )
                if current.get("UID"):
                    event["source_uid"] = current["UID"]
                if current.get("DESCRIPTION"):
                    event["source_description"] = current["DESCRIPTION"]
                events.append(event)
            current = {}
            current_params = {}
        else:
            key, params, value = _parse_property(line)
            if key:
                current[key] = value
                current_params[key] = params
    return dedupe_events(events)


def parse_bls_schedule_html(
    payload: str,
    *,
    year: int | None = None,
    source_url=BLS_CALENDAR_URL,
    loaded_at=None,
) -> list[dict]:
    loaded_at = loaded_at or now_iso()
    lines = html_lines(payload)
    year = year or _year_from_lines(lines) or date.today().year
    events = []
    current_day = None
    for index, line in enumerate(lines):
        day_match = re.fullmatch(r"\d{1,2}", line)
        if day_match:
            current_day = int(line)
            continue
        mapping = _match_event_name(line)
        if not mapping or current_day is None:
            continue
        month = _month_from_context(lines, index)
        if month is None:
            continue
        event_date = date(year, month, current_day)
        time_text = lines[index + 2] if index + 2 < len(lines) else None
        name, event_type, importance = mapping
        events.append(
            normalized_event(
                source_agency="BLS",
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


def _year_from_lines(lines):
    for line in lines:
        match = re.search(r"\b(20\d{2})\b", line)
        if match:
            return int(match.group(1))
    return None


def _month_from_context(lines, index):
    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    for prior in reversed(lines[:index]):
        text = prior.lower()
        for name, month in month_names.items():
            if name in text:
                return month
    return None


def fetch_events(as_of=None, get=None, loaded_at=None) -> SourceResult:
    loaded_at = loaded_at or now_iso()
    attempts = []
    events = []
    source_url = BLS_ICS_URL
    try:
        payload = fetch_text(BLS_ICS_URL, get=get)
        events = parse_bls_ics(payload, loaded_at=loaded_at)
        if not events:
            raise CalendarSourceError("BLS iCalendar produced no recognized events")
        attempts.append({"source_variant": "official_ical", "status": "success"})
    except Exception as error:
        attempts.append(
            {
                "source_variant": "official_ical",
                "status": "failed",
                "error": str(error),
            }
        )

    if not events:
        try:
            source_url = BLS_CALENDAR_URL
            payload = fetch_text(BLS_CALENDAR_URL, get=get)
            events = parse_bls_schedule_html(payload, loaded_at=loaded_at)
            if not events:
                raise CalendarSourceError("BLS HTML schedule produced no recognized events")
            attempts.append({"source_variant": "official_html", "status": "success"})
        except Exception as error:
            attempts.append(
                {
                    "source_variant": "official_html",
                    "status": "failed",
                    "error": str(error),
                }
            )

    if not events:
        fred_result = get_fred_bls_calendar_events(
            as_of=as_of,
            get=get,
            loaded_at=loaded_at,
        )
        attempts.extend(fred_result.attempts or [])
        if fred_result.status in {"success", "partial"} and fred_result.events:
            return SourceResult(
                "bls",
                fred_result.status,
                fred_result.events,
                loaded_at,
                FRED_TARGETED_RELEASE_DATES_URL,
                fred_result.error,
                source_variant=FRED_TARGETED_SOURCE_VARIANT,
                attempts=attempts,
            )

    if events:
        successful_attempt = next(
            attempt for attempt in attempts if attempt["status"] == "success"
        )
        source_variant = successful_attempt["source_variant"]
        if source_variant == "official_html":
            source_variant = "official_html_fallback"
        return SourceResult(
            "bls",
            "success",
            events,
            loaded_at,
            source_url,
            source_variant=source_variant,
            attempts=attempts,
        )

    return SourceResult(
        "bls",
        "failed",
        [],
        loaded_at,
        source_url,
        "BLS schedule produced no recognized events",
        attempts=attempts,
    )
