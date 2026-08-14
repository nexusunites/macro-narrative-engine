"""Deterministic plain-language translations for the user dashboard.

Engine vocabulary remains canonical.  This module only describes how that
vocabulary is presented on the public dashboard.
"""

from __future__ import annotations

import re
from datetime import datetime
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


ATTENTION_CLOUD_COPY = {
    "eyebrow": "The Centerpiece",
    "title": "What everyone's talking about",
    "framing": "Story size reflects how much of the market's attention it holds. Choose a story for the detail.",
    "research": "Explore in Research →",
    "why_label": "Why it matters",
    "tape_label": "From the tape",
    "driving_label": "Currently driving",
    "watch_label": "Watch for",
    "connected_label": "Connected stories",
    "empty_title": "No clear attention leader yet",
    "empty": "No market story has enough current evidence to appear here yet.",
    "none": "No current evidence",
}


def attention_cloud_copy(key: str) -> str:
    """Return fixed user-facing copy for the interim attention cloud."""
    return ATTENTION_CLOUD_COPY[key]


def attention_cloud_direction(acceleration: Any = None, pulse: Any = None) -> dict[str, str]:
    """Translate persisted movement signals into the dashboard's direction vocabulary."""
    rising = {"ACCELERATING", "RISING", "BUILDING", "EMERGING", "STRONG"}
    fading = {"COOLING", "FADING", "LOSING", "DORMANT"}
    directions = set()
    for value in (acceleration, pulse):
        token = str(value or "").strip().upper().replace(" ", "_")
        if token in rising:
            directions.add("up")
        elif token in fading:
            directions.add("down")
    direction = directions.pop() if len(directions) == 1 else "steady"
    return {
        "direction": direction,
        "label": "Strengthening" if direction == "up" else "Fading" if direction == "down" else "Holding steady",
    }


def attention_direction_from_share_delta(share_delta: Any = None) -> dict[str, str]:
    """Translate the story-card coverage-share movement into shared UI direction copy."""
    try:
        delta = float(share_delta)
    except (TypeError, ValueError):
        delta = 0.0
    direction = "up" if delta > 0 else "down" if delta < 0 else "steady"
    return {
        "direction": direction,
        "label": "Strengthening" if direction == "up" else "Fading" if direction == "down" else "Holding steady",
        "tone": "good" if direction == "up" else "caution" if direction == "down" else "neutral",
    }


def dashboard_attention_summary(name: str, direction: str) -> str:
    """Describe card movement from the unified coverage-share direction state."""
    if direction == "up":
        return f"Attention around {name} is building."
    if direction == "down":
        return f"Attention around {name} has been declining."
    return f"Attention around {name} is holding steady."


def attention_cloud_why(name: str, direction_label: str, share: float) -> str:
    """Explain one group-level chip using its persisted share and translated direction."""
    return f"{name} holds {share:.1f}% of visible narrative attention and is {direction_label.lower()} in this update."


def attention_cloud_watch_for(name: str) -> str:
    return f"New evidence around {name}"


def attention_cloud_trend(direction_label: str) -> str:
    return f"{direction_label} in this update"


def attention_cloud_evidence(value: Any) -> str:
    """Pass persisted headline evidence through the presentation boundary."""
    return str(value or "").strip()


WATCHLIST_COPY = {
    "title": "Watchlist",
    "count_singular": "narrative",
    "count_plural": "narratives",
    "open": "Open watchlist",
    "close": "Close watchlist",
    "add": "Add to watchlist",
    "remove": "Remove from watchlist",
    "empty": "No narratives watched yet. Star one from a story's detail panel to track it here.",
    "history": "Recent narrative history is not available yet.",
    "investigate": "Investigate history →",
}


def watchlist_copy(key: str) -> str:
    """Return fixed user-facing copy for the in-page watchlist."""
    return WATCHLIST_COPY[key]


