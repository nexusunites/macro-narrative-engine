import json
from collections import Counter
from pathlib import Path

from mne.feed_health import BLOCKED, EMPTY, HEALTHY, OFFLINE, PARSE_ERROR, RATE_LIMITED, UNKNOWN
from mne.freshness import FRESH, STALE


STABLE = "STABLE"
WATCH = "WATCH"
REPEATED_FAILURE = "REPEATED_FAILURE"
QUARANTINE_RECOMMENDED = "QUARANTINE_RECOMMENDED"
UNKNOWN_STATE = "UNKNOWN"

ERROR_HEALTH_STATES = {OFFLINE, RATE_LIMITED, UNKNOWN}
MALFORMED_HEALTH_STATES = {PARSE_ERROR}
CONDITION_COUNTER_BY_HEALTH_STATE = {
    BLOCKED: "blocked_runs",
    EMPTY: "empty_runs",
    PARSE_ERROR: "malformed_runs",
    OFFLINE: "error_runs",
    RATE_LIMITED: "error_runs",
    UNKNOWN: "error_runs",
}

ACTION_BY_STATE_AND_PATTERN = {
    (STABLE, "healthy"): "No action needed.",
    (WATCH, "blocked_runs"): "Monitor access restrictions in upcoming runs.",
    (WATCH, "stale_runs"): "Monitor source freshness in upcoming runs.",
    (WATCH, "empty_runs"): "Monitor whether the source resumes publishing parseable entries.",
    (WATCH, "malformed_runs"): "Monitor feed format and parser compatibility in upcoming runs.",
    (WATCH, "error_runs"): "Monitor fetch failures in upcoming runs.",
    (WATCH, "non_contributing_runs"): "Monitor whether healthy fetches begin producing accepted evidence.",
    (REPEATED_FAILURE, "blocked_runs"): "Review provider access pattern; restrictions are recurring.",
    (REPEATED_FAILURE, "stale_runs"): "Review source freshness; stale content is recurring.",
    (REPEATED_FAILURE, "empty_runs"): "Review whether the source is still publishing usable entries.",
    (REPEATED_FAILURE, "malformed_runs"): "Review feed format and parser compatibility.",
    (REPEATED_FAILURE, "error_runs"): "Review recurring fetch failures before relying on this source.",
    (REPEATED_FAILURE, "non_contributing_runs"): "Review why repeated healthy fetches produce no accepted evidence.",
    (
        QUARANTINE_RECOMMENDED,
        "blocked_runs",
    ): "Review for disabling or replacement; provider appears to be restricting access persistently.",
    (
        QUARANTINE_RECOMMENDED,
        "stale_runs",
    ): "Review for disabling or replacement; source appears persistently stale.",
    (
        QUARANTINE_RECOMMENDED,
        "empty_runs",
    ): "Review for disabling or replacement; source repeatedly provides no usable entries.",
    (
        QUARANTINE_RECOMMENDED,
        "malformed_runs",
    ): "Review for disabling or replacement; feed format appears persistently incompatible.",
    (
        QUARANTINE_RECOMMENDED,
        "error_runs",
    ): "Review for disabling or replacement; fetch failures are persistent.",
    (
        QUARANTINE_RECOMMENDED,
        "non_contributing_runs",
    ): "Review for disabling or replacement; source repeatedly contributes no accepted evidence.",
    (UNKNOWN_STATE, "insufficient_history"): "Collect more persisted runs before evaluating reliability.",
}


def build_source_reliability(registry, current_run, results_dir):
    thresholds = dict(registry.source_reliability_thresholds)
    historical_runs = load_recent_source_intelligence_runs(
        results_dir,
        thresholds["source_reliability_window_runs"],
    )
    current_timestamp = current_run.get("timestamp") if isinstance(current_run, dict) else None
    window_runs = _merge_current_run(historical_runs, current_run, current_timestamp)
    return build_source_reliability_from_runs(registry, window_runs, thresholds)


def build_source_reliability_from_runs(registry, runs, thresholds):
    window_size = thresholds["source_reliability_window_runs"]
    window_runs = list(runs or [])[-window_size:]
    sources = [
        evaluate_source_reliability(source, window_runs, thresholds)
        for source in registry.sources
    ]
    return {
        "evaluation_window": evaluation_window(window_runs, window_size),
        "thresholds_used": {
            "source_reliability_window_runs": thresholds["source_reliability_window_runs"],
            "minimum_required_runs": thresholds["minimum_required_runs"],
            "repeated_failure_ratio": thresholds["repeated_failure_ratio"],
            "quarantine_ratio": thresholds["quarantine_ratio"],
        },
        "sources": sources,
        "summary": summarize_source_reliability(sources),
    }


