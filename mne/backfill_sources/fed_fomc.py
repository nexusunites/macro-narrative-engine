import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests


SOURCE_ID = "fed_fomc"
SOURCE_NAME = "Federal Reserve"
PROVIDER = "Federal Reserve"
CATEGORY = "Central Bank Communications"
SOURCE_TYPE = "official_central_bank_statement"
USAGE_STORAGE_RIGHTS = "NORMALIZED_EVIDENCE"
ARCHIVE_URL_TEMPLATE = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
DEFAULT_USER_AGENT = "MacroNarrativeEngine/1.0 historical-backfill"
STATEMENT_TIME_UTC = dt_time(19, 0, tzinfo=timezone.utc)


class FedFomcBackfillError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Link:
    href: str
    text: str


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[_Link] = []
        self._href_stack: list[str | None] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs_by_name = {name.lower(): value for name, value in attrs}
        self._href_stack.append(attrs_by_name.get("href"))
        self._parts.append("")

    def handle_data(self, data):
        if self._href_stack:
            self._parts[-1] = f"{self._parts[-1]} {data}".strip()

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = self._parts.pop().strip()
        if href:
            self.links.append(_Link(href=href, text=re.sub(r"\s+", " ", text)))


def fetch_fed_fomc_records(start_date, end_date, get: Callable | None = None) -> list[dict]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")

    records: list[dict] = []
    for year in range(start.year, end.year + 1):
        url = ARCHIVE_URL_TEMPLATE.format(year=year)
        payload = _fetch_text(url, get=get)
        records.extend(parse_fed_fomc_records(payload, year))

    return [
        record
        for record in _dedupe_records(records)
        if start.isoformat() <= record.get("published_date", "") <= end.isoformat()
    ]


def parse_fed_fomc_records(payload, year) -> list[dict]:
    parser = _LinkParser()
    parser.feed(payload or "")

    records = []
    for link in parser.links:
        record = _record_from_link(link, year)
        if record is not None:
            records.append(record)
    return _dedupe_records(records)


def normalize_fed_fomc_record(raw_record, retrieval_timestamp=None) -> dict:
    if not isinstance(raw_record, dict):
        raise TypeError("raw_record must be a dictionary.")

    title = _text(raw_record.get("title")) or "Federal Reserve issues FOMC statement"
    published_at = _published_at(raw_record)
    url = _text(raw_record.get("url"))
    raw_id = _text(raw_record.get("raw_id")) or _raw_id_from_url(url)
    retrieval = _format_utc(retrieval_timestamp or raw_record.get("retrieval_timestamp") or _now_utc())

    return {
        "title": title,
        "source": SOURCE_NAME,
        "provider": PROVIDER,
        "published_at": published_at,
        "url": url,
        "source_type": SOURCE_TYPE,
        "category": CATEGORY,
        "raw_id": raw_id,
        "retrieval_timestamp": retrieval,
        "usage_storage_rights": USAGE_STORAGE_RIGHTS,
        "source_id": SOURCE_ID,
    }


def _fetch_text(url: str, timeout=15, retries=1, get: Callable | None = None) -> str:
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
    raise FedFomcBackfillError(str(last_error))


def _record_from_link(link: _Link, year: int) -> dict | None:
    absolute = urljoin(ARCHIVE_URL_TEMPLATE.format(year=year), link.href)
    raw_id = _raw_id_from_url(absolute)
    if raw_id is None or not _looks_like_post_meeting_statement(raw_id, link.text, absolute):
        return None

    match = re.search(r"(\d{8})", raw_id)
    if not match:
        return None
    statement_day = _date_from_yyyymmdd(match.group(1))
    if statement_day is None:
        return None

    return {
        "title": _statement_title(link.text),
        "published_date": statement_day.isoformat(),
        "published_at": _format_utc(datetime.combine(statement_day, STATEMENT_TIME_UTC)),
        "url": absolute,
        "raw_id": raw_id,
    }


def _looks_like_post_meeting_statement(raw_id: str, text: str, url: str) -> bool:
    lower_text = (text or "").casefold()
    lower_url = (url or "").casefold()
    if "minutes" in lower_text or "minutes" in lower_url:
        return False
    if "projection" in lower_text or "projection" in lower_url:
        return False
    return bool(re.fullmatch(r"monetary\d{8}a", raw_id)) or (
        "fomc statement" in lower_text and "monetary" in lower_url
    )


def _statement_title(text: str) -> str:
    normalized = _text(text)
    if normalized and "statement" in normalized.casefold():
        return normalized
    return "Federal Reserve issues FOMC statement"


def _published_at(record: dict) -> str:
    value = record.get("published_at")
    if value:
        return _format_utc(value)
    published_date = _parse_date(record.get("published_date"), "published_date")
    return _format_utc(datetime.combine(published_date, STATEMENT_TIME_UTC))


def _raw_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    name = PurePosixPath(urlparse(url).path).name
    return name.removesuffix(".htm").removesuffix(".html") or None


def _dedupe_records(records: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for record in records:
        key = record.get("raw_id") or record.get("url")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return sorted(deduped, key=lambda item: (item.get("published_at") or "", item.get("url") or ""))


def _date_from_yyyymmdd(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_date(value, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid {field_name} {value!r}; expected YYYY-MM-DD.") from error


def _format_utc(value) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_utc() -> str:
    return _format_utc(datetime.now(timezone.utc))


def _text(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None

