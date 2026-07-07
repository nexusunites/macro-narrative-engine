import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from mne.source_registry import SourceRegistryError, load_source_registry


EVIDENCE_TYPE_HEADLINE = "Headline"


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


def normalize_rss_entries_to_evidence(entries, run_timestamp: str | None = None, registry=None):
    registry = registry or load_source_registry()
    fallback_timestamp = run_timestamp or datetime.now(timezone.utc).isoformat()
    evidence_objects = []
    seen_ids = set()

    for entry in entries:
        normalized = _normalize_entry(entry, fallback_timestamp)
        title = normalized["title"]
        if not title:
            continue

        source = registry.source_by_url(normalized["feed_url"])
        if source["status"] != "ACTIVE":
            raise SourceRegistryError(
                "RSS entry resolved to a non-active source that should not have been fetched: "
                f"{source['source_id']} ({source['status']})"
            )
        source_id = source["source_id"]
        source_name = source["display_name"]
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


def source_intelligence_counts(evidence_objects, registry_version: str | None = None):
    evidence_count = len(evidence_objects)
    accepted_count = 0
    for evidence in evidence_objects:
        if isinstance(evidence, EvidenceObject):
            accepted_count += int(evidence.accepted)
        else:
            accepted_count += int(bool(evidence.get("accepted")))
    rejected_count = evidence_count - accepted_count
    counts = {}
    if registry_version is not None:
        counts["registry_version"] = registry_version
    counts.update({
        "evidence_count": evidence_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
    })
    return counts
