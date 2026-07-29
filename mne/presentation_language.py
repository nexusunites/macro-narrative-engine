"""Deterministic plain-language translations for the user dashboard.

Engine vocabulary remains canonical.  This module only describes how that
vocabulary is presented on the public dashboard.
"""

from __future__ import annotations

import re
from typing import Any

from mne.narrative_signals import NARRATIVE_GROUPS


def _entry(label: str, meaning: str = "", tone: str = "neutral") -> dict[str, str]:
    return {"label": label, "meaning": meaning, "tone": tone}


METRICS = {
    "Regime Alignment": {
        "label": "Market Support",
        "question": "How supportive is the market backdrop right now?",
    },
    "Dominant Narrative": {
        "label": "Today's Top Story",
        "question": "What is the market talking about most?",
    },
    "Narrative Leadership": {
        "label": "The Stories Driving Markets",
        "question": "Which stories lead, and who's gaining or fading?",
    },
    "Narrative Pulse": {"label": "Strength", "question": None},
    "Acceleration": {"label": "Momentum", "question": None},
    "Crowding": {"label": "Attention", "question": None},
    "Market Environment": {"label": "Market Mood", "question": None},
    "Catalyst Environment": {"label": "Upcoming Events", "question": None},
    "Positioning": {"label": "Trader Behavior", "question": None},
    "Change Summary": {"label": "What Changed", "question": "Since the last update"},
    "Market Snapshot": {"label": "Markets Right Now", "question": None},
    "Example Headlines / Top Theme Evidence": {
        "label": "What We Read",
        "question": "The headlines behind today's read",
    },
    "Regime Alignment History": {"label": "Support Over Time", "question": None},
    "Data Quality": {"label": "Data Quality", "question": None},
    "Historical Snapshot": {"label": "Historical Snapshot", "question": None},
    "Historical Narrative Explanation": {"label": "Narrative Explanation", "question": None},
    "Supporting Historical Evidence": {"label": "Supporting Historical Evidence", "question": None},
    "Historical Coverage": {"label": "Coverage and Limitations", "question": None},
    "Historical Next Steps": {"label": "Where to Look Next", "question": None},
}

HISTORICAL_COPY = {
    "archive_label": "Historical Narratives",
    "archive_intro": "Browse completed reconstructions of what the available evidence showed at an earlier market cutoff.",
    "archive_empty_title": "No historical reconstructions are available yet",
    "archive_empty_body": "Historical reconstructions bring together evidence that was available by a past cutoff. Completed reconstructions will appear here.",
    "limited_badge": "Limited reconstruction",
    "evidence_singular": "piece of evidence",
    "evidence_plural": "pieces of evidence",
    "story_singular": "story",
    "story_plural": "stories",
    "historical_banner": "Historical reconstruction",
    "read_only": "Read-only",
    "not_current": "This is not current market intelligence.",
    "unavailable_title": "This historical reconstruction isn't available",
    "unavailable_body": "It may have been removed or may not contain enough information for a user-facing investigation.",
    "zero_evidence_title": "Evidence is limited for this reconstruction",
    "zero_evidence_body": "The historical snapshot is available, but no supporting evidence items were accepted for display.",
    "missing_link": "Original article unavailable",
    "read_original": "Read original →",
    "coverage_supported": "Historical coverage reflects the supported sources available for this reconstruction.",
    "coverage_incomplete": "This is not complete historical market-news coverage.",
    "coverage_cutoff": "Evidence published after the historical cutoff is excluded.",
    "breadth_explanation": "Breadth describes how much evidence was available, not whether the narrative was true or high quality.",
    "origin_historical_backfill": "From an official historical source archive",
    "origin_live_persisted": "From live news collection at the time",
    "origin_fed_fomc": "From the official Federal Reserve statement archive",
    "origin_bls_cpi": "From the official Bureau of Labor Statistics release archive",
    "origin_bea_gdp_pce": "From the official Bureau of Economic Analysis release archive",
    "origin_eia_energy": "From the official U.S. Energy Information Administration release archive",
    "origin_default": "From evidence collected by Macro Narrative Engine",
}

