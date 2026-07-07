import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


PLATFORM_VERSION = "1.0.0"
PIPELINE_VERSION = "1.0.0"

SUCCESS = "SUCCESS"
PARTIAL = "PARTIAL"
FAILED = "FAILED"
SKIPPED = "SKIPPED"

STAGE_NAMES = (
    "RSS_FETCH",
    "EVIDENCE_NORMALIZATION",
    "FEED_HEALTH",
    "FRESHNESS_VALIDATION",
    "NARRATIVE_INTELLIGENCE",
    "EVIDENCE_QUALITY",
    "NARRATIVE_BRIEF",
    "EVENT_LIFECYCLE",
    "RUN_PERSISTENCE",
    "REPORT_GENERATION",
)

HEALTH_SUCCESS_STATES = {"HEALTHY"}
HEALTH_PARTIAL_STATES = {"PARTIAL", "EMPTY", "REDIRECTED"}


def utc_now():
    return datetime.now(timezone.utc)


def isoformat_utc(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def duration_ms(start_time, end_time):
    if start_time is None or end_time is None:
        return None
    milliseconds = (end_time - start_time).total_seconds() * 1000
    return max(1, math.ceil(milliseconds))


@dataclass
class StageRecord:
    stage_name: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str = SKIPPED
    diagnostic_message: str = "Stage was not executed in this run."
    result_counts: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "stage_name": self.stage_name,
            "start_time": isoformat_utc(self.start_time),
            "end_time": isoformat_utc(self.end_time),
            "duration_ms": duration_ms(self.start_time, self.end_time),
            "status": self.status,
            "diagnostic_message": self.diagnostic_message,
            "result_counts": dict(self.result_counts),
        }


class StageObserver:
    def __init__(self, recorder, stage_name):
        self.recorder = recorder
        self.stage_name = stage_name
        self.record = None

    def __enter__(self):
        self.record = StageRecord(
            stage_name=self.stage_name,
            start_time=utc_now(),
            status=SUCCESS,
            diagnostic_message="Stage completed successfully.",
        )
        self.recorder._set_record(self.record)
        return self

    def set_result(self, status=SUCCESS, diagnostic_message=None, result_counts=None):
        self.record.status = status
        if diagnostic_message is not None:
            self.record.diagnostic_message = diagnostic_message
        if result_counts is not None:
            self.record.result_counts = dict(result_counts)

    def __exit__(self, exc_type, exc, _traceback):
        self.record.end_time = utc_now()
        if exc_type is not None:
            self.record.status = FAILED
            self.record.diagnostic_message = f"{exc_type.__name__}: {exc}"
        return False


class PipelineTelemetryRecorder:
    def __init__(
        self,
        engine_versions,
        execution_mode="LIVE",
        platform_version=PLATFORM_VERSION,
        pipeline_version=PIPELINE_VERSION,
        run_id=None,
        run_start_time=None,
    ):
        self.run_id = run_id or str(uuid.uuid4())
        self.run_start_time = run_start_time or utc_now()
        self.engine_versions = dict(engine_versions)
        self.execution_mode = execution_mode
        self.platform_version = platform_version
        self.pipeline_version = pipeline_version
        self.records = {stage: StageRecord(stage) for stage in STAGE_NAMES}

    def observe(self, stage_name):
        if stage_name not in self.records:
            raise ValueError(f"Unknown pipeline stage: {stage_name}")
        return StageObserver(self, stage_name)

    def skip(self, stage_name, diagnostic_message):
        self._set_record(
            StageRecord(
                stage_name=stage_name,
                status=SKIPPED,
                diagnostic_message=diagnostic_message,
            )
        )

    def _set_record(self, record):
        self.records[record.stage_name] = record

    def to_block(self):
        stages = [self.records[stage].to_dict() for stage in STAGE_NAMES]
        started = [
            self.records[stage]
            for stage in STAGE_NAMES
            if self.records[stage].start_time is not None
        ]
        ended = [
            self.records[stage]
            for stage in STAGE_NAMES
            if self.records[stage].end_time is not None
        ]
        run_end_time = ended[-1].end_time if ended else self.run_start_time
        run_start_time = started[0].start_time if started else self.run_start_time

        return {
            "run_metadata": {
                "run_id": self.run_id,
                "platform_version": self.platform_version,
                "pipeline_version": self.pipeline_version,
                "run_duration_ms": duration_ms(run_start_time, run_end_time),
                "execution_mode": self.execution_mode,
                "timestamp": isoformat_utc(run_start_time),
                "engine_versions": dict(self.engine_versions),
            },
            "stages": stages,
        }


