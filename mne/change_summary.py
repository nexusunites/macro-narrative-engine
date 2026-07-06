SCORE_DELTA_THRESHOLD = 2
SHARE_DELTA_THRESHOLD = 0.03
REGIME_SCORE_DELTA_THRESHOLD = 5


def _numeric_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_share(value):
    number = _numeric_or_none(value)
    if number is None:
        return None
    if number > 1:
        return number / 100
    return number


def _display_state(value):
    if not value:
        return "Unavailable"
    return str(value).replace("_", " ").replace("-", " ").title()


def _format_score(value):
    number = _numeric_or_none(value)
    if number is None:
        return "Unavailable"
    if number.is_integer():
        return str(int(number))
    return str(round(number, 1))


def _format_share(value):
    if value is None:
        return "Unavailable"
    return f"{value * 100:.1f}%"


def _add_change(changes, category, text, importance=1):
    changes.setdefault(category, []).append(
        {
            "text": text,
            "importance": importance,
        }
    )


def _add_score_changes(changes, category, previous_scores, current_scores):
    if not isinstance(previous_scores, dict) or not isinstance(current_scores, dict):
        return

    names = sorted(set(previous_scores) | set(current_scores))
    for name in names:
        previous = _numeric_or_none(previous_scores.get(name)) or 0
        current = _numeric_or_none(current_scores.get(name)) or 0
        delta = current - previous
        if abs(delta) >= SCORE_DELTA_THRESHOLD:
            direction = "strengthened" if delta > 0 else "weakened"
            _add_change(
                changes,
                category,
                (
                    f"{_display_state(name)} {direction}: "
                    f"{_format_score(previous)} -> {_format_score(current)}."
                ),
                abs(delta),
            )


def _get_nested(run, *keys):
    current = run
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _add_state_change(changes, category, label, previous, current):
    if previous and current and previous != current:
        _add_change(
            changes,
            category,
            f"{label} shifted: {_display_state(previous)} -> {_display_state(current)}.",
            5,
        )


def build_change_summary(current_run, prior_run=None, compared_with=None):
    changes = {
        "major": [],
        "narratives": [],
        "market": [],
        "catalysts": [],
    }

    if not isinstance(prior_run, dict):
        return {
            "compared_with": compared_with or "No prior run",
            "changes": changes,
            "has_changes": False,
        }

    previous_group = prior_run.get("dominant_group")
    current_group = current_run.get("dominant_group")
    if previous_group and current_group and previous_group != current_group:
        _add_change(
            changes,
            "major",
            f"{current_group} took leadership from {previous_group}.",
            10,
        )

    previous_theme = prior_run.get("dominant_theme")
    current_theme = current_run.get("dominant_theme")
    if previous_theme and current_theme and previous_theme != current_theme:
        _add_change(
            changes,
            "major",
            (
                "Dominant theme shifted from "
                f"{_display_state(previous_theme)} to {_display_state(current_theme)}."
            ),
            8,
        )

    _add_score_changes(
        changes,
        "narratives",
        prior_run.get("theme_scores") or prior_run.get("theme_counts"),
        current_run.get("theme_scores") or current_run.get("theme_counts"),
    )
    _add_score_changes(
        changes,
        "narratives",
        prior_run.get("group_scores"),
        current_run.get("group_scores"),
    )

    previous_share = _normalize_share(prior_run.get("dominant_share"))
    current_share = _normalize_share(current_run.get("dominant_share"))
    if previous_share is not None and current_share is not None:
        share_delta = current_share - previous_share
        if abs(share_delta) >= SHARE_DELTA_THRESHOLD:
            direction = "strengthened" if share_delta > 0 else "weakened"
            _add_change(
                changes,
                "narratives",
                (
                    f"Dominant share {direction}: "
                    f"{_format_share(previous_share)} -> {_format_share(current_share)}."
                ),
                abs(share_delta) * 100,
            )

    previous_gap = _numeric_or_none(prior_run.get("concentration_gap"))
    current_gap = _numeric_or_none(current_run.get("concentration_gap"))
    if previous_gap is not None and current_gap is not None:
        gap_delta = current_gap - previous_gap
        if abs(gap_delta) >= SCORE_DELTA_THRESHOLD:
            direction = "widened" if gap_delta > 0 else "narrowed"
            _add_change(
                changes,
                "narratives",
                (
                    f"Concentration gap {direction}: "
                    f"{_format_score(previous_gap)} -> {_format_score(current_gap)}."
                ),
                abs(gap_delta),
            )

    state_fields = (
        ("market", "Market Environment", ("market_environment", "state")),
        (
            "market",
            "Narrative / Market Relationship",
            ("narrative_market_relationship", "state"),
        ),
        ("market", "Breadth", ("breadth_confirmation", "state")),
        ("catalysts", "Catalyst Environment", ("catalyst_environment", "state")),
        ("catalysts", "Positioning", ("positioning_environment", "state")),
    )
    for category, label, keys in state_fields:
        _add_state_change(
            changes,
            category,
            label,
            _get_nested(prior_run, *keys),
            _get_nested(current_run, *keys),
        )

    previous_regime = _numeric_or_none(_get_nested(prior_run, "regime_alignment", "score"))
    current_regime = _numeric_or_none(_get_nested(current_run, "regime_alignment", "score"))
    if previous_regime is not None and current_regime is not None:
        regime_delta = current_regime - previous_regime
        if abs(regime_delta) >= REGIME_SCORE_DELTA_THRESHOLD:
            direction = "strengthened" if regime_delta > 0 else "weakened"
            _add_change(
                changes,
                "market",
                (
                    f"Regime Alignment {direction}: "
                    f"{_format_score(previous_regime)} -> {_format_score(current_regime)}."
                ),
                abs(regime_delta),
            )

    _add_state_change(
        changes,
        "market",
        "Regime Alignment",
        _get_nested(prior_run, "regime_alignment", "state"),
        _get_nested(current_run, "regime_alignment", "state"),
    )

    for category in changes:
        changes[category] = sorted(
            changes[category],
            key=lambda item: item["importance"],
            reverse=True,
        )[:5]

    return {
        "compared_with": compared_with or str(prior_run.get("timestamp") or "Prior run"),
        "changes": changes,
        "has_changes": any(changes[category] for category in changes),
    }