HISTORICAL_BREADTH = {
    "MINIMAL": _entry("Very limited coverage", "Only a small evidence base was available."),
    "NARROW": _entry("Narrow coverage", "The reconstruction draws from a limited range of evidence."),
    "MODERATE": _entry("Moderate coverage", "The reconstruction draws from a meaningful range of evidence."),
    "BROAD": _entry("Broad coverage", "The reconstruction draws from a wider range of evidence."),
    "ROBUST": _entry("Broad coverage", "The reconstruction draws from a wider range of evidence."),
}


def historical_copy(key: str) -> str:
    """Return fixed user-facing historical vocabulary."""
    return HISTORICAL_COPY[key]


def historical_breadth(value: Any) -> dict[str, Any]:
    """Translate replay coverage breadth without making a quality claim."""
    raw = "" if value in (None, "") else str(value)
    translated = HISTORICAL_BREADTH.get(raw.upper())
    if translated is None:
        return {"label": "", "meaning": "", "tone": "neutral", "raw": raw, "untranslated": bool(raw)}
    return {**translated, "raw": raw, "untranslated": False}


def historical_origin(origin: Any = None, source_id: Any = None) -> str:
    """Explain an evidence origin using a deterministic, user-safe mapping."""
    source_key = str(source_id or "").strip().lower()
    origin_key = str(origin or "").strip().lower()
    if source_key and f"origin_{source_key}" in HISTORICAL_COPY:
        return HISTORICAL_COPY[f"origin_{source_key}"]
    if origin_key and f"origin_{origin_key}" in HISTORICAL_COPY:
        return HISTORICAL_COPY[f"origin_{origin_key}"]
    return HISTORICAL_COPY["origin_default"]