def rss_fetch_counts(rss_urls, source_health):
    return {
        "feeds_attempted": len(rss_urls or []),
        "feeds_successful": sum(
            1
            for source in source_health or []
            if source.get("state") in HEALTH_SUCCESS_STATES | HEALTH_PARTIAL_STATES
        ),
        "entries_received": sum(int(source.get("entries_parsed") or 0) for source in source_health or []),
    }


def source_health_state_counts(source_health):
    counts = {}
    for source in source_health or []:
        key = f"{str(source.get('state') or 'UNKNOWN').lower()}_count"
        counts[key] = counts.get(key, 0) + 1
    return counts


def status_from_source_health(source_health):
    if not source_health:
        return FAILED, "No source health records were produced."
    states = {source.get("state") for source in source_health}
    if states <= HEALTH_SUCCESS_STATES:
        return SUCCESS, "All active sources reported healthy feed health."
    if states <= {"OFFLINE", "PARSE_ERROR", "RATE_LIMITED", "BLOCKED", "UNKNOWN"}:
        return FAILED, "All source health records indicate failed feed collection."
    return PARTIAL, "At least one source health record indicates degraded feed collection."


def evidence_normalization_counts(source_intelligence):
    return {
        "evidence_created": source_intelligence.get("evidence_count", 0),
        "accepted": source_intelligence.get("accepted_count", 0),
        "rejected": source_intelligence.get("rejected_count", 0),
    }


def freshness_counts(source_intelligence):
    freshness = source_intelligence.get("evidence_freshness") or {}
    return {
        "fresh": freshness.get("fresh_count", 0),
        "stale": freshness.get("stale_count", 0),
        "unknown": freshness.get("unknown_count", 0),
    }


def freshness_status(source_intelligence):
    counts = freshness_counts(source_intelligence)
    if counts["unknown"] > 0:
        return PARTIAL, "Freshness validation completed with unknown-timestamp evidence."
    if counts["stale"] > 0:
        return PARTIAL, "Freshness validation completed with stale evidence rejected."
    return SUCCESS, "Freshness validation completed from evidence diagnostics."


def narrative_intelligence_counts(theme_scores, group_scores):
    return {
        "themes_detected": sum(1 for score in (theme_scores or {}).values() if score > 0),
        "groups_detected": len(group_scores or {}),
    }


def evidence_quality_counts(coverage_intelligence):
    per_narrative = (coverage_intelligence or {}).get("per_narrative") or []
    provider_diversity = (
        (coverage_intelligence or {})
        .get("overall", {})
        .get("provider_diversity", {})
        .get("unique_provider_count", 0)
    )
    return {
        "narratives_measured": len(per_narrative),
        "provider_diversity": provider_diversity,
    }


def narrative_brief_counts(narrative_brief):
    return {"brief_generated": narrative_brief is not None}


def event_lifecycle_counts(event_lifecycle):
    events = (event_lifecycle or {}).get("events") or []
    return {
        "active_events": sum(
            1
            for event in events
            if event.get("lifecycle_state") not in {"Upcoming", "Complete"}
        )
    }


def stage_by_name(platform_observability, stage_name):
    for stage in (platform_observability or {}).get("stages") or []:
        if stage.get("stage_name") == stage_name:
            return stage
    return None