DASHBOARD_PARITY_COPY = {
    "brand_short": "MNE",
    "brand_full": "Macro Narrative Engine",
    "nav_overview": "Overview",
    "nav_research": "Research",
    "nav_studio": "Studio",
    "nav_history": "History",
    "nav_preferences": "Preferences",
    "nav_sign_in": "Sign in",
    "big_picture_eyebrow": "The big picture",
    "big_picture_title": "Three narratives running the tape",
    "big_picture_intro": "How the day's stories cluster, ranked by how much they're moving markets.",
    "rank": "Rank",
    "focus": "Today's focus",
    "steady": "Steady",
    "cooling": "Cooling",
    "strengthening": "Strengthening",
    "strength": "Strength",
    "momentum": "Momentum",
    "attention": "Attention",
    "share": "Share of attention",
    "investigate": "Investigate narrative →",
    "sector_eyebrow": "Where the story is landing",
    "sector_title": "Which sectors are actually participating",
    "sector_intro": "The stripe shows whether a sector is driving the day's story, steady, or detached from it.",
    "sector_driving": "Driving the story",
    "sector_steady": "Steady",
    "sector_detached": "Detached",
    "sector_unavailable": "No fresh data this session",
    "evidence_eyebrow": "What we read",
    "evidence_title": "The evidence behind the story",
    "evidence_intro": "Every narrative above traces back to real headlines from the latest engine run.",
    "evidence_why": "These headlines contributed to today's read of this story.",
    "evidence_empty": "No supporting headlines were stored for the leading stories in this update.",
    "source_unavailable": "Source unavailable",
}


def dashboard_parity_copy(key: str) -> str:
    """Return approved mockup-parity copy for the user dashboard."""
    return DASHBOARD_PARITY_COPY[key]


RESEARCH_FINDER_COPY = {
    "eyebrow": "Research",
    "status": "Latest verified read · {run_label}",
    "headline": "Find the story you need",
    "subtitle": "Search the day's narratives and the stories inside them, then open one to investigate what changed and why.",
    "search_placeholder": "Search narratives and stories…",
    "search_label": "Search narratives and stories",
    "clear_search": "Clear search",
    "finder_helper": "Find a narrative or a specific story by name, keyword, sector, or catalyst.",
    "finder_note": "This deterministic finder matches what you type against the day's narratives and stories. For deeper questions, open a narrative and ask the AI Analyst on its page.",
    "topic_filter": "Filter by topic",
    "theme_ai": "AI",
    "theme_rates": "Rates",
    "theme_inflation": "Inflation",
    "theme_energy": "Energy",
    "theme_recession": "Recession",
    "crypto": "Crypto · not tracked yet",
    "crypto_hint": "No crypto narrative is tracked yet — nothing to show.",
    "index_eyebrow": "The index",
    "index_title": "Narratives in today's read",
    "index_intro": "Each narrative holds its own stories. Follow a narrative or investigate it in depth.",
    "score": "Strength",
    "share": "Share of attention",
    "unscored": "Defined, not currently scored",
    "investigate": "Investigate →",
    "follow": "Follow",
    "unfollow": "Following",
    "sign_in_to_follow": "Sign in to follow",
    "follow_unavailable": "Following is unavailable for this account",
    "story_star": "Story saving is coming with Studio",
    "studio_hint": "Story saving is coming with Studio and is not available yet.",
    "story_save": "Save story",
    "story_saved": "Saved story",
    "story_track": "Track story",
    "story_tracked": "Tracked story",
    "sign_in_to_save": "Sign in to save",
    "story_save_unavailable": "Story saving is unavailable for this account",
    "empty": "No narrative or story matches that. Try a different word, or clear the filters.",
    "no_run_eyebrow": "Research",
    "no_run_title": "No narratives are ready to explore",
    "no_run_body": "A completed run with narrative evidence is needed before the Research index can be shown.",
}


def research_finder_copy() -> dict[str, str]:
    """Return fixed user-facing copy for the deterministic Research finder."""
    return dict(RESEARCH_FINDER_COPY)


