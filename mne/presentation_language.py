"""Deterministic plain-language translations for the user dashboard.

Engine vocabulary remains canonical.  This module only describes how that
vocabulary is presented on the public dashboard.
"""

from __future__ import annotations

import re
from typing import Any


MARKET_EXPRESSION_COPY = {
    "headlines": {
        "STRONGLY_CONFIRMING": "The market is broadly confirming the {name} narrative.",
        "CONFIRMING": "The market is confirming the {name} narrative.",
        "PARTIALLY_CONFIRMING": "The market is partially confirming the {name} narrative.",
        "MIXED": "The {name} narrative is producing a mixed market response.",
        "DIVERGING": "The market is diverging from the {name} narrative.",
        "MUTED": "The market response to the {name} narrative is muted.",
        "UNAVAILABLE": "The current narrative is not yet being clearly reflected in the available market indicators.",
    },
    "why": {
        "STRONGLY_CONFIRMING": "The narrative is reflected across several relevant market areas without meaningful offset pressure.",
        "CONFIRMING": "The narrative is visible in available price behavior, though the expression is not broad.",
        "PARTIALLY_CONFIRMING": "The narrative is visible in price behavior, but counter-pressure or incomplete coverage limits the confirmation.",
        "MIXED": "The core market expressions disagree, so price behavior does not support one clear reading.",
        "DIVERGING": "Available primary market expressions are moving against the narrative.",
        "MUTED": "Available indicators have not moved enough to establish a meaningful market expression.",
        "UNAVAILABLE": "There is not enough current primary-market coverage to classify the expression.",
    },
    "context_note": "This is descriptive market context, not a recommendation.",
}

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
    "Narrative Direction": {"label": "Narrative Direction", "question": "Is this story strengthening, fading, or holding steady?"},
    "Recent Movement": {"label": "Recent Movement", "question": "How has this story changed recently?"},
    "X-Ray View": {"label": "X-Ray View", "question": "What supports this read?"},
    "Market Reaction": {"label": "Market Reaction", "question": "Where is this story showing up in markets?"},
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

NARRATIVE_CONSTELLATION_COPY = {
    "eyebrow": "Narrative Discovery",
    "title": "Today's narrative constellation",
    "framing": "Larger stories are receiving more attention. Accent and direction show whether attention is building or easing.",
    "research": "Explore in Research →",
    "xray": "X-Ray View",
    "xray_explanation": "Show the confirmed themes within each visible story and the relationships between them.",
    "themes_unavailable": "Deeper theme relationships are not available for this update.",
    "empty_title": "No clear narrative cluster yet",
    "empty": "No clear narrative cluster is available yet. MNE will show the strongest market stories here when enough evidence is present.",
    "summary": "{name} is receiving the most attention and is currently {direction}.",
}


def constellation_copy(key: str) -> str:
    """Return fixed, user-safe copy for Narrative Constellation."""
    return NARRATIVE_CONSTELLATION_COPY[key]


NARRATIVE_RELATIONSHIP_COPY = {
    "type_SUPPORTIVE": "Supportive connection",
    "type_DEPENDENCY": "Dependency",
    "type_OVERLAP": "Evidence overlap",
    "type_TRANSMISSION": "Transmission channel",
    "type_OFFSETTING": "Offsetting pressure",
    "type_CONDITIONAL": "Conditional connection",
    "type_SHARED_DRIVER": "Shared driver",
    "strength_STRONG": "Strong structural connection",
    "strength_MODERATE": "Moderate structural connection",
    "strength_LIMITED": "Limited structural connection",
    "section_eyebrow": "Connected context",
    "section_title": "Related narratives",
    "section_intro": "Curated structural connections that can help frame this narrative.",
}


def narrative_relationship_copy(key: str) -> str:
    return NARRATIVE_RELATIONSHIP_COPY[key]


