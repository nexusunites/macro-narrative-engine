def compute_narrative_concentration(nonzero_results):
    top_theme = None
    top_count = 0
    total_mentions = 0
    dominant_share = 0.0
    concentration_gap = 0

    if not nonzero_results:
        return {
            "dominant_theme": top_theme,
            "dominant_count": top_count,
            "total_mentions": total_mentions,
            "dominant_share": dominant_share,
            "concentration_gap": concentration_gap,
        }

    top_theme, top_count = nonzero_results[0]
    total_mentions = sum(count for _, count in nonzero_results)
    dominant_share = top_count / total_mentions if total_mentions > 0 else 0.0

    if len(nonzero_results) >= 2:
        _, second_count = nonzero_results[1]
        concentration_gap = top_count - second_count
    else:
        concentration_gap = top_count

    return {
        "dominant_theme": top_theme,
        "dominant_count": top_count,
        "total_mentions": total_mentions,
        "dominant_share": dominant_share,
        "concentration_gap": concentration_gap,
    }


def compute_narrative_signals(top_theme, share, concentration, results):
    signals = {}

    energy_count = results.get("energy", 0)
    ai_count = results.get("ai", 0)
    rates_count = results.get("rates", 0)
    inflation_count = results.get("inflation", 0)
    recession_count = results.get("recession", 0)

    if top_theme == "energy" and share >= 0.60 and concentration >= 15:
        signals["Energy Dominance"] = "HIGH"
    elif top_theme == "energy" and share >= 0.40:
        signals["Energy Dominance"] = "ELEVATED"
    else:
        signals["Energy Dominance"] = "LOW"

    if top_theme == "ai" and share >= 0.60:
        signals["AI Narrative Strength"] = "DOMINANT"
    elif ai_count >= 10:
        signals["AI Narrative Strength"] = "STRONG"
    elif ai_count >= 5:
        signals["AI Narrative Strength"] = "ACTIVE"
    else:
        signals["AI Narrative Strength"] = "WEAK"

    stress_score = 0

    if energy_count >= 10:
        stress_score += 1
    if rates_count >= 4:
        stress_score += 1
    if inflation_count >= 3:
        stress_score += 1
    if recession_count >= 2:
        stress_score += 1

    if stress_score >= 3:
        signals["Macro Stress"] = "HIGH"
    elif stress_score == 2:
        signals["Macro Stress"] = "ELEVATED"
    elif stress_score == 1:
        signals["Macro Stress"] = "MODERATE"
    else:
        signals["Macro Stress"] = "LOW"

    return signals
