"""Deterministic NYSE-session freshness for persisted daily market observations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal


STALE_GRACE_WINDOW = timedelta(hours=8)
ABSOLUTE_STALE_BACKSTOP = timedelta(days=10)
FreshnessState = Literal["FRESH", "STALE", "UNAVAILABLE"]


def _nyse_session_closes(start: datetime, end: datetime) -> tuple[datetime, ...] | None:
    """Return NYSE closes in the inclusive date range, or None if unresolved.

    Importing lazily keeps the failure mode explicit. The conservative fallback is
    UNAVAILABLE; an absent or failing calendar never silently marks data fresh.
    """
    try:
        import pandas_market_calendars as market_calendars

        schedule = market_calendars.get_calendar("NYSE").schedule(
            start_date=start.date(),
            end_date=end.date(),
        )
        return tuple(value.to_pydatetime().astimezone(timezone.utc) for value in schedule["market_close"])
    except Exception:  # Calendar resolution is optional; all failures fail closed.
        return None


def classify_session_freshness(observed_at: datetime, as_of: datetime) -> FreshnessState:
    """Classify a persisted observation against completed NYSE sessions."""
    if observed_at.tzinfo is None or as_of.tzinfo is None:
        return "UNAVAILABLE"
    observed = observed_at.astimezone(timezone.utc)
    reference = as_of.astimezone(timezone.utc)
    if observed > reference:
        return "UNAVAILABLE"
    if reference - observed > ABSOLUTE_STALE_BACKSTOP:
        return "STALE"

    closes = _nyse_session_closes(observed, reference)
    if closes is None:
        return "UNAVAILABLE"
    completed_since = tuple(close for close in closes if observed < close <= reference)
    if not completed_since:
        return "FRESH"
    if len(completed_since) == 1 and reference <= completed_since[0] + STALE_GRACE_WINDOW:
        return "FRESH"
    return "STALE"