def load_recent_source_intelligence_runs(results_dir, limit):
    path = Path(results_dir)
    if not path.exists():
        return []

    runs = []
    for result_file in sorted(path.glob("*.json")):
        try:
            with open(result_file, "r", encoding="utf-8") as fh:
                run = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(run, dict):
            continue
        source_intelligence = run.get("source_intelligence")
        if not isinstance(source_intelligence, dict):
            continue
        if not _has_usable_diagnostics(source_intelligence):
            continue
        runs.append(
            {
                "timestamp": str(run.get("timestamp") or result_file.stem),
                "source_intelligence": source_intelligence,
            }
        )
    runs = sorted(runs, key=lambda item: item["timestamp"])
    return runs[-limit:]


def evaluate_source_reliability(source, runs, thresholds):
    source_id = source["source_id"]
    metrics = _empty_metrics(source)

    for run in runs or []:
        observation = _source_observation(source_id, run.get("source_intelligence") or {})
        if observation is None:
            continue
        metrics["runs_observed"] += 1
        metrics["latest_state"] = observation["health_state"]
        if observation["contributed"]:
            metrics["contributing_runs"] += 1

        condition = classify_run_condition(observation)
        if condition == "healthy":
            metrics["healthy_runs"] += 1
        else:
            metrics[condition] += 1

    metrics["non_contributing_runs"] = metrics["runs_observed"] - metrics["contributing_runs"]
    weak_runs = weak_run_count(metrics)
    state = source_reliability_state(
        metrics["runs_observed"],
        weak_runs,
        thresholds,
    )
    dominant_pattern = dominant_failure_pattern(metrics)
    metrics["reliability_state"] = state
    metrics["reason"] = reliability_reason(
        state,
        metrics,
        weak_runs,
        dominant_pattern,
        thresholds["minimum_required_runs"],
    )
    metrics["recommended_action"] = recommended_action(state, dominant_pattern)
    return metrics


def source_reliability_state(runs_observed, weak_runs, thresholds):
    if runs_observed < thresholds["minimum_required_runs"]:
        return UNKNOWN_STATE
    weak_ratio = weak_runs / runs_observed if runs_observed else 0
    if weak_ratio >= thresholds["quarantine_ratio"]:
        return QUARANTINE_RECOMMENDED
    if weak_ratio >= thresholds["repeated_failure_ratio"]:
        return REPEATED_FAILURE
    if weak_runs >= 1:
        return WATCH
    return STABLE


def summarize_source_reliability(sources):
    counts = Counter(source.get("reliability_state") for source in sources or [])
    return {
        "stable_count": counts.get(STABLE, 0),
        "watch_count": counts.get(WATCH, 0),
        "repeated_failure_count": counts.get(REPEATED_FAILURE, 0),
        "quarantine_recommended_count": counts.get(QUARANTINE_RECOMMENDED, 0),
        "unknown_count": counts.get(UNKNOWN_STATE, 0),
    }


def classify_run_condition(observation):
    freshness_status = observation["freshness_status"]
    health_state = observation["health_state"]
    health_severity = observation["health_severity"]

    if health_state in CONDITION_COUNTER_BY_HEALTH_STATE:
        return CONDITION_COUNTER_BY_HEALTH_STATE[health_state]
    if freshness_status == STALE:
        return "stale_runs"
    if health_severity == "INFO" and freshness_status == FRESH:
        return "healthy"
    if health_state in MALFORMED_HEALTH_STATES:
        return "malformed_runs"
    if health_state in ERROR_HEALTH_STATES:
        return "error_runs"
    if health_state == EMPTY:
        return "empty_runs"
    return "error_runs"


def weak_run_count(metrics):
    failure_runs = (
        metrics["stale_runs"]
        + metrics["blocked_runs"]
        + metrics["empty_runs"]
        + metrics["malformed_runs"]
        + metrics["error_runs"]
    )
    healthy_non_contributing = max(0, metrics["healthy_runs"] - metrics["contributing_runs"])
    return failure_runs + healthy_non_contributing