STATES = {
    # Market environment.
    "Clean Risk-On": _entry(
        "Markets are confident",
        "Investors are buying broadly with little hedging.",
        "good",
    ),
    "Fragile Risk-On": _entry(
        "Confident, but on edge",
        "Markets are rising, but the gains are narrow and easily shaken.",
        "caution",
    ),
    "Risk-Off": _entry(
        "Markets are defensive",
        "Investors are pulling back toward safety.",
        "caution",
    ),
    "Macro Stress": _entry(
        "Economic worry is driving markets",
        "Big-picture concerns (rates, inflation, growth) are in control.",
        "caution",
    ),
    "Energy Shock": _entry(
        "Energy pressure is driving markets",
        "Energy and inflation concerns are dominating the market backdrop.",
        "caution",
    ),
    "AI Momentum": _entry(
        "Tech enthusiasm is leading",
        "AI and technology shares are leading a rising market.",
        "good",
    ),
    "Narrative Rotation": _entry(
        "Leadership is changing",
        "No single market story has a firm hold on attention.",
    ),
    "Low-Conviction Chop": _entry(
        "Markets are drifting",
        "Price moves and market stories are mixed, without a clear direction.",
    ),
    # Operating-mode context.
    "Broad Macro Read": _entry(
        "The big picture is in focus",
        "Broad economic and market signals are shaping today's read.",
    ),
    "Nasdaq Macro Pressure": _entry(
        "Economic pressure is weighing on tech",
        "Rates, inflation, or growth concerns are creating a headwind for technology shares.",
        "caution",
    ),
    "Nasdaq Pre-Catalyst Chop": _entry(
        "Drifting before a big event",
        "Markets are moving sideways while waiting on an upcoming event.",
    ),
    "Nasdaq Risk-On Confirmation": _entry(
        "Tech strength is confirmed",
        "Technology leadership is supported by prices and calmer volatility.",
        "good",
    ),
    "Nasdaq Divergence": _entry(
        "The signals don't agree",
        "Technology headlines and market prices are pointing in different directions.",
        "caution",
    ),
    "Nasdaq Mixed Conditions": _entry(
        "Tech signals are mixed",
        "Technology leadership, prices, volatility, and economic signals do not point one way.",
    ),
    # Positioning.
    "Active Catalyst Positioning": _entry(
        "Traders are positioning for an event",
        "An imminent event is visibly shaping trading behavior.",
    ),
    "Pre-Catalyst Positioning": _entry(
        "Getting set ahead of an event",
        "An upcoming event is starting to influence positioning.",
    ),
    "Normal Positioning Environment": _entry(
        "Nothing unusual",
        "No event is meaningfully distorting trading behavior.",
    ),
    "Heavy Event Positioning": _entry(
        "Heavy event preparation",
        "Several major events are clustered together and strongly influencing trading.",
        "caution",
    ),
    "Elevated Positioning Activity": _entry(
        "More event preparation than usual",
        "Several nearby events are influencing trading behavior.",
        "caution",
    ),
    "Light Event Positioning": _entry(
        "Some event preparation",
        "A nearby event may be influencing a limited amount of trading.",
    ),
    "Unknown": _entry(
        "Not enough information",
        "The available data cannot describe trader behavior for this run.",
        "caution",
    ),
    # Catalyst density.
    "No Scheduled Catalyst Environment": _entry(
        "Schedule unavailable",
        "Scheduled event data was not available for this run.",
        "caution",
    ),
    "Quiet": _entry("Few events ahead", "The upcoming calendar is light."),
    "Light": _entry("A few events ahead", "The upcoming calendar has limited event pressure."),
    "Elevated": _entry(
        "Several important events ahead",
        "Important events are clustered on the upcoming calendar.",
        "caution",
    ),
    "Heavy": _entry(
        "A packed event calendar",
        "Several high-impact events are clustered together.",
        "caution",
    ),
    # Pulse.
    "Pulse: Dormant": _entry("Quiet", "This story is barely present in the news."),
    "Pulse: Emerging": _entry(
        "Starting to build",
        "This story is beginning to show up consistently.",
    ),
    "Pulse: Building": _entry("Gaining traction", "Coverage is growing steadily.", "good"),
    "Pulse: Strong": _entry(
        "A major story",
        "This story commands a large share of coverage.",
        "good",
    ),
    "Pulse: Dominant": _entry(
        "The story everyone's telling",
        "This story dominates the news cycle.",
        "good",
    ),
    # Acceleration.
    "Acceleration: Accelerating": _entry("Heating up", "", "good"),
    "Acceleration: Rising": _entry("Heating up", "", "good"),
    "Acceleration: Stable": _entry("Holding steady"),
    "Acceleration: Cooling": _entry("Cooling off", "", "caution"),
    "Acceleration: Insufficient History": _entry(
        "Too new to compare",
        "There is not enough recent history to measure momentum.",
    ),
    # Crowding.
    "Crowding: Low": _entry(
        "Room to grow",
        "Attention isn't concentrated here yet.",
    ),
    "Crowding: Moderate": _entry(
        "Getting noticed",
        "A meaningful share of coverage is converging here.",
    ),
    "Crowding: High": _entry(
        "Everyone's watching",
        "Attention is heavily concentrated — crowded stories can reverse fast.",
        "caution",
    ),
    "Crowding: Unavailable": _entry(
        "Not enough information",
        "Attention concentration is not available for this story.",
    ),
    # Rotation (current engine names and canonical aliases).
    "Rotation: Dominant": _entry("Firmly in the lead", "", "good"),
    "Rotation: Holding": _entry("Holding the lead", "", "good"),
    "Rotation: Holding Leadership": _entry("Holding the lead", "", "good"),
    "Rotation: Challenged": _entry("The lead is narrowing", "", "caution"),
    "Rotation: Challenging": _entry("Closing in"),
    "Rotation: Emerging": _entry("Starting to rise", "", "good"),
    "Rotation: Losing": _entry("Fading", "", "caution"),
    "Rotation: Losing Influence": _entry("Fading", "", "caution"),
    "Rotation: Stable": _entry("Holding steady"),
    # Event lifecycle.
    "Upcoming": _entry("Coming up", "The event is scheduled but its active window has not begun."),
    "Pre-Positioning": _entry("Traders are getting ready", "Trading may be adjusting ahead of the event."),
    "Immediate Pre-Event": _entry("Starting very soon", "The event is within its immediate pre-release window."),
    "Active Release": _entry("Happening now", "New information is being released now.", "caution"),
    "Initial Digestion": _entry("Markets are reacting", "Markets are processing the new information."),
    "Narrative Repricing": _entry("The story is being reassessed", "Markets are continuing to reassess the event's implications."),
    "Complete": _entry("Finished", "The event's tracked window is complete."),
    "Unavailable": _entry("Unavailable", "This state was not available for the run."),
}


