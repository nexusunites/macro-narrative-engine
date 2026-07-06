import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


EVIDENCE_TYPE_HEADLINE = "Headline"
UNKNOWN_SOURCE_ID = "unknown-source"
UNKNOWN_SOURCE_NAME = "Unknown Source"


SOURCE_NAMES_BY_URL = {
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml": ("wsj-markets", "WSJ Markets"),
    "https://www.cnbc.com/id/100003114/device/rss/rss.html": ("cnbc-top-news", "CNBC Top News"),
    "https://feeds.reuters.com/reuters/businessNews": ("reuters-business-news", "Reuters Business News"),
    "https://www.ft.com/?format=rss": ("financial-times", "Financial Times"),
    "https://www.bloomberg.com/feed/podcast/etf-report.xml": ("bloomberg-etf-report", "Bloomberg ETF Report"),
    "https://www.bbc.co.uk/news/business/rss.xml": ("bbc-business", "BBC Business"),
    "https://www.npr.org/rss/rss.php?id=1001": ("npr-business", "NPR Business"),
    "https://www.economist.com/finance-and-economics/rss.xml": (
        "economist-finance-economics",
        "Economist Finance and Economics",
    ),
}


@dataclass
class EvidenceObject:
    evidence_id: str
    source_id: str
    source_name: str
    evidence_type: str
    timestamp: str
    title: str
    summary: str | None
    url: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    accepted: bool = True
    rejection_reason: str | None = None

    def to_dict(self):
        return asdict(self)


def normalize_title_for_evidence_id(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def generate_evidence_id(
    source_id: str,
    evidence_type: str,
    timestamp: str,
    title: str,
    url: str | None,
):
    normalized_title = normalize_title_for_evidence_id(title)
    parts = [source_id, evidence_type, timestamp, normalized_title]
    if url:
        parts.append(url)
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def source_identity(feed_url: str | None):
    if feed_url in SOURCE_NAMES_BY_URL:
        return SOURCE_NAMES_BY_URL[feed_url]

    if feed_url:
        parsed = urlparse(feed_url)
        host = parsed.netloc or parsed.path
        if host:
            slug = re.sub(r"[^a-z0-9]+", "-", host.casefold()).strip("-")
            return slug or UNKNOWN_SOURCE_ID, host

    return UNKNOWN_SOURCE_ID, UNKNOWN_SOURCE_NAME


def _text_or_none(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _entry_value(entry, key, default=None):
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _entry_timestamp(entry, fallback_timestamp: str):
    timestamp = _entry_value(entry, "timestamp")
    if timestamp:
        return str(timestamp)
    return fallback_timestamp


def _normalize_entry(entry, fallback_timestamp: str):
    if isinstance(entry, str):
        return {
            "title": entry.strip(),
            "summary": None,
            "url": None,
            "timestamp": fallback_timestamp,
            "feed_url": None,
            "metadata": {},
        }

    metadata = dict(_entry_value(entry, "metadata", {}) or {})
    return {
        "title": str(_entry_value(entry, "title", "")).strip(),
        "summary": _text_or_none(_entry_value(entry, "summary")),
        "url": _text_or_none(_entry_value(entry, "url")),
        "timestamp": _entry_timestamp(entry, fallback_timestamp),
        "feed_url": _entry_value(entry, "feed_url"),
        "metadata": metadata,
    }


def normalize_rss_entries_to_evidence(entries, run_timestamp: str | None = None):
    fallback_timestamp = run_timestamp or datetime.now(timezone.utc).isoformat()
    evidence_objects = []
    seen_ids = set()

    for entry in entries:
        normalized = _normalize_entry(entry, fallback_timestamp)
        title = normalized["title"]
        if not title:
            continue

        source_id, source_name = source_identity(normalized["feed_url"])
        evidence_id = generate_evidence_id(
            source_id=source_id,
            evidence_type=EVIDENCE_TYPE_HEADLINE,
            timestamp=normalized["timestamp"],
            title=title,
            url=normalized["url"],
        )
        accepted = evidence_id not in seen_ids
        rejection_reason = None if accepted else "duplicate"
        seen_ids.add(evidence_id)

        evidence_objects.append(
            EvidenceObject(
                evidence_id=evidence_id,
                source_id=source_id,
                source_name=source_name,
                evidence_type=EVIDENCE_TYPE_HEADLINE,
                timestamp=normalized["timestamp"],
                title=title,
                summary=normalized["summary"],
                url=normalized["url"],
                metadata=normalized["metadata"],
                accepted=accepted,
                rejection_reason=rejection_reason,
            )
        )

    return evidence_objects


def evidence_to_headlines(evidence_objects):
    headlines = []
    for evidence in evidence_objects:
        if isinstance(evidence, EvidenceObject):
            if evidence.accepted:
                headlines.append(evidence.title)
        elif evidence.get("accepted"):
            headlines.append(evidence["title"])
    return headlines


def source_intelligence_counts(evidence_objects):
    evidence_count = len(evidence_objects)
    accepted_count = 0
    for evidence in evidence_objects:
        if isinstance(evidence, EvidenceObject):
            accepted_count += int(evidence.accepted)
        else:
            accepted_count += int(bool(evidence.get("accepted")))
    rejected_count = evidence_count - accepted_count
    return {
        "evidence_count": evidence_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
    }
