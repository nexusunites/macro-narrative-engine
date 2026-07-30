"""Read-only narrative history built exclusively from daily snapshots.

Pulse lifecycle labels come from each snapshot narrative row. Memory-derived
labels are included only when the same snapshot explicitly persists a matching
``narrative_memory`` or ``narrative_dynamics`` value; this module never derives
those labels from scores, shares, ranks, replay artifacts, or live evidence.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from mne.explanation_layer import explain_history_pattern

from mne.render_cache import get_or_load
from mne.storage import SNAPSHOTS_DIR


DEFAULT_WINDOW_DAYS = 90
MEMORY_STATES = {
    "recurring": "Recurring",
    "re-accelerating": "Re-accelerating",
    "re_accelerating": "Re-accelerating",
    "persistent": "Persistent",
    "fading": "Fading",
}


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file_handle:
        value = json.load(file_handle)
    if not isinstance(value, dict):
        raise ValueError("snapshot must be an object")
    return value


def _snapshot_files(snapshot_dir: Path) -> list[Path]:
    valid = []
    if not snapshot_dir.exists():
        return valid
    for path in snapshot_dir.glob("*.json"):
        try:
            date.fromisoformat(path.stem)
        except ValueError:
            continue
        valid.append(path)
    return sorted(valid, key=lambda item: item.stem)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _rank(value: Any) -> int | float | None:
    numeric = _number(value)
    return numeric if numeric is not None and numeric > 0 else None


def _matching_row(snapshot: dict, group_key: str) -> dict | None:
    rows = snapshot.get("narratives")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("group") == group_key:
            return row
    return None


def _normalized_memory_state(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    return MEMORY_STATES.get(key)


def _persisted_memory_state(snapshot: dict, row: dict | None, group_key: str) -> str | None:
    if row:
        for key in ("memory_state", "momentum_label", "dynamics_state"):
            state = _normalized_memory_state(row.get(key))
            if state:
                return state

    memory = snapshot.get("narrative_memory")
    if isinstance(memory, dict):
        groups = memory.get("groups")
        if isinstance(groups, list):
            for record in groups:
                if isinstance(record, dict) and record.get("name") == group_key:
                    for key in ("memory_state", "momentum_label"):
                        state = _normalized_memory_state(record.get(key))
                        if state:
                            return state

    dynamics = snapshot.get("narrative_dynamics")
    if isinstance(dynamics, dict):
        groups = dynamics.get("groups")
        record = groups.get(group_key) if isinstance(groups, dict) else None
        if isinstance(record, dict):
            for key in ("state", "momentum_label", "persistence_label"):
                state = _normalized_memory_state(record.get(key))
                if state:
                    return state
    return None


def _peak(points: list[dict], key: str) -> dict | None:
    available = [point for point in points if point[key] is not None]
    if not available:
        return None
    point = max(available, key=lambda item: (item[key], item["date"]))
    return {"value": point[key], "date": point["date"]}


def _current_streak(points: list[dict]) -> int:
    streak = 0
    for point in reversed(points):
        if point["pulse_state"] == "Absent":
            break
        streak += 1
    return streak


def _chart(points: list[dict], key: str, *, invert: bool = False) -> dict:
    available = [point for point in points if point[key] is not None]
    if len(available) < 3:
        return {"available": False, "segments": [], "minimum": None, "maximum": None}

    values = [point[key] for point in available]
    low, high = min(values), max(values)
    domain_low = 1 if invert else min(0, low)
    domain_high = max(high, domain_low + 1)
    width, height, pad_x, pad_y = 640, 180, 34, 22
    x_step = (width - 2 * pad_x) / max(1, len(points) - 1)
    segments: list[list[dict]] = []
    segment: list[dict] = []
    for index, point in enumerate(points):
        value = point[key]
        if value is None:
            if segment:
                segments.append(segment)
                segment = []
            continue
        ratio = (value - domain_low) / (domain_high - domain_low)
        if invert:
            ratio = 1 - ratio
        plotted = {
            "date": point["date"],
            "label": point["label"],
            "value": value,
            "pulse_state": point["pulse_state"],
            "x": round(pad_x + x_step * index, 2),
            "y": round(pad_y + (1 - ratio) * (height - 2 * pad_y), 2),
        }
        segment.append(plotted)
    if segment:
        segments.append(segment)
    if invert:
        stepped_segments = []
        for current in segments:
            stepped = []
            for plotted in current:
                if stepped:
                    stepped.append({**plotted, "y": stepped[-1]["y"]})
                stepped.append(plotted)
            stepped_segments.append(stepped)
        segments = stepped_segments
    return {
        "available": True,
        "segments": segments,
        "minimum": low,
        "maximum": high,
    }


def build_narrative_history(
    group_key: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    *,
    snapshot_dir: Path | None = None,
) -> dict:
    """Return a deterministic, presentation-ready group history context."""
    limit = max(1, int(window_days))
    directory = Path(snapshot_dir) if snapshot_dir is not None else SNAPSHOTS_DIR
    snapshots = []
    for path in reversed(_snapshot_files(directory)):
        try:
            snapshot = get_or_load(path, _load_json)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        snapshot_date = snapshot.get("date")
        try:
            parsed_date = date.fromisoformat(str(snapshot_date))
        except ValueError:
            continue
        if str(snapshot_date) != path.stem:
            continue
        snapshots.append((parsed_date, snapshot))
        if len(snapshots) >= limit:
            break
    snapshots.reverse()

    points = []
    for snapshot_date, snapshot in snapshots:
        row = _matching_row(snapshot, group_key)
        rank = _rank(row.get("rank")) if row else None
        pulse = str(row.get("pulse_state") or "").strip() if row else ""
        points.append(
            {
                "date": snapshot_date.isoformat(),
                "label": snapshot_date.strftime("%b %-d, %Y"),
                "score": _number(row.get("score")) if row else None,
                "share": _number(row.get("share")) if row else None,
                "rank": rank,
                "dominant": rank == 1,
                "pulse_state": pulse or ("Absent" if row is None else "Unavailable"),
                "memory_state": _persisted_memory_state(snapshot, row, group_key),
            }
        )

    present = [point for point in points if point["pulse_state"] != "Absent"]
    current = present[-1] if present else None
    previous = present[-2] if len(present) > 1 else None
    persisted_events = [
        {"date": point["date"], "state": point["memory_state"]}
        for point in points
        if point["memory_state"] in {"Recurring", "Re-accelerating"}
    ]
    timeline_legend = []
    for point in points:
        for state in (point["pulse_state"], point["memory_state"]):
            if state and state not in timeline_legend:
                timeline_legend.append(state)
    context = {
        "group_key": group_key,
        "window_days": limit,
        "days_in_window": len(points),
        "points": points,
        "has_history": bool(points),
        "has_chart_history": (
            len(points) >= 3
            and sum(1 for point in points if point["score"] is not None) >= 3
        ),
        "score_chart": _chart(points, "score"),
        "share_chart": _chart(points, "share"),
        "rank_chart": _chart(points, "rank", invert=True),
        "timeline_legend": timeline_legend,
        "summary": {
            "current_stage": current["pulse_state"] if current else None,
            "previous_stage": previous["pulse_state"] if previous else None,
            "current_streak": _current_streak(points),
            "appearances": len(present),
            "dominance_count": sum(1 for point in points if point["dominant"]),
            "peak_score": _peak(points, "score"),
            "peak_share": _peak(points, "share"),
            "latest_memory_event": persisted_events[-1] if persisted_events else None,
        },
    }
    context["explanation"] = explain_history_pattern(context)
    return context