STUDIO_COPY = {
    "eyebrow": "Studio",
    "concept_tag": "Your working view",
    "headline": "Build the case you believe",
    "subtitle": "Arrange saved stories as evidence, connect what matters, and keep the view you are testing in focus.",
    "library_headline": "Your thesis library",
    "library_subtitle": "Build, revisit, and refine the market views you are testing.",
    "library_sign_in": "Sign in to build and revisit your theses.",
    "library_new": "+ New thesis",
    "library_empty_title": "Start your first thesis",
    "library_empty_body": "Create a place for the market view you want to test.",
    "library_untitled": "Untitled thesis",
    "library_evidence": "evidence",
    "library_link": "link",
    "library_links": "links",
    "library_open": "Open thesis",
    "library_delete": "Delete",
    "library_delete_confirm": "Delete this thesis? This cannot be undone.",
    "library_updated_now": "Updated just now",
    "library_updated_minutes": "Updated {count}m ago",
    "library_updated_hours": "Updated {count}h ago",
    "library_updated_days": "Updated {count}d ago",
    "library_updated_unknown": "Update time unavailable",
    "library_capacity": "You can keep up to 25 theses.",
    "thesis_not_found": "That thesis was not found.",
    "all_theses": "← All theses",
    "rail_label": "Your saved material",
    "watchlist": "Watchlist",
    "watchlist_note": "The stories you're actively tracking — a subset of Saved below.",
    "saved": "Saved",
    "saved_note": "Everything you starred in Research.",
    "tracked": "Tracked",
    "empty": "Star stories in Research to build your collection",
    "sign_in": "Sign in to see your saved stories and watchlist.",
    "sign_in_action": "Sign in",
    "watchlist_empty": "Track a saved story to add it to your watchlist.",
    "thesis_label": "What you think",
    "thesis_placeholder": "State the view you are building.",
    "board_title": "The case you are building",
    "board_hint": "Drag a saved story here to add evidence to your view.",
    "board_empty": "Start with a saved story",
    "board_empty_body": "Star stories in Research, then bring them here as evidence.",
    "board_empty_action": "Find stories in Research",
    "remove_evidence": "Remove from this view",
    "connect_evidence": "Connect this evidence",
    "connection_moves_with": "Moves with",
    "connection_moves_against": "Moves against",
    "connection_drives": "Drives",
    "connection_depends_on": "Depends on",
    "connection_supports": "Supports",
    "connection_prompt": "How do these relate?",
    "evidence_add": "Add as evidence",
    "evidence_added": "Added",
    "headline_evidence": "Headline evidence",
    "catalyst_evidence": "Catalyst evidence",
    "save_saving": "Saving…",
    "save_saved": "Saved",
    "save_error": "Could not save changes",
    "intelligence_title": "What supports this",
    "intelligence_loading": "Gathering current evidence…",
    "intelligence_empty": "Nothing is attached to this story in the current read.",
    "intelligence_headlines": "Supporting headlines",
    "intelligence_related": "Related narratives",
    "intelligence_catalyst": "Next thing to watch",
    "relationship_title": "A known relationship",
    "relationship_action": "Use this relationship",
    "research_deep_dive": "Investigate in Research",
    "authentication_required": "Sign in to keep working on this view.",
    "board_invalid": "These changes could not be saved.",
    "intelligence_unavailable": "Current story intelligence is unavailable.",
    "compare_eyebrow": "Compare tool",
    "compare_history_tag": "Was: History",
    "compare_title": "Compare over time",
    "compare_description": "See how a narrative looked at two points in time, side by side.",
    "compare_point_a": "Point A",
    "compare_point_b": "Point B",
    "compare_vs": "vs",
    "compare_prompt": "Pick two points in time to compare",
    "compare_no_replays": "No saved reconstructions to compare yet",
    "compare_leader_unavailable": "Leading narrative unavailable",
    "compare_result": "What changed",
}


def studio_copy() -> dict[str, str]:
    """Return fixed user-facing copy for the Studio shell."""
    return dict(STUDIO_COPY)


