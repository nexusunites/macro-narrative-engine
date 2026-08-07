"""Validated, deterministic persistence for per-asset chart events."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from config import DATA_DIR
from mne.company_catalysts import (
    MAJOR_COMPANY_CATALYSTS,
    get_historical_company_earnings_dates,
)
from mne.macro_catalysts import MACRO_CALENDAR_FILE, _load_macro_calendar


ASSET_EVENTS_DIR = DATA_DIR / "asset_events"
STORE_VERSION = "1.0.0"
EVENT_TYPES = frozenset({"earnings", "macro"})
EVENT_FIELDS = frozenset({"date", "type", "title", "blurb", "detail", "source"})
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class AssetEventsError(ValueError):
    """Raised when a persisted asset event feed is unavailable or invalid."""


@dataclass(frozen=True)
class AssetEvent:
    date: str
    type: str
    title: str
    blurb: str
    detail: str
    source: str


@dataclass(frozen=True)
class AssetEventFeed:
    ticker: str
    version: str
    events: tuple[AssetEvent, ...]


def _required_text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssetEventsError(f"{location} must be a non-empty string")
    return value.strip()


def _iso_date(value: Any, location: str) -> str:
    value = _required_text(value, location)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AssetEventsError(f"{location} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise AssetEventsError(f"{location} must use YYYY-MM-DD")
    return value


def validate_asset_event_feed(data: Any) -> AssetEventFeed:
    if not isinstance(data, dict):
        raise AssetEventsError("asset event feed must be an object")
    if set(data) != {"ticker", "version", "events"}:
        raise AssetEventsError("asset event feed must contain exactly ticker, version, and events")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise AssetEventsError("version must use MAJOR.MINOR.PATCH semantic versioning")
    ticker = _required_text(data.get("ticker"), "ticker")
    if not isinstance(data.get("events"), list):
        raise AssetEventsError("events must be a list")
    events = []
    for index, raw in enumerate(data["events"]):
        location = f"events[{index}]"
        if not isinstance(raw, dict) or set(raw) != EVENT_FIELDS:
            raise AssetEventsError(f"{location} must contain exactly the ratified event fields")
        event_type = _required_text(raw.get("type"), f"{location}.type")
        if event_type not in EVENT_TYPES:
            raise AssetEventsError(f"{location}.type must be earnings or macro")
        events.append(AssetEvent(
            date=_iso_date(raw.get("date"), f"{location}.date"),
            type=event_type,
            title=_required_text(raw.get("title"), f"{location}.title"),
            blurb=_required_text(raw.get("blurb"), f"{location}.blurb"),
            detail=_required_text(raw.get("detail"), f"{location}.detail"),
            source=_required_text(raw.get("source"), f"{location}.source"),
        ))
    return AssetEventFeed(ticker, version, tuple(sorted(events, key=_event_key)))


def _event_key(event: AssetEvent) -> tuple[str, str, str, str]:
    return event.date, event.type, event.title.casefold(), event.source.casefold()


def load_asset_events(ticker: str, path: str | Path | None = None) -> AssetEventFeed:
    event_path = Path(path) if path is not None else ASSET_EVENTS_DIR / f"{ticker}.json"
    try:
        data = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetEventsError(f"unable to load asset event feed: {exc}") from exc
    feed = validate_asset_event_feed(data)
    if feed.ticker != ticker:
        raise AssetEventsError("ticker does not match requested asset")
    return feed


def load_asset_events_or_empty(ticker: str, path: str | Path | None = None) -> AssetEventFeed:
    event_path = Path(path) if path is not None else ASSET_EVENTS_DIR / f"{ticker}.json"
    if not event_path.exists():
        return AssetEventFeed(ticker, STORE_VERSION, ())
    return load_asset_events(ticker, event_path)


def write_asset_events(ticker: str, events: tuple[AssetEvent, ...] | list[AssetEvent], path: str | Path | None = None) -> None:
    event_path = Path(path) if path is not None else ASSET_EVENTS_DIR / f"{ticker}.json"
    feed = validate_asset_event_feed({
        "ticker": ticker,
        "version": STORE_VERSION,
        "events": [asdict(event) for event in events],
    })
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(json.dumps({
        "ticker": feed.ticker,
        "version": feed.version,
        "events": [asdict(event) for event in feed.events],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _matches(name: str, catalyst_names: set[str]) -> bool:
    name = name.casefold()
    return any(token.casefold() in name or name in token.casefold() for token in catalyst_names)


def _scheduled_date(event: dict) -> date | None:
    value = event.get("scheduled_at")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _macro_event(event: dict) -> AssetEvent | None:
    scheduled_date = _scheduled_date(event)
    title = str(event.get("name") or "").strip()
    scheduled_at = str(event.get("scheduled_at") or "").strip()
    source = str(event.get("source_url") or event.get("source") or event.get("source_agency") or "").strip()
    if scheduled_date is None or not title or not source:
        return None
    agency = str(event.get("source_agency") or event.get("source") or "the persisted macro calendar").strip()
    return AssetEvent(
        date=scheduled_date.isoformat(),
        type="macro",
        title=title,
        blurb=f"{title} was scheduled for this session in the persisted macro calendar.",
        detail=f"Scheduled at {scheduled_at}. Calendar attribution: {agency}.",
        source=source,
    )


def _earnings_event(symbol: str, earnings_date: date) -> AssetEvent:
    return AssetEvent(
        date=earnings_date.isoformat(),
        type="earnings",
        title=f"{symbol} Earnings",
        blurb=f"The persisted yfinance earnings calendar places {symbol} earnings on this date.",
        detail="This records the calendar date only; it does not describe the result or the market reaction.",
        source="yfinance get_earnings_dates",
    )


def refresh_asset_event_feeds(
    ticker_symbols: dict[str, str],
    narrative_assets: Any,
    story_registry: Any,
    *,
    as_of: date | None = None,
    calendar_file: str | Path = MACRO_CALENDAR_FILE,
    events_dir: str | Path = ASSET_EVENTS_DIR,
    earnings_loader: Callable = get_historical_company_earnings_dates,
) -> int:
    """Replace each registry ticker feed from current persisted source inputs."""
    as_of = as_of or date.today()
    catalyst_names_by_group = {
        group: {name for story in story_registry.stories if story.group == group for name in story.catalyst_names}
        for group, _ in narrative_assets.narratives
    }
    groups_by_ticker: dict[str, set[str]] = {}
    for group, mappings in narrative_assets.narratives:
        for mapping in mappings:
            groups_by_ticker.setdefault(mapping.ticker, set()).add(group)
    macro_inputs = [event for event in _load_macro_calendar(calendar_file) if isinstance(event, dict)]
    written = 0
    for canonical_ticker, groups in sorted(groups_by_ticker.items()):
        symbol = ticker_symbols.get(canonical_ticker)
        if not symbol:
            continue
        relevant_names = {name for group in groups for name in catalyst_names_by_group.get(group, set())}
        events = []
        for raw in macro_inputs:
            if _matches(str(raw.get("name") or ""), relevant_names):
                normalized = _macro_event(raw)
                if normalized is not None:
                    events.append(normalized)
        if canonical_ticker in MAJOR_COMPANY_CATALYSTS:
            events.extend(_earnings_event(canonical_ticker, value) for value in earnings_loader(symbol, as_of=as_of))
        deduped = {_event_key(event): event for event in events}
        write_asset_events(symbol, list(deduped.values()), Path(events_dir) / f"{symbol}.json")
        written += 1
    return written


def select_upcoming_asset_catalysts(
    catalysts: list[dict] | tuple[dict, ...] | None,
    narrative: str,
    ticker: str,
    story_registry: Any,
    *,
    calendar_file: str | Path = MACRO_CALENDAR_FILE,
) -> tuple[dict, ...]:
    """Select the engine's forward feed and attach only persisted real timestamps."""
    relevant_names = {
        name
        for story in story_registry.stories
        if story.group == narrative
        for name in story.catalyst_names
    }
    scheduled = {}
    for event in _load_macro_calendar(calendar_file):
        if not isinstance(event, dict):
            continue
        key = (str(event.get("date") or ""), str(event.get("name") or "").strip().casefold())
        if _scheduled_date(event) is not None:
            scheduled[key] = event.get("scheduled_at")
    selected = []
    for catalyst in catalysts or ():
        name = str(catalyst.get("name") or "").strip()
        is_ticker_earnings = catalyst.get("ticker") == ticker and "earnings" in name.casefold()
        if not is_ticker_earnings and not _matches(name, relevant_names):
            continue
        item = dict(catalyst)
        item["type"] = "earnings" if is_ticker_earnings else "macro"
        timestamp = scheduled.get((str(item.get("date") or ""), name.casefold()))
        if timestamp:
            item["scheduled_at"] = timestamp
        selected.append(item)
    return tuple(sorted(selected, key=lambda item: (item.get("date", ""), item.get("name", ""))))
