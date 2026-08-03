"""Validated, deterministic read model for curated narrative relationships."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mne.narrative_signals import NARRATIVE_GROUPS
from mne.presentation_language import narrative_relationship_copy
from mne.presentation_language import narrative_display_name


DEFAULT_RELATIONSHIP_PATH = Path(__file__).resolve().parents[1] / "config" / "narrative_relationships.json"
RELATIONSHIP_TYPES = frozenset({"SUPPORTIVE", "DEPENDENCY", "OVERLAP", "TRANSMISSION", "OFFSETTING", "CONDITIONAL", "SHARED_DRIVER"})
DIRECTIONALITIES = frozenset({"SOURCE_TO_TARGET", "TARGET_TO_SOURCE", "BIDIRECTIONAL"})
STRENGTHS = frozenset({"STRONG", "MODERATE", "LIMITED"})
_STRENGTH_ORDER = {"STRONG": 0, "MODERATE": 1, "LIMITED": 2}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class NarrativeRelationshipError(ValueError):
    """Raised when curated relationship configuration is unavailable or invalid."""


@dataclass(frozen=True)
class NarrativeRelationship:
    source_group: str
    target_group: str
    relationship_type: str
    directionality: str
    strength: str
    public_label: str
    explanation: str
    display_enabled: bool
    evidence_basis: str


@dataclass(frozen=True)
class NarrativeRelationshipConfig:
    version: str
    relationships: tuple[NarrativeRelationship, ...]


def _required_text(item: dict, key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NarrativeRelationshipError(f"relationships[{index}].{key} must be a non-empty string")
    return value.strip()


def _sort_key(relationship: NarrativeRelationship) -> tuple:
    return (_STRENGTH_ORDER[relationship.strength], relationship.relationship_type, relationship.target_group, relationship.source_group)


def validate_relationship_config(data: Any) -> NarrativeRelationshipConfig:
    if not isinstance(data, dict):
        raise NarrativeRelationshipError("relationship config must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise NarrativeRelationshipError("version must use MAJOR.MINOR.PATCH semantic versioning")
    raw_relationships = data.get("relationships")
    if not isinstance(raw_relationships, list):
        raise NarrativeRelationshipError("relationships must be a list")
    relationships = []
    seen = set()
    for index, item in enumerate(raw_relationships):
        if not isinstance(item, dict):
            raise NarrativeRelationshipError(f"relationships[{index}] must be an object")
        source = _required_text(item, "source_group", index)
        target = _required_text(item, "target_group", index)
        if source not in NARRATIVE_GROUPS or target not in NARRATIVE_GROUPS:
            raise NarrativeRelationshipError(f"relationships[{index}] references an unknown narrative group")
        if source == target:
            raise NarrativeRelationshipError(f"relationships[{index}] cannot link a group to itself")
        relationship_type = _required_text(item, "relationship_type", index)
        directionality = _required_text(item, "directionality", index)
        strength = _required_text(item, "strength", index)
        if relationship_type not in RELATIONSHIP_TYPES:
            raise NarrativeRelationshipError(f"relationships[{index}].relationship_type is invalid")
        if directionality not in DIRECTIONALITIES:
            raise NarrativeRelationshipError(f"relationships[{index}].directionality is invalid")
        if strength not in STRENGTHS:
            raise NarrativeRelationshipError(f"relationships[{index}].strength is invalid")
        duplicate_key = (source, target, directionality)
        if duplicate_key in seen:
            raise NarrativeRelationshipError(f"relationships[{index}] duplicates an existing relationship")
        seen.add(duplicate_key)
        public_label = _required_text(item, "public_label", index)
        explanation = _required_text(item, "explanation", index)
        display_enabled = item.get("display_enabled")
        if not isinstance(display_enabled, bool):
            raise NarrativeRelationshipError(f"relationships[{index}].display_enabled must be boolean")
        evidence_basis = _required_text(item, "evidence_basis", index)
        relationships.append(NarrativeRelationship(source, target, relationship_type, directionality, strength, public_label, explanation, display_enabled, evidence_basis))
    return NarrativeRelationshipConfig(version, tuple(sorted(relationships, key=_sort_key)))


def load_narrative_relationships(path: str | Path = DEFAULT_RELATIONSHIP_PATH) -> NarrativeRelationshipConfig:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise NarrativeRelationshipError(f"unable to load narrative relationship config: {exc}") from exc
    return validate_relationship_config(data)


def _relationships(config: NarrativeRelationshipConfig | None) -> tuple[NarrativeRelationship, ...]:
    return (config or load_narrative_relationships()).relationships


def _resolved_endpoints(relationship: NarrativeRelationship) -> tuple[str, str]:
    if relationship.directionality == "TARGET_TO_SOURCE":
        return relationship.target_group, relationship.source_group
    return relationship.source_group, relationship.target_group


def get_relationships_for_group(group_key: str, config: NarrativeRelationshipConfig | None = None) -> tuple[dict, ...]:
    if group_key not in NARRATIVE_GROUPS:
        return ()
    output = []
    for relationship in _relationships(config):
        if not relationship.display_enabled:
            continue
        source, target = _resolved_endpoints(relationship)
        if relationship.directionality == "BIDIRECTIONAL" and group_key in (source, target):
            output.append((relationship, normalize_relationship(relationship, group_key)))
        elif group_key == source or group_key == target:
            output.append((relationship, normalize_relationship(relationship, group_key)))
    output.sort(key=lambda item: (_STRENGTH_ORDER[item[0].strength], item[0].relationship_type, item[1]["related_group"]))
    return tuple(public for _, public in output)


def get_display_relationships(config: NarrativeRelationshipConfig | None = None) -> tuple[NarrativeRelationship, ...]:
    return tuple(item for item in _relationships(config) if item.display_enabled)


def normalize_relationship(relationship: NarrativeRelationship, group_key: str | None = None) -> dict:
    source, target = _resolved_endpoints(relationship)
    related_group = target if group_key == source else source if group_key == target else target
    direction = "bidirectional" if relationship.directionality == "BIDIRECTIONAL" else "outbound" if group_key == source else "inbound"
    return {
        "related_group": related_group,
        "related_display_name": narrative_display_name(related_group),
        "label": relationship.public_label,
        "type_label": narrative_relationship_copy(f"type_{relationship.relationship_type}"),
        "strength_label": narrative_relationship_copy(f"strength_{relationship.strength}"),
        "explanation": relationship.explanation,
        "directionality": direction,
    }


def build_relationship_adjacency(config: NarrativeRelationshipConfig | None = None) -> dict[str, tuple[str, ...]]:
    adjacency = {group: set() for group in NARRATIVE_GROUPS}
    for relationship in get_display_relationships(config):
        adjacency[relationship.source_group].add(relationship.target_group)
        adjacency[relationship.target_group].add(relationship.source_group)
    return {group: tuple(sorted(related)) for group, related in adjacency.items()}


def build_relationship_summary(group_key: str, config: NarrativeRelationshipConfig | None = None) -> dict:
    relationships = get_relationships_for_group(group_key, config)
    return {"count": len(relationships), "labels": tuple(item["label"] for item in relationships)}


def relationship_exists(source: str, target: str, config: NarrativeRelationshipConfig | None = None) -> bool:
    for relationship in _relationships(config):
        resolved_source, resolved_target = _resolved_endpoints(relationship)
        if relationship.directionality == "BIDIRECTIONAL" and {source, target} == {resolved_source, resolved_target}:
            return True
        if source == resolved_source and target == resolved_target:
            return True
    return False