SECTOR_ISOLATION_COPY = {
    "section_eyebrow": "Sector Isolation",
    "section_title": "Where this narrative connects",
    "section_intro": "Structural sector connections from MNE's curated narrative model.",
    "role_PRIMARY": "Primary connection",
    "role_SECONDARY": "Secondary connection",
    "role_EMERGING": "Developing connection",
    "role_OFFSET": "Offsetting connection",
    "role_DETACHED": "Structurally detached",
    "participation_STRONG": "Strong current participation",
    "participation_PARTICIPATING": "Currently participating",
    "participation_EMERGING": "Early current participation",
    "participation_MIXED": "Mixed current participation",
    "participation_DETACHED": "Current move is muted",
    "participation_CONTRADICTING": "Current move contradicts the expected expression",
    "participation_UNAVAILABLE": "Current participation unavailable",
    "participation_explanation_STRONG": "Persisted sector ETF data shows a strong move in the curated expected direction.",
    "participation_explanation_PARTICIPATING": "Persisted sector ETF data is moving meaningfully in the curated expected direction.",
    "participation_explanation_EMERGING": "Persisted sector ETF data shows an early move in the curated expected direction.",
    "participation_explanation_MIXED": "Persisted sector inputs disagree; this state requires genuine multi-input evidence.",
    "participation_explanation_DETACHED": "Fresh sector ETF data is muted or is not expressing the curated direction meaningfully.",
    "participation_explanation_CONTRADICTING": "Fresh sector ETF data is moving meaningfully against the curated expected direction.",
    "participation_explanation_UNAVAILABLE": "Current sector-level market participation is unavailable because data is missing, stale, or not classifiable.",
    "freshness_FRESH": "Based on the latest completed market session",
    "freshness_STALE": "Older than the latest expected market session",
    "freshness_UNAVAILABLE": "Observation time unavailable",
    "breadth_CONTRADICTED": "Current participation includes a meaningful contradiction.",
    "breadth_BROAD": "Current participation is broad across the mapped sectors.",
    "breadth_MODERATE": "Current participation is visible across two mapped sectors.",
    "breadth_CONCENTRATED": "Current participation is concentrated in one mapped sector.",
    "breadth_LIMITED": "Only early current participation is visible.",
    "breadth_UNAVAILABLE": "Current participation breadth is unavailable.",
    "structural_connection": "This sector is meaningfully connected to the narrative.",
    "participation_unavailable": "Current sector-level market participation is not yet available.",
    "curated_notice": "Sector relationships are curated from MNE's narrative model.",
    "persisted_notice": "Current participation reflects available persisted sector ETF data.",
    "separate_notice": "Structural relationships are curated separately from current market behavior.",
    "unavailable_not_detached": "Missing or stale data is shown as unavailable, not detached.",
    "not_forecast": "Sector participation describes current market expression, not a forecast.",
    "calendar_limit": "Current sector data is from the most recent available session.",
}


