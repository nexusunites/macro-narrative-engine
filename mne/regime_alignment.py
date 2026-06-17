UP_MOVES = {"UP", "STRONG UP"}
DOWN_MOVES = {"DOWN", "STRONG DOWN"}
MACRO_STRESS_LEVELS = {"HIGH", "ELEVATED"}
AI_TECH_GROUP = "AI / Tech Growth"


def clamp_score(score):
    return max(0, min(100, int(score)))


def get_state(value):
    if not value:
        return None
    return value.get("state")


def get_signal(narrative_signals, name, default=None):
    if not narrative_signals:
        return default
    return narrative_signals.get(name, default)


def classify_market_move(pct_change):
    if pct_change is None:
        return "UNKNOWN"

    if pct_change >= 1.0:
        return "STRONG UP"
    if pct_change >= 0.25:
        return "UP"
    if pct_change <= -1.0:
        return "STRONG DOWN"
    if pct_change <= -0.25:
        return "DOWN"
    return "FLAT"


def get_market_move(market_snapshot, symbol):
    data = market_snapshot.get(symbol) if market_snapshot else None
    if not data:
        return "UNKNOWN"
    return classify_market_move(data.get("pct_change"))


def dominant_is_ai_or_tech(dominant_group=None, dominant_theme=None):
    return dominant_group == AI_TECH_GROUP or dominant_theme in {
        "ai",
        "semiconductors",
        "big_tech",
    }


def is_mixed_or_choppy(state):
    if not state:
        return False
    return any(
        label in state
        for label in (
            "Low-Conviction Chop",
            "Narrative Rotation",
            "Neutral",
            "Mixed",
            "Divergence",
        )
    )


def score_narrative_market_relationship(relationship):
    state = get_state(relationship)

    if state in {"Narrative Confirmation"}:
        return 20, "Narrative and market signals are confirming each other.", True
    if state in {"Narrative Divergence", "Narrative Exhaustion"}:
        return -20, "Narrative leadership is diverging from market confirmation.", False
    if state == "Narrative Rotation":
        return -5, "Narrative leadership is rotating rather than cleanly aligned.", False
    return 0, None, None


def score_breadth_confirmation(breadth_confirmation):
    state = get_state(breadth_confirmation)

    if state == "Strong Breadth Confirmation":
        return 15, "Breadth participation is confirming the environment.", True
    if state == "Broad Risk-Off":
        return 15, "Broad selling pressure is confirming a risk-off environment.", True
    if state == "Weak Breadth":
        return -15, "Breadth is deteriorating beneath the headline environment.", False
    return 0, None, None


def score_market_environment(market_environment, narrative_relationship, macro_stress):
    market_state = get_state(market_environment)
    relationship_state = get_state(narrative_relationship)

    if market_state in {"AI Momentum", "Clean Risk-On", "Fragile Risk-On"}:
        if relationship_state == "Narrative Confirmation":
            return 10, "Risk-on market action is aligned with narrative confirmation.", True
        return 0, None, None

    if market_state in {"Risk-Off", "Macro Stress", "Energy Shock"}:
        if macro_stress in MACRO_STRESS_LEVELS:
            return 10, "Macro stress is elevated and market action is defensive.", True
        return 0, None, None

    if market_state == "Low-Conviction Chop":
        return -5, "Market action is choppy with low conviction.", False

    return 0, None, None


def score_positioning(positioning_environment, market_environment, narrative_relationship):
    positioning_state = get_state(positioning_environment)
    market_state = get_state(market_environment)
    relationship_state = get_state(narrative_relationship)

    if (
        positioning_state == "Active Catalyst Positioning"
        and market_state not in {"AI Momentum", "Clean Risk-On", "Risk-Off", "Macro Stress"}
    ):
        return 5, "Active catalyst positioning helps explain mixed or volatile action.", True

    if positioning_state == "Pre-Catalyst Positioning" and (
        market_state == "Low-Conviction Chop"
        or relationship_state == "Narrative Divergence"
    ):
        return 5, "Pre-catalyst positioning helps explain uncertainty in price action.", True

    if positioning_state == "Heavy Event Positioning" and is_mixed_or_choppy(market_state):
        return 5, "Heavy event positioning is consistent with a mixed or choppy tape.", True

    if positioning_state == "Elevated Positioning Activity" and is_mixed_or_choppy(market_state):
        return 5, "Elevated catalyst pressure helps explain mixed or choppy price action.", True

    return 0, None, None