CONFIDENCE = {
    "LOW": _entry("Based on partial data", "The read has limited supporting data.", "caution"),
    "MODERATE": _entry("Based on solid data", "The read has meaningful supporting data."),
    "MEDIUM": _entry("Based on solid data", "The read has meaningful supporting data."),
    "HIGH": _entry("Based on solid data", "The read has strong supporting data.", "good"),
    "UNAVAILABLE": _entry("Data basis unavailable", "Confidence was not available for this run.", "caution"),
}


def metric(name: str) -> dict[str, Any]:
    """Return dashboard copy for a canonical metric name."""
    return METRICS.get(name, {"label": name, "question": None})


def state(value: Any, *, category: str | None = None) -> dict[str, Any]:
    """Translate a state, passing unknown values through with a review flag."""
    raw = "" if value is None else str(value)
    if not raw:
        return {**STATES["Unavailable"], "raw": raw, "untranslated": False}
    key = f"{category}: {raw.title()}" if category else raw
    translated = STATES.get(key)
    if translated is None and not category:
        translated = STATES.get(raw.title())
    if translated is None:
        return {
            "label": raw or "Unavailable",
            "meaning": "",
            "tone": "neutral",
            "raw": raw,
            "untranslated": True,
        }
    return {**translated, "raw": raw, "untranslated": False}


def confidence(value: Any) -> dict[str, Any]:
    """Translate confidence wording without changing its engine value."""
    raw = "Unavailable" if value in (None, "") else str(value)
    translated = CONFIDENCE.get(raw.upper())
    if translated is None:
        return {
            "label": raw,
            "meaning": "",
            "tone": "neutral",
            "raw": raw,
            "untranslated": True,
        }
    return {**translated, "raw": raw, "untranslated": False}


def support(score: Any, engine_state: Any = None) -> dict[str, Any]:
    """Present the score using engine truth when a translated state exists."""
    if engine_state:
        translated = state(engine_state)
        if not translated["untranslated"]:
            return translated
    try:
        number = float(score)
    except (TypeError, ValueError):
        return state(engine_state or "Unavailable")
    if number < 40:
        return {**_entry("Unsupportive", "The market backdrop offers limited support.", "caution"), "raw": str(engine_state or score), "untranslated": False}
    if number < 60:
        return {**_entry("Mixed support", "The market backdrop is giving mixed signals."), "raw": str(engine_state or score), "untranslated": False}
    if number < 80:
        return {**_entry("Supportive", "The market backdrop is generally supportive.", "good"), "raw": str(engine_state or score), "untranslated": False}
    return {**_entry("Strongly supportive", "The market backdrop is strongly supportive.", "good"), "raw": str(engine_state or score), "untranslated": False}


def compose_sentence(*parts: dict[str, Any] | None) -> str:
    """Join available translated labels as a deterministic sentence."""
    labels = [
        str(part["label"]).strip()
        for part in parts
        if part
        and str(part.get("raw", "")).strip().lower() != "unavailable"
        and str(part.get("label", "")).strip().lower() != "unavailable"
    ]
    if not labels:
        return ""
    labels = [labels[0], *(label.lower() for label in labels[1:])]
    if len(labels) == 1:
        return f"{labels[0]}."
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}."
    return f"{', '.join(labels[:-1])}, and {labels[-1]}."


