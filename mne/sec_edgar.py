"""Fail-closed SEC EDGAR submissions client for persisted company-news markers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_SEC_EDGAR_MAP_PATH = Path(__file__).resolve().parents[1] / "config" / "sec_edgar_map.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_RECENT_FIELDS = (
    "accessionNumber",
    "filingDate",
    "reportDate",
    "form",
    "items",
    "primaryDocument",
    "primaryDocDescription",
)
_TRANSIENT_STATUSES = frozenset({429, 503})
_LAST_REQUEST_AT = 0.0
ITEM_LABELS = {
    "2.02": "Results of operations and financial condition",
    "5.02": "Leadership / director & officer changes",
    "8.01": "Other events",
    "9.01": "Financial statements and exhibits",
    "7.01": "Regulation FD disclosure",
    "1.01": "Material definitive agreement",
    "2.01": "Completion of acquisition or disposition",
}
GENERIC_TITLE = "Material event (8-K)"


class SecEdgarError(ValueError):
    """Raised when EDGAR input or required configuration is invalid."""


@dataclass(frozen=True)
class Edgar8K:
    filing_date: str
    items: tuple[str, ...]
    accession: str
    primary_document: str
    url: str
    title: str


@dataclass(frozen=True)
class SecEdgarMap:
    version: str
    contact: str
    ciks: tuple[tuple[str, tuple[str, ...]], ...]

    def as_dict(self) -> dict[str, tuple[str, ...]]:
        return dict(self.ciks)


def title_for_items(items: tuple[str, ...] | list[str]) -> str:
    labels = []
    for item in items:
        label = ITEM_LABELS.get(str(item).strip())
        if label and label not in labels:
            labels.append(label)
    return "; ".join(labels) if labels else GENERIC_TITLE


def build_filing_url(cik: str, accession: str, primary_document: str) -> str:
    try:
        cik_int = str(int(str(cik)))
    except (TypeError, ValueError) as exc:
        raise SecEdgarError("cik must be a numeric string") from exc
    accession_plain = str(accession).replace("-", "").strip()
    document = str(primary_document).strip()
    if not accession_plain or not document:
        raise SecEdgarError("accession and primary_document must be non-empty")
    return ARCHIVES_URL.format(cik=cik_int, accession=accession_plain, document=document)


def _iso_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def parse_submissions(payload: Any, cik: str) -> tuple[Edgar8K, ...]:
    if not isinstance(payload, dict):
        raise SecEdgarError("submissions payload must be an object")
    filings = payload.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        raise SecEdgarError("filings.recent must be an object")
    arrays = []
    for field in _RECENT_FIELDS:
        values = recent.get(field)
        if not isinstance(values, list):
            raise SecEdgarError(f"filings.recent.{field} must be a list")
        arrays.append(values)
    lengths = {len(values) for values in arrays}
    if len(lengths) != 1:
        raise SecEdgarError("filings.recent arrays must have matching lengths")

    records = []
    for accession, filing_date, _report_date, form, items, document, _description in zip(*arrays):
        required = (accession, filing_date, form, items, document)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            continue
        if form.strip() != "8-K":
            continue
        normalized_date = _iso_date(filing_date.strip())
        if normalized_date is None:
            continue
        item_codes = tuple(code.strip() for code in items.split(",") if code.strip())
        if not item_codes:
            continue
        try:
            url = build_filing_url(cik, accession, document)
        except SecEdgarError:
            continue
        records.append(Edgar8K(
            filing_date=normalized_date,
            items=item_codes,
            accession=accession.strip(),
            primary_document=document.strip(),
            url=url,
            title=title_for_items(item_codes),
        ))
    return tuple(sorted(records, key=lambda item: (item.filing_date, item.accession)))


def validate_sec_edgar_map(data: Any) -> SecEdgarMap:
    if not isinstance(data, dict):
        raise SecEdgarError("SEC EDGAR map must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise SecEdgarError("version must use MAJOR.MINOR.PATCH semantic versioning")
    contact = data.get("contact")
    if not isinstance(contact, str) or not contact.strip():
        raise SecEdgarError("contact must be a non-empty string")
    raw_ciks = data.get("ciks")
    if not isinstance(raw_ciks, dict):
        raise SecEdgarError("ciks must be an object")
    ciks = []
    for ticker in sorted(raw_ciks):
        location = f"ciks[{ticker}]"
        values = raw_ciks[ticker]
        if not isinstance(ticker, str) or not ticker.strip():
            raise SecEdgarError(f"{location} ticker must be a non-empty string")
        if not isinstance(values, list):
            raise SecEdgarError(f"{location} must be a list")
        if not values:
            raise SecEdgarError(f"{location} must be a non-empty list")
        normalized = []
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip() or not value.isdigit():
                raise SecEdgarError(f"{location}[{index}] must be a numeric string")
            normalized.append(value)
        ciks.append((ticker.strip().upper(), tuple(normalized)))
    return SecEdgarMap(version, contact.strip(), tuple(ciks))


def load_sec_edgar_map(path: str | Path = DEFAULT_SEC_EDGAR_MAP_PATH) -> SecEdgarMap:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecEdgarError(f"unable to load SEC EDGAR map: {exc}") from exc
    return validate_sec_edgar_map(data)


def _request_json(transport: Any, url: str, headers: dict[str, str], *, paced: bool) -> Any:
    global _LAST_REQUEST_AT
    for attempt in range(3):
        if paced:
            remaining = 0.2 - (time.monotonic() - _LAST_REQUEST_AT)
            if remaining > 0:
                time.sleep(remaining)
        try:
            response = transport.get(url, headers=headers, timeout=10)
        except (requests.Timeout, requests.ConnectionError):
            if attempt < 2:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise
        if paced:
            _LAST_REQUEST_AT = time.monotonic()
        if response.status_code in _TRANSIENT_STATUSES:
            if attempt < 2:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise requests.HTTPError(f"HTTP {response.status_code}")
        response.raise_for_status()
        return response.json()
    raise requests.RequestException("SEC EDGAR request retries exhausted")


def fetch_8k_filings(
    ciks: list[str] | tuple[str, ...],
    *,
    contact: str,
    session: Any = None,
    as_of: date | datetime | None = None,
    since: date | datetime | None = None,
) -> tuple[Edgar8K, ...]:
    """Fetch and merge recent 8-K rows; every network/JSON failure degrades empty."""
    if not isinstance(contact, str) or not contact.strip():
        return ()
    as_of_date = as_of.date() if isinstance(as_of, datetime) else as_of
    since_date = since.date() if isinstance(since, datetime) else since
    transport = session or requests
    headers = {"User-Agent": contact.strip(), "Accept-Encoding": "gzip, deflate"}
    merged: dict[str, Edgar8K] = {}
    try:
        for cik in ciks:
            payload = _request_json(
                transport,
                SUBMISSIONS_URL.format(cik10=str(cik).zfill(10)),
                headers,
                paced=session is None,
            )
            for filing in parse_submissions(payload, str(cik)):
                filing_date = date.fromisoformat(filing.filing_date)
                if since_date is not None and filing_date < since_date:
                    continue
                if as_of_date is not None and filing_date > as_of_date:
                    continue
                merged.setdefault(filing.accession, filing)
    except Exception:
        return ()
    return tuple(sorted(merged.values(), key=lambda item: (item.filing_date, item.accession)))