RESEARCH_INVESTIGATION_COPY = {
    "all_narratives": "All narratives",
    "jump_happening": "What's happening",
    "jump_memory": "Recent memory",
    "jump_why": "Why",
    "jump_clock": "On the clock",
    "jump_market": "Market",
    "jump_evidence": "From the tape",
    "jump_analyst": "Ask the analyst",
    "jump_related": "Related",
    "jump_sectors": "Sectors",
    "jump_stories": "Stories",
    "clock_eyebrow": "On the clock",
    "clock_title": "On the clock for this narrative",
    "clock_intro": "Dated events already matched to this narrative in the latest read.",
    "clock_soonest": "Soonest",
    "clock_upcoming": "Upcoming",
    "clock_timing_unavailable": "Timing unavailable",
    "clock_why_fallback": "Relevant catalyst context matched to this narrative.",
    "candle_role": "lead instrument",
    "candle_open": "Open asset view →",
    "candle_caption": "A compact read of persisted daily price history. Open the asset view for the full context.",
    "candle_empty": "No price history yet for this instrument.",
    "candle_lead_empty": "No lead instrument is available for this narrative.",
    "latest_read": "Latest verified read · {run_label}",
    "sectors_eyebrow": "Market expression",
    "sectors_title": "Sectors expressing it",
    "sectors_intro": "Where this narrative is showing up across the available market data.",
    "sectors_empty": "No curated sector relationships are available for this narrative.",
    "sectors_explore": "Explore assets →",
    "sectors_legend_driving": "Driving",
    "sectors_legend_steady": "Steady or unavailable",
    "sectors_legend_detached": "Detached",
    "sectors_legend_label": "Sector participation legend",
    "stories_eyebrow": "Story threads",
    "stories_title": "Stories in this narrative",
    "stories_intro": "The matched story threads that make up this narrative in the latest read.",
    "stories_empty": "No matched stories are available for this narrative in the latest read.",
    "story_matches": "{count} matched headline{suffix}",
    "story_star": "Story saving is coming with Studio",
    "story_save": "Save story",
    "story_saved": "Saved story",
    "story_track": "Track story",
    "story_tracked": "Tracked story",
    "sign_in_to_save": "Sign in to save",
    "story_save_unavailable": "Story saving is unavailable for this account",
}


def research_investigation_copy() -> dict[str, str]:
    """Return fixed user-facing copy for Narrative Investigation v2."""
    return dict(RESEARCH_INVESTIGATION_COPY)


def dashboard_sector_presentation(state: Any, existing_label: Any = None) -> dict[str, str]:
    """Map persisted participation states to the three-state dashboard tile vocabulary."""
    token = str(state or "UNAVAILABLE").upper()
    if token in {"STRONG", "PARTICIPATING", "EMERGING"}:
        visual = "driving"
    elif token in {"DETACHED", "CONTRADICTING"}:
        visual = "detached"
    else:
        visual = "steady"
    label = (
        DASHBOARD_PARITY_COPY["sector_unavailable"]
        if token == "UNAVAILABLE"
        else str(existing_label or DASHBOARD_PARITY_COPY[f"sector_{visual}"])
    )
    return {"state": visual, "label": label}


ASSET_EXECUTION_COPY = {
    "page_title": "Asset Execution View",
    "asset_view": "Asset view",
    "dashboard": "Dashboard",
    "primary_expression": "Primary expression",
    "supporting_expression": "Supporting expression",
    "moving_with": "Moving with the story",
    "steady": "Steady / sitting out",
    "moving_against": "Moving against the story",
    "today": "today",
    "todays_launch": "Today's launch",
    "launch_line": "Launch line",
    "above_launch": "above launch",
    "below_launch": "below launch",
    "at_launch": "at launch",
    "launch_caption": "The Daily Launch Line is where the latest verified session opened.",
    "launch_path_label": "Latest verified session, from open to close",
    "unavailable": "Unavailable",
    "tape_eyebrow": "The tape",
    "tape_title": "The tape, in context",
    "tape_intro": "Daily candles inside their recent range, so a move is always read against what came before.",
    "daily_candles": "daily candles",
    "chart_range": "Chart range",
    "range_1m": "1M",
    "range_3m": "3M",
    "range_6m": "6M",
    "event_filters": "Event filters",
    "filter_all": "All",
    "filter_earnings": "Earnings",
    "filter_news": "News",
    "filter_macro": "Macro",
    "filter_hide": "Hide",
    "event_details": "Event details",
    "close_panel": "Close",
    "event_source": "Source",
    "view_filing": "View filing on SEC EDGAR",
    "on_clock_eyebrow": "On the clock",
    "on_clock_title": "Upcoming catalysts",
    "on_clock_intro": "Scheduled catalysts connected to this asset's story.",
    "no_upcoming": "No upcoming story-relevant catalysts are scheduled in the verified window.",
    "days_away": "days away",
    "today_countdown": "today",
    "no_history": "No price history yet for this instrument",
    "up_day": "Up day",
    "down_day": "Down day",
    "todays_launch_legend": "Today's launch",
    "recent_range": "20-day range",
    "chart_requires_js": "Chart requires JavaScript.",
    "latest_close": "Latest close",
    "last_verified_close": "Last verified close",
    "story_eyebrow": "The story it carries",
    "story_title": "The story this asset carries",
    "story_intro": "What this instrument stands for in the narrative, and how it has been participating.",
    "role_in_narrative": "Role in the narrative",
    "connected_stories": "Connected stories",
    "participation_heading": "How it's been participating",
    "sector_eyebrow": "The sector",
    "sector_instruments": "instruments",
    "sector_intro": "Every supported instrument mapped here links to its own execution view.",
    "viewing": "Viewing",
    "xray": "X-Ray View",
    "ticker": "Ticker",
    "expected_direction": "Expected direction",
    "no_directional_claim": "No separate directional claim",
    "freshness": "Freshness",
    "sector_relationship": "Sector relationship",
    "broader_context": "Broader market context",
    "market_expression_role": "Market Expression role",
    "no_matching_role": "No matching role",
    "latest_persisted_move": "Latest persisted move",
    "return_to_research": "Return to narrative research",
    "assets_empty": "No supported assets are mapped in this section. Limited coverage is shown as unavailable.",
    "honesty_title": "What this view is not",
    "honesty_behavior": "This describes how the market has been behaving around the instrument. It does not advise buying, selling, or holding.",
    "honesty_prices": "Prices shown are the engine's last verified data, not a live quote.",
    "honesty_missing": "When data is missing or stale, the view says so rather than filling the gap with a guess.",
    "unmapped_ticker": "This instrument is not mapped in the asset registry.",
    "unavailable_relationships": "Asset relationships are temporarily unavailable.",
    "group_only": "Asset Execution View is available for narrative groups.",
    "sector_unmapped": "This sector is not mapped to the selected narrative.",
    "instrument_sector_unmapped": "This instrument is not mapped to the selected sector.",
    "rail_high": "20-day high",
    "rail_low": "20-day low",
    "open_short": "O",
    "high_short": "H",
    "low_short": "L",
    "close_short": "C",
}


