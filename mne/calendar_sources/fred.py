import json
import os
import time
from datetime import date, timedelta

import requests

from mne.calendar_sources.base import (
    CalendarSourceError,
    DEFAULT_USER_AGENT,
    SourceResult,
    dedupe_events,
    now_iso,
)


FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/releases/dates"
FRED_TARGETED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"
FRED_API_KEY_ENV_VAR = "FRED_API_KEY"
SOURCE_FAMILY = "fred_release_dates_fallback"
TARGETED_SOURCE_VARIANT = "fred_targeted_release_dates"

FRED_BLS_RELEASES = {
    "cpi": {
        "release_id": 10,
        "expected_name": "Consumer Price Index",
        "event_type": "cpi",
        "importance": "red",
    },
    "ppi": {
        "release_id": 46,
        "expected_name": "Producer Price Index",
        "event_type": "ppi",
        "importance": "red",
    },
    "employment_situation": {
        "release_id": 50,
        "expected_name": "Employment Situation",
        "event_type": "employment_situation",
        "importance": "red",
    },
    "jolts": {
        "release_id": 192,
        "expected_name": "Job Openings and Labor Turnover Survey",
        "event_type": "jolts",
        "importance": "orange",
    },
    "employment_cost_index": {
        "release_id": 11,
        "expected_name": "Employment Cost Index",
        "event_type": "employment_cost_index",
        "importance": "orange",
    },
    "import_export_prices": {
        "release_id": 188,
        "expected_name": "U.S. Import and Export Price Indexes",
        "event_type": "import_export_prices",
        "importance": "orange",
    },
}

FRED_RELEASES = {
    10: ("Consumer Price Index", "cpi", "red"),
    11: ("Employment Cost Index", "employment_cost_index", "orange"),
    46: ("Producer Price Index", "ppi", "red"),
    50: ("Employment Situation", "employment_situation", "red"),
    188: ("U.S. Import and Export Price Indexes", "import_export_prices", "orange"),
    192: ("Job Openings and Labor Turnover Survey", "jolts", "orange"),
    "Consumer Price Index": ("Consumer Price Index", "cpi", "red"),
    "Producer Price Index": ("Producer Price Index", "ppi", "red"),
    "Employment Situation": ("Employment Situation", "employment_situation", "red"),
    "Job Openings and Labor Turnover Survey": (
        "Job Openings and Labor Turnover Survey",
        "jolts",
        "orange",
    ),
    "Employment Cost Index": (
        "Employment Cost Index",
        "employment_cost_index",
        "orange",
    ),
    "U.S. Import and Export Price Indexes": (
        "U.S. Import and Export Price Indexes",
        "import_export_prices",
        "orange",
    ),
    "U.S. Export and Import Price Indexes": (
        "U.S. Import and Export Price Indexes",
        "import_export_prices",
        "orange",
    ),
}


def get_fred_api_key(env=None):
    env = os.environ if env is None else env
    return env.get(FRED_API_KEY_ENV_VAR)


def parse_fred_release_dates(payload: str, *, source_url=FRED_RELEASE_DATES_URL, loaded_at=None):
    loaded_at = loaded_at or now_iso()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CalendarSourceError("FRED response was not valid JSON") from error
    rows = data.get("release_dates")
    if not isinstance(rows, list):
        raise CalendarSourceError("FRED response did not contain release_dates")

    events = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mapping = _mapping_for_release(row)
        if not mapping:
            continue
        try:
            release_date = date.fromisoformat(str(row.get("date")))
        except (TypeError, ValueError):
            continue
        name, event_type, importance = mapping
        events.append(
            {
                "event_id": f"fred:{event_type}:{release_date.isoformat()}",
                "date": release_date.isoformat(),
                "time": None,
                "timezone": "America/New_York",
                "scheduled_at": None,
                "time_precision": "date_only",
                "name": name,
                "event_type": event_type,
                "importance": importance,
                "source": "official_macro_calendar",
                "source_agency": "BLS",
                "source_family": SOURCE_FAMILY,
                "source_url": source_url,
                "loaded_at": loaded_at,
                "fred_release_id": row.get("release_id"),
                "fred_release_name": row.get("release_name"),
            }
        )
    return dedupe_events(events)