def score_nasdaq_context(market_snapshot, macro_stress, dominant_group, dominant_theme):
    qqq_move = get_market_move(market_snapshot, "QQQ")
    nvda_move = get_market_move(market_snapshot, "NVDA")
    vix_move = get_market_move(market_snapshot, "VIX")
    ai_or_tech = dominant_is_ai_or_tech(dominant_group, dominant_theme)

    if ai_or_tech and qqq_move in UP_MOVES and nvda_move in UP_MOVES:
        return 10, "AI / Tech Growth is dominant and QQQ/NVDA are confirming.", True

    if ai_or_tech and qqq_move in DOWN_MOVES and nvda_move in DOWN_MOVES:
        return -15, "AI / Tech Growth is dominant, but QQQ/NVDA are weakening.", False

    if macro_stress in MACRO_STRESS_LEVELS and vix_move == "STRONG UP" and qqq_move in DOWN_MOVES:
        return 5, "Volatility is rising while QQQ is down, confirming a defensive setup.", True

    if ai_or_tech and vix_move == "STRONG DOWN" and qqq_move in UP_MOVES:
        return 5, "QQQ strength and falling volatility support the AI / Tech Growth tape.", True

    return 0, None, None


def state_from_score(score):
    if score >= 80:
        return "High Alignment"
    if score >= 60:
        return "Moderate Alignment"
    if score >= 40:
        return "Mixed / Low Alignment"
    if score >= 20:
        return "Conflicted Environment"
    return "Highly Conflicted Environment"


def confidence_from_score(score, contributors, missing_inputs):
    aligned_components = sum(1 for contributor in contributors if contributor["aligned"])
    conflicted_components = sum(1 for contributor in contributors if not contributor["aligned"])
    non_neutral_components = len(contributors)

    if missing_inputs >= 3 or non_neutral_components <= 1:
        return "Low"

    if score >= 75 and aligned_components >= 3:
        return "High"
    if score <= 25 and conflicted_components >= 3:
        return "High"

    if 40 <= score <= 74 or non_neutral_components >= 2:
        return "Moderate"

    return "Low"


def _market_move_label(move, up_text, down_text, flat_text=None):
    if move in UP_MOVES:
        return up_text
    if move in DOWN_MOVES:
        return down_text
    if move == "FLAT" and flat_text:
        return flat_text
    return None


def _add_reason_factor(factors, priority, strength, text, aligned=None):
    if not text:
        return

    factors.append(
        {
            "priority": priority,
            "strength": abs(strength),
            "text": text,
            "aligned": aligned,
        }
    )


