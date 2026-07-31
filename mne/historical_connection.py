"""Deterministic, read-only connections between current and historical narratives.

The helper consumes already-persisted live, snapshot, and completed historical
reconstruction data.  It performs no fetching, scoring, replay, backfill, or
persistence.  Similarity is descriptive presentation context, not a prediction.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from mne.historical_research import (
    HistoricalResearchError,
    default_replay_dir,
    load_replay_for_historical_research,
)
from mne.presentation_language import narrative_display_name


# Each available component is normalized over the available component weights.
SIMILARITY_WEIGHTS = {
    "dominant_theme": 0.20,
    "dominant_group": 0.25,
    "theme_distribution": 0.20,
    "group_distribution": 0.20,
    "rank_overlap": 0.15,
}
"""Named component weights for the internal descriptive resemblance score."""

RESEMBLANCE_LABEL_THRESHOLDS = (
    (0.82, "Strong resemblance"),
    (0.66, "Moderate resemblance"),
    (0.48, "Some shared features"),
    (0.32, "Limited resemblance"),
)
"""Rounded internal-score floors, from strongest to weakest displayed label."""

TRAJECTORY_DELTA_THRESHOLDS = {"building": 0.03, "easing": -0.03}
"""Average recent share-delta boundaries for influence trajectory labels."""

RECENT_PEAK_WINDOW = 90
"""Maximum daily snapshot window used for recent peak and trajectory context."""

RECENT_TRAJECTORY_POINTS = 4
"""Maximum number of present snapshot points used for trajectory deltas."""

SIMILAR_SHARE_TOLERANCE = 0.05
"""Maximum absolute share difference for a prior similar-influence period."""

COVERAGE_CAP_LEVEL_GAP = 2
"""Coverage-level gap that demotes high-confidence resemblance by one step."""

MAX_CONNECTIONS = 3
"""Maximum historical reconstructions returned to presentation surfaces."""

SCORE_PRECISION = 6
"""Decimal precision applied before thresholds and deterministic ordering."""

COVERAGE_LEVELS = {
    "MINIMAL": 0,
    "LIMITED": 1,
    "NARROW": 1,
    "MODERATE": 2,
    "BROAD": 3,
    "ROBUST": 3,
    "EXTENSIVE": 4,
}

COVERAGE_CAVEAT = (
    "Part of the difference may reflect the sources available for the "
    "historical reconstruction."
)
MISSING_COVERAGE_LIMITATION = (
    "Coverage context is unavailable for one of the compared periods."
)
DESCRIPTIVE_LIMITATION = "The comparison is descriptive, not predictive."


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _share_fraction(value: Any) -> float | None:
    numeric = _number(value)
    if numeric is None:
        return None
    return numeric / 100 if abs(numeric) > 1 else numeric


def _positive_score_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    scores = {}
    for key, value_score in sorted(value.items(), key=lambda item: str(item[0])):
        score = _number(value_score)
        if score is not None and score > 0:
            scores[str(key)] = score
    return scores


def _normalized_distribution(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values())
    if total <= 0:
        return {}
    return {
        key: round(value / total, SCORE_PRECISION)
        for key, value in sorted(scores.items())
    }


def _rank_map(scores: dict[str, float]) -> dict[str, int]:
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return {key: index + 1 for index, (key, _) in enumerate(ordered)}


def _coverage_state(value: dict[str, Any]) -> str | None:
    source_intelligence = value.get("source_intelligence")
    coverage = (
        source_intelligence.get("coverage_intelligence")
        if isinstance(source_intelligence, dict)
        else None
    )
    if not isinstance(coverage, dict):
        return None
    raw = coverage.get("breadth_state") or coverage.get("coverage_state")
    if raw:
        return str(raw).strip().upper()
    per_narrative = coverage.get("per_narrative")
    if isinstance(per_narrative, list):
        known = [
            str(row.get("coverage_state")).strip().upper()
            for row in per_narrative
            if isinstance(row, dict) and row.get("coverage_state")
        ]
        levels = [COVERAGE_LEVELS[item] for item in known if item in COVERAGE_LEVELS]
        if levels:
            target = round(sum(levels) / len(levels))
            return min(COVERAGE_LEVELS, key=lambda key: (abs(COVERAGE_LEVELS[key] - target), key))
    return None


def build_current_narrative_profile(current: dict[str, Any]) -> dict[str, Any]:
    """Normalize a persisted meaningful live result for comparison."""
    current = current if isinstance(current, dict) else {}
    themes = _positive_score_map(current.get("theme_scores") or current.get("theme_counts"))
    groups = _positive_score_map(current.get("group_scores"))
    return _build_profile(
        themes,
        groups,
        dominant_theme=current.get("dominant_theme"),
        dominant_group=current.get("dominant_group"),
        coverage_state=_coverage_state(current),
        period_date=_period_date(current),
    )


def build_replay_narrative_profile(artifact: dict[str, Any]) -> dict[str, Any]:
    """Normalize one already-loaded completed reconstruction for comparison."""
    artifact = artifact if isinstance(artifact, dict) else {}
    return _build_profile(
        _positive_score_map(artifact.get("theme_scores")),
        _positive_score_map(artifact.get("group_scores")),
        dominant_theme=artifact.get("dominant_theme"),
        dominant_group=artifact.get("dominant_group"),
        coverage_state=_coverage_state(artifact),
        period_date=str(artifact.get("replay_date") or ""),
    )


def _build_profile(
    themes: dict[str, float],
    groups: dict[str, float],
    *,
    dominant_theme: Any,
    dominant_group: Any,
    coverage_state: str | None,
    period_date: str,
) -> dict[str, Any]:
    return {
        "date": period_date,
        "dominant_theme": str(dominant_theme) if dominant_theme else None,
        "dominant_group": str(dominant_group) if dominant_group else None,
        "theme_scores": themes,
        "group_scores": groups,
        "theme_distribution": _normalized_distribution(themes),
        "group_distribution": _normalized_distribution(groups),
        "theme_ranks": _rank_map(themes),
        "group_ranks": _rank_map(groups),
        "coverage_state": coverage_state,
    }


def _period_date(value: dict[str, Any]) -> str:
    timestamp = str(value.get("timestamp") or "")
    try:
        return date.fromisoformat(timestamp[:10]).isoformat()
    except ValueError:
        return ""


def _distribution_similarity(left: dict[str, float], right: dict[str, float]) -> float | None:
    if not left or not right:
        return None
    keys = set(left) | set(right)
    distance = sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys) / 2
    return round(max(0.0, 1.0 - distance), SCORE_PRECISION)


def _top_rank_overlap(current: dict[str, Any], historical: dict[str, Any]) -> float | None:
    current_order = sorted(
        current.get("group_scores", {}).items(), key=lambda item: (-item[1], item[0])
    )[:3]
    historical_order = sorted(
        historical.get("group_scores", {}).items(), key=lambda item: (-item[1], item[0])
    )[:3]
    if not current_order or not historical_order:
        return None
    current_keys = {item[0] for item in current_order}
    historical_keys = {item[0] for item in historical_order}
    return round(
        len(current_keys & historical_keys) / len(current_keys | historical_keys),
        SCORE_PRECISION,
    )


def compute_profile_similarity(
    current: dict[str, Any], historical: dict[str, Any]
) -> dict[str, Any]:
    """Return the hand-derivable internal score and all component values."""
    components: dict[str, float | None] = {
        "dominant_theme": (
            1.0
            if current.get("dominant_theme")
            and current.get("dominant_theme") == historical.get("dominant_theme")
            else 0.0
        ),
        "dominant_group": (
            1.0
            if current.get("dominant_group")
            and current.get("dominant_group") == historical.get("dominant_group")
            else 0.0
        ),
        "theme_distribution": _distribution_similarity(
            current.get("theme_distribution", {}),
            historical.get("theme_distribution", {}),
        ),
        "group_distribution": _distribution_similarity(
            current.get("group_distribution", {}),
            historical.get("group_distribution", {}),
        ),
        "rank_overlap": _top_rank_overlap(current, historical),
    }
    available = {
        key: value for key, value in components.items() if value is not None
    }
    denominator = sum(SIMILARITY_WEIGHTS[key] for key in available)
    score = (
        sum(SIMILARITY_WEIGHTS[key] * value for key, value in available.items())
        / denominator
        if denominator
        else 0.0
    )
    rounded = round(score, SCORE_PRECISION)
    raw_label = _resemblance_label(rounded)
    coverage = _coverage_compatibility(
        current.get("coverage_state"), historical.get("coverage_state")
    )
    label = _apply_coverage_cap(raw_label, coverage["material_mismatch"])
    return {
        "score": rounded,
        "components": components,
        "raw_label": raw_label,
        "label": label,
        "coverage": coverage,
    }


def _resemblance_label(score: float) -> str | None:
    for floor, label in RESEMBLANCE_LABEL_THRESHOLDS:
        if score >= floor:
            return label
    return None


def _coverage_compatibility(current: Any, historical: Any) -> dict[str, Any]:
    current_key = str(current or "").upper()
    historical_key = str(historical or "").upper()
    if current_key not in COVERAGE_LEVELS or historical_key not in COVERAGE_LEVELS:
        return {
            "known": False,
            "level_gap": None,
            "differs": False,
            "material_mismatch": False,
        }
    gap = abs(COVERAGE_LEVELS[current_key] - COVERAGE_LEVELS[historical_key])
    return {
        "known": True,
        "level_gap": gap,
        "differs": gap > 0,
        "material_mismatch": gap >= COVERAGE_CAP_LEVEL_GAP,
    }


def _apply_coverage_cap(label: str | None, material: bool) -> str | None:
    if not material:
        return label
    return {
        "Strong resemblance": "Moderate resemblance",
        "Moderate resemblance": "Some shared features",
    }.get(label, label)


def _display(value: Any) -> str:
    return narrative_display_name(value) or str(value or "")


def _shared_features(current: dict[str, Any], historical: dict[str, Any]) -> list[str]:
    features = []
    if current.get("dominant_group") == historical.get("dominant_group") and current.get(
        "dominant_group"
    ):
        features.append(f"{_display(current['dominant_group'])} leads in both periods.")
    elif current.get("dominant_theme") == historical.get("dominant_theme") and current.get(
        "dominant_theme"
    ):
        features.append(f"{_display(current['dominant_theme'])} is the leading theme in both periods.")
    current_top = [
        key
        for key, _ in sorted(
            current.get("group_scores", {}).items(), key=lambda item: (-item[1], item[0])
        )[:3]
    ]
    historical_top = set(
        key
        for key, _ in sorted(
            historical.get("group_scores", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:3]
    )
    shared_secondary = [
        key for key in current_top if key in historical_top and key != current.get("dominant_group")
    ]
    if shared_secondary:
        features.append(f"{_display(shared_secondary[0])} is influential in both periods.")
    return features[:2]


def _meaningful_differences(
    current: dict[str, Any], historical: dict[str, Any]
) -> list[str]:
    differences = []
    if (
        current.get("dominant_group")
        and historical.get("dominant_group")
        and current["dominant_group"] != historical["dominant_group"]
    ):
        differences.append(
            f"{_display(current['dominant_group'])} leads today, while "
            f"{_display(historical['dominant_group'])} led the earlier period."
        )
    current_groups = current.get("group_distribution", {})
    historical_groups = historical.get("group_distribution", {})
    deltas = sorted(
        (
            (current_groups.get(key, 0.0) - historical_groups.get(key, 0.0), key)
            for key in set(current_groups) | set(historical_groups)
        ),
        key=lambda item: (-abs(item[0]), item[1]),
    )
    for delta, key in deltas:
        if abs(delta) >= 0.08 and key not in {
            current.get("dominant_group"),
            historical.get("dominant_group"),
        }:
            direction = "larger" if delta > 0 else "smaller"
            differences.append(f"{_display(key)} plays a {direction} role today.")
            break
    return differences[:2]


def build_connection_limitations(similarity: dict[str, Any]) -> list[str]:
    limitations = [DESCRIPTIVE_LIMITATION]
    coverage = similarity.get("coverage", {})
    if coverage.get("differs"):
        limitations.insert(0, COVERAGE_CAVEAT)
    elif not coverage.get("known"):
        limitations.insert(0, MISSING_COVERAGE_LIMITATION)
    return limitations


def explain_historical_connection(
    current: dict[str, Any],
    historical: dict[str, Any],
    similarity: dict[str, Any],
) -> dict[str, Any]:
    """Build one user-safe Explanation Layer structure."""
    date_label = historical.get("date") or "the selected earlier period"
    shared = _shared_features(current, historical)
    differences = _meaningful_differences(current, historical)
    lead = shared[0] if shared else "The periods share parts of their narrative mix."
    headline = f"The current narrative mix resembles the reconstruction from {date_label}."
    return {
        "headline": headline,
        "what_changed": differences[0] if differences else None,
        "why_it_matters": lead,
        "supporting_points": (shared[1:] + differences)[:3],
        "limitations": build_connection_limitations(similarity),
        "technical_details": [],
    }


def rank_historical_connections(
    current: dict[str, Any],
    replay_artifacts: Iterable[tuple[str, dict[str, Any]]],
    *,
    limit: int = MAX_CONNECTIONS,
) -> list[dict[str, Any]]:
    """Rank completed artifacts by score descending and date descending."""
    current_profile = build_current_narrative_profile(current)
    candidates = []
    for url_id, artifact in replay_artifacts:
        historical_profile = build_replay_narrative_profile(artifact)
        if not historical_profile["theme_scores"] and not historical_profile["group_scores"]:
            continue
        similarity = compute_profile_similarity(current_profile, historical_profile)
        if similarity["label"] is None:
            continue
        explanation = explain_historical_connection(
            current_profile, historical_profile, similarity
        )
        candidates.append(
            {
                "date": historical_profile["date"],
                "label": similarity["label"],
                "shared_features": _shared_features(current_profile, historical_profile),
                "differences": _meaningful_differences(current_profile, historical_profile),
                "coverage_caveat": (
                    COVERAGE_CAVEAT if similarity["coverage"]["differs"] else None
                ),
                "limitations": explanation["limitations"],
                "historical_url": f"/history/{url_id}",
                "comparison_url": f"/history/{url_id}",
                "explanation": explanation,
                "metadata": similarity,
            }
        )
    candidates.sort(key=lambda item: (item["metadata"]["score"], item["date"]), reverse=True)
    return candidates[: max(0, min(int(limit), MAX_CONNECTIONS))]


def load_completed_replay_artifacts(
    replay_dir: Path | None = None,
    *,
    loader: Callable[..., tuple[dict[str, Any], Path]] = load_replay_for_historical_research,
) -> list[tuple[str, dict[str, Any]]]:
    """Load valid completed reconstructions without triggering any execution."""
    directory = Path(replay_dir) if replay_dir is not None else default_replay_dir()
    if not directory.exists():
        return []
    artifacts = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        try:
            artifact, _ = loader(path.stem, replay_dir=directory)
        except (HistoricalResearchError, OSError, ValueError, TypeError):
            continue
        status = str(artifact.get("status") or "completed").strip().lower()
        if status not in {"complete", "completed", "success"}:
            continue
        if not artifact.get("replay_date"):
            continue
        artifacts.append((path.stem, artifact))
    return artifacts


def compare_current_to_recent_peak(
    narrative_name: str, history: dict[str, Any] | None
) -> dict[str, Any]:
    """Describe current influence, recent peaks, trajectory, and prior peers."""
    history = history if isinstance(history, dict) else {}
    points = history.get("points") if isinstance(history.get("points"), list) else []
    points = points[-RECENT_PEAK_WINDOW:]
    present = [
        point
        for point in points
        if isinstance(point, dict)
        and any(_number(point.get(key)) is not None for key in ("score", "share", "rank"))
    ]
    if not present:
        return {
            "available": False,
            "headline": f"Recent history is still limited for {_display(narrative_name)}.",
            "trajectory": "limited",
            "current": None,
            "peak_score": None,
            "peak_share": None,
            "prior_similar_periods": [],
        }
    current = present[-1]
    peak_score = _peak(present, "score")
    peak_share = _peak(present, "share")
    trajectory = _trajectory(points, present)
    prior_similar = _prior_similar_periods(present)
    name = _display(narrative_name)
    current_share = _number(current.get("share"))
    peak_share_value = _number((peak_share or {}).get("value"))
    if current_share is not None and peak_share_value is not None and current_share < peak_share_value:
        headline = f"{name} is less concentrated than at its recent peak."
    elif trajectory == "building":
        headline = f"Influence around {name} is building across recent history."
    elif trajectory == "easing":
        headline = f"Influence around {name} has eased across recent history."
    elif trajectory == "returning":
        headline = f"{name} has returned after a quieter stretch."
    elif len(present) < 3:
        headline = f"Recent history is still limited for {name}."
    else:
        headline = f"{name}'s recent influence has been broadly stable."
    return {
        "available": len(present) >= 2,
        "headline": headline,
        "trajectory": trajectory,
        "current": {
            "date": current.get("date"),
            "score": _number(current.get("score")),
            "share": current_share,
            "rank": _number(current.get("rank")),
        },
        "peak_score": peak_score,
        "peak_share": peak_share,
        "score_delta_from_peak": _delta_from_peak(current, peak_score, "score"),
        "share_delta_from_peak": _delta_from_peak(current, peak_share, "share"),
        "prior_similar_periods": prior_similar,
    }


def _peak(points: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    available = [
        point for point in points if _number(point.get(key)) is not None
    ]
    if not available:
        return None
    point = max(available, key=lambda item: (_number(item.get(key)), str(item.get("date") or "")))
    return {"value": _number(point.get(key)), "date": point.get("date")}


def _delta_from_peak(
    current: dict[str, Any], peak: dict[str, Any] | None, key: str
) -> float | None:
    current_value = _number(current.get(key))
    peak_value = _number((peak or {}).get("value"))
    if current_value is None or peak_value is None:
        return None
    return round(current_value - peak_value, SCORE_PRECISION)


def _trajectory(points: list[dict[str, Any]], present: list[dict[str, Any]]) -> str:
    if len(present) < 3:
        return "limited"
    latest_index = points.index(present[-1])
    recent_window = points[max(0, latest_index - RECENT_TRAJECTORY_POINTS) : latest_index]
    if any(
        point.get("pulse_state") == "Absent"
        or all(_number(point.get(key)) is None for key in ("score", "share", "rank"))
        for point in recent_window
    ):
        return "returning"
    recent = present[-RECENT_TRAJECTORY_POINTS:]
    shares = [_share_fraction(point.get("share")) for point in recent]
    shares = [value for value in shares if value is not None]
    if len(shares) < 3:
        scores = [_number(point.get("score")) for point in recent]
        scores = [value for value in scores if value is not None]
        total = max(scores) if scores else 0
        shares = [value / total for value in scores] if total else []
    if len(shares) < 3:
        return "limited"
    deltas = [right - left for left, right in zip(shares, shares[1:])]
    average = round(sum(deltas) / len(deltas), SCORE_PRECISION)
    if average >= TRAJECTORY_DELTA_THRESHOLDS["building"]:
        return "building"
    if average <= TRAJECTORY_DELTA_THRESHOLDS["easing"]:
        return "easing"
    return "stable"


def _prior_similar_periods(present: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(present) < 2:
        return []
    current = present[-1]
    current_rank = _number(current.get("rank"))
    current_share = _share_fraction(current.get("share"))
    matches = []
    for point in reversed(present[:-1]):
        rank = _number(point.get("rank"))
        share = _share_fraction(point.get("share"))
        if (
            current_rank is not None
            and rank == current_rank
            or current_share is not None
            and share is not None
            and abs(share - current_share) <= SIMILAR_SHARE_TOLERANCE
        ):
            matches.append(
                {"date": point.get("date"), "rank": rank, "share": share}
            )
        if len(matches) >= 3:
            break
    return matches


def load_current_and_historical_context(
    current: dict[str, Any],
    *,
    narrative_name: str | None = None,
    history: dict[str, Any] | None = None,
    replay_dir: Path | None = None,
    replay_artifacts: Iterable[tuple[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Return complete current-to-history presentation context."""
    artifacts = (
        list(replay_artifacts)
        if replay_artifacts is not None
        else load_completed_replay_artifacts(replay_dir)
    )
    connections = rank_historical_connections(current, artifacts)
    current_profile = build_current_narrative_profile(current)
    selected_name = narrative_name or current_profile.get("dominant_group") or current_profile.get(
        "dominant_theme"
    )
    recent = compare_current_to_recent_peak(str(selected_name or "This narrative"), history)
    if recent.get("current") is None and selected_name:
        if selected_name in current_profile["group_scores"]:
            scores = current_profile["group_scores"]
            distribution = current_profile["group_distribution"]
            ranks = current_profile["group_ranks"]
        else:
            scores = current_profile["theme_scores"]
            distribution = current_profile["theme_distribution"]
            ranks = current_profile["theme_ranks"]
        if selected_name in scores:
            recent["current"] = {
                "date": current_profile.get("date"),
                "score": scores[selected_name],
                "share": distribution.get(selected_name),
                "rank": ranks.get(selected_name),
            }
    if connections:
        best = connections[0]
        summary = (
            recent["headline"]
            if recent.get("available")
            else best["explanation"]["headline"]
        )
        dashboard_sentence = (
            f"Today's narrative mix resembles the reconstruction from {best['date']}, "
            "with differences in how attention is distributed."
        )
    else:
        summary = (
            recent["headline"]
            if recent.get("available")
            else "No prior reconstruction closely resembles today's mix."
        )
        dashboard_sentence = None
    explanation = {
        "headline": summary,
        "what_changed": (
            connections[0]["explanation"]["what_changed"] if connections else None
        ),
        "why_it_matters": (
            connections[0]["explanation"]["why_it_matters"] if connections else None
        ),
        "supporting_points": (
            connections[0]["explanation"]["supporting_points"] if connections else []
        ),
        "limitations": (
            connections[0]["limitations"]
            if connections
            else [DESCRIPTIVE_LIMITATION]
        ),
        "technical_details": [],
    }
    return {
        "available": bool(recent.get("available") or connections),
        "recent": recent,
        "connections": connections,
        "explanation": explanation,
        "dashboard_sentence": (
            dashboard_sentence
            if connections
            and connections[0]["label"] in {"Strong resemblance", "Moderate resemblance"}
            else None
        ),
        "empty_message": (
            None
            if connections
            else "No prior reconstruction closely resembles today's mix."
        ),
    }