def fetch_fred_release_dates(
    *,
    api_key=None,
    as_of=None,
    coverage_days=370,
    limit=1000,
    offset=0,
    get=None,
    timeout=15,
):
    if not api_key:
        raise CalendarSourceError("FRED API key is not configured.")
    as_of = as_of or date.today()
    end_date = as_of + timedelta(days=coverage_days)
    getter = get or requests.get
    params = {
        "api_key": api_key,
        "file_type": "json",
        "realtime_start": as_of.isoformat(),
        "realtime_end": end_date.isoformat(),
        "include_release_dates_with_no_data": "true",
        "limit": str(limit),
        "offset": str(offset),
    }
    response = getter(
        FRED_RELEASE_DATES_URL,
        params=params,
        timeout=timeout,
        headers={"User-Agent": DEFAULT_USER_AGENT},
    )
    response.raise_for_status()
    return response.text


def fetch_fred_targeted_release_dates(
    release_id,
    *,
    api_key,
    as_of=None,
    coverage_days=370,
    limit=24,
    get=None,
    timeout=15,
    retries=1,
):
    if not api_key:
        raise CalendarSourceError("FRED API key is not configured.")
    as_of = as_of or date.today()
    end_date = as_of + timedelta(days=coverage_days)
    getter = get or requests.get
    params = {
        "release_id": str(release_id),
        "api_key": api_key,
        "file_type": "json",
        "realtime_start": as_of.isoformat(),
        "realtime_end": end_date.isoformat(),
        "include_release_dates_with_no_data": "true",
        "limit": str(limit),
    }
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = getter(
                FRED_TARGETED_RELEASE_DATES_URL,
                params=params,
                timeout=timeout,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            )
            if getattr(response, "status_code", 200) in {400, 401, 403}:
                response.raise_for_status()
            response.raise_for_status()
            return response.text
        except Exception as error:
            last_error = error
            if not _is_retryable_fred_error(error) or attempt >= retries:
                break
            time.sleep(0.25)
    raise CalendarSourceError(str(last_error))


def parse_fred_targeted_release_dates(
    payload: str,
    release_key: str,
    *,
    source_url=FRED_TARGETED_RELEASE_DATES_URL,
    loaded_at=None,
):
    loaded_at = loaded_at or now_iso()
    config = FRED_BLS_RELEASES[release_key]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CalendarSourceError("FRED response was not valid JSON") from error
    rows = data.get("release_dates")
    if not isinstance(rows, list):
        raise CalendarSourceError("FRED response did not contain release_dates")

    events = []
    observed_name = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_release_id = _coerce_int(row.get("release_id"))
        if row_release_id is not None and row_release_id != config["release_id"]:
            raise CalendarSourceError(
                f"FRED release_id {config['release_id']} returned unexpected release_id "
                f"{row_release_id}"
            )
        release_name = str(row.get("release_name") or "").strip()
        if release_name:
            observed_name = release_name
            _validate_release_name(release_key, release_name)
        try:
            release_date = date.fromisoformat(str(row.get("date")))
        except (TypeError, ValueError):
            continue
        events.append(
            {
                "event_id": f"fred:{config['event_type']}:{release_date.isoformat()}",
                "date": release_date.isoformat(),
                "time": None,
                "timezone": "America/New_York",
                "scheduled_at": None,
                "time_precision": "date_only",
                "name": config["expected_name"],
                "event_type": config["event_type"],
                "importance": config["importance"],
                "source": "official_macro_calendar",
                "source_agency": "BLS",
                "source_family": SOURCE_FAMILY,
                "source_url": source_url,
                "loaded_at": loaded_at,
                "fred_release_id": config["release_id"],
                "fred_release_name": observed_name or config["expected_name"],
            }
        )
    return dedupe_events(events)