def _extract_reason_factors(
    contributors,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    market_snapshot,
    macro_stress,
    dominant_group,
    dominant_theme,
):
    factors = []
    contributor_strength = {
        contributor["reason"]: abs(contributor["points"]) for contributor in contributors
    }
    relationship_state = get_state(narrative_market_relationship)
    breadth_state = get_state(breadth_confirmation)
    catalyst_state = get_state(catalyst_environment)
    positioning_state = get_state(positioning_environment)
    qqq_move = get_market_move(market_snapshot, "QQQ")
    nvda_move = get_market_move(market_snapshot, "NVDA")
    vix_move = get_market_move(market_snapshot, "VIX")
    ai_or_tech = dominant_is_ai_or_tech(dominant_group, dominant_theme)

    relationship_text = None
    relationship_strength = 0
    relationship_aligned = None
    if relationship_state == "Narrative Confirmation":
        if ai_or_tech:
            relationship_text = "AI / Tech Growth is dominant and price action is confirming"
        else:
            relationship_text = "narratives and price action are confirming"
        relationship_strength = 20
        relationship_aligned = True
    elif relationship_state in {"Narrative Divergence", "Narrative Exhaustion"}:
        if ai_or_tech:
            relationship_text = "AI / Tech Growth remains dominant but price action is not confirming"
        elif dominant_group == "Macro Pressure" and macro_stress in MACRO_STRESS_LEVELS:
            relationship_text = "macro stress is elevated and price action is weakening"
        else:
            relationship_text = "narrative strength is not being confirmed by price action"
        relationship_strength = 20
        relationship_aligned = False
    elif relationship_state == "Narrative Rotation":
        relationship_text = "narrative leadership is rotating"
        relationship_strength = 5
        relationship_aligned = False
    elif is_mixed_or_choppy(relationship_state):
        relationship_text = "narrative confirmation is limited"
        relationship_strength = 4
        relationship_aligned = False
    _add_reason_factor(
        factors,
        1,
        relationship_strength,
        relationship_text,
        relationship_aligned,
    )

    relationship_covers_group = (
        ai_or_tech
        and relationship_state in {"Narrative Confirmation", "Narrative Divergence", "Narrative Exhaustion"}
    ) or (
        dominant_group == "Macro Pressure"
        and relationship_state in {"Narrative Divergence", "Narrative Exhaustion"}
        and macro_stress in MACRO_STRESS_LEVELS
    )
    if dominant_group and not relationship_covers_group:
        group_strength = 8
        if ai_or_tech:
            group_text = "AI / Tech Growth remains dominant"
        else:
            group_text = f"{dominant_group} is leading the narrative tape"
        _add_reason_factor(factors, 2, group_strength, group_text, True)

    qqq_nvda_text = None
    qqq_nvda_strength = 0
    qqq_nvda_aligned = None
    if qqq_move in UP_MOVES and nvda_move in UP_MOVES:
        qqq_nvda_text = "QQQ/NVDA are confirming"
        qqq_nvda_strength = 10
        qqq_nvda_aligned = True
    elif qqq_move in DOWN_MOVES and nvda_move in DOWN_MOVES:
        qqq_nvda_text = "QQQ/NVDA are weakening"
        qqq_nvda_strength = 15
        qqq_nvda_aligned = False
    elif ai_or_tech and qqq_move in UP_MOVES and nvda_move not in UP_MOVES:
        qqq_nvda_text = "NVDA is not confirming QQQ strength"
        qqq_nvda_strength = 12
        qqq_nvda_aligned = False
    elif ai_or_tech and nvda_move in UP_MOVES and qqq_move not in UP_MOVES:
        qqq_nvda_text = "QQQ is not confirming NVDA strength"
        qqq_nvda_strength = 12
        qqq_nvda_aligned = False
    elif qqq_move in DOWN_MOVES or nvda_move in DOWN_MOVES:
        qqq_nvda_text = "Nasdaq leadership is uneven"
        qqq_nvda_strength = 7
        qqq_nvda_aligned = False
    _add_reason_factor(factors, 3, qqq_nvda_strength, qqq_nvda_text, qqq_nvda_aligned)

    vix_text = _market_move_label(
        vix_move,
        "VIX is rising",
        "VIX is falling",
        "VIX is stable",
    )
    if vix_text:
        vix_strength = 11 if vix_move in {"STRONG UP", "STRONG DOWN"} else 5
        _add_reason_factor(factors, 4, vix_strength, vix_text, vix_move != "STRONG UP")

    if relationship_covers_group:
        pass
    elif macro_stress in MACRO_STRESS_LEVELS:
        stress_text = f"macro stress is {macro_stress.lower()}"
        _add_reason_factor(factors, 5, 10, stress_text, False)
    elif macro_stress == "LOW":
        _add_reason_factor(factors, 5, 5, "macro stress is low", True)

    breadth_text = None
    breadth_strength = contributor_strength.get(
        "Breadth participation is confirming the environment.",
        0,
    )
    breadth_aligned = None
    if breadth_state == "Strong Breadth Confirmation":
        breadth_text = "breadth participation remains supportive"
        breadth_strength = max(breadth_strength, 15)
        breadth_aligned = True
    elif breadth_state == "Broad Risk-Off":
        breadth_text = "broad selling pressure confirms the defensive tone"
        breadth_strength = max(breadth_strength, 15)
        breadth_aligned = True
    elif breadth_state == "Weak Breadth":
        breadth_text = "breadth is deteriorating"
        breadth_strength = max(breadth_strength, 15)
        breadth_aligned = False
    _add_reason_factor(factors, 6, breadth_strength, breadth_text, breadth_aligned)

    days_to_next_red = (
        catalyst_environment.get("days_to_next_red") if catalyst_environment else None
    )
    density_score = catalyst_environment.get("density_score") if catalyst_environment else None
    density_state = catalyst_environment.get("density_state") if catalyst_environment else None
    catalyst_text = None
    catalyst_strength = 0
    if days_to_next_red == 0:
        catalyst_text = "a high-impact catalyst is scheduled today"
        catalyst_strength = 10
    elif days_to_next_red == 1:
        catalyst_text = "a high-impact catalyst is scheduled tomorrow"
        catalyst_strength = 7
    elif catalyst_state in {"Heavy", "Elevated"} or density_state in {"Heavy", "Elevated"}:
        catalyst_text = "the catalyst calendar is heavy"
        catalyst_strength = 7
    elif density_score and density_score > 0:
        catalyst_text = "event pressure is present but limited"
        catalyst_strength = 4
    _add_reason_factor(factors, 7, catalyst_strength, catalyst_text, False)

    positioning_text = None
    positioning_strength = 0
    if positioning_state == "Active Catalyst Positioning":
        positioning_text = "positioning activity is elevated around the event window"
        positioning_strength = 8
    elif positioning_state == "Pre-Catalyst Positioning":
        positioning_text = "pre-catalyst positioning is active"
        positioning_strength = 6
    elif positioning_state in {"Heavy Event Positioning", "Elevated Positioning Activity"}:
        positioning_text = "positioning activity is elevated"
        positioning_strength = 6
    _add_reason_factor(factors, 8, positioning_strength, positioning_text, False)

    return factors


