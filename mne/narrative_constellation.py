"""Deterministic, read-only presentation context for Narrative Constellation.

Visual encoding is intentionally hand-derivable: group size uses current score
relative to the visible maximum (52--74px), theme size uses the same bounded
mapping (24--34px), the dominant group is centered, and remaining groups use
rank-stable radial positions with key-sorted tie breaks. Themes use confirmed
``NARRATIVE_GROUPS`` membership and sit at fixed angles around their parent.
Direction uses persisted lifecycle behavior first, then persisted acceleration
or pulse only when lifecycle is missing/non-directional; conflicting directional
signals degrade to Stable. Strengthening, weakening, and neutral are expressed
with the dashboard's existing up, down, and slate treatments plus text/icons.

Cross-group relationships are loaded only from curated configuration. No
relationship is inferred from wording, movement, or proximity.
The module performs no fetching, scoring, taxonomy mutation, or persistence.
"""

from __future__ import annotations

import json
import math
from typing import Any

from mne.explanation_layer import explain_lifecycle_state
from mne.narrative_signals import NARRATIVE_GROUPS
from mne.narrative_relationships import (
    NarrativeRelationshipError,
    build_relationship_adjacency,
    get_display_relationships,
    normalize_relationship,
)
from mne.presentation_language import constellation_copy, narrative_display_name
from mne.research_workspace import narrative_key


