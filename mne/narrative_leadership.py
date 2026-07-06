def _numeric(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_score(value):
    number = _numeric(value)
    if number.is_integer():
        return int(number)
    return round(number, 1)


def build_narrative_leadership(group_scores, narrative_pulse=None, dynamics=None, limit=3):
    if not isinstance(group_scores, dict) or not group_scores:
        return {
            "leaders": [],
            "dominant_group": None,
        }

    narrative_pulse = narrative_pulse if isinstance(narrative_pulse, dict) else {}
    dynamics = dynamics if isinstance(dynamics, dict) else {}
    dynamic_groups = dynamics.get("groups") if isinstance(dynamics.get("groups"), dict) else {}
    persistence = dynamics.get("persistence") if isinstance(dynamics.get("persistence"), dict) else {}
    sorted_groups = sorted(
        group_scores.items(),
        key=lambda item: _numeric(item[1]),
        reverse=True,
    )[:limit]

    leaders = []
    leader_score = _numeric(sorted_groups[0][1]) if sorted_groups else 0.0
    for index, (group, score) in enumerate(sorted_groups, start=1):
        pulse = narrative_pulse.get(group) if isinstance(narrative_pulse.get(group), dict) else {}
        group_dynamics = dynamic_groups.get(group) if isinstance(dynamic_groups.get(group), dict) else {}
        numeric_score = _numeric(score)
        leaders.append(
            {
                "rank": index,
                "group": group,
                "score": _format_score(score),
                "leader_gap": _format_score(leader_score - numeric_score),
                "pulse_state": pulse.get("pulse_state"),
                "pulse_confidence": pulse.get("confidence"),
                "acceleration": group_dynamics.get("acceleration"),
            }
        )

    return {
        "leaders": leaders,
        "dominant_group": sorted_groups[0][0] if sorted_groups else None,
        "dominant_group_runs": persistence.get("dominant_group_runs"),
    }