def _rank_reason_factors(factors):
    deduped = {}
    for factor in factors:
        current = deduped.get(factor["text"])
        if not current or (
            factor["strength"],
            -factor["priority"],
        ) > (
            current["strength"],
            -current["priority"],
        ):
            deduped[factor["text"]] = factor

    return sorted(
        deduped.values(),
        key=lambda factor: (-factor["strength"], factor["priority"]),
    )


def _build_reason(factors):
    if not factors:
        return (
            "Major inputs are mostly neutral or unavailable, so regime alignment is "
            "low-confidence and mixed."
        )

    selected = sorted(factors[:4], key=lambda factor: factor["priority"])
    clauses = [factor["text"] for factor in selected]
    alignments = [factor["aligned"] for factor in selected if factor["aligned"] is not None]
    has_positive = any(alignments)
    has_negative = any(aligned is False for aligned in alignments)
    connector = "but" if has_positive and has_negative else "and"

    def sentence_case(text):
        return text[:1].upper() + text[1:] if text else text

    def join_clauses(items):
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return f"{', '.join(items[:-1])}, and {items[-1]}"

    if len(clauses) == 1:
        return sentence_case(clauses[0]) + "."
    if len(clauses) == 2:
        return f"{sentence_case(clauses[0])}, {connector} {clauses[1]}."
    if connector == "but":
        if len(clauses) == 3:
            return f"{sentence_case(clauses[0])}; {join_clauses(clauses[1:])}."

        first_sentence = f"{sentence_case(clauses[0])}; {join_clauses(clauses[1:3])}."
        return f"{first_sentence} {sentence_case(clauses[3])}."

    if len(clauses) == 3:
        return f"{sentence_case(clauses[0])}; {join_clauses(clauses[1:])}."

    return f"{sentence_case(clauses[0])}; {join_clauses(clauses[1:3])}. {sentence_case(clauses[3])}."


def reason_from_contributors(
    contributors,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    market_snapshot,
    macro_stress,
    dominant_group,
    dominant_theme,
):
    factors = _extract_reason_factors(
        contributors,
        narrative_market_relationship,
        breadth_confirmation,
        catalyst_environment,
        positioning_environment,
        market_snapshot,
        macro_stress,
        dominant_group,
        dominant_theme,
    )
    return _build_reason(_rank_reason_factors(factors))


def calculate_regime_alignment(
    narrative_signals,
    market_environment,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    market_snapshot,
    dominant_group=None,
    dominant_theme=None,
):
    macro_stress = get_signal(narrative_signals, "Macro Stress", "LOW")
    score = 50
    contributors = []
    missing_inputs = sum(
        int(not value)
        for value in (
            narrative_signals,
            market_environment,
            narrative_market_relationship,
            breadth_confirmation,
            catalyst_environment,
            positioning_environment,
            market_snapshot,
        )
    )

    scoring_steps = [
        score_narrative_market_relationship(narrative_market_relationship),
        score_breadth_confirmation(breadth_confirmation),
        score_market_environment(
            market_environment,
            narrative_market_relationship,
            macro_stress,
        ),
        score_positioning(
            positioning_environment,
            market_environment,
            narrative_market_relationship,
        ),
        score_nasdaq_context(
            market_snapshot,
            macro_stress,
            dominant_group,
            dominant_theme,
        ),
    ]

    for points, reason, aligned in scoring_steps:
        score += points
        if reason:
            contributors.append(
                {
                    "points": points,
                    "reason": reason,
                    "aligned": bool(aligned),
                }
            )

    score = clamp_score(score)

    return {
        "score": score,
        "state": state_from_score(score),
        "confidence": confidence_from_score(score, contributors, missing_inputs),
        "reason": reason_from_contributors(
            contributors,
            narrative_market_relationship,
            breadth_confirmation,
            catalyst_environment,
            positioning_environment,
            market_snapshot,
            macro_stress,
            dominant_group,
            dominant_theme,
        ),
    }