def asset_execution_copy(key: str) -> str:
    """Return approved copy for the per-instrument execution view."""
    return ASSET_EXECUTION_COPY[key]


def asset_execution_copy_bundle() -> dict[str, str]:
    """Return a detached template/JavaScript copy bundle."""
    return dict(ASSET_EXECUTION_COPY)


def dashboard_evidence_meta(source: Any, timestamp: Any) -> str:
    """Format persisted evidence attribution without manufacturing missing fields."""
    source_label = str(source or DASHBOARD_PARITY_COPY["source_unavailable"]).strip()
    if not timestamp:
        return source_label
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        time_label = parsed.strftime("%b %-d, %-I:%M %p")
    except (TypeError, ValueError):
        return source_label
    return f"{source_label} · {time_label}"


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

ASSET_EXPLORATION_COPY = {
    "role_PRIMARY": "Primary expression", "role_SECONDARY": "Secondary expression",
    "role_OFFSET": "Offsetting expression", "role_CONTEXT": "Broader context",
    "participation_STRONG": "Strong current participation",
    "participation_PARTICIPATING": "Currently participating",
    "participation_EMERGING": "Early current participation",
    "participation_MUTED": "Current movement is limited",
    "participation_CONTRADICTING": "Current move contradicts the expected expression",
    "participation_UNAVAILABLE": "Current participation unavailable",
    "participation_explanation_STRONG": "Fresh persisted data shows a strong move in the curated expected direction.",
    "participation_explanation_PARTICIPATING": "Fresh persisted data is moving meaningfully in the curated expected direction.",
    "participation_explanation_EMERGING": "Fresh persisted data shows a smaller move in the curated expected direction.",
    "participation_explanation_MUTED": "Fresh persisted data exists, but current movement is limited.",
    "participation_explanation_CONTRADICTING": "Fresh persisted data is moving meaningfully against the curated expected direction.",
    "participation_explanation_UNAVAILABLE": "Current participation cannot be classified because data is missing, stale, malformed, or unsupported.",
    "freshness_FRESH": "Based on the latest completed market session",
    "freshness_STALE": "Older than the latest expected market session",
    "freshness_UNAVAILABLE": "Observation time unavailable",
    "breadth_CONTRADICTED": "Current asset participation includes a meaningful contradiction.",
    "breadth_BROAD": "Current participation confirms across at least three mapped assets.",
    "breadth_MODERATE": "Current participation confirms across two mapped assets.",
    "breadth_CONCENTRATED": "Current participation confirms in one mapped asset.",
    "breadth_LIMITED": "Only early current asset participation is visible.",
    "breadth_UNAVAILABLE": "Current asset participation breadth is unavailable.",
    "sector_etf_rationale": "This sector ETF represents the selected sector and reuses its current Sector Isolation observation.",
    "curated_notice": "Asset relationships are curated from MNE's narrative model.",
    "persisted_notice": "Current participation reflects available persisted market data.",
    "unavailable_notice": "Unavailable assets are not assumed to be detached.",
    "not_recommendation": "This view describes current market expression and is not a recommendation.",
}


