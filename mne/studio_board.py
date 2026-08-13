"""Validated persistence for the one-per-account Studio board."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from mne.database import session_scope
from mne.models import StudioBoard
from mne.story_registry import StoryRegistryError, load_story_registry

SCHEMA_VERSION = 1
MAX_THESIS_LENGTH = 240
MAX_NODES = 40
MAX_CONNECTIONS = 80
BOARD_MAX_X = 1800
BOARD_MAX_Y = 1200
CONNECTION_LABELS = ("moves_with", "moves_against", "drives", "depends_on")
_MARKUP = re.compile(r"<[^>]*>")
_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


def empty_board() -> dict:
    return {"schema_version": SCHEMA_VERSION, "thesis": "", "nodes": [], "connections": []}


def _plain_text(value: Any) -> str:
    text = _CONTROLS.sub("", _MARKUP.sub("", str(value or "")))
    return " ".join(text.split())[:MAX_THESIS_LENGTH]


def _coordinate(value: Any, maximum: int) -> int:
    if isinstance(value, bool):
        value = 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if number != number:
        number = 0
    return round(max(0, min(maximum, number)))


def validate_board(payload: Any) -> dict:
    """Normalize a board, dropping dead references and rejecting unsafe shape/caps."""
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Invalid board payload.")
    raw_nodes = payload.get("nodes")
    raw_connections = payload.get("connections")
    if not isinstance(raw_nodes, list) or not isinstance(raw_connections, list):
        raise ValueError("Invalid board payload.")
    if len(raw_nodes) > MAX_NODES or len(raw_connections) > MAX_CONNECTIONS:
        raise ValueError("Board capacity exceeded.")
    try:
        valid_slugs = {story.slug for story in load_story_registry().stories}
    except (StoryRegistryError, OSError, ValueError) as exc:
        raise ValueError("Story registry is unavailable.") from exc

    nodes = []
    seen_ids = set()
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_id, kind, slug = item.get("id"), item.get("kind"), item.get("slug")
        if kind != "story" or slug not in valid_slugs:
            continue
        if not isinstance(node_id, str) or not _SAFE_ID.fullmatch(node_id) or node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        nodes.append({
            "id": node_id,
            "kind": "story",
            "slug": slug,
            "x": _coordinate(item.get("x"), BOARD_MAX_X),
            "y": _coordinate(item.get("y"), BOARD_MAX_Y),
        })

    connections = []
    seen_connections = set()
    for item in raw_connections:
        if not isinstance(item, dict):
            continue
        connection_id = item.get("id")
        source, target, label = item.get("from"), item.get("to"), item.get("label")
        if (
            not isinstance(connection_id, str)
            or not _SAFE_ID.fullmatch(connection_id)
            or connection_id in seen_connections
            or source not in seen_ids
            or target not in seen_ids
            or source == target
            or label not in CONNECTION_LABELS
        ):
            continue
        seen_connections.add(connection_id)
        connections.append({"id": connection_id, "from": source, "to": target, "label": label})

    return {
        "schema_version": SCHEMA_VERSION,
        "thesis": _plain_text(payload.get("thesis")),
        "nodes": nodes,
        "connections": connections,
    }


def load_board(user_id: str) -> dict:
    with session_scope() as db:
        row = db.get(StudioBoard, user_id)
        if not row:
            return empty_board()
        try:
            return validate_board(deepcopy(row.payload))
        except ValueError:
            return empty_board()


def save_board(user_id: str, payload: Any) -> dict:
    normalized = validate_board(payload)
    with session_scope() as db:
        row = db.get(StudioBoard, user_id) or StudioBoard(user_id=user_id)
        row.payload = deepcopy(normalized)
        db.add(row)
    return normalized
