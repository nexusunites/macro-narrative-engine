def unavailable_positioning_environment():
    return {
        "state": "Unknown",
        "confidence": "Low",
        "reason": "No catalyst environment data available.",
    }


def classify_positioning_environment(catalyst_environment):
    if not catalyst_environment or not catalyst_environment.get("calendar_found", True):
        return unavailable_positioning_environment()

    density_score = catalyst_environment.get("density_score")
    days_to_next_red = catalyst_environment.get("days_to_next_red")

    if density_score is None:
        return unavailable_positioning_environment()

    if days_to_next_red == 0:
        return {
            "state": "Active Catalyst Positioning",
            "confidence": "High",
            "reason": (
                "A high-impact catalyst is scheduled today. Volatility and positioning "
                "adjustments may be elevated around the event window."
            ),
        }

    if density_score >= 6:
        return {
            "state": "Heavy Event Positioning",
            "confidence": "High",
            "reason": (
                "Several high-impact catalysts are clustered together. The market is "
                "likely processing a heavy information calendar."
            ),
        }

    if density_score >= 4:
        return {
            "state": "Elevated Positioning Activity",
            "confidence": "Moderate",
            "reason": (
                "Multiple important catalysts are clustered nearby. Markets may show "
                "increased positioning activity and elevated volatility expectations."
            ),
        }

    if days_to_next_red == 1:
        return {
            "state": "Pre-Catalyst Positioning",
            "confidence": "Moderate",
            "reason": (
                "A high-impact catalyst is scheduled tomorrow. Market participants may "
                "reduce risk, hedge, or position ahead of new information."
            ),
        }

    if density_score > 0:
        return {
            "state": "Light Event Positioning",
            "confidence": "Moderate",
            "reason": (
                "One lower-impact catalyst is nearby. Some positioning adjustments may "
                "occur, but event pressure is limited."
            ),
        }

    return {
        "state": "Normal Positioning Environment",
        "confidence": "Moderate",
        "reason": (
            "No major scheduled catalysts are nearby. Positioning pressure from event "
            "risk appears limited."
        ),
    }
