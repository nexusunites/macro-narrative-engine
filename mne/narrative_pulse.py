from mne.narrative_signals import NARRATIVE_GROUPS


ACCELERATION_POINTS = {
    "accelerating": 5,
    "stable": 3,
    "cooling": 1,
}

PULSE_THRESHOLDS = (
    (70, "Dominant"),
    (50, "Strong"),
    (30, "Building"),
    (15, "Emerging"),
    (0, "Dormant"),
)


def _numeric(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_pct(value):
    return f"{value * 100:.1f}%"


def _classify_state(strength_index):
    for threshold, state in PULSE_THRESHOLDS:
        if strength_index >= threshold:
            return state
    return "Dormant"


def _confidence(state, share, persistence_runs, current_score):
    if current_score <= 0 and share <= 0:
        return "High"
    if state in {"Strong", "Dominant"} and (share >= 0.30 or persistence_runs >= 3):
        return "High"
    if share >= 0.10 or persistence_runs >= 1:
        return "Medium"
    return "Low"


def _reason(group, state, share, persistence_runs, current_score, acceleration):
    if state == "Dormant":
        return f"{group} has little current narrative presence in this run."

    parts = [
        f"{group} controls {_fmt_pct(share)} of narrative group share",
        f"with a current group score of {current_score:g}",
    ]

    if persistence_runs > 0:
        parts.append(f"and has led for {persistence_runs} consecutive runs")
    else:
        parts.append("with no current leadership persistence")

    if acceleration in ACCELERATION_POINTS:
        parts.append(f"while acceleration is {acceleration}")

    return " ".join(parts) + "."


def calculate_narrative_pulse(
    current_run,
    narrative_dynamics=None,
    narrative_groups=None,
):
    """Classify narrative strength for narrative groups using existing outputs.

    Pulse is intentionally separate from acceleration, crowding, and direction. The
    strength index weights narrative group share and leadership persistence most
    heavily, with current score and acceleration as smaller secondary inputs.
    """
    narrative_dynamics = narrative_dynamics or {}
    group_scores = current_run.get("group_scores") or {}
    dynamics_groups = narrative_dynamics.get("groups") or {}
    persistence = narrative_dynamics.get("persistence") or {}
    narrative_groups = narrative_groups or NARRATIVE_GROUPS.keys()

    groups = set(narrative_groups)
    groups.update(group_scores.keys())
    groups.update(dynamics_groups.keys())
    if persistence.get("dominant_group"):
        groups.add(persistence["dominant_group"])

    total_group_score = sum(_numeric(score) for score in group_scores.values())
    dominant_group = persistence.get("dominant_group")
    dominant_group_runs = int(_numeric(persistence.get("dominant_group_runs"), 0))

    pulse = {}
    for group in sorted(groups):
        current_score = _numeric(group_scores.get(group))
        share = current_score / total_group_score if total_group_score > 0 else 0.0
        dynamics = dynamics_groups.get(group) or {}
        acceleration = dynamics.get("acceleration", "insufficient history")
        persistence_runs = dominant_group_runs if group == dominant_group else 0

        share_points = min(60.0, share * 120.0)
        persistence_points = min(30.0, persistence_runs * 5.0)
        score_points = min(5.0, current_score / 4.0)
        acceleration_points = ACCELERATION_POINTS.get(acceleration, 0)
        strength_index = round(
            share_points + persistence_points + score_points + acceleration_points,
            1,
        )

        state = _classify_state(strength_index)
        pulse[group] = {
            "pulse_state": state,
            "confidence": _confidence(state, share, persistence_runs, current_score),
            "reason": _reason(
                group,
                state,
                share,
                persistence_runs,
                current_score,
                acceleration,
            ),
            "strength_index": strength_index,
            "inputs": {
                "narrative_share": round(share, 4),
                "persistence_runs": persistence_runs,
                "current_score": current_score,
                "acceleration": acceleration,
            },
        }

    return pulse
