from __future__ import annotations

from pathlib import Path
from typing import Iterable

from config import RESULTS_DIR
from mne.research_workspace import _has_narrative_data
from mne.storage import get_recent_runs
from mne.trends import classify_trend


DEFAULT_MEMORY_RUNS = 10
MIN_THIN_HISTORY_RUNS = 3
MEANINGFUL_SCORE_THRESHOLD = 0
PERSISTENT_STREAK_LENGTH = 3
MOST_RUNS_RATIO = 0.7
RECURRING_APPEARANCES = 2

STATE_DOMINANT = "DOMINANT"
STATE_PERSISTENT = "PERSISTENT"
STATE_BUILDING = "BUILDING"
STATE_FADING = "FADING"
STATE_RECURRING = "RECURRING"
STATE_RE_ACCELERATING = "RE_ACCELERATING"
STATE_DORMANT = "DORMANT"
STATE_EMERGING = "EMERGING"
STATE_ABSENT = "ABSENT"

TREND_BUILDING = "building"
TREND_FADING = "fading"
TREND_RE_ACCELERATING = "re-accelerating"


def load_recent_memory_runs(
    results_dir: Path = RESULTS_DIR,
    lookback: int = DEFAULT_MEMORY_RUNS,
    current_run: dict | None = None,
) -> list[dict]:
    """Load recent meaningful live result runs from RESULTS_DIR only."""
    candidate_lookback = 100000
    runs = get_recent_runs(results_dir, candidate_lookback)
    meaningful_runs = [run for run in runs if _is_memory_eligible_run(run)]

    if _is_memory_eligible_run(current_run):
        meaningful_runs.append(current_run)

    return meaningful_runs[-lookback:]


def build_narrative_memory(
    current_run: dict | None = None,
    results_dir: Path = RESULTS_DIR,
    lookback: int = DEFAULT_MEMORY_RUNS,
) -> dict:
    runs = load_recent_memory_runs(
        results_dir=results_dir,
        lookback=lookback,
        current_run=current_run,
    )
    themes = build_theme_memory(runs)
    groups = build_group_memory(runs)
    warnings = build_memory_warning_messages(runs, lookback)
    return {
        "memory_window": {
            "configured_runs": lookback,
            "runs_used": len(runs),
            "oldest_run": _run_timestamp(runs[0]) if runs else None,
            "newest_run": _run_timestamp(runs[-1]) if runs else None,
        },
        "themes": themes,
        "groups": groups,
        "summary": summarize_memory(themes, groups, warnings),
        "warnings": warnings,
    }


def build_theme_memory(runs: list[dict]) -> list[dict]:
    return _build_memory_records(runs, "theme")


def build_group_memory(runs: list[dict]) -> list[dict]:
    return _build_memory_records(runs, "group")


def classify_memory_state(
    *,
    is_dominant: bool,
    appearances_in_window: int,
    runs_used: int,
    streak_length: int,
    current_score: float,
    score_history: list[float],
) -> str:
    trend = classify_trend(score_history)
    most_runs_count = _most_runs_count(runs_used)

    if is_dominant:
        return STATE_DOMINANT
    if (
        current_score > MEANINGFUL_SCORE_THRESHOLD
        and streak_length >= PERSISTENT_STREAK_LENGTH
        and appearances_in_window >= most_runs_count
    ):
        return STATE_PERSISTENT
    if current_score > MEANINGFUL_SCORE_THRESHOLD and trend == TREND_BUILDING:
        return STATE_BUILDING
    if current_score > MEANINGFUL_SCORE_THRESHOLD and trend == TREND_FADING:
        return STATE_FADING
    if (
        current_score > MEANINGFUL_SCORE_THRESHOLD
        and appearances_in_window >= RECURRING_APPEARANCES
        and streak_length < appearances_in_window
    ):
        return STATE_RECURRING
    if current_score > MEANINGFUL_SCORE_THRESHOLD and trend == TREND_RE_ACCELERATING:
        return STATE_RE_ACCELERATING
    if appearances_in_window > 0 and current_score <= MEANINGFUL_SCORE_THRESHOLD:
        return STATE_DORMANT
    if current_score > MEANINGFUL_SCORE_THRESHOLD:
        return STATE_EMERGING
    return STATE_ABSENT


def compute_narrative_streak(score_history: Iterable[float]) -> int:
    streak = 0
    for score in reversed(list(score_history)):
        if score > MEANINGFUL_SCORE_THRESHOLD:
            streak += 1
        else:
            break
    return streak


