from pathlib import Path

from mne.narrative_signals import compute_group_scores
from mne.storage import load_json

NARRATIVE_CROWDING_NOTE = (
    "This measures narrative attention crowding, not actual market positioning."
)


def get_theme_scores(run):
    return run.get("theme_scores") or run.get("theme_counts", {})


def get_group_scores(run):
    if run.get("group_scores"):
        return run["group_scores"]

    return compute_group_scores(get_theme_scores(run))


def average(values):
    if not values:
        return 0.0

    return round(sum(values) / len(values), 1)


def classify_acceleration(values):
    if len(values) < 3:
        return "insufficient history"

    latest_change = values[-1] - values[-2]
    previous_change = values[-2] - values[-3]

    if latest_change > previous_change:
        return "accelerating"
    if latest_change < previous_change:
        return "cooling"
    return "stable"


def classify_decay(values):
    if len(values) < 3:
        return "insufficient history"

    if values[-1] < values[-2] and values[-2] < values[-3]:
        return "ACTIVE"

    return "NONE"


def load_recent_runs(results_dir=Path("data/results"), lookback=5):
    files = sorted(Path(results_dir).glob("*.json"))
    return [load_json(file) for file in files[-lookback:]]


def build_history(runs, score_getter, names):
    history = {name: [] for name in names}

    for run in runs:
        scores = score_getter(run)
        for name in names:
            history[name].append(scores.get(name, 0))

    return history


def summarize_history(history):
    summaries = {}

    for name, values in history.items():
        summaries[name] = {
            "current_score": values[-1] if values else 0,
            "rolling_avg_3": average(values[-3:]),
            "rolling_avg_5": average(values[-5:]),
            "acceleration": classify_acceleration(values),
            "decay": classify_decay(values),
        }

    return summaries


def count_persistence(runs, key, value):
    if not value:
        return 0

    count = 0

    for run in reversed(runs):
        if run.get(key) == value:
            count += 1
        else:
            break

    return count


def calculate_narrative_crowding(current_run, dynamics, dominant_group_runs):
    dominant_group = current_run.get("dominant_group")
    dominant_theme = current_run.get("dominant_theme")
    dominant_share = float(current_run.get("dominant_share", 0))
    concentration_gap = int(current_run.get("concentration_gap", 0))

    group_acceleration = dynamics.get("groups", {}).get(dominant_group, {}).get(
        "acceleration",
        "insufficient history",
    )
    theme_acceleration = dynamics.get("themes", {}).get(dominant_theme, {}).get(
        "acceleration",
        "insufficient history",
    )
    acceleration = group_acceleration
    if acceleration == "insufficient history":
        acceleration = theme_acceleration

    if (
        dominant_share >= 0.50
        and dominant_group_runs >= 3
        and acceleration in {"accelerating", "stable"}
    ):
        risk = "HIGH"
    elif dominant_share >= 0.35 and dominant_group_runs >= 2:
        risk = "MODERATE"
    else:
        risk = "LOW"

    reason = (
        f"{dominant_group} remains dominant with a {dominant_share * 100:.1f}% share "
        f"and {dominant_group_runs}-run persistence."
    )

    if concentration_gap > 0:
        reason += f" Theme concentration gap is {concentration_gap}."

    return {
        "risk": risk,
        "reason": reason,
        "note": NARRATIVE_CROWDING_NOTE,
    }


def calculate_narrative_dynamics(
    results_dir=Path("data/results"),
    current_run=None,
    top_themes=None,
    top_groups=None,
    lookback=5,
):
    runs = load_recent_runs(results_dir, lookback)

    if current_run is not None:
        runs = runs + [current_run]

    if not runs:
        return {
            "themes": {},
            "groups": {},
            "persistence": {
                "dominant_theme": None,
                "dominant_theme_runs": 0,
                "dominant_group": None,
                "dominant_group_runs": 0,
            },
            "narrative_crowding": {
                "risk": "LOW",
                "reason": "Not enough narrative history is available.",
                "note": NARRATIVE_CROWDING_NOTE,
            },
        }

    current = runs[-1]
    top_themes = top_themes or []
    top_groups = top_groups or []

    theme_names = [theme for theme, _ in top_themes[:3]]
    group_names = [group for group, _ in top_groups[:3]]

    dominant_theme = current.get("dominant_theme")
    dominant_group = current.get("dominant_group")

    if dominant_theme and dominant_theme not in theme_names:
        theme_names.append(dominant_theme)
    if dominant_group and dominant_group not in group_names:
        group_names.append(dominant_group)

    dynamics = {
        "themes": summarize_history(build_history(runs, get_theme_scores, theme_names)),
        "groups": summarize_history(build_history(runs, get_group_scores, group_names)),
        "persistence": {
            "dominant_theme": dominant_theme,
            "dominant_theme_runs": count_persistence(runs, "dominant_theme", dominant_theme),
            "dominant_group": dominant_group,
            "dominant_group_runs": count_persistence(runs, "dominant_group", dominant_group),
        },
    }

    dynamics["narrative_crowding"] = calculate_narrative_crowding(
        current,
        dynamics,
        dynamics["persistence"]["dominant_group_runs"],
    )

    return dynamics
