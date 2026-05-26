from mne.market_context import classify_market_move


def get_pct_change(market_snapshot, symbol):
    data = market_snapshot.get(symbol)
    if not data:
        return None
    return data.get("pct_change")


def is_up(move_label):
    return move_label in {"UP", "STRONG UP"}


def is_down(move_label):
    return move_label in {"DOWN", "STRONG DOWN"}


def is_flat_or_down(move_label):
    return move_label in {"FLAT", "DOWN", "STRONG DOWN"}


def scores_are_balanced(group_scores, tolerance=0.20):
    positive_scores = sorted(
        [score for score in group_scores.values() if score > 0],
        reverse=True,
    )

    if len(positive_scores) < 2:
        return False

    top = positive_scores[0]
    second = positive_scores[1]

    if top == 0:
        return False

    return (top - second) / top <= tolerance


def confidence_from_points(points):
    if points >= 3:
        return "High"
    if points == 2:
        return "Moderate"
    return "Low"


def classify_market_environment(
    theme_scores,
    group_scores,
    signals,
    market_snapshot,
    concentration,
    dominant_group,
):
    qqq_move = classify_market_move(get_pct_change(market_snapshot, "QQQ"))
    vix_move = classify_market_move(get_pct_change(market_snapshot, "VIX"))

    ai_score = theme_scores.get("ai", 0)
    energy_score = theme_scores.get("energy", 0)
    inflation_score = theme_scores.get("inflation", 0)
    macro_stress = signals.get("Macro Stress", "LOW")
    ai_strength = signals.get("AI Narrative Strength", "WEAK")
    energy_dominance = signals.get("Energy Dominance", "LOW")
    dominant_share = concentration.get("dominant_share", 0)
    concentration_gap = concentration.get("concentration_gap", 0)
    energy_group_score = group_scores.get("Energy / Commodities", 0)

    if (
        energy_group_score >= 16
        and inflation_score >= 8
        and macro_stress in {"HIGH", "ELEVATED"}
    ):
        points = 1
        points += int(energy_dominance in {"HIGH", "ELEVATED"})
        points += int(vix_move in {"UP", "STRONG UP"})
        points += int(dominant_group == "Energy / Commodities")
        return {
            "state": "Energy Shock",
            "confidence": confidence_from_points(points),
            "reason": (
                "Energy and inflation scores are elevated while macro stress remains "
                f"{macro_stress.lower()}."
            ),
        }

    if (
        vix_move == "STRONG UP"
        and is_down(qqq_move)
        and dominant_group == "Macro Pressure"
    ):
        points = 2
        points += int(macro_stress in {"HIGH", "ELEVATED"})
        points += int(dominant_share >= 0.40)
        return {
            "state": "Risk-Off",
            "confidence": confidence_from_points(points),
            "reason": (
                "VIX is strongly higher, QQQ is lower, and Macro Pressure is the "
                "dominant narrative group."
            ),
        }

    if is_up(qqq_move) and vix_move == "STRONG UP" and macro_stress == "HIGH":
        points = 2
        points += int(qqq_move == "STRONG UP")
        points += int(dominant_share >= 0.35)
        return {
            "state": "Fragile Risk-On",
            "confidence": confidence_from_points(points),
            "reason": (
                "QQQ is strongly up, but VIX is also strongly up while macro stress "
                "remains high."
            ),
        }

    if (
        dominant_group == "AI / Tech Growth"
        and ai_score >= 10
        and qqq_move == "STRONG UP"
    ):
        points = 2
        points += int(ai_strength in {"STRONG", "DOMINANT"})
        points += int(vix_move in {"FLAT", "DOWN", "STRONG DOWN"})
        points += int(dominant_share >= 0.35)
        return {
            "state": "AI Momentum",
            "confidence": confidence_from_points(points),
            "reason": (
                "AI / Tech Growth is dominant with strong AI narrative scores while "
                "QQQ remains strongly positive."
            ),
        }

    if (
        qqq_move == "STRONG UP"
        and is_flat_or_down(vix_move)
        and dominant_group == "AI / Tech Growth"
        and macro_stress == "LOW"
    ):
        points = 3
        points += int(dominant_share >= 0.40)
        return {
            "state": "Clean Risk-On",
            "confidence": confidence_from_points(points),
            "reason": (
                "QQQ is strongly higher, VIX is not rising, AI / Tech Growth is "
                "dominant, and macro stress is low."
            ),
        }

    if macro_stress == "HIGH" and (
        dominant_group == "Macro Pressure" or vix_move in {"UP", "STRONG UP"}
    ):
        points = 1
        points += int(dominant_group == "Macro Pressure")
        points += int(vix_move in {"UP", "STRONG UP"})
        points += int(not is_up(qqq_move))
        return {
            "state": "Macro Stress",
            "confidence": confidence_from_points(points),
            "reason": (
                "Macro stress is high and is confirmed by either Macro Pressure "
                "leadership or rising volatility."
            ),
        }

    if dominant_share < 0.40 and scores_are_balanced(group_scores):
        points = 1
        points += int(concentration_gap <= 3)
        points += int(qqq_move == "FLAT" or vix_move == "FLAT")
        return {
            "state": "Narrative Rotation",
            "confidence": confidence_from_points(points),
            "reason": (
                "Narrative scores are balanced and no single theme has strong "
                "concentration."
            ),
        }

    if qqq_move == "FLAT" and vix_move == "FLAT" and dominant_share < 0.45:
        return {
            "state": "Low-Conviction Chop",
            "confidence": "Low",
            "reason": (
                "QQQ and VIX are flat while narrative concentration remains muted."
            ),
        }

    return {
        "state": "Low-Conviction Chop",
        "confidence": "Low",
        "reason": (
            "Market and narrative signals are mixed, with no clear aligned regime."
        ),
    }
