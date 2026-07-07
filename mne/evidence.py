import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from mne.freshness import (
    STALE,
    UNKNOWN,
    build_source_freshness_outputs,
    evaluate_evidence_freshness,
    evidence_freshness_counts,
    rejected_evidence_preview,
)
from mne.source_registry import SourceRegistryError, load_source_registry


EVIDENCE_TYPE_HEADLINE = "Headline"


@dataclass
class EvidenceObject:
    evidence_id: str
    source_id: str
    source_name: str
    evidence_type: str
    timestamp: str | None
    title: str
    summary: str | None
    url: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    accepted: bool = True
    rejection_reason: str | None = None
    freshness_state: str = UNKNOWN
    freshness_age_minutes: int | None = None
    freshness_checked_at: str | None = None

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
    return None


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


def _health_checked_at_by_source_id(source_health):
    checked_at = {}
    for health in source_health or []:
        if isinstance(health, dict) and health.get("source_id"):
            checked_at[health["source_id"]] = health.get("checked_at")
    return checked_at


def normalize_rss_entries_to_evidence(
    entries,
    run_timestamp: str | None = None,
    registry=None,
    source_health=None,
):
    registry = registry or load_source_registry()
    fallback_timestamp = run_timestamp or datetime.now(timezone.utc).isoformat()
    evidence_objects = []
    seen_ids = set()
    checked_at_by_source_id = _health_checked_at_by_source_id(source_health)

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
        evaluation_time = checked_at_by_source_id.get(source_id) or fallback_timestamp
        freshness = evaluate_evidence_freshness(
            normalized["timestamp"],
            source["freshness_threshold_minutes"],
            evaluation_time,
        )
        evidence_id = generate_evidence_id(
            source_id=source_id,
            evidence_type=EVIDENCE_TYPE_HEADLINE,
            timestamp=normalized["timestamp"] or "",
            title=title,
            url=normalized["url"],
        )
        accepted = evidence_id not in seen_ids
        rejection_reason = None if accepted else "duplicate"
        seen_ids.add(evidence_id)
        if accepted and freshness.freshness_state == STALE:
            accepted = False
            rejection_reason = "stale"
        elif accepted and freshness.freshness_state == UNKNOWN:
            accepted = False
            rejection_reason = "unknown_timestamp"

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
                freshness_state=freshness.freshness_state,
                freshness_age_minutes=freshness.age_minutes,
                freshness_checked_at=evaluation_time,
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


def source_intelligence_counts(
    evidence_objects,
    registry_version: str | None = None,
    source_health=None,
    registry=None,
):
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
    if source_health is not None:
        counts["source_health"] = list(source_health)
    counts["evidence_freshness"] = evidence_freshness_counts(evidence_objects)
    if registry is not None:
        counts["source_freshness"] = build_source_freshness_outputs(
            registry,
            evidence_objects,
            source_health,
        )
    preview, truncated = rejected_evidence_preview(evidence_objects)
    counts["rejected_evidence_preview"] = preview
    counts["rejected_evidence_preview_truncated"] = truncated
    return counts
