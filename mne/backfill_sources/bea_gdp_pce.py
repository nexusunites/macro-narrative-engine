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


SOURCE_ID = "bea_gdp_pce"
SOURCE_NAME = "Bureau of Economic Analysis"
PROVIDER = "BEA"
CATEGORY = "Economic Data / Growth / Inflation"
SOURCE_TYPE = "official_release"
USAGE_STORAGE_RIGHTS = "NORMALIZED_EVIDENCE"
ARCHIVE_URL = "https://www.bea.gov/news/all-news-releases"
DEFAULT_USER_AGENT = "MacroNarrativeEngine/1.0 historical-backfill"
RELEASE_TIME = dt_time(8, 30)
EASTERN = ZoneInfo("America/New_York")


class BeaGdpPceBackfillError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Candidate:
    date_text: str
    href: str
    title: str


class _RowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates: list[_Candidate] = []
        self._pending_text: str | None = None
        self._href_stack: list[str | None] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs_by_name = {name.lower(): value for name, value in attrs}
        self._href_stack.append(attrs_by_name.get("href"))
        self._parts.append("")

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._href_stack:
            self._parts[-1] = f"{self._parts[-1]} {text}".strip()
        else:
            self._pending_text = text

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        title = re.sub(r"\s+", " ", self._parts.pop()).strip()
        if href and self._pending_text:
            self.candidates.append(_Candidate(self._pending_text, href, title))
        self._pending_text = None


def fetch_bea_gdp_pce_records(start_date, end_date, get: Callable | None = None) -> list[dict]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")
    payload = _fetch_text(ARCHIVE_URL, get=get)
    return [
        record
        for record in parse_bea_gdp_pce_records(payload)
        if start.isoformat() <= record["published_date"] <= end.isoformat()
    ]


def parse_bea_gdp_pce_records(payload) -> list[dict]:
    parser = _RowParser()
    parser.feed(payload or "")
    records = []
    for candidate in parser.candidates:
        if not (_is_gdp_release(candidate.title) or _is_pce_release(candidate.title)):
            continue
        try:
            release_day = datetime.strptime(candidate.date_text, "%B %d, %Y").date()
        except ValueError:
            continue
        absolute_url = urljoin(ARCHIVE_URL, candidate.href)
        raw_id = PurePosixPath(urlparse(absolute_url).path).name or None
        if not raw_id:
            continue
        records.append({
            "title": candidate.title,
            "published_date": release_day.isoformat(),
            "published_at": _format_utc(datetime.combine(release_day, RELEASE_TIME, tzinfo=EASTERN)),
            "url": absolute_url,
            "raw_id": raw_id,
            "reference_id": raw_id,
        })
    return _dedupe_records(records)


def normalize_bea_gdp_pce_record(raw_record, retrieval_timestamp=None) -> dict:
    if not isinstance(raw_record, dict):
        raise TypeError("raw_record must be a dictionary.")
    url = _text(raw_record.get("url"))
    raw_id = _text(raw_record.get("raw_id")) or _raw_id_from_url(url)
    return {
        "title": _text(raw_record.get("title")) or "BEA GDP/PCE News Release",
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


def _is_gdp_release(title: str) -> bool:
    lowered = title.casefold()
    return (
        "gross domestic product" in lowered
        and "industry" not in lowered
        and "regional" not in lowered
        and "by state" not in lowered
    )


def _is_pce_release(title: str) -> bool:
    return "personal income and outlays" in title.casefold()


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
    raise BeaGdpPceBackfillError(str(last_error))


def _dedupe_records(records: list[dict]) -> list[dict]:
    by_id = {}
    for record in records:
        key = record.get("raw_id") or record.get("url")
        if key not in by_id:
            by_id[key] = record
    return sorted(by_id.values(), key=lambda item: (item.get("published_at") or "", item.get("url") or ""))


def _raw_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    return PurePosixPath(urlparse(url).path).name or None


def _published_at(record: dict) -> str:
    if record.get("published_at"):
        return _format_utc(record["published_at"])
    published_date = _parse_date(record.get("published_date"), "published_date")
    return _format_utc(datetime.combine(published_date, RELEASE_TIME, tzinfo=EASTERN))


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