def asset_exploration_copy(key: str) -> str:
    return ASSET_EXPLORATION_COPY[key]

HISTORICAL_COPY = {
    "archive_label": "Historical Narratives",
    "archive_page_title": "Historical Narratives · MNE",
    "archive_title": "Explore earlier market narratives",
    "archive_intro": "Browse completed reconstructions of what the available evidence showed at an earlier market cutoff.",
    "archive_empty_title": "No historical reconstructions are available yet",
    "archive_empty_body": "Historical reconstructions bring together evidence that was available by a past cutoff. Completed reconstructions will appear here.",
    "limited_badge": "Limited reconstruction",
    "evidence_singular": "piece of evidence",
    "evidence_plural": "pieces of evidence",
    "story_singular": "story",
    "story_plural": "stories",
    "evidence_label": "Evidence",
    "coverage_label": "Coverage",
    "historical_banner": "Historical reconstruction",
    "investigation_page_title": "Historical Investigation · MNE",
    "investigation_save": "Save investigation",
    "investigation_save_label": "Reconstruction",
    "investigation_browse": "Browse historical narratives →",
    "investigation_context_label": "Historical context",
    "investigation_cutoff": "Evidence cutoff",
    "investigation_sections_label": "Historical investigation sections",
    "investigation_jump_snapshot": "Snapshot",
    "investigation_jump_explanation": "Explanation",
    "investigation_jump_evidence": "Evidence",
    "investigation_jump_coverage": "Coverage",
    "investigation_jump_next": "Next",
    "investigation_snapshot_label": "Historical Snapshot",
    "investigation_supporting_details": "Supporting details",
    "investigation_leading_story": "Leading market story",
    "investigation_theme_strength": "Theme strength",
    "investigation_group_strength": "Group strength",
    "investigation_sources": "Sources",
    "investigation_engine_values": "Engine values",
    "investigation_engine_theme": "Dominant Theme",
    "investigation_engine_group": "Dominant Group",
    "investigation_engine_theme_score": "theme score",
    "investigation_engine_group_score": "group score",
    "investigation_engine_evidence_count": "evidence count",
    "investigation_engine_source_count": "source count",
    "investigation_engine_breadth": "coverage breadth",
    "investigation_explanation_label": "Narrative Explanation",
    "investigation_explanation_title": "What was shaping the market story?",
    "investigation_evidence_label": "Supporting Historical Evidence",
    "investigation_evidence_title": "What evidence supported the reconstruction?",
    "investigation_narrative_label": "Narrative",
    "investigation_why": "Why?",
    "investigation_open_reader": "Open Evidence Reader",
    "investigation_reader_label": "Evidence Reader",
    "investigation_reader_title": "Headline-level explanation",
    "investigation_reader_empty": "Select an evidence item to inspect its narrative connection.",
    "investigation_main_point": "Main point",
    "investigation_why_it_matters": "Why it matters",
    "investigation_narrative_connection": "Narrative connection",
    "investigation_close": "Close",
    "investigation_coverage_label": "Coverage and Limitations",
    "investigation_coverage_title": "How much of the historical record is represented?",
    "investigation_next_label": "Where to Look Next",
    "investigation_next_title": "Continue historical research",
    "investigation_next_link": "Explore another historical narrative →",
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
    "access_page_title": "Access unavailable · MNE",
    "access_title": "Access unavailable",
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
    "saved_stories_heading": "Saved stories",
    "saved_stories_intro": "Stories you save in Research appear here. Track the ones you want to keep especially close.",
    "saved_stories_empty": "Star stories in Research to build your collection.",
    "story_name_unavailable": "Saved story",
    "story_remove": "Remove",
    "story_track": "Track",
    "story_untrack": "Untrack",
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
    "SAVED_STORIES": "saved stories",
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