def sector_isolation_copy(key: str) -> str:
    return SECTOR_ISOLATION_COPY[key]

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
    "compare_entry": "Compare historical narratives →",
    "compare_label": "Historical Comparison",
    "compare_intro": "Choose two historical reconstructions to see how the market narrative changed.",
    "compare_needs_two_title": "Two historical reconstructions are needed",
    "compare_needs_two_body": "Once at least two completed reconstructions are available, you can compare narrative change across periods.",
    "compare_period_a": "Earlier selection",
    "compare_period_b": "Later selection",
    "compare_submit": "Compare narratives",
    "compare_invalid_title": "This historical comparison isn't available",
    "compare_invalid_body": "Choose two available historical reconstructions and try again.",
    "compare_banner": "Historical comparison",
    "compare_not_current": "This is not current market intelligence.",
    "compare_persisted": "Based on persisted historical reconstructions.",
    "compare_snapshot": "Comparison Snapshot",
    "compare_snapshot_question": "What changed from the earlier period to the later period?",
    "compare_dominance": "Dominance Changes",
    "compare_theme_changes": "Theme Changes",
    "compare_group_changes": "Narrative Group Changes",
    "compare_evidence": "Evidence Base Changes",
    "compare_coverage": "Historical Coverage and Limitations",
    "compare_explore": "Explore Each Period",
    "compare_same_title": "These are the same reconstruction — nothing to compare",
    "compare_same_body": "Choose a different historical period to see narrative change.",
    "compare_no_changes": "No scored narrative changes were available for this comparison.",
    "compare_earlier": "Earlier period",
    "compare_later": "Later period",
    "compare_dominant_theme": "Dominant theme",
    "compare_dominant_group": "Dominant narrative group",
    "compare_evidence_label": "Evidence",
    "compare_sources_label": "Sources",
    "compare_coverage_label": "Coverage",
    "compare_score": "Score",
    "compare_change": "Change",
    "compare_rank": "Rank",
    "compare_explore_earlier": "Explore earlier period →",
    "compare_explore_later": "Explore later period →",
    "compare_coverage_supported": "Historical coverage reflects supported sources available for each reconstruction.",
    "compare_coverage_incomplete": "This is not complete historical market-news coverage.",
    "compare_coverage_difference": "Differences may partly reflect differences in available historical evidence.",
    "compare_evidence_neutral": "Evidence counts describe the available historical record; they do not measure truth or predict what came next.",
    "request_entry": "Request a historical reconstruction →",
    "request_empty_entry": "None exist yet — request one",
    "request_label": "Historical Reconstruction",
    "request_title": "Reconstruct an earlier market period",
    "request_intro": "Choose a period and the official historical coverage to include.",
    "request_start_date": "Start date",
    "request_end_date": "End date",
    "request_categories": "Coverage to include",
    "request_submit": "Start reconstruction",
    "request_pacing": "Reconstruction runs while you wait — this may take a minute.",
    "request_coverage_supported": "Reconstruction uses supported official historical sources.",
    "request_coverage_partial": "Coverage may be partial.",
    "request_coverage_incomplete": "This is not complete historical market-news coverage.",
    "request_coverage_cutoff": "Evidence after the historical cutoff is excluded.",
    "request_invalid_dates": "Enter a valid historical start and end date.",
    "request_empty_categories": "Choose at least one coverage category.",
    "request_invalid_categories": "Choose only the available coverage categories.",
    "request_invalid_submission": "This request could not be accepted. Check the form and try again.",
    "request_range_too_large": "Choose a period of 92 days or fewer. Larger historical periods are handled separately.",
    "request_status_label": "Reconstruction Status",
    "request_period": "Historical period",
    "request_selected_coverage": "Requested coverage",
    "request_state_complete": "Reconstruction complete",
    "request_state_partial": "Reconstruction complete with partial coverage",
    "request_state_failed": "Reconstruction unavailable",
    "request_state_working": "Reconstruction is being prepared",
    "request_complete_body": "The requested official sources were reconstructed for this period.",
    "request_partial_body": "A historical reconstruction is available, but some requested sources had no records or could not be reconstructed.",
    "request_failed_body": "No requested source was available for a historical reconstruction.",
    "request_no_records_note": "Official releases are periodic, so no records in a short period can be a correct result.",
    "request_view_result": "View this reconstruction →",
    "request_compare_result": "Compare historical narratives →",
    "request_unavailable_title": "This reconstruction request isn't available",
    "request_unavailable_body": "It may have been removed or could not be opened safely.",
}

NARRATIVE_HISTORY_COPY = {
    "page_label": "Narrative History",
    "page_intro": "See how this narrative appeared and changed across persisted daily history.",
    "back": "Back to narrative investigation",
    "summary_title": "Lifecycle summary",
    "summary_question": "How has this narrative been behaving?",
    "current_stage": "Current stage",
    "previous_stage": "Previous stage",
    "current_streak": "Current streak",
    "appearances": "Appearances",
    "dominance": "Days led",
    "peak_score": "Peak score",
    "peak_share": "Highest share",
    "latest_memory_event": "Most recent recurrence",
    "days": "days",
    "day": "day",
    "unavailable": "Unavailable",
    "score": "Score",
    "share": "Share of narrative attention",
    "rank": "Rank",
    "timeline": "Lifecycle over time",
    "timeline_note": "Each segment shows the persisted state for that snapshot day.",
    "gap_note": "Breaks show snapshot days when this narrative was absent.",
    "thin": "Not enough history to chart yet — history builds as daily runs accrue.",
    "empty": "No persisted daily history is available for this narrative yet.",
    "no_share": "Share history is unavailable for this narrative.",
    "no_rank": "Rank history is unavailable for this narrative.",
    "history_reflects": "History reflects persisted MNE runs.",
    "missing_dates": "Missing run dates are not interpolated.",
    "lifecycle_integrity": "Lifecycle labels describe observed narrative behavior, not future outcomes.",
    "why_title": "Why these labels?",
    "why_body": "Narrative Pulse supplies daily lifecycle labels. Narrative Memory or Narrative Dynamics labels appear only when they were persisted for that period.",
    "preview_label": "History preview",
    "preview_title": "Lifecycle at a glance",
    "view_full": "View full history →",
    "not_found": "This narrative history isn't available.",
    "groups_only": "Daily history is currently available for narrative groups.",
}

