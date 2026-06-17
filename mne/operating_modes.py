from mne.market_context import classify_market_move


VALID_MODES = {"macro", "nasdaq"}
AI_TECH_GROUP = "AI / Tech Growth"
MACRO_STRESS_LEVELS = {"ELEVATED", "HIGH"}
UP_MOVES = {"UP", "STRONG UP"}
DOWN_MOVES = {"DOWN", "STRONG DOWN"}
VIX_SUPPORTIVE_MOVES = {"DOWN", "STRONG DOWN"}


def normalize_operating_mode(mode):
    normalized = (mode or "macro").strip().lower()
    if normalized in VALID_MODES:
        return normalized, None
    return "macro", "Unknown operating mode; defaulting to macro."


def format_operating_mode(mode):
    normalized, _ = normalize_operating_mode(mode)
    return normalized.capitalize()


def get_move(market_snapshot, symbol):
    data = market_snapshot.get(symbol) if market_snapshot else None
    if not data:
        return "UNKNOWN"
    return classify_market_move(data.get("pct_change"))


def get_state(value):
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get("state") or ""
    return str(value)


def macro_stress_level(narrative_signals):
    if not narrative_signals:
        return "LOW"
    return narrative_signals.get("Macro Stress", "LOW")


def has_catalyst_positioning(positioning_environment):
    state = get_state(positioning_environment)
    return "Pre-Catalyst" in state or "Active Catalyst" in state


def generate_macro_context(
    dominant_theme,
    dominant_group,
    narrative_signals,
    market_environment,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    regime_alignment,
    market_snapshot,
):
    group_text = dominant_group or "No dominant narrative group is active"
    market_state = get_state(market_environment) or "market confirmation is unclear"
    breadth_state = get_state(breadth_confirmation) or "breadth is unclear"

    if dominant_group:
        subject = f"{group_text} is the dominant narrative group"
    else:
        subject = group_text

    return {
        "mode": "macro",
        "state": "Broad Macro Read",
        "confidence": "Moderate",
        "read": (
            f"{subject}, while market context is {market_state.lower()} "
            f"and breadth is {breadth_state.lower()}."
        ),
    }


def generate_nasdaq_context(
    dominant_theme,
    dominant_group,
    narrative_signals,
    market_environment,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    regime_alignment,
    market_snapshot,
):
    qqq_move = get_move(market_snapshot, "QQQ")
    nvda_move = get_move(market_snapshot, "NVDA")
    vix_move = get_move(market_snapshot, "VIX")
    dxy_move = get_move(market_snapshot, "DXY")
    macro_stress = macro_stress_level(narrative_signals)
    qqq_strong = qqq_move in UP_MOVES
    nvda_strong = nvda_move in UP_MOVES
    qqq_weak = qqq_move in DOWN_MOVES
    nvda_weak = nvda_move in DOWN_MOVES
    ai_dominant = dominant_group == AI_TECH_GROUP
    catalyst_positioning = has_catalyst_positioning(positioning_environment)
    breadth_state = get_state(breadth_confirmation)
    regime_state = get_state(regime_alignment)

    if macro_stress in MACRO_STRESS_LEVELS and (qqq_weak or nvda_weak):
        state = "Nasdaq Macro Pressure"
        confidence = "Moderate"
        read = (
            "Macro Pressure is elevated, creating a potential headwind for Nasdaq "
            "risk appetite through rates, inflation, or recession concerns."
        )
    elif catalyst_positioning and not (qqq_strong and nvda_strong):
        state = "Nasdaq Pre-Catalyst Chop"
        confidence = "Moderate"
        read = (
            "A high-impact catalyst is approaching, which may keep Nasdaq positioning "
            "cautious. QQQ/NVDA confirmation is limited."
        )
    elif ai_dominant and qqq_strong and nvda_strong and vix_move in VIX_SUPPORTIVE_MOVES:
        state = "Nasdaq Risk-On Confirmation"
        confidence = "High"
        breadth_text = (
            " and breadth supportive"
            if "strong" in breadth_state.lower() or "confirmation" in breadth_state.lower()
            else ""
        )
        read = (
            "AI / Tech Growth is dominant while QQQ and NVDA are confirming strength, "
            f"with VIX lower{breadth_text}."
        )
    elif ai_dominant and (qqq_weak or nvda_weak or (qqq_strong and not nvda_strong)):
        state = "Nasdaq Divergence"
        confidence = "High"
        volatility_text = "and VIX is rising" if vix_move in {"UP", "STRONG UP"} else "and volatility confirmation is limited"
        confirmation_text = (
            "NVDA is not confirming"
            if qqq_strong and not nvda_strong
            else "QQQ/NVDA confirmation is weak"
        )
        read = (
            f"AI / Tech Growth remains dominant, but {confirmation_text} "
            f"{volatility_text}. Nasdaq conditions are mixed despite strong AI "
            "narrative attention."
        )
    else:
        state = "Nasdaq Mixed Conditions"
        confidence = "Moderate"
        read = (
            "Nasdaq inputs are mixed across AI narrative leadership, QQQ/NVDA price "
            "confirmation, volatility, macro stress, and regime alignment."
        )

    details = []
    if catalyst_positioning and "catalyst" not in read.lower():
        details.append("Catalyst positioning remains relevant.")
    if dxy_move in {"UP", "STRONG UP"}:
        details.append("DXY strength may pressure growth risk appetite.")
    if regime_state and "regime" not in read.lower():
        details.append("Regime alignment " f"is {regime_state.lower()}.")
    if breadth_state and "breadth" not in read.lower():
        details.append(f"Breadth is {breadth_state.lower()}.")

    if details:
        read = f"{read} {details[0]}"

    return {
        "mode": "nasdaq",
        "state": state,
        "confidence": confidence,
        "read": read,
    }


def generate_mode_context(
    mode,
    dominant_theme,
    dominant_group,
    narrative_signals,
    market_environment,
    narrative_market_relationship,
    breadth_confirmation,
    catalyst_environment,
    positioning_environment,
    regime_alignment,
    market_snapshot,
):
    normalized_mode, _ = normalize_operating_mode(mode)
    kwargs = {
        "dominant_theme": dominant_theme,
        "dominant_group": dominant_group,
        "narrative_signals": narrative_signals,
        "market_environment": market_environment,
        "narrative_market_relationship": narrative_market_relationship,
        "breadth_confirmation": breadth_confirmation,
        "catalyst_environment": catalyst_environment,
        "positioning_environment": positioning_environment,
        "regime_alignment": regime_alignment,
        "market_snapshot": market_snapshot,
    }

    if normalized_mode == "nasdaq":
        return generate_nasdaq_context(**kwargs)
    return generate_macro_context(**kwargs)
