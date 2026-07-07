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
from mne.narrative_signals import NARRATIVE_GROUPS
from mne.source_registry import SourceRegistryError, load_source_registry


EVIDENCE_TYPE_HEADLINE = "Headline"
ENGINE_VERSION = "1.0.0"
ACCEPTED_EVIDENCE_LIMIT = 500
SEVERE_STALENESS_RATIO_THRESHOLD = 100


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


def evidence_is_accepted(evidence):
    if isinstance(evidence, EvidenceObject):
        return evidence.accepted
    return bool(evidence.get("accepted"))


def evidence_record(evidence):
    if isinstance(evidence, EvidenceObject):
        return {
            "evidence_id": evidence.evidence_id,
            "source_id": evidence.source_id,
            "title": evidence.title,
            "timestamp": evidence.timestamp,
        }
    return {
        "evidence_id": evidence.get("evidence_id"),
        "source_id": evidence.get("source_id"),
        "title": evidence.get("title"),
        "timestamp": evidence.get("timestamp"),
    }


def accepted_attributed_evidence_records(
    evidence_objects,
    theme_attribution,
    registry,
    narrative_groups=None,
    limit=ACCEPTED_EVIDENCE_LIMIT,
):
    narrative_groups = narrative_groups or NARRATIVE_GROUPS
    records = []
    truncated = False

    for evidence, attribution in zip(evidence_objects, theme_attribution):
        if not evidence_is_accepted(evidence):
            continue
        themes = attribution.get("themes", []) if isinstance(attribution, dict) else []
        if len(records) >= limit:
            truncated = True
            continue
        records.append(_accepted_attributed_record(evidence, themes, registry, narrative_groups))

    return records, truncated


def _accepted_attributed_record(evidence, themes, registry, narrative_groups):
    if isinstance(evidence, EvidenceObject):
        source_id = evidence.source_id
        source_name = evidence.source_name
        evidence_type = evidence.evidence_type
        timestamp = evidence.timestamp
        title = evidence.title
        url = evidence.url
        freshness_state = evidence.freshness_state
        accepted = evidence.accepted
        rejection_reason = evidence.rejection_reason
    else:
        source_id = evidence.get("source_id")
        source_name = evidence.get("source_name")
        evidence_type = evidence.get("evidence_type")
        timestamp = evidence.get("timestamp") or evidence.get("published_at")
        title = evidence.get("title")
        url = evidence.get("url") or evidence.get("link")
        freshness_state = evidence.get("freshness_state")
        accepted = bool(evidence.get("accepted"))
        rejection_reason = evidence.get("rejection_reason") or evidence.get("rejection_state")

    source = registry.source_by_id(source_id) if source_id else {}
    attributed_themes = [theme for theme in themes if theme]
    attributed_groups = sorted(
        {
            group
            for group, group_themes in narrative_groups.items()
            if any(theme in group_themes for theme in attributed_themes)
        }
    )
    return {
        "evidence_id": evidence.evidence_id if isinstance(evidence, EvidenceObject) else evidence.get("evidence_id"),
        "title": title,
        "source_id": source_id,
        "source_name": source_name or source.get("display_name"),
        "provider": source.get("provider"),
        "evidence_type": evidence_type,
        "published_at": timestamp,
        "timestamp": timestamp,
        "url": url,
        "freshness_state": freshness_state,
        "accepted": accepted,
        "rejection_state": rejection_reason,
        "themes": attributed_themes,
        "groups": attributed_groups,
        "narrative_keys": [
            *[f"theme:{theme}" for theme in attributed_themes],
            *[f"group:{group}" for group in attributed_groups],
        ],
    }


def accepted_evidence_records(evidence_objects, limit=ACCEPTED_EVIDENCE_LIMIT):
    records = []
    truncated = False

    for evidence in evidence_objects:
        if not evidence_is_accepted(evidence):
            continue
        if len(records) >= limit:
            truncated = True
            continue
        records.append(evidence_record(evidence))

    return records, truncated


def rejection_reason_counts(evidence_objects):
    counts = {
        "stale": 0,
        "duplicate": 0,
        "unknown_timestamp": 0,
    }
    for evidence in evidence_objects:
        if evidence_is_accepted(evidence):
            continue
        reason = (
            evidence.rejection_reason
            if isinstance(evidence, EvidenceObject)
            else evidence.get("rejection_reason")
        )
        if reason in counts:
            counts[reason] += 1
    return counts