AI_ANALYST_COPY = {
    "title": "AI Analyst",
    "description": "AI Analyst explains MNE's persisted evidence and analysis.",
    "no_fetch": "It does not fetch new information.",
    "no_prediction": "It does not provide predictions or trade recommendations.",
    "evidence_limit": "Responses may be limited by the evidence available to MNE.",
    "input_label": "Ask about MNE's analysis",
    "input_placeholder": "What is driving the market narrative today?",
    "submit": "Ask Analyst",
    "loading": "Reviewing MNE's persisted analysis…",
    "error": "The Analyst response was unavailable.",
    "fallback_note": "Showing MNE's built-in explanation.",
}

HISTORICAL_CONNECTION_COPY = {
    "eyebrow": "Historical Context",
    "heading": "Connections to recent history",
    "explore": "Explore this historical reconstruction →",
}

HISTORICAL_REQUEST_CATEGORIES = {
    "monetary_policy": {
        "label": "Monetary policy",
        "description": "Official central-bank statements and policy decisions.",
    },
    "inflation": {
        "label": "Inflation",
        "description": "Official consumer-price releases.",
    },
    "growth_consumer": {
        "label": "Growth and consumer activity",
        "description": "Official economic-growth and consumer-spending releases.",
    },
    "energy_commodities": {
        "label": "Energy and commodities",
        "description": "Official energy-market releases.",
    },
}

