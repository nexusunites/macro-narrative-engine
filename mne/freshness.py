from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from mne.feed_health import BLOCKED, OFFLINE, PARSE_ERROR, RATE_LIMITED


FRESH = "FRESH"
STALE = "STALE"
UNKNOWN = "UNKNOWN"
QUIET = "QUIET"

FETCH_FAILED_HEALTH_STATES = {OFFLINE, RATE_LIMITED, BLOCKED, PARSE_ERROR}
REJECTED_EVIDENCE_PREVIEW_LIMIT = 10


@dataclass(frozen=True)
class FreshnessEvaluation:
    freshness_state: str
    age_minutes: int | None
    parsed_timestamp: str | None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SourceFreshnessOutput:
    source_id: str
    source_name: str
    status: str
    newest_evidence_timestamp: str | None
    newest_evidence_age_minutes: int | None
    freshness_threshold_minutes: int

    def to_dict(self):
        return asdict(self)


def parse_datetime_utc(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_evidence_freshness(timestamp, freshness_threshold_minutes, evaluation_time):
    evidence_time = parse_datetime_utc(timestamp)
    checked_at = parse_datetime_utc(evaluation_time)
    if evidence_time is None or checked_at is None:
        return FreshnessEvaluation(UNKNOWN, None, None)

    age_seconds = (checked_at - evidence_time).total_seconds()
    if age_seconds < 0:
        return FreshnessEvaluation(UNKNOWN, None, None)

    age_minutes = int(age_seconds // 60)
    parsed_timestamp = evidence_time.isoformat()
    if age_minutes <= freshness_threshold_minutes:
        return FreshnessEvaluation(FRESH, age_minutes, parsed_timestamp)
    return FreshnessEvaluation(STALE, age_minutes, parsed_timestamp)


def classify_source_freshness(feed_health_state, freshness_states):
    if feed_health_state in FETCH_FAILED_HEALTH_STATES:
        return UNKNOWN
    if FRESH in freshness_states:
        return FRESH
    if STALE in freshness_states:
        return STALE
    if not freshness_states:
        return QUIET
    return UNKNOWN


def build_source_freshness_outputs(registry, evidence_objects, source_health):
    health_by_source_id = {
        health.get("source_id"): health
        for health in source_health or []
        if isinstance(health, dict)
    }
    evidence_by_source_id = {}
    for evidence in evidence_objects:
        evidence_by_source_id.setdefault(evidence.source_id, []).append(evidence)

    outputs = []
    for source in registry.active_sources:
        source_evidence = evidence_by_source_id.get(source["source_id"], [])
        freshness_states = [
            evidence.freshness_state
            for evidence in source_evidence
            if evidence.rejection_reason != "duplicate"
        ]
        health_state = health_by_source_id.get(source["source_id"], {}).get("state")
        status = classify_source_freshness(health_state, freshness_states)

        parseable = [
            evidence
            for evidence in source_evidence
            if evidence.freshness_checked_at is not None
            and evidence.freshness_age_minutes is not None
        ]
        newest = None
        if parseable:
            newest = min(parseable, key=lambda item: item.freshness_age_minutes)

        outputs.append(
            SourceFreshnessOutput(
                source_id=source["source_id"],
                source_name=source["display_name"],
                status=status,
                newest_evidence_timestamp=newest.timestamp if newest else None,
                newest_evidence_age_minutes=newest.freshness_age_minutes if newest else None,
                freshness_threshold_minutes=source["freshness_threshold_minutes"],
            ).to_dict()
        )
    return outputs


def evidence_freshness_counts(evidence_objects):
    counts = {
        "fresh_count": 0,
        "stale_count": 0,
        "unknown_count": 0,
    }
    for evidence in evidence_objects:
        if evidence.freshness_state == FRESH:
            counts["fresh_count"] += 1
        elif evidence.freshness_state == STALE:
            counts["stale_count"] += 1
        else:
            counts["unknown_count"] += 1
    return counts


def rejected_evidence_preview(evidence_objects, limit=REJECTED_EVIDENCE_PREVIEW_LIMIT):
    preview = []
    rejected = [evidence for evidence in evidence_objects if not evidence.accepted]
    for evidence in rejected[:limit]:
        preview.append(
            {
                "evidence_id": evidence.evidence_id,
                "source_id": evidence.source_id,
                "title": evidence.title,
                "rejection_reason": evidence.rejection_reason,
                "timestamp": evidence.timestamp,
            }
        )
    return preview, len(rejected) > limit
