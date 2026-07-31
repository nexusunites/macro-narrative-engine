"""Deterministic narrative-to-market expression evaluation.

The module consumes persisted market snapshots and a curated configuration map.
It never fetches market data, changes narrative scoring, or produces a trading
recommendation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mne.market_context import classify_market_move


DEFAULT_EXPRESSION_MAP_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "market_expression_map.json"
)

# Named boundaries make every final state hand-derivable.
EXPRESSION_STATE_THRESHOLDS = {
    "meaningful_move_pct": 0.25,
    "strong_move_pct": 1.0,
    "minimum_primary_coverage": 1,
    "broad_confirming_assets": 2,
}
"""Boundaries used by per-instrument and overall expression classification."""

BREADTH_THRESHOLDS = {
    "broad_confirming_assets": 2,
    "concentrated_confirming_assets": 1,
}
"""Minimum confirming core-expression counts for breadth labels."""

STALE_DATA_MAX_AGE = timedelta(hours=36)
"""Maximum accepted age when a persisted instrument timestamp is available."""

EXPRESSION_STATE_PRECEDENCE = (
    "UNAVAILABLE",
    "MUTED",
    "DIVERGING",
    "MIXED",
    "PARTIALLY_CONFIRMING",
    "CONFIRMING",
    "STRONGLY_CONFIRMING",
)
"""Explicit overall-state precedence, from fail-closed to broad confirmation."""

ROLES = ("primary", "secondary", "offsets")
CORE_ROLES = {"primary", "secondary"}
VALID_DIRECTIONS = {"UP", "DOWN"}
UP_MOVES = {"UP", "STRONG UP"}
DOWN_MOVES = {"DOWN", "STRONG DOWN"}


def _closed_config(error: str) -> dict[str, Any]:
    return {
        "mapping_version": None,
        "narratives": {},
        "valid": False,
        "errors": [error],
    }


def load_market_expression_map(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the versioned curated map, failing closed on errors."""
    config_path = Path(path) if path is not None else DEFAULT_EXPRESSION_MAP_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return _closed_config(f"Market expression map could not be loaded: {error}")

    if not isinstance(payload, dict) or not isinstance(payload.get("mapping_version"), str):
        return _closed_config("Market expression map has no valid mapping_version.")
    narratives = payload.get("narratives")
    if not isinstance(narratives, dict) or not narratives:
        return _closed_config("Market expression map has no valid narratives.")

    normalized = {}
    for narrative_key, entry in narratives.items():
        if not isinstance(narrative_key, str) or not isinstance(entry, dict):
            return _closed_config("Market expression map contains a malformed narrative.")
        normalized_entry = {"aliases": []}
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(v, str) for v in aliases):
            return _closed_config(f"{narrative_key} has malformed aliases.")
        normalized_entry["aliases"] = list(aliases)
        for role in ROLES:
            instruments = entry.get(role)
            if not isinstance(instruments, list):
                return _closed_config(f"{narrative_key}.{role} must be a list.")
            normalized_entry[role] = []
            for instrument in instruments:
                direction_key = (
                    "pressure_direction" if role == "offsets" else "confirming_direction"
                )
                if (
                    not isinstance(instrument, dict)
                    or not isinstance(instrument.get("asset"), str)
                    or not isinstance(instrument.get("label"), str)
                    or instrument.get(direction_key) not in VALID_DIRECTIONS
                ):
                    return _closed_config(
                        f"{narrative_key}.{role} contains a malformed instrument."
                    )
                normalized_entry[role].append(
                    {
                        "asset": instrument["asset"],
                        "label": instrument["label"],
                        direction_key: instrument[direction_key],
                    }
                )
        normalized[narrative_key] = normalized_entry

    return {
        "mapping_version": payload["mapping_version"],
        "narratives": normalized,
        "valid": True,
        "errors": [],
    }


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def build_narrative_expression_profile(
    narrative_key: Any,
    expression_map: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a group or theme alias to its ordered curated expression profile."""
    config = expression_map or load_market_expression_map()
    if not isinstance(config, dict) or not config.get("valid"):
        return None
    sought = _normalize_key(narrative_key)
    for canonical, entry in config["narratives"].items():
        candidates = [canonical, *entry.get("aliases", [])]
        if sought not in {_normalize_key(candidate) for candidate in candidates}:
            continue
        return {
            "narrative_key": canonical,
            "mapping_version": config["mapping_version"],
            "primary": [dict(item) for item in entry["primary"]],
            "secondary": [dict(item) for item in entry["secondary"]],
            "offsets": [dict(item) for item in entry["offsets"]],
        }
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) == 15 and text[8] == "_":
        try:
            return datetime.strptime(text, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_instrument_expression(
    instrument: dict[str, Any],
    snapshot_record: dict[str, Any] | None,
    *,
    role: str,
    as_of: Any = None,
) -> dict[str, Any]:
    """Classify one mapped instrument from its persisted move and optional age."""
    result = {
        "asset": instrument["asset"],
        "label": instrument["label"],
        "role": "offset" if role == "offsets" else role,
        "move": "UNKNOWN",
        "status": "UNAVAILABLE",
        "pct_change": None,
        "missing": True,
        "stale": False,
    }
    if not isinstance(snapshot_record, dict):
        return result

    pct_change = snapshot_record.get("pct_change")
    if isinstance(pct_change, bool):
        pct_change = None
    try:
        pct_change = float(pct_change)
    except (TypeError, ValueError):
        return result

    observed_at = _parse_timestamp(
        snapshot_record.get("timestamp") or snapshot_record.get("as_of")
    )
    reference_time = _parse_timestamp(as_of)
    if observed_at and reference_time and reference_time - observed_at > STALE_DATA_MAX_AGE:
        result["stale"] = True
        return result

    move = classify_market_move(pct_change)
    result.update(
        {
            "move": move,
            "pct_change": round(pct_change, 4),
            "missing": False,
        }
    )
    if move == "FLAT":
        result["status"] = "MUTED"
        return result

    actual_direction = "UP" if move in UP_MOVES else "DOWN"
    if role == "offsets":
        pressure = actual_direction == instrument["pressure_direction"]
        result["status"] = "PRESSURE" if pressure else "ALIGNED"
    else:
        confirms = actual_direction == instrument["confirming_direction"]
        result["status"] = "CONFIRMING" if confirms else "DIVERGING"
    return result


def compute_expression_breadth(
    instruments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure ordered expression breadth and return exactly reconciling lists."""
    confirming = [
        item["asset"]
        for item in instruments
        if item["status"] in {"CONFIRMING", "ALIGNED"}
    ]
    diverging = [
        item["asset"]
        for item in instruments
        if item["status"] in {"DIVERGING", "PRESSURE"}
    ]
    unavailable = [
        item["asset"] for item in instruments if item["status"] == "UNAVAILABLE"
    ]
    core_confirming = [
        item for item in instruments
        if item["role"] in CORE_ROLES and item["status"] == "CONFIRMING"
    ]
    core_diverging = [
        item for item in instruments
        if item["role"] in CORE_ROLES and item["status"] == "DIVERGING"
    ]
    offset_pressure = [
        item for item in instruments
        if item["role"] == "offset" and item["status"] == "PRESSURE"
    ]

    if not any(
        item["role"] == "primary" and item["status"] != "UNAVAILABLE"
        for item in instruments
    ):
        breadth = "unavailable"
    elif core_confirming and core_diverging:
        breadth = "mixed"
    elif offset_pressure:
        breadth = "contradicted"
    elif len(core_confirming) >= BREADTH_THRESHOLDS["broad_confirming_assets"]:
        breadth = "broad"
    elif len(core_confirming) >= BREADTH_THRESHOLDS["concentrated_confirming_assets"]:
        breadth = "concentrated"
    elif core_diverging:
        breadth = "contradicted"
    else:
        breadth = "unavailable"

    return {
        "expression_breadth": breadth,
        "confirming_assets": confirming,
        "diverging_assets": diverging,
        "unavailable_assets": unavailable,
        "confirming_asset_count": len(confirming),
        "diverging_asset_count": len(diverging),
        "unavailable_asset_count": len(unavailable),
        "primary_expression_count": sum(
            item["role"] == "primary" for item in instruments
        ),
        "secondary_expression_count": sum(
            item["role"] == "secondary" for item in instruments
        ),
        "offset_signal_count": sum(
            item["role"] == "offset"
            and item["status"] not in {"UNAVAILABLE", "MUTED"}
            for item in instruments
        ),
    }


def classify_market_expression_state(
    instruments: list[dict[str, Any]],
    breadth: dict[str, Any] | None = None,
) -> str:
    """Apply the ratified state precedence to instrument classifications."""
    primary = [item for item in instruments if item["role"] == "primary"]
    core = [item for item in instruments if item["role"] in CORE_ROLES]
    primary_available = [item for item in primary if item["status"] != "UNAVAILABLE"]
    available = [item for item in instruments if item["status"] != "UNAVAILABLE"]
    if len(primary_available) < EXPRESSION_STATE_THRESHOLDS["minimum_primary_coverage"]:
        return "UNAVAILABLE"
    if available and all(item["status"] == "MUTED" for item in available):
        return "MUTED"

    primary_confirming = [item for item in primary if item["status"] == "CONFIRMING"]
    primary_diverging = [item for item in primary if item["status"] == "DIVERGING"]
    core_confirming = [item for item in core if item["status"] == "CONFIRMING"]
    core_diverging = [item for item in core if item["status"] == "DIVERGING"]
    offset_pressure = [
        item for item in instruments
        if item["role"] == "offset" and item["status"] == "PRESSURE"
    ]
    if primary_diverging and not primary_confirming:
        return "DIVERGING"
    if core_confirming and core_diverging:
        return "MIXED"

    partial_coverage = any(item["status"] == "UNAVAILABLE" for item in core)
    if primary_confirming and (offset_pressure or partial_coverage):
        return "PARTIALLY_CONFIRMING"
    expression_breadth = (breadth or compute_expression_breadth(instruments))[
        "expression_breadth"
    ]
    if (
        expression_breadth == "broad"
        and len(core_confirming)
        >= EXPRESSION_STATE_THRESHOLDS["broad_confirming_assets"]
        and not offset_pressure
        and not core_diverging
    ):
        return "STRONGLY_CONFIRMING"
    if core_confirming:
        return "CONFIRMING"
    return "MUTED"


def build_market_expression_limitations(
    instruments: list[dict[str, Any]],
) -> list[str]:
    """Describe missing and stale inputs without inventing a conclusion."""
    stale = [item["label"] for item in instruments if item["stale"]]
    missing = [
        item["label"]
        for item in instruments
        if item["status"] == "UNAVAILABLE" and not item["stale"]
    ]
    limitations = []
    if stale:
        limitations.append(
            f"Stale market data was excluded for {', '.join(stale)}."
        )
    if missing:
        limitations.append(
            f"Market data was unavailable for {', '.join(missing)}."
        )
    return limitations


def build_market_expression_summary(
    narrative_key: Any,
    market_snapshot: dict[str, Any] | None,
    *,
    as_of: Any = None,
    expression_map: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build byte-stable expression context from an ordered map and snapshot."""
    profile = build_narrative_expression_profile(narrative_key, expression_map)
    if profile is None:
        return None
    snapshot = market_snapshot if isinstance(market_snapshot, dict) else {}
    instruments = []
    for role in ROLES:
        for instrument in profile[role]:
            instruments.append(
                classify_instrument_expression(
                    instrument,
                    snapshot.get(instrument["asset"]),
                    role=role,
                    as_of=as_of,
                )
            )
    breadth = compute_expression_breadth(instruments)
    return {
        "narrative_key": profile["narrative_key"],
        "mapping_version": profile["mapping_version"],
        "state": classify_market_expression_state(instruments, breadth),
        **breadth,
        "instruments": instruments,
        "limitations": build_market_expression_limitations(instruments),
        "context_only": True,
        "is_signal": False,
        "thresholds_used": {
            **EXPRESSION_STATE_THRESHOLDS,
            "stale_data_max_age_hours": int(
                STALE_DATA_MAX_AGE.total_seconds() / 3600
            ),
        },
    }


def build_market_expression_for_run(
    run: dict[str, Any],
    narrative_key: Any = None,
) -> dict[str, Any] | None:
    """Evaluate one narrative from already-persisted run fields only."""
    if not isinstance(run, dict):
        return None
    key = narrative_key or run.get("dominant_group") or run.get("dominant_theme")
    return build_market_expression_summary(
        key,
        run.get("market_snapshot"),
        as_of=run.get("timestamp"),
    )
