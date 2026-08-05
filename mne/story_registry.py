"""Validated, deterministic read model for curated sub-narrative stories."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mne.narrative_signals import NARRATIVE_GROUPS
from mne.sector_isolation import SECTOR_KEYS
from mne.theme_analysis import load_taxonomy_config


DEFAULT_STORY_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "story_registry.json"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_SLUG = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_TIERS = ("strong", "medium", "weak")


class StoryRegistryError(ValueError):
    """Raised when curated story configuration is unavailable or invalid."""


@dataclass(frozen=True)
class StoryKeywords:
    strong: tuple[str, ...]
    medium: tuple[str, ...]
    weak: tuple[str, ...]

    def as_dict(self) -> dict[str, tuple[str, ...]]:
        return {tier: getattr(self, tier) for tier in _TIERS}


@dataclass(frozen=True)
class Story:
    slug: str
    display_name: str
    group: str
    themes: tuple[str, ...]
    keywords: StoryKeywords
    driving_sectors: tuple[str, ...]
    catalyst_names: tuple[str, ...]
    connected: tuple[str, ...]


@dataclass(frozen=True)
class StoryRegistry:
    version: str
    stories: tuple[Story, ...]


def _required_text(item: dict, key: str, location: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StoryRegistryError(f"{location}.{key} must be a non-empty string")
    return value.strip()


def _text_list(item: dict, key: str, location: str, *, required: bool = False) -> tuple[str, ...]:
    value = item.get(key)
    if not isinstance(value, list) or required and not value:
        qualifier = "a non-empty list" if required else "a list"
        raise StoryRegistryError(f"{location}.{key} must be {qualifier}")
    if any(not isinstance(entry, str) or not entry.strip() for entry in value):
        raise StoryRegistryError(f"{location}.{key} must contain non-empty strings")
    normalized = [entry.strip() for entry in value]
    if len(normalized) != len(set(normalized)):
        raise StoryRegistryError(f"{location}.{key} must not contain duplicates")
    return tuple(sorted(normalized))


def validate_story_registry(data: Any) -> StoryRegistry:
    if not isinstance(data, dict):
        raise StoryRegistryError("story registry must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise StoryRegistryError("version must use MAJOR.MINOR.PATCH semantic versioning")
    raw_stories = data.get("stories")
    if not isinstance(raw_stories, dict):
        raise StoryRegistryError("stories must be an object")

    taxonomy_themes = set(load_taxonomy_config()["themes"])
    stories = []
    for slug, item in raw_stories.items():
        location = f"stories[{slug}]"
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise StoryRegistryError(f"{location}.slug must be a stable lowercase slug")
        if not isinstance(item, dict):
            raise StoryRegistryError(f"{location} must be an object")
        display_name = _required_text(item, "display_name", location)
        group = _required_text(item, "group", location)
        if group not in NARRATIVE_GROUPS:
            raise StoryRegistryError(f"{location}.group references an unknown narrative group")
        themes = _text_list(item, "themes", location, required=True)
        eligible_themes = set(NARRATIVE_GROUPS[group]) & taxonomy_themes
        if any(theme not in eligible_themes for theme in themes):
            raise StoryRegistryError(f"{location}.themes must belong to the group and taxonomy")

        raw_keywords = item.get("keywords")
        if not isinstance(raw_keywords, dict) or set(raw_keywords) != set(_TIERS):
            raise StoryRegistryError(f"{location}.keywords must contain strong, medium, and weak lists")
        keyword_tiers = {
            tier: _text_list(raw_keywords, tier, f"{location}.keywords") for tier in _TIERS
        }
        if not any(keyword_tiers.values()):
            raise StoryRegistryError(f"{location}.keywords must contain at least one keyword")

        driving_sectors = _text_list(item, "driving_sectors", location)
        if any(sector not in SECTOR_KEYS for sector in driving_sectors):
            raise StoryRegistryError(f"{location}.driving_sectors contains an invalid sector key")
        catalyst_names = _text_list(item, "catalyst_names", location)
        connected = _text_list(item, "connected", location)
        if slug in connected:
            raise StoryRegistryError(f"{location}.connected cannot link a story to itself")
        stories.append(Story(
            slug=slug,
            display_name=display_name,
            group=group,
            themes=themes,
            keywords=StoryKeywords(**keyword_tiers),
            driving_sectors=driving_sectors,
            catalyst_names=catalyst_names,
            connected=connected,
        ))

    slugs = set(raw_stories)
    for story in stories:
        missing = [slug for slug in story.connected if slug not in slugs]
        if missing:
            raise StoryRegistryError(f"stories[{story.slug}].connected references an unknown story slug")
    return StoryRegistry(version, tuple(sorted(stories, key=lambda story: (story.group, story.slug))))


def load_story_registry(path: str | Path = DEFAULT_STORY_REGISTRY_PATH) -> StoryRegistry:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StoryRegistryError(f"unable to load story registry: {exc}") from exc
    return validate_story_registry(data)
