from mne.market_context import classify_market_move


CONFIRMATION_GROUP = "AI / Tech Growth"
UP_MOVES = {"UP", "STRONG UP"}
DOWN_MOVES = {"DOWN", "STRONG DOWN"}
STABLE_OR_ACCELERATING = {"accelerating", "stable"}
VOL_CONTROLLED_MOVES = {"FLAT", "DOWN", "STRONG DOWN"}


def neutral_mixed(reason, confidence="Low"):
    return {
        "state": "Neutral / Mixed",
        "confidence": confidence,
        "reason": reason,
    }


def normalize_share(value):
    try:
        share = float(value)
    except (TypeError, ValueError):
        return None

    if share > 1:
        return share / 100
    return share


def get_market_move(market_snapshot, symbol):
    data = market_snapshot.get(symbol) if market_snapshot else None
    if not data:
        return "UNKNOWN"

    return classify_market_move(data.get("pct_change"))


def get_dominant_acceleration(narrative_dynamics, dominant_group):
    return (
        narrative_dynamics.get("groups", {})
        .get(dominant_group, {})
        .get("acceleration", "insufficient history")
    )


def another_major_group_is_accelerating(narrative_dynamics, dominant_group):
    for group, values in narrative_dynamics.get("groups", {}).items():
        if group != dominant_group and values.get("acceleration") == "accelerating":
            return True

    return False


def relationship_confidence(state, support_points):
    if state == "Narrative Exhaustion" and support_points >= 4:
        return "High"
    if support_points >= 3:
        return "High"
    if support_points >= 2:
        return "Moderate"
    return "Low"


def classify_narrative_market_relationship(
    current_run,
    narrative_dynamics,
    market_snapshot,
    prior_dominant_group=None,
):
    dominant_group = current_run.get("dominant_group")
    dominant_share = normalize_share(current_run.get("dominant_share"))
    concentration_gap = current_run.get("concentration_gap")

    qqq_move = get_market_move(market_snapshot, "QQQ")
    nvda_move = get_market_move(market_snapshot, "NVDA")
    vix_move = get_market_move(market_snapshot, "VIX")
    dxy_move = get_market_move(market_snapshot, "DXY")
    market_moves = {
        "QQQ": qqq_move,
        "NVDA": nvda_move,
        "VIX": vix_move,
        "DXY": dxy_move,
    }

    if (
        not dominant_group
        or dominant_share is None
        or not narrative_dynamics
        or "UNKNOWN" in market_moves.values()
    ):
        return neutral_mixed(
            "Narrative and market relationship could not be classified because one "
            "or more required current inputs are unavailable."
        )

    persistence = narrative_dynamics.get("persistence", {})
    dominant_persistence = int(persistence.get("dominant_group_runs", 0) or 0)
    crowding_risk = (
        narrative_dynamics.get("narrative_crowding", {}).get("risk", "LOW")
    )
    dominant_acceleration = get_dominant_acceleration(
        narrative_dynamics,
        dominant_group,
    )
    dominant_is_aligned = dominant_acceleration in STABLE_OR_ACCELERATING
    qqq_or_nvda_down = qqq_move in DOWN_MOVES or nvda_move in DOWN_MOVES

    if (
        crowding_risk == "HIGH"
        and dominant_persistence >= 5
        and dominant_share >= 0.50
        and qqq_or_nvda_down
    ):
        support = 3
        support += int(qqq_move in DOWN_MOVES and nvda_move in DOWN_MOVES)
        support += int(vix_move in {"UP", "STRONG UP"})
        support += int(dominant_acceleration in STABLE_OR_ACCELERATING)
        return {
            "state": "Narrative Exhaustion",
            "confidence": relationship_confidence("Narrative Exhaustion", support),
            "reason": (
                f"{dominant_group} is highly crowded and persistent, but QQQ/NVDA "
                "price action is weakening. Narrative attention remains strong "
                "while market confirmation is deteriorating."
            ),
        }

    if (
        dominant_group == CONFIRMATION_GROUP
        and dominant_is_aligned
        and qqq_or_nvda_down
    ):
        support = 2
        support += int(qqq_move in DOWN_MOVES and nvda_move in DOWN_MOVES)
        support += int(vix_move in {"UP", "STRONG UP"})
        return {
            "state": "Narrative Divergence",
            "confidence": relationship_confidence("Narrative Divergence", support),
            "reason": (
                "AI / Tech Growth remains dominant, but QQQ/NVDA price action is "
                "weakening, suggesting narrative strength is not being confirmed "
                "by market leadership."
            ),
        }

    if (
        dominant_group == CONFIRMATION_GROUP
        and dominant_is_aligned
        and qqq_move in UP_MOVES
        and nvda_move in UP_MOVES
        and vix_move in VOL_CONTROLLED_MOVES
    ):
        support = 3
        support += int(qqq_move == "STRONG UP" or nvda_move == "STRONG UP")
        support += int(dominant_share >= 0.40)
        return {
            "state": "Narrative Confirmation",
            "confidence": relationship_confidence("Narrative Confirmation", support),
            "reason": (
                "AI / Tech Growth is dominant and market confirmation is aligned "
                "through QQQ/NVDA strength with controlled volatility."
            ),
        }

    rotating_from_prior = bool(
        prior_dominant_group and prior_dominant_group != dominant_group
    )
    cooling_with_new_leadership = (
        dominant_acceleration == "cooling"
        and another_major_group_is_accelerating(narrative_dynamics, dominant_group)
    )

    if rotating_from_prior or cooling_with_new_leadership:
        support = 1
        support += int(rotating_from_prior)
        support += int(cooling_with_new_leadership)
        support += int(dominant_share < 0.50 or int(concentration_gap or 0) <= 3)

        if cooling_with_new_leadership:
            reason = (
                "Narrative leadership appears to be shifting as the dominant group "
                "cools while another group accelerates."
            )
        else:
            reason = (
                "Narrative leadership appears to be shifting because the current "
                "dominant group differs from the prior dominant group."
            )

        return {
            "state": "Narrative Rotation",
            "confidence": relationship_confidence("Narrative Rotation", support),
            "reason": reason,
        }

    return neutral_mixed(
        "Narrative and market signals are mixed, with no clear confirmation or rejection."
    )