HISTORICAL_REQUEST_OUTCOMES = {
    "RECONSTRUCTED": "reconstructed from {count} official {record_word}",
    "NO_RECORDS": "no records available in this period",
    "FAILED": "could not be reconstructed",
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


def historical_request_category(token: str) -> dict[str, str]:
    """Return product copy for a whitelisted historical request category."""
    return HISTORICAL_REQUEST_CATEGORIES[token]


def historical_request_outcome(outcome: str, count: int = 0) -> str:
    """Compose a user-safe, deterministic per-category outcome."""
    template = HISTORICAL_REQUEST_OUTCOMES[outcome]
    return template.format(
        count=max(0, int(count or 0)),
        record_word="record" if int(count or 0) == 1 else "records",
    )


def historical_breadth(value: Any) -> dict[str, Any]:
    """Translate replay coverage breadth without making a quality claim."""
    raw = "" if value in (None, "") else str(value)
    translated = HISTORICAL_BREADTH.get(raw.upper())
    if translated is None:
        return {"label": "", "meaning": "", "tone": "neutral", "raw": raw, "untranslated": bool(raw)}
    return {**translated, "raw": raw, "untranslated": False}


def narrative_display_name(value: Any) -> str:
    """Translate a persisted narrative key at the presentation boundary."""
    if value in (None, ""):
        return ""
    text = str(value)
    if text in NARRATIVE_GROUPS:
        return text
    translated = _THEME_DISPLAY.get(text)
    if translated:
        return translated
    text = text.replace("_", " ").replace("-", " ").title()
    return text.replace("Ai", "AI").replace("Gdp", "GDP").replace("Pce", "PCE")


def historical_origin(origin: Any = None, source_id: Any = None) -> str:
    """Explain an evidence origin using a deterministic, user-safe mapping."""
    source_key = str(source_id or "").strip().lower()
    origin_key = str(origin or "").strip().lower()
    if source_key and f"origin_{source_key}" in HISTORICAL_COPY:
        return HISTORICAL_COPY[f"origin_{source_key}"]
    if origin_key and f"origin_{origin_key}" in HISTORICAL_COPY:
        return HISTORICAL_COPY[f"origin_{origin_key}"]
    return HISTORICAL_COPY["origin_default"]


HISTORICAL_DIRECTIONS = {
    "INCREASED": _entry("Increased"),
    "DECREASED": _entry("Decreased"),
    "UNCHANGED": _entry("Unchanged"),
    "NEW": _entry("New"),
    "DROPPED": _entry("No longer present"),
}


def historical_direction(value: Any) -> dict[str, Any]:
    """Translate historical score movement without attaching judgment."""
    raw = "" if value in (None, "") else str(value).upper()
    translated = HISTORICAL_DIRECTIONS.get(raw)
    if translated is None:
        return {"label": "", "meaning": "", "tone": "neutral", "raw": raw, "untranslated": bool(raw)}
    return {**translated, "raw": raw, "untranslated": False}


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
PERSONALIZATION_COPY = {
    "heading": "Preferences",
    "intro": "Choose the narratives and meaningful changes you want to keep close.",
    "local_notice": "Preferences are stored locally on this machine in one anonymous profile. They are not tied to an account, are not account-secured, and do not sync across devices.",
    "alerts_heading": "In-app alerts",
    "alert_descriptions": {
        "NARRATIVE_BECAME_DOMINANT": "Tell me when a narrative becomes dominant",
        "NARRATIVE_BUILDING_AGAIN": "Tell me when a narrative starts building again",
        "NARRATIVE_FADING": "Tell me when a narrative begins fading",
        "NARRATIVE_RETURNED": "Tell me when a narrative returns",
        "DOMINANT_NARRATIVE_CHANGED": "Tell me when the dominant narrative changes",
        "MARKET_EXPRESSION_CHANGED_MATERIALLY": "Tell me when market expression changes materially",
        "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE": "Tell me when the evidence base becomes limited",
        "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG": "Tell me when a historical connection becomes meaningfully strong",
    },
}


def narrative_display_name(value):
    """Translate a narrative key at the presentation boundary."""
    text = str(value or "").replace("_", " ").strip()
    known = {"ai": "AI", "ai / tech growth": "AI / Tech Growth", "fed": "Federal Reserve"}
    return known.get(text.lower(), text.title())
ACCOUNT_COPY = {
    "account": "Account", "sign_in": "Sign in", "sign_out": "Sign out",
    "create_account": "Create an account", "email": "Email", "password": "Password",
    "display_name": "Display name", "login_intro": "Use your MNE account to access preferences and saved work.",
    "signup_intro": "Your preferences and saved views will be stored with this account.",
    "existing_account": "Already have an account?", "terms": "I accept the terms.",
    "privacy": "I accept the privacy notice.", "profile": "Profile", "save": "Save",
    "storage_note": "Your preferences, followed narratives, alerts, and saved historical views are stored with this account. Anonymous data saved on this machine does not sync across devices.",
    "import_heading": "Preferences found on this machine",
    "import_intro": "Import the preferences saved on this machine? Invalid or missing references will be skipped. The local file will remain in place.",
    "import": "Import preferences", "not_now": "Not now", "reset_heading": "Set a new password",
    "new_password": "New password", "set_password": "Set password",
}

ENTITLEMENT_COPY = {
    "plan_heading": "Your plan",
    "usage_heading": "Included usage",
    "internal_access": "Internal product access is enabled for this account.",
    "upgrade_prompt": "Upgrade to Pro for deeper historical research and higher limits.",
    "feature_unavailable": "This feature is not included with your current plan.",
    "upgrade_required": "This feature is not included with your current plan.",
    "monthly_allowance_used": "You've used this month's included allowance.",
    "capacity_reached": "Your current plan's saved-item limit has been reached. You can still view and remove existing items.",
    "temporarily_unavailable": "This feature is temporarily unavailable.",
    "HISTORICAL_INVESTIGATION_VIEWS": "historical investigations",
    "HISTORICAL_COMPARISONS": "historical comparisons",
    "HISTORICAL_REQUESTS": "historical requests",
    "AI_ANALYST_QUESTIONS": "Analyst questions",
    "SAVED_HISTORICAL_VIEWS": "saved historical views",
    "FOLLOWED_NARRATIVES": "followed narratives",
    "ALERT_RULES": "alert rules",
}


def entitlement_denial(reason, metric=None):
    if reason == "monthly_allowance_used" and metric == "HISTORICAL_COMPARISONS":
        return "You've used this month's included historical comparisons."
    if reason == "monthly_allowance_used" and metric:
        label = ENTITLEMENT_COPY.get(metric, "allowance")
        return f"You've used this month's included {label}."
    return ENTITLEMENT_COPY.get(reason, ENTITLEMENT_COPY["temporarily_unavailable"])


def usage_summary(entitlement_context):
    monthly = {"HISTORICAL_INVESTIGATION_VIEWS", "HISTORICAL_COMPARISONS", "HISTORICAL_REQUESTS"}
    result = []
    for metric, usage in entitlement_context.get("usage", {}).items():
        if metric == "AI_ANALYST_QUESTIONS":
            continue
        suffix = " this month" if metric in monthly else ""
        result.append(f"{usage['used']} of {usage['limit']} {ENTITLEMENT_COPY[metric]} used{suffix}.")
    return result
"""Deterministic product language for authentication and account surfaces."""
