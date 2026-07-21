import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Callable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests


SOURCE_ID = "bls_cpi"
SOURCE_NAME = "Bureau of Labor Statistics"
PROVIDER = "BLS"
CATEGORY = "Inflation / Economic Data"
SOURCE_TYPE = "official_release"
USAGE_STORAGE_RIGHTS = "NORMALIZED_EVIDENCE"
ARCHIVE_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
DEFAULT_USER_AGENT = "MacroNarrativeEngine/1.0 historical-backfill"
RELEASE_TIME = dt_time(8, 30)
EASTERN = ZoneInfo("America/New_York")


class BlsCpiBackfillError(RuntimeError):
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


def fetch_bls_cpi_records(start_date, end_date, get: Callable | None = None) -> list[dict]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")

    payload = _fetch_text(ARCHIVE_URL, get=get)
    return [
        record
        for record in parse_bls_cpi_records(payload)
        if start.isoformat() <= record["published_date"] <= end.isoformat()
    ]


def parse_bls_cpi_records(payload) -> list[dict]:
    parser = _LinkParser()
    parser.feed(payload or "")
    records = []
    for link in parser.links:
        record = _record_from_link(link)
        if record is not None:
            records.append(record)
    return _dedupe_records(records)


def normalize_bls_cpi_record(raw_record, retrieval_timestamp=None) -> dict:
    if not isinstance(raw_record, dict):
        raise TypeError("raw_record must be a dictionary.")

    url = _text(raw_record.get("url"))
    raw_id = _text(raw_record.get("raw_id")) or _raw_id_from_url(url)
    return {
        "title": _text(raw_record.get("title")) or "Consumer Price Index News Release",
        "source": SOURCE_NAME,
        "provider": PROVIDER,
        "published_at": _published_at(raw_record),
        "url": url,
        "source_type": SOURCE_TYPE,
        "category": CATEGORY,
        "raw_id": raw_id,
        "reference_id": raw_id,
        "retrieval_timestamp": _format_utc(
            retrieval_timestamp or raw_record.get("retrieval_timestamp") or _now_utc()
        ),
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
    raise BlsCpiBackfillError(str(last_error))


def _record_from_link(link: _Link) -> dict | None:
    absolute = urljoin(ARCHIVE_URL, link.href)
    raw_id = _raw_id_from_url(absolute)
    if raw_id is None:
        return None
    match = re.fullmatch(r"cpi_(\d{2})(\d{2})(\d{4})", raw_id, re.IGNORECASE)
    if not match:
        return None
    try:
        release_day = date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None

    reference_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\s+Consumer Price Index\b",
        link.text,
        re.IGNORECASE,
    )
    title = (
        f"Consumer Price Index — {reference_match.group(1).title()} {reference_match.group(2)}"
        if reference_match
        else "Consumer Price Index News Release"
    )
    published = datetime.combine(release_day, RELEASE_TIME, tzinfo=EASTERN)
    return {
        "title": title,
        "published_date": release_day.isoformat(),
        "published_at": _format_utc(published),
        "url": absolute,
        "raw_id": raw_id.lower(),
        "reference_id": raw_id.lower(),
    }


def _raw_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    name = PurePosixPath(urlparse(url).path).name
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in {".htm", ".html", ".txt", ".pdf"}:
        return None
    return name[: -len(suffix)] or None


def _published_at(record: dict) -> str:
    if record.get("published_at"):
        return _format_utc(record["published_at"])
    published_date = _parse_date(record.get("published_date"), "published_date")
    return _format_utc(datetime.combine(published_date, RELEASE_TIME, tzinfo=EASTERN))


def _dedupe_records(records: list[dict]) -> list[dict]:
    by_id = {}
    extension_rank = {".htm": 0, ".html": 1, ".txt": 2, ".pdf": 3}
    for record in records:
        key = record.get("raw_id") or record.get("url")
        current = by_id.get(key)
        rank = extension_rank.get(PurePosixPath(urlparse(record.get("url") or "").path).suffix.lower(), 9)
        current_rank = extension_rank.get(
            PurePosixPath(urlparse((current or {}).get("url") or "").path).suffix.lower(), 9
        )
        if current is None or rank < current_rank:
            by_id[key] = record
    return sorted(by_id.values(), key=lambda item: (item.get("published_at") or "", item.get("url") or ""))


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