def compute_rank_changes(
    current_ranks: dict[str, int],
    previous_ranks: dict[str, int],
    narrative: str,
) -> dict:
    latest_rank = current_ranks.get(narrative)
    previous_rank = previous_ranks.get(narrative)
    rank_delta = None
    if latest_rank is not None and previous_rank is not None:
        rank_delta = previous_rank - latest_rank
    return {
        "latest_rank": latest_rank,
        "previous_rank": previous_rank,
        "rank_delta": rank_delta,
    }


def summarize_memory(themes: list[dict], groups: list[dict], warnings: list[str] | None = None) -> dict:
    records = themes + groups
    latest_dominant = next(
        (record for record in records if record.get("memory_state") == STATE_DOMINANT),
        None,
    )
    return {
        "dominant_memory": latest_dominant,
        "persistent_narratives": _summary_names(records, STATE_PERSISTENT),
        "building_narratives": _summary_names(records, STATE_BUILDING),
        "fading_narratives": _summary_names(records, STATE_FADING),
        "recurring_narratives": _summary_names(records, STATE_RECURRING),
        "re_accelerating_narratives": _summary_names(records, STATE_RE_ACCELERATING),
        "dormant_narratives": _summary_names(records, STATE_DORMANT),
        "notable_changes": [
            record["plain_language_summary"]
            for record in records
            if record.get("memory_state")
            in {STATE_DOMINANT, STATE_BUILDING, STATE_FADING, STATE_RE_ACCELERATING}
        ][:8],
        "memory_warnings": list(warnings or []),
    }


def build_memory_warning_messages(runs: list[dict], configured_runs: int) -> list[str]:
    warnings = []
    if len(runs) < MIN_THIN_HISTORY_RUNS:
        warnings.append(
            f"Narrative memory has thin history: {len(runs)} meaningful run(s) available."
        )
    if len(runs) < configured_runs:
        warnings.append(
            f"Narrative memory used {len(runs)} of {configured_runs} configured meaningful runs."
        )
    return warnings


def _build_memory_records(runs: list[dict], level: str) -> list[dict]:
    score_key = "theme_scores" if level == "theme" else "group_scores"
    dominant_key = "dominant_theme" if level == "theme" else "dominant_group"
    names = sorted(
        {
            str(name)
            for run in runs
            for name, score in _scores(run, score_key).items()
            if _numeric(score) > MEANINGFUL_SCORE_THRESHOLD
        }
    )
    current_scores = _scores(runs[-1], score_key) if runs else {}
    previous_scores = _scores(runs[-2], score_key) if len(runs) >= 2 else {}
    current_ranks = _rank_scores(current_scores)
    previous_ranks = _rank_scores(previous_scores)
    dominance_counts = _dominance_counts(runs, dominant_key)

    records = []
    for name in names:
        score_history = [_numeric(_scores(run, score_key).get(name)) for run in runs]
        current_score = score_history[-1] if score_history else 0
        previous_score = score_history[-2] if len(score_history) >= 2 else 0
        current_total = _score_total(current_scores)
        previous_total = _score_total(previous_scores)
        current_share = current_score / current_total if current_total else 0
        previous_share = previous_score / previous_total if previous_total else 0
        rank_changes = compute_rank_changes(current_ranks, previous_ranks, name)
        appearances = sum(1 for value in score_history if value > MEANINGFUL_SCORE_THRESHOLD)
        streak_length = compute_narrative_streak(score_history)
        is_dominant = runs[-1].get(dominant_key) == name if runs else False
        state = classify_memory_state(
            is_dominant=is_dominant,
            appearances_in_window=appearances,
            runs_used=len(runs),
            streak_length=streak_length,
            current_score=current_score,
            score_history=score_history,
        )
        momentum = _momentum_label(score_history)
        record = {
            "narrative_level": level,
            "name": name,
            "current_score": _clean_number(current_score),
            "current_share": round(current_share, 4),
            "appearances_in_window": appearances,
            "dominance_count": dominance_counts.get(name, 0),
            "latest_rank": rank_changes["latest_rank"],
            "previous_rank": rank_changes["previous_rank"],
            "rank_delta": rank_changes["rank_delta"],
            "score_delta": _clean_number(current_score - previous_score),
            "share_delta": round(current_share - previous_share, 4),
            "streak_length": streak_length,
            "persistence_label": _persistence_label(appearances, len(runs), streak_length),
            "momentum_label": momentum,
            "memory_state": state,
        }
        record["plain_language_summary"] = _summary_sentence(record, len(runs))
        records.append(record)

    return sorted(
        records,
        key=lambda item: (
            _state_order(item["memory_state"]),
            item["latest_rank"] if item["latest_rank"] is not None else 999,
            -item["current_score"],
            item["name"],
        ),
    )


