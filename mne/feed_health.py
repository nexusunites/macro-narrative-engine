from dataclasses import asdict, dataclass
from datetime import datetime, timezone


HEALTHY = "HEALTHY"
PARTIAL = "PARTIAL"
EMPTY = "EMPTY"
OFFLINE = "OFFLINE"
REDIRECTED = "REDIRECTED"
PARSE_ERROR = "PARSE_ERROR"
RATE_LIMITED = "RATE_LIMITED"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"

INFO = "INFO"
WARNING = "WARNING"
CRITICAL = "CRITICAL"

SEVERITY_BY_STATE = {
    HEALTHY: INFO,
    PARTIAL: WARNING,
    EMPTY: WARNING,
    REDIRECTED: WARNING,
    OFFLINE: CRITICAL,
    PARSE_ERROR: CRITICAL,
    RATE_LIMITED: CRITICAL,
    BLOCKED: CRITICAL,
    UNKNOWN: CRITICAL,
}

RECOMMENDED_ACTION_BY_STATE = {
    HEALTHY: "No action needed.",
    PARTIAL: "Review feed structure if persistent; parsed entries remain usable.",
    EMPTY: "Confirm whether the source is expected to publish entries.",
    OFFLINE: "No action needed if transient; investigate if persistent across multiple runs.",
    REDIRECTED: "Review registered URL and update source registry if the redirect is permanent.",
    PARSE_ERROR: "Inspect feed format and parser compatibility.",
    RATE_LIMITED: "Reduce request frequency or review source rate-limit policy.",
    BLOCKED: "Review access credentials or check if source has changed access policy.",
    UNKNOWN: "Inspect fetch metadata and add a deterministic classification rule if needed.",
}


@dataclass(frozen=True)
class FetchMetadata:
    http_status: int | None
    entries_seen: int
    entries_parsed: int
    fetch_error: str | None
    checked_at: str
    redirected: bool = False
    final_url: str | None = None
    parse_error: bool = False
    no_response: bool = False


@dataclass(frozen=True)
class SourceHealthOutput:
    source_id: str
    source_name: str
    state: str
    severity: str
    reason: str
    recommended_action: str
    http_status: int | None
    entries_seen: int
    entries_parsed: int
    fetch_error: str | None
    checked_at: str

    def to_dict(self):
        return asdict(self)


def checked_at_now():
    return datetime.now(timezone.utc).isoformat()


def evaluate_feed_health(metadata: FetchMetadata):
    if metadata.no_response:
        return OFFLINE, "No response received"

    if metadata.http_status == 429:
        return RATE_LIMITED, "HTTP 429 received"

    if metadata.http_status == 403:
        return BLOCKED, "HTTP 403 received"

    if metadata.redirected:
        final_url = metadata.final_url or "unknown URL"
        return REDIRECTED, f"Redirected to {final_url}"

    if metadata.parse_error and metadata.entries_seen == 0 and metadata.entries_parsed == 0:
        if metadata.fetch_error:
            return PARSE_ERROR, f"Feed could not be parsed: {metadata.fetch_error}"
        return PARSE_ERROR, "Feed could not be parsed as valid feed content"

    successful_http = (
        metadata.http_status is not None
        and 200 <= metadata.http_status < 400
    )
    if metadata.entries_seen == 0 and metadata.entries_parsed == 0 and successful_http:
        return EMPTY, "Zero entries present in feed"

    if metadata.entries_seen > 0 and metadata.entries_parsed == metadata.entries_seen:
        return HEALTHY, f"Feed parsed successfully; {metadata.entries_parsed} entries parsed"

    if 0 < metadata.entries_parsed < metadata.entries_seen:
        failed_count = metadata.entries_seen - metadata.entries_parsed
        return (
            PARTIAL,
            f"Feed parsed successfully; {failed_count} of {metadata.entries_seen} entries failed to parse",
        )

    return UNKNOWN, "Fetch outcome did not match a deterministic health rule"


def build_source_health_output(source, metadata: FetchMetadata):
    state, base_reason = evaluate_feed_health(metadata)
    reason = base_reason
    if state == REDIRECTED:
        reason = f"{base_reason} (registered URL: {source['url']})"
    return SourceHealthOutput(
        source_id=source["source_id"],
        source_name=source["display_name"],
        state=state,
        severity=SEVERITY_BY_STATE[state],
        reason=reason,
        recommended_action=RECOMMENDED_ACTION_BY_STATE[state],
        http_status=metadata.http_status,
        entries_seen=metadata.entries_seen,
        entries_parsed=metadata.entries_parsed,
        fetch_error=metadata.fetch_error,
        checked_at=metadata.checked_at,
    )