GROUP_LIMIT = 5
THEME_LIMIT = 3
_RELATIONSHIP_STRENGTH_ORDER = {"STRONG": 0, "MODERATE": 1, "LIMITED": 2}
_DIRECTIONAL_LIFECYCLE = {
    "BUILDING": "Strengthening",
    "EMERGING": "Strengthening",
    "RECURRING": "Strengthening",
    "RE-ACCELERATING": "Strengthening",
    "RE_ACCELERATING": "Strengthening",
    "FADING": "Weakening",
    "DORMANT": "Weakening",
    "ABSENT": "Weakening",
}
_STRENGTHENING = {"ACCELERATING", "RISING", "BUILDING", "EMERGING", "STRONG"}
_WEAKENING = {"COOLING", "FADING", "LOSING", "DORMANT"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _records(memory: Any, level: str) -> dict[str, dict]:
    if not isinstance(memory, dict):
        return {}
    values = memory.get("groups" if level == "group" else "themes")
    if not isinstance(values, list):
        return {}
    return {
        str(item["name"]): item
        for item in values
        if isinstance(item, dict) and item.get("name") not in (None, "")
    }


def _signal_direction(*values: Any) -> str:
    directions = set()
    for value in values:
        token = str(value or "").strip().upper().replace(" ", "_")
        if token in _STRENGTHENING:
            directions.add("Strengthening")
        elif token in _WEAKENING:
            directions.add("Weakening")
    return directions.pop() if len(directions) == 1 else "Stable"


def derive_direction(lifecycle_state: Any, acceleration: Any = None, pulse: Any = None) -> str:
    """Apply the ratified lifecycle-first precedence without combining signals."""
    lifecycle = str(lifecycle_state or "").strip().upper().replace(" ", "_")
    lifecycle_direction = _DIRECTIONAL_LIFECYCLE.get(lifecycle)
    fallback = _signal_direction(acceleration, pulse)
    if lifecycle_direction:
        if fallback != "Stable" and fallback != lifecycle_direction:
            return "Stable"
        return lifecycle_direction
    return fallback


def normalize_constellation_node(
    *, key: Any, score: Any, level: str, rank: int, total_score: float,
    dominant: bool = False, parent_group: str | None = None,
    memory_record: dict | None = None, pulse: dict | None = None,
    dynamics: dict | None = None,
) -> dict | None:
    """Normalize one persisted score entry; malformed/zero entries fail closed."""
    numeric = _number(score)
    if not isinstance(key, str) or not key.strip() or numeric is None or numeric <= 0:
        return None
    memory_record = memory_record if isinstance(memory_record, dict) else {}
    pulse = pulse if isinstance(pulse, dict) else {}
    dynamics = dynamics if isinstance(dynamics, dict) else {}
    lifecycle = memory_record.get("memory_state")
    acceleration = dynamics.get("acceleration")
    pulse_state = pulse.get("pulse_state")
    direction = derive_direction(lifecycle, acceleration, pulse_state)
    display_name = narrative_display_name(key)
    state_label = str(lifecycle).replace("_", " ").title() if lifecycle else None
    explanation = memory_record.get("plain_language_summary")
    if not explanation:
        explanation = explain_lifecycle_state(display_name, lifecycle or ("DOMINANT" if dominant else "PERSISTENT"))
    share = round((numeric / total_score) * 100, 1) if total_score > 0 else None
    return {
        "key": narrative_key(level, key),
        "taxonomy_key": key,
        "display_name": display_name,
        "level": level,
        "score": round(numeric, 2),
        "share": share,
        "rank": rank,
        "dominant": bool(dominant),
        "lifecycle_state": state_label,
        "direction": direction,
        "direction_tone": "up" if direction == "Strengthening" else "down" if direction == "Weakening" else "neutral",
        "direction_icon": "↑" if direction == "Strengthening" else "↓" if direction == "Weakening" else "→",
        "parent_group": parent_group,
        "related_keys": [],
        "explanation": explanation,
        "href": f"/research/{narrative_key(level, key)}",
    }


def select_visible_nodes(run: dict, max_groups: int = GROUP_LIMIT, max_themes: int = THEME_LIMIT) -> list[dict]:
    """Select 3--5 positive groups and at most three confirmed themes per group."""
    group_scores = run.get("group_scores") if isinstance(run.get("group_scores"), dict) else {}
    theme_scores = run.get("theme_scores") or run.get("theme_counts")
    theme_scores = theme_scores if isinstance(theme_scores, dict) else {}
    positive_groups = [(str(k), _number(v)) for k, v in group_scores.items() if _number(v) and _number(v) > 0]
    positive_groups.sort(key=lambda item: (-item[1], item[0]))
    positive_groups = positive_groups[: max(1, min(GROUP_LIMIT, max_groups))]
    total_groups = sum(score for _, score in positive_groups)
    memory = run.get("narrative_memory")
    group_memory, theme_memory = _records(memory, "group"), _records(memory, "theme")
    pulse = run.get("narrative_pulse") if isinstance(run.get("narrative_pulse"), dict) else {}
    dynamics = run.get("narrative_dynamics") if isinstance(run.get("narrative_dynamics"), dict) else {}
    dynamic_groups = dynamics.get("groups") if isinstance(dynamics.get("groups"), dict) else {}
    dominant_group = run.get("dominant_group") or (positive_groups[0][0] if positive_groups else None)
    nodes = []
    for index, (group, score) in enumerate(positive_groups, 1):
        node = normalize_constellation_node(
            key=group, score=score, level="group", rank=index, total_score=total_groups,
            dominant=group == dominant_group or index == 1, memory_record=group_memory.get(group),
            pulse=pulse.get(group), dynamics=dynamic_groups.get(group),
        )
        if node:
            nodes.append(node)
        confirmed = NARRATIVE_GROUPS.get(group, [])
        ranked_themes = sorted(
            ((theme, _number(theme_scores.get(theme))) for theme in confirmed),
            key=lambda item: (-(item[1] or 0), item[0]),
        )
        ranked_themes = [(theme, value) for theme, value in ranked_themes if value and value > 0][:max_themes]
        theme_total = sum(value for _, value in ranked_themes)
        for theme_rank, (theme, theme_score) in enumerate(ranked_themes, 1):
            theme_node = normalize_constellation_node(
                key=theme, score=theme_score, level="theme", rank=theme_rank,
                total_score=theme_total, parent_group=group,
                memory_record=theme_memory.get(theme),
            )
            if theme_node:
                nodes.append(theme_node)
    return nodes


def build_group_theme_relationships(nodes: list[dict]) -> list[dict]:
    """Return confirmed taxonomy membership only; never infer relationships."""
    group_keys = {node["taxonomy_key"]: node["key"] for node in nodes if node.get("level") == "group"}
    relationships = []
    for node in nodes:
        parent = node.get("parent_group")
        if node.get("level") == "theme" and parent in group_keys and node["taxonomy_key"] in NARRATIVE_GROUPS.get(parent, []):
            relationships.append({"source": group_keys[parent], "target": node["key"], "type": "group_theme"})
    return sorted(relationships, key=lambda item: (item["source"], item["target"]))


def build_cross_group_relationships(nodes: list[dict]) -> list[dict]:
    """Return visible curated group edges; config failures omit this layer."""
    group_keys = {node["taxonomy_key"]: node["key"] for node in nodes if node.get("level") == "group"}
    try:
        configured = get_display_relationships()
    except NarrativeRelationshipError:
        return []
    relationships = []
    for relationship in configured:
        if relationship.source_group not in group_keys or relationship.target_group not in group_keys:
            continue
        public = normalize_relationship(relationship)
        relationships.append({
            "source": group_keys[relationship.source_group],
            "target": group_keys[relationship.target_group],
            "type": "cross_group",
            "relationship_type": relationship.relationship_type,
            "strength": relationship.strength,
            "label": public["label"],
            "type_label": public["type_label"],
            "strength_label": public["strength_label"],
            "explanation": public["explanation"],
            "directionality": public["directionality"],
        })
    return sorted(relationships, key=lambda item: (_RELATIONSHIP_STRENGTH_ORDER[item["strength"]], item["relationship_type"], item["target"]))


def compute_deterministic_positions(nodes: list[dict], width: int = 800, height: int = 430) -> dict[str, dict]:
    """Compute fixed radial positions with rank then key as the stable order."""
    groups = sorted((n for n in nodes if n.get("level") == "group"), key=lambda n: (n["rank"], n["key"]))
    themes = [n for n in nodes if n.get("level") == "theme"]
    positions = {}
    center_x, center_y = width / 2, height / 2
    if groups:
        positions[groups[0]["key"]] = {"x": center_x, "y": center_y}
    outer = groups[1:]
    for index, node in enumerate(outer):
        angle = (-math.pi / 2) + (2 * math.pi * index / max(1, len(outer)))
        positions[node["key"]] = {"x": center_x + 245 * math.cos(angle), "y": center_y + 145 * math.sin(angle)}
    for group in groups:
        children = sorted((n for n in themes if n.get("parent_group") == group["taxonomy_key"]), key=lambda n: (n["rank"], n["key"]))
        base = positions[group["key"]]
        for index, child in enumerate(children):
            angle = (-math.pi / 2) + (2 * math.pi * index / max(1, len(children)))
            positions[child["key"]] = {"x": base["x"] + 92 * math.cos(angle), "y": base["y"] + 72 * math.sin(angle)}
    return {key: {"x": round(value["x"], 2), "y": round(value["y"], 2)} for key, value in sorted(positions.items())}


def _apply_visuals(nodes: list[dict], positions: dict[str, dict]) -> list[dict]:
    group_scores = [n["score"] for n in nodes if n["level"] == "group"] or [1]
    theme_scores = [n["score"] for n in nodes if n["level"] == "theme"] or [1]
    output = []
    for node in nodes:
        maximum = max(group_scores if node["level"] == "group" else theme_scores)
        minimum, maximum_radius = ((52, 74) if node["level"] == "group" else (24, 34))
        radius = minimum + (maximum_radius - minimum) * (node["score"] / maximum if maximum else 0)
        state_bits = ["dominant" if node["dominant"] else None]
        if str(node["lifecycle_state"] or "").casefold() != "dominant":
            state_bits.append(node["lifecycle_state"])
        state_bits.append(node["direction"])
        output.append({**node, **positions[node["key"]], "radius": round(radius, 2),
            "sr_label": " — ".join(str(bit).lower() if index else str(bit) for index, bit in enumerate([node["display_name"], *state_bits]) if bit)})
    return output


def build_constellation_summary(nodes: list[dict]) -> str:
    groups = [node for node in nodes if node.get("level") == "group"]
    if not groups:
        return constellation_copy("empty")
    leader = groups[0]
    return constellation_copy("summary").format(name=leader["display_name"], direction=leader["direction"].lower())


def build_constellation_empty_state() -> dict:
    return {"title": constellation_copy("empty_title"), "body": constellation_copy("empty")}


def validate_constellation_context(context: Any) -> dict:
    if not isinstance(context, dict) or not isinstance(context.get("nodes"), list):
        return {"nodes": [], "relationships": [], "has_data": False, "empty_state": build_constellation_empty_state()}
    valid = [n for n in context["nodes"] if isinstance(n, dict) and n.get("key") and n.get("display_name") and _number(n.get("x")) is not None and _number(n.get("y")) is not None]
    keys = {n["key"] for n in valid}
    relationships = [r for r in context.get("relationships", []) if isinstance(r, dict) and r.get("source") in keys and r.get("target") in keys]
    return {**context, "nodes": valid, "relationships": relationships, "has_data": any(n["level"] == "group" for n in valid)}


def build_constellation_context(run: Any) -> dict:
    """Build a JSON-stable context solely from one already-persisted run."""
    if not isinstance(run, dict):
        return validate_constellation_context({})
    selected = select_visible_nodes(run)
    positions = compute_deterministic_positions(selected)
    nodes = _apply_visuals(selected, positions)
    cross_group_relationships = build_cross_group_relationships(nodes)
    try:
        adjacency = build_relationship_adjacency()
    except NarrativeRelationshipError:
        adjacency = {}
    for node in nodes:
        if node["level"] == "group":
            node["related_keys"] = list(adjacency.get(node["taxonomy_key"], ()))
            node["relationship_details"] = [
                {key: relation[key] for key in ("label", "type_label", "strength_label", "explanation", "directionality")}
                for relation in cross_group_relationships
                if node["key"] in (relation["source"], relation["target"])
            ]
    relationships = build_group_theme_relationships(nodes) + cross_group_relationships
    context = {
        "width": 800, "height": 430, "nodes": nodes, "relationships": relationships,
        "has_data": bool(nodes), "has_themes": any(n["level"] == "theme" for n in nodes),
        "summary": build_constellation_summary(nodes), "empty_state": build_constellation_empty_state(),
        "copy": {key: constellation_copy(key) for key in ("eyebrow", "title", "framing", "research", "xray", "xray_explanation", "themes_unavailable")},
    }
    # A canonical JSON round-trip also prevents incidental dict subclass/order leakage.
    return validate_constellation_context(json.loads(json.dumps(context, sort_keys=True)))
