"""Local, anonymous, single-profile personalization persistence."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from config import get_data_dir
from mne.story_registry import StoryRegistryError, load_story_registry

PREFERENCES_SCHEMA_VERSION = 1
"""Schema version for the anonymous local preference profile."""

SUPPORTED_ALERT_TYPES = (
    "NARRATIVE_BECAME_DOMINANT",
    "NARRATIVE_BUILDING_AGAIN",
    "NARRATIVE_FADING",
    "NARRATIVE_RETURNED",
    "DOMINANT_NARRATIVE_CHANGED",
    "MARKET_EXPRESSION_CHANGED_MATERIALLY",
    "EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE",
    "HISTORICAL_CONNECTION_MEANINGFULLY_STRONG",
)
"""Alert types exposed by the local preference model."""

_NARRATIVE_LEVELS = ("theme", "group")
_VIEW_TYPES = ("investigation", "comparison")
_SAFE_REPLAY_ID = re.compile(r"^replay_[A-Za-z0-9][A-Za-z0-9_.-]{2,119}$")


def preferences_path(data_dir: Path | None = None) -> Path:
    return (data_dir or get_data_dir()) / "preferences" / "profile.json"


def alert_state_path(data_dir: Path | None = None) -> Path:
    return (data_dir or get_data_dir()) / "preferences" / "alert_state.json"


def build_default_preferences() -> dict[str, Any]:
    """Build a fresh deterministic local profile."""
    return {
        "schema_version": PREFERENCES_SCHEMA_VERSION,
        "profile_type": "anonymous_local_single_profile",
        "enabled": True,
        "followed_narratives": [],
        "saved_stories": [],
        "saved_historical_views": [],
        "preferred_alert_types": list(SUPPORTED_ALERT_TYPES),
        "alert_thresholds": {},
        "alert_rules": [],
        "limitation_note": None,
    }


def validate_preferences(value: Any) -> dict[str, Any] | None:
    """Return a normalized profile or fail closed with ``None``."""
    if not isinstance(value, dict) or value.get("schema_version") != PREFERENCES_SCHEMA_VERSION:
        return None
    result = build_default_preferences()
    if not isinstance(value.get("enabled"), bool):
        return None
    result["enabled"] = value["enabled"]

    followed = value.get("followed_narratives")
    if not isinstance(followed, list):
        return None
    normalized_followed = []
    for item in followed:
        if not isinstance(item, dict):
            return None
        level, key = item.get("narrative_level"), item.get("narrative_key")
        if level not in _NARRATIVE_LEVELS or not _safe_key(key):
            return None
        record = {"narrative_level": level, "narrative_key": str(key)}
        if record not in normalized_followed:
            normalized_followed.append(record)
    result["followed_narratives"] = normalized_followed

    saved_stories = value.get("saved_stories")
    if not isinstance(saved_stories, list):
        return None
    try:
        valid_story_slugs = {story.slug for story in load_story_registry().stories}
    except (StoryRegistryError, OSError, ValueError):
        return None
    normalized_stories = []
    seen_story_slugs = set()
    for item in saved_stories:
        if not isinstance(item, dict):
            return None
        story_slug, tracked = item.get("story_slug"), item.get("tracked")
        if story_slug not in valid_story_slugs or not isinstance(tracked, bool):
            return None
        if story_slug not in seen_story_slugs:
            normalized_stories.append({"story_slug": story_slug, "tracked": tracked})
            seen_story_slugs.add(story_slug)
    result["saved_stories"] = normalized_stories

    views = value.get("saved_historical_views")
    if not isinstance(views, list):
        return None
    normalized_views = []
    for item in views:
        normalized = _validate_saved_view(item)
        if normalized is None:
            return None
        if normalized not in normalized_views:
            normalized_views.append(normalized)
    result["saved_historical_views"] = normalized_views

    preferred = value.get("preferred_alert_types")
    if not isinstance(preferred, list) or any(item not in SUPPORTED_ALERT_TYPES for item in preferred):
        return None
    result["preferred_alert_types"] = [item for item in SUPPORTED_ALERT_TYPES if item in preferred]
    if not isinstance(value.get("alert_thresholds", {}), dict):
        return None
    result["alert_thresholds"] = deepcopy(value.get("alert_thresholds", {}))
    if not isinstance(value.get("alert_rules", []), list):
        return None
    result["alert_rules"] = deepcopy(value.get("alert_rules", []))
    return result


def load_preferences(data_dir: Path | None = None) -> dict[str, Any]:
    path = preferences_path(data_dir)
    try:
        normalized = validate_preferences(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        normalized = None
    if normalized is not None:
        return normalized
    default = build_default_preferences()
    default["limitation_note"] = (
        "Local preferences were unavailable or invalid, so safe defaults are being used."
    )
    return default


def save_preferences(profile: dict[str, Any], data_dir: Path | None = None) -> dict[str, Any]:
    normalized = validate_preferences(profile)
    if normalized is None:
        raise ValueError("Invalid local preference profile.")
    _atomic_json_write(preferences_path(data_dir), normalized)
    return normalized


def follow_narrative(profile: dict, narrative_level: str, narrative_key: str) -> dict:
    if narrative_level not in _NARRATIVE_LEVELS or not _safe_key(narrative_key):
        raise ValueError("Invalid narrative selection.")
    result = deepcopy(profile)
    record = {"narrative_level": narrative_level, "narrative_key": narrative_key}
    if record not in result["followed_narratives"]:
        result["followed_narratives"].append(record)
    return result


def unfollow_narrative(profile: dict, narrative_level: str, narrative_key: str) -> dict:
    result = deepcopy(profile)
    result["followed_narratives"] = [
        item for item in result["followed_narratives"]
        if not (item["narrative_level"] == narrative_level and item["narrative_key"] == narrative_key)
    ]
    return result


def save_story(profile: dict, story_slug: str) -> dict:
    try:
        valid_story_slugs = {story.slug for story in load_story_registry().stories}
    except (StoryRegistryError, OSError, ValueError) as exc:
        raise ValueError("Story registry is unavailable.") from exc
    if story_slug not in valid_story_slugs:
        raise ValueError("Invalid story selection.")
    result = deepcopy(profile)
    if not any(item["story_slug"] == story_slug for item in result["saved_stories"]):
        result["saved_stories"].append({"story_slug": story_slug, "tracked": False})
    return result


def unsave_story(profile: dict, story_slug: str) -> dict:
    result = deepcopy(profile)
    result["saved_stories"] = [
        item for item in result["saved_stories"] if item["story_slug"] != story_slug
    ]
    return result


def set_story_tracked(profile: dict, story_slug: str, tracked: bool) -> dict:
    if not isinstance(tracked, bool):
        raise ValueError("Invalid tracked state.")
    result = deepcopy(profile)
    for item in result["saved_stories"]:
        if item["story_slug"] == story_slug:
            item["tracked"] = tracked
            break
    return result


def save_historical_view(
    profile: dict,
    view_type: str,
    replay_ids: list[str],
    *,
    label: str | None = None,
) -> dict:
    if view_type not in _VIEW_TYPES:
        raise ValueError("Invalid historical view type.")
    expected = 1 if view_type == "investigation" else 2
    if len(replay_ids) != expected or len(set(replay_ids)) != expected:
        raise ValueError("Invalid historical view reference.")
    if any(not isinstance(item, str) or not _SAFE_REPLAY_ID.fullmatch(item) for item in replay_ids):
        raise ValueError("Invalid historical view reference.")
    result = deepcopy(profile)
    record = {
        "view_type": view_type,
        "replay_ids": list(replay_ids),
        "label": _safe_view_label(label, replay_ids, view_type),
    }
    identity = (view_type, tuple(replay_ids))
    result["saved_historical_views"] = [
        item for item in result["saved_historical_views"]
        if (item["view_type"], tuple(item["replay_ids"])) != identity
    ]
    result["saved_historical_views"].append(record)
    return result


def remove_historical_view(profile: dict, view_type: str, replay_ids: list[str]) -> dict:
    result = deepcopy(profile)
    result["saved_historical_views"] = [
        item for item in result["saved_historical_views"]
        if not (item["view_type"] == view_type and item["replay_ids"] == replay_ids)
    ]
    return result


def historical_view_url(view: dict) -> str:
    ids = view["replay_ids"]
    if view["view_type"] == "investigation":
        return f"/history/{ids[0]}"
    return f"/studio/compare?replay_a={ids[0]}&replay_b={ids[1]}"


def _validate_saved_view(item: Any) -> dict | None:
    if not isinstance(item, dict) or item.get("view_type") not in _VIEW_TYPES:
        return None
    ids = item.get("replay_ids")
    expected = 1 if item["view_type"] == "investigation" else 2
    if not isinstance(ids, list) or len(ids) != expected or len(set(ids)) != expected:
        return None
    if any(not isinstance(value, str) or not _SAFE_REPLAY_ID.fullmatch(value) for value in ids):
        return None
    label = item.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        return None
    return {"view_type": item["view_type"], "replay_ids": list(ids), "label": label.strip()}


def _safe_key(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 120 and bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 /&+_.-]*", value)
    )


def _safe_view_label(label: str | None, replay_ids: list[str], view_type: str) -> str:
    if isinstance(label, str) and label.strip() and len(label.strip()) <= 120:
        return label.strip()
    dates = [re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", item) for item in replay_ids]
    rendered = []
    for match in dates:
        if match:
            try:
                rendered.append(date(int(match[1]), int(match[2]), int(match[3])).strftime("%B %Y"))
            except ValueError:
                pass
    if view_type == "comparison" and len(rendered) == 2:
        return f"Comparison — {rendered[0]} and {rendered[1]}"
    if rendered:
        return f"Reconstruction — {rendered[0]}"
    return "Saved historical comparison" if view_type == "comparison" else "Saved historical investigation"


def _atomic_json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)