def evidence_funnel_counts(evidence_objects, analyzer_input_count=None):
    rejected = rejection_reason_counts(evidence_objects)
    accepted_count = sum(1 for evidence in evidence_objects if evidence_is_accepted(evidence))
    if analyzer_input_count is None:
        analyzer_input_count = accepted_count
    return {
        "fetched": len(evidence_objects),
        "accepted_fresh": accepted_count,
        "rejected_stale": rejected["stale"],
        "rejected_duplicate": rejected["duplicate"],
        "rejected_unknown_timestamp": rejected["unknown_timestamp"],
        "analyzer_input_count": analyzer_input_count,
    }


def zero_match_warning(accepted_evidence, accepted_count, matched_headlines, sample_size=5):
    if accepted_count <= 0 or matched_headlines != 0:
        return None
    return {
        "triggered": True,
        "accepted_count": accepted_count,
        "matched_headlines": 0,
        "sample_accepted_titles": [
            evidence.get("title")
            for evidence in accepted_evidence[:sample_size]
            if evidence.get("title")
        ],
    }


def annotate_healthy_but_stale_sources(
    source_health,
    source_freshness,
    severe_ratio_threshold=SEVERE_STALENESS_RATIO_THRESHOLD,
):
    freshness_by_source_id = {
        item.get("source_id"): item
        for item in source_freshness or []
        if isinstance(item, dict) and item.get("source_id")
    }
    annotated = []

    for health in source_health or []:
        row = dict(health)
        freshness = freshness_by_source_id.get(row.get("source_id")) or {}
        age = freshness.get("newest_evidence_age_minutes")
        threshold = freshness.get("freshness_threshold_minutes")
        staleness_ratio = None
        if isinstance(age, (int, float)) and isinstance(threshold, (int, float)) and threshold > 0:
            staleness_ratio = round(age / threshold, 2)

        severity = row.get("severity")
        non_critical = severity in {"INFO", "WARNING"} or row.get("state") == "HEALTHY"
        row["healthy_but_severely_stale"] = bool(
            non_critical
            and freshness.get("status") == STALE
            and staleness_ratio is not None
            and staleness_ratio >= severe_ratio_threshold
        )
        row["staleness_ratio"] = staleness_ratio
        annotated.append(row)

    return annotated


def finalize_source_intelligence_diagnostics(
    source_intelligence,
    analyzer_input_evidence,
    matched_headlines=None,
):
    accepted_records, truncated = accepted_evidence_records(analyzer_input_evidence)
    source_intelligence["accepted_evidence"] = accepted_records
    source_intelligence["accepted_evidence_truncated"] = truncated
    source_intelligence["evidence_funnel"] = {
        **(source_intelligence.get("evidence_funnel") or {}),
        "analyzer_input_count": len(analyzer_input_evidence),
    }
    if matched_headlines is not None:
        source_intelligence["zero_match_warning"] = zero_match_warning(
            accepted_records,
            len(analyzer_input_evidence),
            matched_headlines,
        )
    return source_intelligence


def persist_attributed_accepted_evidence(
    source_intelligence,
    evidence_objects,
    theme_attribution,
    registry,
):
    accepted_records, truncated = accepted_attributed_evidence_records(
        evidence_objects,
        theme_attribution,
        registry,
    )
    source_intelligence["accepted_evidence"] = accepted_records
    source_intelligence["accepted_evidence_truncated"] = truncated
    return source_intelligence


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
    source_freshness = None
    counts["evidence_freshness"] = evidence_freshness_counts(evidence_objects)
    if registry is not None:
        source_freshness = build_source_freshness_outputs(
            registry,
            evidence_objects,
            source_health,
        )
        counts["source_freshness"] = source_freshness
    if source_health is not None:
        counts["source_health"] = annotate_healthy_but_stale_sources(
            source_health,
            source_freshness,
        )
    preview, truncated = rejected_evidence_preview(evidence_objects)
    counts["rejected_evidence_preview"] = preview
    counts["rejected_evidence_preview_truncated"] = truncated
    accepted, accepted_truncated = accepted_evidence_records(evidence_objects)
    counts["accepted_evidence"] = accepted
    counts["accepted_evidence_truncated"] = accepted_truncated
    counts["evidence_funnel"] = evidence_funnel_counts(evidence_objects)
    return counts
