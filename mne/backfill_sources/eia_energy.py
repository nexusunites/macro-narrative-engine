import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timezone, timedelta
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests


SOURCE_ID = "eia_energy"
SOURCE_NAME = "U.S. Energy Information Administration"
PROVIDER = "EIA"
CATEGORY = "Energy / Commodities"
SOURCE_TYPE = "official_release"
USAGE_STORAGE_RIGHTS = "NORMALIZED_EVIDENCE"
WPSR_ARCHIVE_URL = "https://www.eia.gov/petroleum/supply/weekly/archive/"
NG_STORAGE_ARCHIVE_URL = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/"
DEFAULT_USER_AGENT = "MacroNarrativeEngine/1.0 historical-backfill"
RELEASE_TIME = dt_time(10, 30)
EASTERN = ZoneInfo("America/New_York")


class EiaEnergyBackfillError(RuntimeError):
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


def fetch_eia_energy_records(start_date, end_date, get: Callable | None = None) -> list[dict]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")

    records = []
    for archive_url, report_kind in (
        (WPSR_ARCHIVE_URL, "wpsr"),
        (NG_STORAGE_ARCHIVE_URL, "ng_storage"),
    ):
        payload = _fetch_text(archive_url, get=get)
        records.extend(parse_eia_energy_records(payload, report_kind))

    return [
        record
        for record in _dedupe_records(records)
        if start.isoformat() <= record["published_date"] <= end.isoformat()
    ]


def parse_eia_energy_records(payload, report_kind) -> list[dict]:
    if report_kind not in {"wpsr", "ng_storage"}:
        raise ValueError("report_kind must be 'wpsr' or 'ng_storage'.")

    parser = _LinkParser()
    parser.feed(payload or "")
    records = []
    for link in parser.links:
        record = _record_from_link(link, report_kind)
        if record is not None:
            records.append(record)
    return _dedupe_records(records)


def normalize_eia_energy_record(raw_record, retrieval_timestamp=None) -> dict:
    if not isinstance(raw_record, dict):
        raise TypeError("raw_record must be a dictionary.")

    url = _text(raw_record.get("url"))
    raw_id = _text(raw_record.get("raw_id")) or _raw_id_from_url(url)
    return {
        "title": _text(raw_record.get("title")) or "EIA Energy Release",
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
    raise EiaEnergyBackfillError(str(last_error))


def _record_from_link(link: _Link, report_kind: str) -> dict | None:
    base_url = WPSR_ARCHIVE_URL if report_kind == "wpsr" else NG_STORAGE_ARCHIVE_URL
    absolute = urljoin(base_url, link.href)
    parsed_path = urlparse(absolute).path
    if report_kind == "wpsr":
        return _wpsr_record(parsed_path, absolute)
    return _ng_storage_record(parsed_path, absolute)


def _wpsr_record(path: str, absolute_url: str) -> dict | None:
    match = re.fullmatch(
        r"/petroleum/supply/weekly/archive/(\d{4})/(\d{4})_(\d{2})_(\d{2})/wpsr_(\d{4})_(\d{2})_(\d{2})\.php",
        path,
        re.IGNORECASE,
    )
    if not match or match.group(1) != match.group(2) or match.group(2, 3, 4) != match.group(5, 6, 7):
        return None
    release_day = _date_from_parts(match.group(2), match.group(3), match.group(4))
    if release_day is None:
        return None
    raw_id = f"wpsr_{match.group(2)}_{match.group(3)}_{match.group(4)}"
    week_ending = release_day - timedelta(days=5)
    return _build_record(
        title=f"Weekly Petroleum Status Report — Week Ending {_format_display_date(week_ending)}",
        published_date=release_day,
        url=absolute_url,
        raw_id=raw_id,
    )


def _ng_storage_record(path: str, absolute_url: str) -> dict | None:
    match = re.fullmatch(
        r"/naturalgas/weekly/(?:archivenew_ngwu/)?(\d{4})/(\d{2})_(\d{2})/index\.(?:cfm|php)",
        path,
        re.IGNORECASE,
    )
    if not match:
        return None
    release_day = _date_from_parts(match.group(1), match.group(2), match.group(3))
    if release_day is None:
        return None
    raw_id = f"ng_storage_{match.group(1)}_{match.group(2)}_{match.group(3)}"
    week_ending = release_day - timedelta(days=1)
    return _build_record(
        title=f"Weekly Natural Gas Storage Report — Week Ending {_format_display_date(week_ending)}",
        published_date=release_day,
        url=absolute_url,
        raw_id=raw_id,
    )


def _build_record(title: str, published_date: date, url: str, raw_id: str) -> dict:
    return {
        "title": title,
        "published_date": published_date.isoformat(),
        "published_at": _format_utc(datetime.combine(published_date, RELEASE_TIME, tzinfo=EASTERN)),
        "url": url,
        "raw_id": raw_id,
        "reference_id": raw_id,
    }


def _date_from_parts(year: str, month: str, day: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _raw_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    for report_kind in ("wpsr", "ng_storage"):
        record = _record_from_link(_Link(href=path, text=""), report_kind)
        if record is not None:
            return record["raw_id"]
    return None


def _published_at(record: dict) -> str:
    if record.get("published_at"):
        return _format_utc(record["published_at"])
    published_date = _parse_date(record.get("published_date"), "published_date")
    return _format_utc(datetime.combine(published_date, RELEASE_TIME, tzinfo=EASTERN))


def _dedupe_records(records: list[dict]) -> list[dict]:
    by_id = {}
    for record in records:
        key = record.get("raw_id") or record.get("url")
        if key not in by_id:
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


def _format_display_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _text(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None
