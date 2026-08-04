"""Classify observed asset participation from persisted market data only."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from mne.market_calendar import classify_session_freshness
from mne.sector_market_context import DETACHED_MOVE_EPSILON, MEANINGFUL_MOVE_PCT, STRONG_MOVE_PCT


def _timestamp(value: Any) -> datetime | None:
    if not value: return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d_%H%M%S", "%Y%m%d_%H%M%S"):
        try: return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError: pass
    try: parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError: return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _freshness(record: dict | None, now: Any) -> str:
    if not isinstance(record, dict): return "UNAVAILABLE"
    observed = _timestamp(record.get("observed_at"))
    reference = _timestamp(now) if now is not None else datetime.now(timezone.utc)
    return classify_session_freshness(observed, reference) if observed and reference else "UNAVAILABLE"


def classify_asset_participation(mapping: Any, record: dict | None, asset: dict | None, *, now: Any = None) -> dict[str, Any]:
    freshness = _freshness(record, now)
    base = {"participation_state": "UNAVAILABLE", "data_freshness": freshness, "pct_change": None}
    if not isinstance(asset, dict) or not asset.get("display_enabled") or not isinstance(record, dict) or freshness != "FRESH" or not getattr(mapping, "expected_expression", None): return base
    try: change = float(record.get("pct_change"))
    except (TypeError, ValueError): return base
    if not math.isfinite(change): return base
    absolute = abs(change)
    aligned = (change > 0 and mapping.expected_expression == "UP") or (change < 0 and mapping.expected_expression == "DOWN")
    if absolute < DETACHED_MOVE_EPSILON: state = "MUTED"
    elif not aligned and absolute >= MEANINGFUL_MOVE_PCT: state = "CONTRADICTING"
    elif aligned and absolute >= STRONG_MOVE_PCT: state = "STRONG"
    elif aligned and absolute >= MEANINGFUL_MOVE_PCT: state = "PARTICIPATING"
    elif aligned and absolute > 0: state = "EMERGING"
    else: state = "MUTED"
    return {**base, "participation_state": state, "pct_change": round(change, 4)}


def classify_assets_for_run(run: dict[str, Any], asset_map: Any, registry: dict[str, Any], narrative: str, *, now: Any = None) -> dict[str, Any]:
    snapshot = run.get("market_snapshot") if isinstance(run, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    rows = {}
    for mapping in dict(asset_map.narratives).get(narrative, ()):
        asset = registry["assets"].get(mapping.ticker)
        record = snapshot.get(mapping.ticker)
        if record is None and isinstance(asset, dict) and asset.get("asset_type") == "ETF" and asset.get("sector_key"):
            record = snapshot.get(asset["sector_key"])
        result = classify_asset_participation(mapping, record, asset, now=now)
        rows[mapping.ticker] = result
    return {"assets": rows}