def pluralize(count: Any, singular: str, plural: str | None = None) -> str:
    """Return a count with a deterministic singular/plural noun."""
    try:
        is_one = float(count) == 1
    except (TypeError, ValueError):
        is_one = False
    default_plural = (
        f"{singular[:-1]}ies"
        if singular.endswith("y") and len(singular) > 1 and singular[-2].lower() not in "aeiou"
        else f"{singular}s"
    )
    noun = singular if is_one else (plural or default_plural)
    return f"{count} {noun}"


_UP_WORDS = {
    "strengthened", "rose", "widened", "improved", "took leadership",
}
_DOWN_WORDS = {"weakened", "fell", "narrowed"}
_THEME_DISPLAY = {
    theme: theme.replace("_", " ").replace("-", " ").title()
    for themes in NARRATIVE_GROUPS.values()
    for theme in themes
}
_THEME_DISPLAY.update({"ai": "AI", "big_tech": "Big Tech"})
_GROUP_BY_THEME = {
    theme: group for group, themes in NARRATIVE_GROUPS.items() for theme in themes
}


def _change_direction(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in _UP_WORDS):
        return "up"
    if any(word in lowered for word in _DOWN_WORDS):
        return "down"
    return "flat"


def _score_subject(text: str) -> str | None:
    match = re.match(r"^(.+?) (?:strengthened|weakened):", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def present_change_summary(summary: Any) -> Any:
    """Translate and deduplicate change chips at the presentation boundary."""
    if not isinstance(summary, dict):
        return summary
    raw_changes = summary.get("changes")
    if not isinstance(raw_changes, dict):
        return summary

    translated: dict[str, list[dict[str, Any]]] = {}
    rendered_group_moves: set[tuple[str, str]] = set()
    prepared: dict[str, list[dict[str, Any]]] = {}
    for category, items in raw_changes.items():
        prepared[category] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            text = text.replace(" -> ", " → ").replace("Concentration gap", "Lead over #2")
            text = text.replace("Dominant share", "Top story's share")
            for raw_theme, display_theme in _THEME_DISPLAY.items():
                text = re.sub(
                    rf"\b{re.escape(raw_theme)}\b",
                    display_theme,
                    text,
                    flags=re.IGNORECASE,
                )
            for group in NARRATIVE_GROUPS:
                text = re.sub(re.escape(group), group, text, flags=re.IGNORECASE)
            if category == "narratives":
                text = re.sub(
                    r"^(.+? (?:strengthened|weakened): )(-?\d+(?:\.\d+)?)"
                    r"( → )(-?\d+(?:\.\d+)?)(\.)$",
                    r"\1\2 stories\3\4 stories\5",
                    text,
                    flags=re.IGNORECASE,
                )
            direction = _change_direction(text)
            subject = _score_subject(text)
            prepared_item = {**item, "text": text, "direction": direction}
            prepared[category].append(prepared_item)
            canonical_group = next(
                (group for group in NARRATIVE_GROUPS if subject and group.casefold() == subject.casefold()),
                None,
            )
            if canonical_group and direction != "flat":
                rendered_group_moves.add((canonical_group, direction))

    for category, items in prepared.items():
        translated[category] = []
        for item in items:
            subject = _score_subject(item["text"])
            raw_theme = next(
                (
                    theme
                    for theme, display in _THEME_DISPLAY.items()
                    if subject == display
                ),
                None,
            )
            if (
                raw_theme
                and (_GROUP_BY_THEME[raw_theme], item["direction"]) in rendered_group_moves
            ):
                continue
            translated[category].append(item)

    return {
        **summary,
        "changes": translated,
        "has_changes": any(translated.values()),
    }
