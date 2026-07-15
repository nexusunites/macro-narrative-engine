import json
import os
from datetime import date, datetime
from pathlib import Path

from config import CONFIG_DIR
from mne.calendar_sources import bea, bls, eia, federal_reserve
from mne.calendar_sources.base import dedupe_events, now_iso
from mne.macro_catalysts import MACRO_CALENDAR_FILE, MACRO_CALENDAR_METADATA_FILE


REQUIRED_SOURCES = {
    "bls": bls.fetch_events,
    "bea": bea.fetch_events,
    "federal_reserve": federal_reserve.fetch_events,
    "eia": eia.fetch_events,
}

AUTO_REFRESH_ENV_VAR = "MNE_AUTO_REFRESH_MACRO_CALENDAR"


def auto_refresh_macro_calendar_enabled():
    value = os.environ.get(AUTO_REFRESH_ENV_VAR, "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def refresh_macro_calendar(
    *,
    as_of=None,
    calendar_path=MACRO_CALENDAR_FILE,
    metadata_path=MACRO_CALENDAR_METADATA_FILE,
    source_fetchers=None,
    get=None,
    loaded_at=None,
) -> dict:
    as_of = _coerce_date(as_of) or date.today()
    loaded_at = loaded_at or now_iso()
    source_fetchers = source_fetchers or REQUIRED_SOURCES
    source_results = {}
    all_events = []

    for name, fetcher in source_fetchers.items():
        try:
            result = fetcher(as_of=as_of, get=get, loaded_at=loaded_at)
        except Exception as error:
            result = _failed_source_result(name, loaded_at, str(error))
        source_results[name] = result
        if result.status in {"success", "partial"}:
            all_events.extend(result.events)

    events = dedupe_events(_valid_events(all_events, as_of=as_of))
    failed_sources = [
        name
        for name, result in source_results.items()
        if result.status not in {"success"}
    ]
    successful_sources = [
        name
        for name, result in source_results.items()
        if result.status in {"success", "partial"} and result.events
    ]

    if events and not failed_sources:
        status = "complete"
    elif events and successful_sources:
        status = "partial"
    else:
        status = "failed"

    calendar_path = Path(calendar_path)
    metadata_path = Path(metadata_path)
    used_previous_calendar = False

    if status in {"complete", "partial"}:
        metadata = _build_metadata(
            status=status,
            generated_at=loaded_at,
            events=events,
            source_results=source_results,
            failed_sources=failed_sources,
            partial=status == "partial",
            used_previous_calendar=False,
        )
        _atomic_write_json(calendar_path, events)
        _atomic_write_json(metadata_path, metadata)
    else:
        previous_events = _load_valid_calendar(calendar_path)
        if previous_events:
            used_previous_calendar = True
            events = previous_events
            status = "stale_fallback"
            metadata = _build_metadata(
                status=status,
                generated_at=loaded_at,
                events=events,
                source_results=source_results,
                failed_sources=list(source_results),
                partial=True,
                used_previous_calendar=True,
            )
            _atomic_write_json(metadata_path, metadata)
        else:
            metadata = _build_metadata(
                status="failed",
                generated_at=loaded_at,
                events=[],
                source_results=source_results,
                failed_sources=list(source_results),
                partial=True,
                used_previous_calendar=False,
            )
            _atomic_write_json(metadata_path, metadata)

    return {
        "status": status,
        "event_count": len(events),
        "coverage_start": metadata.get("coverage_start"),
        "coverage_end": metadata.get("coverage_end"),
        "source_results": {
            name: result.to_metadata() for name, result in source_results.items()
        },
        "calendar_path": str(calendar_path),
        "metadata_path": str(metadata_path),
        "used_previous_calendar": used_previous_calendar,
        "warnings": _warnings_for(status, failed_sources, used_previous_calendar),
    }


def _failed_source_result(name, loaded_at, error):
    from mne.calendar_sources.base import SourceResult

    return SourceResult(name, "failed", [], loaded_at, "", error)


def _coerce_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _valid_events(events, as_of=None):
    valid = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if not all(event.get(field) for field in ("date", "name", "importance", "event_id")):
            continue
        if as_of is not None:
            try:
                event_date = date.fromisoformat(str(event["date"]))
            except ValueError:
                continue
            if event_date < as_of:
                continue
        valid.append(event)
    return valid


def _load_valid_calendar(path):
    try:
        events = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if not isinstance(events, list):
        return []
    return _valid_events(events)


def _build_metadata(
    *,
    status,
    generated_at,
    events,
    source_results,
    failed_sources,
    partial,
    used_previous_calendar,
):
    dates = [event["date"] for event in events if event.get("date")]
    return {
        "generated_at": generated_at,
        "coverage_start": min(dates) if dates else None,
        "coverage_end": max(dates) if dates else None,
        "event_count": len(events),
        "status": status,
        "sources": {
            name: result.to_metadata() for name, result in source_results.items()
        },
        "failed_sources": failed_sources,
        "partial": partial,
        "used_previous_calendar": used_previous_calendar,
    }


def _atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json.loads(encoded)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(encoded + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _warnings_for(status, failed_sources, used_previous_calendar):
    warnings = []
    if status == "partial":
        warnings.append(f"Macro calendar refresh was partial: {', '.join(failed_sources)}")
    if status == "stale_fallback" or used_previous_calendar:
        warnings.append("Macro calendar refresh failed; using previous valid calendar.")
    if status == "failed":
        warnings.append("Macro calendar refresh failed and no previous valid calendar was available.")
    return warnings


def main():
    result = refresh_macro_calendar()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
