"""Validated, account-owned persistence for Studio thesis boards."""

from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from mne.database import session_scope
from mne.models import StudioBoard
from mne.story_registry import StoryRegistryError, load_story_registry

SCHEMA_VERSION = 1
MAX_THESIS_LENGTH = 240
MAX_NODES = 40
MAX_CONNECTIONS = 80
BOARD_MAX_X = 1800
BOARD_MAX_Y = 1200
CONNECTION_LABELS = ("moves_with", "moves_against", "drives", "depends_on", "supports")
MAX_BOARDS = 25
MAX_EVIDENCE_PRIMARY_LENGTH = 200
MAX_EVIDENCE_META_LENGTH = 120
_MARKUP = re.compile(r"<[^>]*>")
_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


def empty_board() -> dict:
    return {"schema_version": SCHEMA_VERSION, "thesis": "", "nodes": [], "connections": []}


def _plain_text(value: Any, maximum: int = MAX_THESIS_LENGTH) -> str:
    text = _CONTROLS.sub("", _MARKUP.sub("", str(value or "")))
    return " ".join(text.split())[:maximum]


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
    requested_source_stories = {}
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_id, kind, slug = item.get("id"), item.get("kind"), item.get("slug")
        if not isinstance(node_id, str) or not _SAFE_ID.fullmatch(node_id) or node_id in seen_ids:
            continue
        node = {
            "id": node_id,
            "kind": kind,
            "x": _coordinate(item.get("x"), BOARD_MAX_X),
            "y": _coordinate(item.get("y"), BOARD_MAX_Y),
        }
        if kind == "story":
            if slug not in valid_slugs:
                continue
            node["slug"] = slug
        elif kind == "headline":
            title = _plain_text(item.get("title"), MAX_EVIDENCE_PRIMARY_LENGTH)
            if not title:
                continue
            node["title"] = title
            node["source"] = _plain_text(item.get("source"), MAX_EVIDENCE_META_LENGTH)
            requested_source_stories[node_id] = item.get("source_story")
        elif kind == "catalyst":
            name = _plain_text(item.get("name"), MAX_EVIDENCE_PRIMARY_LENGTH)
            if not name:
                continue
            node["name"] = name
            node["timing"] = _plain_text(item.get("timing"), MAX_EVIDENCE_META_LENGTH)
            requested_source_stories[node_id] = item.get("source_story")
        else:
            continue
        seen_ids.add(node_id)
        nodes.append(node)

    story_ids = {node["id"] for node in nodes if node["kind"] == "story"}
    nodes_by_id = {node["id"]: node for node in nodes}
    for node_id, source_story in requested_source_stories.items():
        if isinstance(source_story, str) and source_story in story_ids:
            nodes_by_id[node_id]["source_story"] = source_story

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
        if label == "supports":
            source_node = nodes_by_id[source]
            if source_node["kind"] not in {"headline", "catalyst"} or source_node.get("source_story") != target:
                continue
        seen_connections.add(connection_id)
        connections.append({"id": connection_id, "from": source, "to": target, "label": label})

    return {
        "schema_version": SCHEMA_VERSION,
        "thesis": _plain_text(payload.get("thesis")),
        "nodes": nodes,
        "connections": connections,
    }


def _owned_board(db, user_id: str, board_id: str) -> StudioBoard | None:
    return db.scalar(
        select(StudioBoard).where(
            StudioBoard.board_id == board_id,
            StudioBoard.user_id == user_id,
        )
    )


def list_boards(user_id: str) -> list[dict]:
    """Return card-sized projections for one account, newest first."""
    with session_scope() as db:
        rows = db.execute(
            select(StudioBoard.board_id, StudioBoard.payload, StudioBoard.updated_at)
            .where(StudioBoard.user_id == user_id)
            .order_by(StudioBoard.updated_at.desc(), StudioBoard.board_id.desc())
        ).all()
    boards = []
    for board_id, payload, updated_at in rows:
        try:
            normalized = validate_board(deepcopy(payload))
        except ValueError:
            normalized = empty_board()
        boards.append({
            "board_id": board_id,
            "thesis": normalized["thesis"],
            "node_count": len(normalized["nodes"]),
            "connection_count": len(normalized["connections"]),
            "updated_at": updated_at,
            "preview_nodes": [
                {"x": node["x"], "y": node["y"]}
                for node in normalized["nodes"][:8]
            ],
        })
    return boards


def create_board(user_id: str) -> str:
    with session_scope() as db:
        count = db.scalar(select(func.count()).select_from(StudioBoard).where(StudioBoard.user_id == user_id))
        if count >= MAX_BOARDS:
            raise ValueError("Thesis capacity exceeded.")
        board_id = str(uuid.uuid4())
        db.add(StudioBoard(board_id=board_id, user_id=user_id, payload=empty_board()))
    return board_id


def load_board(user_id: str, board_id: str) -> dict | None:
    with session_scope() as db:
        row = _owned_board(db, user_id, board_id)
        if not row:
            return None
        try:
            return validate_board(deepcopy(row.payload))
        except ValueError:
            return empty_board()


def save_board(user_id: str, board_id: str, payload: Any) -> dict:
    normalized = validate_board(payload)
    with session_scope() as db:
        row = _owned_board(db, user_id, board_id)
        if not row:
            raise KeyError(board_id)
        row.payload = deepcopy(normalized)
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return normalized


def delete_board(user_id: str, board_id: str) -> bool:
    with session_scope() as db:
        row = _owned_board(db, user_id, board_id)
        if not row:
            return False
        db.delete(row)
    return True