def dominant_failure_pattern(metrics):
    candidates = [
        ("blocked_runs", metrics["blocked_runs"]),
        ("stale_runs", metrics["stale_runs"]),
        ("empty_runs", metrics["empty_runs"]),
        ("malformed_runs", metrics["malformed_runs"]),
        ("error_runs", metrics["error_runs"]),
        (
            "non_contributing_runs",
            max(0, metrics["healthy_runs"] - metrics["contributing_runs"]),
        ),
    ]
    pattern, count = max(candidates, key=lambda item: (item[1], -candidates.index(item)))
    if count <= 0:
        return "healthy"
    return pattern


def reliability_reason(state, metrics, weak_runs, dominant_pattern, minimum_required_runs):
    observed = metrics["runs_observed"]
    if state == UNKNOWN_STATE:
        return (
            f"Only {observed} observed run(s); minimum "
            f"{minimum_required_runs} required."
        )
    if dominant_pattern == "healthy":
        return f"Healthy and contributing in {metrics['contributing_runs']} of {observed} observed runs."
    label = {
        "blocked_runs": "Blocked",
        "stale_runs": "Stale",
        "empty_runs": "Empty",
        "malformed_runs": "Malformed",
        "error_runs": "Fetch error",
        "non_contributing_runs": "Healthy fetches but zero accepted evidence",
    }[dominant_pattern]
    count = (
        max(0, metrics["healthy_runs"] - metrics["contributing_runs"])
        if dominant_pattern == "non_contributing_runs"
        else metrics[dominant_pattern]
    )
    return (
        f"{label} in {count} of {observed} observed runs; "
        f"{weak_runs} weak run(s) total."
    )


def recommended_action(state, dominant_pattern):
    if state == UNKNOWN_STATE:
        dominant_pattern = "insufficient_history"
    return ACTION_BY_STATE_AND_PATTERN.get(
        (state, dominant_pattern),
        ACTION_BY_STATE_AND_PATTERN[(UNKNOWN_STATE, "insufficient_history")],
    )


def evaluation_window(runs, configured_window):
    timestamps = [
        run.get("timestamp")
        for run in runs or []
        if isinstance(run, dict) and run.get("timestamp")
    ]
    return {
        "window_runs_configured": configured_window,
        "runs_evaluated": len(runs or []),
        "oldest_run_timestamp": timestamps[0] if timestamps else None,
        "newest_run_timestamp": timestamps[-1] if timestamps else None,
    }


def _empty_metrics(source):
    return {
        "source_id": source["source_id"],
        "source_name": source.get("display_name") or source["source_id"],
        "provider": source.get("provider"),
        "category": source.get("category"),
        "registry_status": source.get("status"),
        "runs_observed": 0,
        "healthy_runs": 0,
        "stale_runs": 0,
        "blocked_runs": 0,
        "empty_runs": 0,
        "malformed_runs": 0,
        "error_runs": 0,
        "contributing_runs": 0,
        "non_contributing_runs": 0,
        "latest_state": None,
        "reliability_state": UNKNOWN_STATE,
        "reason": "",
        "recommended_action": "",
    }


def _source_observation(source_id, source_intelligence):
    health = _index_by_source_id(source_intelligence.get("source_health")).get(source_id)
    freshness = _index_by_source_id(source_intelligence.get("source_freshness")).get(source_id)
    if not health and not freshness:
        return None
    evidence_count = sum(
        1
        for row in source_intelligence.get("accepted_evidence") or []
        if isinstance(row, dict) and row.get("source_id") == source_id
    )
    return {
        "health_state": (health or {}).get("state"),
        "health_severity": (health or {}).get("severity"),
        "freshness_status": (freshness or {}).get("status"),
        "contributed": evidence_count > 0,
    }


def _index_by_source_id(rows):
    return {
        row.get("source_id"): row
        for row in rows or []
        if isinstance(row, dict) and row.get("source_id")
    }


def _has_usable_diagnostics(source_intelligence):
    return bool(
        source_intelligence.get("source_health")
        or source_intelligence.get("source_freshness")
        or source_intelligence.get("accepted_evidence")
        or source_intelligence.get("evidence_funnel")
    )


def _merge_current_run(historical_runs, current_run, current_timestamp):
    runs = list(historical_runs or [])
    if not isinstance(current_run, dict):
        return runs
    source_intelligence = current_run.get("source_intelligence")
    if not isinstance(source_intelligence, dict) or not _has_usable_diagnostics(source_intelligence):
        return runs
    current_record = {
        "timestamp": str(current_timestamp or current_run.get("run_id") or "current_run"),
        "source_intelligence": source_intelligence,
    }
    if runs and runs[-1].get("timestamp") == current_record["timestamp"]:
        runs[-1] = current_record
    else:
        runs.append(current_record)
    return runs