def _scores(run: dict, key: str) -> dict:
    scores = run.get(key)
    if key == "theme_scores" and not isinstance(scores, dict):
        scores = run.get("theme_counts")
    return scores if isinstance(scores, dict) else {}


def _is_memory_eligible_run(run) -> bool:
    if not isinstance(run, dict):
        return False
    if str(run.get("status") or "").lower() == "failed":
        return False
    if run.get("source_collection_failure"):
        return False
    return _has_narrative_data(run)


def _rank_scores(scores: dict) -> dict[str, int]:
    ranked = sorted(
        (
            (str(name), _numeric(score))
            for name, score in scores.items()
            if _numeric(score) > MEANINGFUL_SCORE_THRESHOLD
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return {name: index + 1 for index, (name, _) in enumerate(ranked)}


def _dominance_counts(runs: list[dict], key: str) -> dict[str, int]:
    counts = {}
    for run in runs:
        dominant = run.get(key)
        if dominant:
            counts[str(dominant)] = counts.get(str(dominant), 0) + 1
    return counts


def _score_total(scores: dict) -> float:
    return sum(_numeric(value) for value in scores.values() if _numeric(value) > 0)


def _numeric(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean_number(value: float):
    if float(value).is_integer():
        return int(value)
    return round(value, 4)


def _run_timestamp(run: dict) -> str | None:
    value = run.get("timestamp") or run.get("run_date") or run.get("run_id")
    return str(value) if value else None


def _most_runs_count(runs_used: int) -> int:
    if runs_used <= 0:
        return 0
    return max(1, int(runs_used * MOST_RUNS_RATIO + 0.999))


def _momentum_label(score_history: list[float]) -> str:
    trend = classify_trend(score_history)
    if trend in {TREND_BUILDING, TREND_FADING, TREND_RE_ACCELERATING, "cooling", "flat"}:
        return trend
    return "stable"


def _persistence_label(appearances: int, runs_used: int, streak_length: int) -> str:
    if appearances == 0:
        return "absent"
    if appearances >= _most_runs_count(runs_used):
        return "most runs"
    if streak_length >= PERSISTENT_STREAK_LENGTH:
        return "persistent streak"
    if appearances >= RECURRING_APPEARANCES:
        return "recurring"
    return "new"


def _summary_sentence(record: dict, runs_used: int) -> str:
    name = record["name"]
    appearances = record["appearances_in_window"]
    state = record["memory_state"]
    if state == STATE_DOMINANT:
        return (
            f"{name} has appeared in {appearances} of the last {runs_used} "
            "meaningful runs and is dominant in the latest run."
        )
    if state == STATE_PERSISTENT:
        return (
            f"{name} has appeared in {appearances} of the last {runs_used} "
            f"meaningful runs with a current streak of {record['streak_length']}."
        )
    if state == STATE_BUILDING:
        return f"{name} is building across the recent memory window."
    if state == STATE_FADING:
        return f"{name} is fading across the recent memory window."
    if state == STATE_RECURRING:
        return f"{name} has recurred after at least one gap in the memory window."
    if state == STATE_RE_ACCELERATING:
        return f"{name} is re-accelerating after a prior slowdown."
    if state == STATE_DORMANT:
        return f"{name} appeared earlier in the memory window but is absent from the latest run."
    if state == STATE_EMERGING:
        return f"{name} appears in the latest meaningful run after limited recent history."
    return f"{name} is absent from the latest meaningful run."


def _summary_names(records: list[dict], state: str) -> list[str]:
    return [record["name"] for record in records if record.get("memory_state") == state]


def _state_order(state: str) -> int:
    order = {
        STATE_DOMINANT: 0,
        STATE_PERSISTENT: 1,
        STATE_BUILDING: 2,
        STATE_FADING: 3,
        STATE_RECURRING: 4,
        STATE_RE_ACCELERATING: 5,
        STATE_DORMANT: 6,
        STATE_EMERGING: 7,
        STATE_ABSENT: 8,
    }
    return order.get(state, 99)
