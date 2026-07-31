"""Pure deterministic in-app alert evaluation and explicit state persistence."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mne.personalization import SUPPORTED_ALERT_TYPES, alert_state_path
from mne.presentation_language import narrative_display_name

ALERT_STATE_SCHEMA_VERSION = 1
"""Schema version for persisted alert history and evaluation state."""

ALERT_HISTORY_MAX = 50
"""Maximum in-app alert events retained."""

DEFAULT_COOLDOWN_PERIODS = {alert_type: 1 for alert_type in SUPPORTED_ALERT_TYPES}
"""Default cooldowns measured in meaningful live runs."""

MATERIAL_EXPRESSION_TRANSITIONS = {
    ("STRONGLY_CONFIRMING", "DIVERGING"),
    ("CONFIRMING", "DIVERGING"),
    ("DIVERGING", "CONFIRMING"),
    ("DIVERGING", "STRONGLY_CONFIRMING"),
    ("MUTED", "STRONGLY_CONFIRMING"),
    ("STRONGLY_CONFIRMING", "MUTED"),
}
"""Market Expression transitions considered material by the existing state model."""

STRONG_CONNECTION_LABELS = {"STRONG", "VERY_STRONG", "Strong", "Very strong"}
"""Persisted Historical Connection resemblance labels that are meaningful."""

ALERT_SEVERITY = {
    "NARRATIVE_BECAME_DOMINANT": "NOTICE",
    "NARRATIVE_BUILDING_AGAIN": "INFO",
    "NARRATIVE_FADING": "INFO",
    "NARRATIVE_RETURNED": "NOTICE",
    "DOMINANT_NARRATIVE_CHANGED": "NOTICE",
    "MARKET_EXPRESSION_CHANGED_MATERIALLY": "NOTICE",
    "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE": "INFO",
    "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG": "NOTICE",
}
"""Stable severity mapping for supported in-app alerts."""

ALERT_TYPE_CONDITIONS = {
    "NARRATIVE_BECAME_DOMINANT": ("DOMINANT",),
    "NARRATIVE_BUILDING_AGAIN": ("BUILDING", "RE_ACCELERATING"),
    "NARRATIVE_FADING": ("FADING",),
    "NARRATIVE_RETURNED": ("RECURRING",),
    "DOMINANT_NARRATIVE_CHANGED": ("dominant_theme", "dominant_group"),
    "MARKET_EXPRESSION_CHANGED_MATERIALLY": tuple(sorted(MATERIAL_EXPRESSION_TRANSITIONS)),
    "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE": ("LIMITED", "MINIMAL", "UNAVAILABLE", "UNKNOWN"),
    "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG": tuple(sorted(STRONG_CONNECTION_LABELS)),
}
"""Explicit persisted-state conditions used by each alert type."""


def build_default_alert_state() -> dict:
    return {
        "schema_version": ALERT_STATE_SCHEMA_VERSION,
        "last_evaluated_run_id": None,
        "meaningful_run_count": 0,
        "rule_last_triggered_run": {},
        "events": [],
        "limitation_note": None,
    }


def load_alert_state(data_dir: Path | None = None) -> dict:
    path = alert_state_path(data_dir)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if _valid_alert_state(value):
            return value
    except (OSError, json.JSONDecodeError):
        pass
    state = build_default_alert_state()
    state["limitation_note"] = "Local alert history was unavailable or invalid, so safe defaults are being used."
    return state


def save_alert_state(state: dict, data_dir: Path | None = None) -> None:
    if not _valid_alert_state(state):
        raise ValueError("Invalid alert state.")
    path = alert_state_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evaluate_alert_rules(
    latest_run: dict | None,
    previous_run: dict | None,
    preferences: dict,
    alert_state: dict | None = None,
) -> dict:
    """Purely evaluate persisted outputs; inputs are never mutated."""
    state = deepcopy(alert_state or build_default_alert_state())
    run_id = _run_id(latest_run)
    if not run_id or state.get("last_evaluated_run_id") == run_id:
        return state
    state["meaningful_run_count"] = int(state.get("meaningful_run_count") or 0) + 1
    state["last_evaluated_run_id"] = run_id
    state["limitation_note"] = None
    if not preferences.get("enabled", True) or not isinstance(previous_run, dict):
        return state

    enabled_types = set(preferences.get("preferred_alert_types") or [])
    rules = preferences.get("alert_rules") or _default_rules(preferences)
    candidates = _candidate_events(latest_run, previous_run)
    accepted = []
    for event in candidates:
        if event["event_type"] not in enabled_types:
            continue
        matching = [rule for rule in rules if _rule_matches(rule, event)]
        if not matching:
            continue
        rule = matching[0]
        identity = _event_identity(event)
        cooldown = int(rule.get("cooldown_period", DEFAULT_COOLDOWN_PERIODS[event["event_type"]]))
        prior_count = state["rule_last_triggered_run"].get(identity)
        if prior_count is not None and state["meaningful_run_count"] - prior_count <= cooldown:
            continue
        state["rule_last_triggered_run"][identity] = state["meaningful_run_count"]
        accepted.append(event)
    state["events"] = dedupe_alert_events(accepted + list(state.get("events") or []))[:ALERT_HISTORY_MAX]
    return state


def dedupe_alert_events(events: list[dict]) -> list[dict]:
    unique = {}
    for event in events:
        unique.setdefault(_event_identity(event), deepcopy(event))
    return sorted(
        unique.values(),
        key=lambda event: (str(event.get("triggered_at") or ""), _event_identity(event)),
        reverse=True,
    )


def build_personalized_dashboard_context(run: dict | None, preferences: dict, alert_state: dict) -> dict:
    memory = (run or {}).get("narrative_memory") or {}
    records = {
        (level, str(item.get("narrative_name") or item.get("name") or item.get("narrative_key") or "")): item
        for level, key in (("theme", "themes"), ("group", "groups"))
        for item in (memory.get(key) or [])
        if isinstance(item, dict)
    }
    events = alert_state.get("events") or []
    items = []
    for followed in preferences.get("followed_narratives") or []:
        level, key = followed["narrative_level"], followed["narrative_key"]
        record = records.get((level, key), {})
        alert = next((event for event in events if event.get("narrative_key") == key), None)
        items.append({
            "narrative_level": level,
            "narrative_key": key,
            "display_name": narrative_display_name(key),
            "lifecycle_state": record.get("memory_state"),
            "summary": record.get("plain_language_summary") or "Recent narrative history is not available yet.",
            "latest_alert": alert,
            "investigation_url": f"/research/{level}:{key}",
        })
    return {"items": items, "recent_alerts": events[:8], "notification_count": len(events)}


def _candidate_events(current: dict, previous: dict) -> list[dict]:
    timestamp = str(current.get("timestamp") or "")
    events = []
    current_records = _memory_records(current)
    previous_records = _memory_records(previous)
    transition_map = {
        "DOMINANT": "NARRATIVE_BECAME_DOMINANT",
        "BUILDING": "NARRATIVE_BUILDING_AGAIN",
        "RE_ACCELERATING": "NARRATIVE_BUILDING_AGAIN",
        "FADING": "NARRATIVE_FADING",
        "RECURRING": "NARRATIVE_RETURNED",
    }
    for key in sorted(set(current_records) & set(previous_records)):
        old, new = previous_records[key], current_records[key]
        alert_type = transition_map.get(new)
        if alert_type and old != new:
            events.append(_event(alert_type, key[1], timestamp, old, new, key[0]))
    for level, dominant_field in (("theme", "dominant_theme"), ("group", "dominant_group")):
        old, new = previous.get(dominant_field), current.get(dominant_field)
        if old and new and old != new:
            events.append(_event("DOMINANT_NARRATIVE_CHANGED", str(new), timestamp, str(old), str(new), level))
    old_expression, new_expression = _expression_state(previous), _expression_state(current)
    if old_expression and new_expression and (old_expression, new_expression) in MATERIAL_EXPRESSION_TRANSITIONS:
        key = str(current.get("dominant_group") or current.get("dominant_theme") or "market narrative")
        events.append(_event("MARKET_EXPRESSION_CHANGED_MATERIALLY", key, timestamp, old_expression, new_expression))
    old_coverage, new_coverage = _coverage_state(previous), _coverage_state(current)
    if new_coverage in ALERT_TYPE_CONDITIONS["EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE"] and new_coverage != old_coverage:
        key = str(current.get("dominant_group") or current.get("dominant_theme") or "current read")
        events.append(_event("EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE", key, timestamp, old_coverage, new_coverage))
    old_connection, new_connection = _connection_label(previous), _connection_label(current)
    if new_connection in STRONG_CONNECTION_LABELS and new_connection != old_connection:
        key = str(current.get("dominant_group") or current.get("dominant_theme") or "current read")
        events.append(_event("HISTORICAL_CONNECTION_MEANINGFULLY_STRONG", key, timestamp, old_connection, new_connection))
    return events


def _event(alert_type: str, key: str, timestamp: str, old: Any, new: Any, level: str | None = None) -> dict:
    name = narrative_display_name(key)
    copy = {
        "NARRATIVE_BECAME_DOMINANT": (f"{name} became the dominant narrative", "It moved into the dominant lifecycle state."),
        "NARRATIVE_BUILDING_AGAIN": (f"{name} is building again", "Its persisted lifecycle state changed to renewed or building attention."),
        "NARRATIVE_FADING": (f"{name} is fading", "Its persisted lifecycle state changed to fading."),
        "NARRATIVE_RETURNED": (f"{name} returned", "It reappeared after an earlier absence."),
        "DOMINANT_NARRATIVE_CHANGED": (f"The dominant narrative changed to {name}", f"{narrative_display_name(str(old))} previously led the persisted read."),
        "MARKET_EXPRESSION_CHANGED_MATERIALLY": (f"Market expression changed materially for {name}", "The persisted Market Expression state crossed a material transition."),
        "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE": ("The evidence base is limited", "The persisted coverage state became limited or unavailable."),
        "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG": (f"{name} has a strong historical resemblance", "The persisted Historical Connection label became meaningfully strong."),
    }[alert_type]
    return {
        "event_type": alert_type,
        "headline": copy[0],
        "summary": copy[1],
        "triggered_at": timestamp,
        "narrative_key": key,
        "narrative_level": level,
        "severity": ALERT_SEVERITY[alert_type],
        "supporting_details": [f"Observed transition: {old or 'unavailable'} → {new}"],
        "transition": f"{old or 'unavailable'}->{new}",
    }


def _default_rules(preferences: dict) -> list[dict]:
    followed = preferences.get("followed_narratives") or []
    rules = []
    for alert_type in SUPPORTED_ALERT_TYPES:
        if alert_type in {"DOMINANT_NARRATIVE_CHANGED", "MARKET_EXPRESSION_CHANGED_MATERIALLY", "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE", "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG"}:
            rules.append({"alert_type": alert_type, "narrative_level": None, "narrative_key": None, "enabled": True, "cooldown_period": DEFAULT_COOLDOWN_PERIODS[alert_type], "last_triggered_at": None})
        for item in followed:
            rules.append({"alert_type": alert_type, **item, "enabled": True, "cooldown_period": DEFAULT_COOLDOWN_PERIODS[alert_type], "last_triggered_at": None})
    return rules


def _rule_matches(rule: dict, event: dict) -> bool:
    return bool(rule.get("enabled", True)) and rule.get("alert_type") == event["event_type"] and (
        rule.get("narrative_key") in (None, event["narrative_key"])
    ) and (rule.get("narrative_level") in (None, event.get("narrative_level")))


def _event_identity(event: dict) -> str:
    return "|".join((str(event.get("event_type") or ""), str(event.get("narrative_key") or ""), str(event.get("transition") or "")))


def _memory_records(run: dict) -> dict:
    memory = run.get("narrative_memory") or {}
    return {
        (level, str(item.get("narrative_name") or item.get("name") or item.get("narrative_key") or "")): str(item.get("memory_state") or "")
        for level, plural in (("theme", "themes"), ("group", "groups"))
        for item in (memory.get(plural) or [])
        if isinstance(item, dict)
    }


def _expression_state(run: dict) -> str | None:
    value = run.get("market_expression_context") or {}
    return value.get("state") if isinstance(value, dict) else None


def _coverage_state(run: dict) -> str | None:
    value = ((run.get("source_intelligence") or {}).get("coverage_intelligence") or {})
    if not isinstance(value, dict):
        return None
    return value.get("breadth_state") or value.get("coverage_state")


def _connection_label(run: dict) -> str | None:
    value = run.get("historical_connection") or run.get("historical_connection_context") or {}
    if not isinstance(value, dict):
        return None
    return value.get("resemblance_label") or value.get("label")


def _run_id(run: dict | None) -> str | None:
    if not isinstance(run, dict):
        return None
    return str(run.get("run_id") or run.get("timestamp") or "") or None


def _valid_alert_state(value: Any) -> bool:
    return isinstance(value, dict) and value.get("schema_version") == ALERT_STATE_SCHEMA_VERSION and isinstance(value.get("events"), list) and isinstance(value.get("rule_last_triggered_run"), dict)