def get_fred_bls_calendar_events(
    *,
    as_of=None,
    api_key=None,
    get=None,
    loaded_at=None,
    env=None,
) -> SourceResult:
    loaded_at = loaded_at or now_iso()
    api_key = api_key if api_key is not None else get_fred_api_key(env)
    if not api_key:
        return SourceResult(
            "fred",
            "skipped",
            [],
            loaded_at,
            FRED_TARGETED_RELEASE_DATES_URL,
            "FRED API key is not configured.",
            source_variant=TARGETED_SOURCE_VARIANT,
            attempts=[
                {
                    "source_variant": TARGETED_SOURCE_VARIANT,
                    "status": "skipped",
                    "reason": "FRED API key is not configured.",
                }
            ],
        )

    events = []
    release_results = {}
    stop_for_invalid_key = False
    for release_key, config in FRED_BLS_RELEASES.items():
        try:
            payload = fetch_fred_targeted_release_dates(
                config["release_id"],
                api_key=api_key,
                as_of=as_of,
                get=get,
            )
            _validate_release_payload(payload, release_key)
            release_events = parse_fred_targeted_release_dates(
                payload,
                release_key,
                loaded_at=loaded_at,
            )
            events.extend(release_events)
            release_results[release_key] = {
                "status": "success",
                "event_count": len(release_events),
            }
        except Exception as error:
            sanitized = _sanitize_error(error, api_key)
            release_results[release_key] = {"status": "failed", "error": sanitized}
            if _is_invalid_key_error(error):
                stop_for_invalid_key = True
                break

    events = dedupe_events(events)
    failed_keys = [
        key for key, result in release_results.items() if result.get("status") != "success"
    ]

    if events:
        status = "partial" if failed_keys or stop_for_invalid_key else "success"
        error = None
        if status == "partial":
            error = f"FRED targeted release dates partial failure: {', '.join(failed_keys)}"
        return SourceResult(
            "fred",
            status,
            events,
            loaded_at,
            FRED_TARGETED_RELEASE_DATES_URL,
            error,
            source_variant=TARGETED_SOURCE_VARIANT,
            attempts=[
                {
                    "source_variant": TARGETED_SOURCE_VARIANT,
                    "status": status,
                    "event_count": len(events),
                    "release_results": release_results,
                }
            ],
        )

    if not failed_keys:
        failed_keys = list(FRED_BLS_RELEASES)
    error = "FRED response produced no recognized BLS events"
    if release_results:
        first_failure = next(
            (result.get("error") for result in release_results.values() if result.get("error")),
            None,
        )
        if first_failure:
            error = first_failure
    return SourceResult(
        "fred",
        "failed",
        [],
        loaded_at,
        FRED_TARGETED_RELEASE_DATES_URL,
        _sanitize_error(error, api_key),
        source_variant=TARGETED_SOURCE_VARIANT,
        attempts=[
            {
                "source_variant": TARGETED_SOURCE_VARIANT,
                "status": "failed",
                "error": _sanitize_error(error, api_key),
                "release_results": release_results,
            }
        ],
    )


def _mapping_for_release(row):
    release_name = str(row.get("release_name") or "").strip()
    release_id = row.get("release_id")
    try:
        release_id = int(release_id)
    except (TypeError, ValueError):
        pass
    if release_id in FRED_RELEASES:
        mapping = FRED_RELEASES[release_id]
        if release_name and release_name != mapping[0]:
            return None
        return mapping
    return FRED_RELEASES.get(release_name)


def _validate_release_payload(payload, release_key):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CalendarSourceError("FRED response was not valid JSON") from error
    rows = data.get("release_dates")
    if not isinstance(rows, list):
        raise CalendarSourceError("FRED response did not contain release_dates")
    for row in rows:
        if isinstance(row, dict) and row.get("release_name"):
            _validate_release_name(release_key, str(row["release_name"]).strip())
            return


def _validate_release_name(release_key, release_name):
    expected = FRED_BLS_RELEASES[release_key]["expected_name"]
    if release_name != expected:
        raise CalendarSourceError(
            f"FRED release_id {FRED_BLS_RELEASES[release_key]['release_id']} returned "
            f"unexpected release name {release_name!r}; expected {expected!r}"
        )


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_retryable_fred_error(error):
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code is not None:
        return status_code >= 500 or status_code == 429
    message = str(error).lower()
    if any(token in message for token in ("invalid api key", "bad api key", "400", "401", "403")):
        return False
    return any(
        token in message
        for token in ("timeout", "timed out", "temporarily", "server", "500", "502", "503", "504", "429")
    )


def _is_invalid_key_error(error):
    message = str(error).lower()
    return any(token in message for token in ("invalid api key", "bad api key", "api key", "400", "401", "403"))


def _sanitize_error(error, api_key):
    message = str(error)
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return message
