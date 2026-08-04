"""Validated, deterministic read model for curated narrative-to-sector structure."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from mne.narrative_signals import NARRATIVE_GROUPS
from mne.presentation_language import sector_isolation_copy


DEFAULT_SECTOR_MAP_PATH = Path(__file__).resolve().parents[1] / "config" / "narrative_sector_map.json"
SECTOR_KEYS = {
    "technology": "Technology", "communication_services": "Communication Services",
    "consumer_discretionary": "Consumer Discretionary", "financials": "Financials",
    "industrials": "Industrials", "energy": "Energy", "materials": "Materials",
    "utilities": "Utilities", "real_estate": "Real Estate",
    "consumer_staples": "Consumer Staples", "health_care": "Health Care",
}
STRUCTURAL_ROLES = frozenset({"PRIMARY", "SECONDARY", "EMERGING", "OFFSET", "DETACHED"})
PARTICIPATION_STATES = frozenset({"STRONG", "PARTICIPATING", "EMERGING", "MIXED", "DETACHED", "CONTRADICTING", "UNAVAILABLE"})
_ROLE_ORDER = {"PRIMARY": 0, "SECONDARY": 1, "EMERGING": 2, "OFFSET": 3, "DETACHED": 4}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SectorIsolationError(ValueError):
    """Raised when curated sector configuration is unavailable or invalid."""


@dataclass(frozen=True)
class SectorMapping:
    sector: str
    role: str
    rationale: str
    display_enabled: bool


@dataclass(frozen=True)
class SectorMapConfig:
    version: str
    narratives: tuple[tuple[str, tuple[SectorMapping, ...]], ...]


def _required_text(item: dict, key: str, location: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SectorIsolationError(f"{location}.{key} must be a non-empty string")
    return value.strip()


def validate_sector_map(data: Any) -> SectorMapConfig:
    if not isinstance(data, dict):
        raise SectorIsolationError("sector map must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise SectorIsolationError("version must use MAJOR.MINOR.PATCH semantic versioning")
    raw_narratives = data.get("narratives")
    if not isinstance(raw_narratives, dict):
        raise SectorIsolationError("narratives must be an object")
    narratives = []
    for narrative in sorted(raw_narratives):
        if narrative not in NARRATIVE_GROUPS:
            raise SectorIsolationError(f"unknown narrative group: {narrative}")
        record = raw_narratives[narrative]
        if not isinstance(record, dict) or not isinstance(record.get("sectors"), list):
            raise SectorIsolationError(f"narratives.{narrative}.sectors must be a list")
        sectors, seen = [], set()
        for index, item in enumerate(record["sectors"]):
            location = f"narratives.{narrative}.sectors[{index}]"
            if not isinstance(item, dict):
                raise SectorIsolationError(f"{location} must be an object")
            sector = _required_text(item, "sector", location)
            role = _required_text(item, "role", location)
            rationale = _required_text(item, "rationale", location)
            if sector not in SECTOR_KEYS:
                raise SectorIsolationError(f"{location}.sector is invalid")
            if sector in seen:
                raise SectorIsolationError(f"{location} duplicates a sector")
            if role not in STRUCTURAL_ROLES:
                raise SectorIsolationError(f"{location}.role is invalid")
            display_enabled = item.get("display_enabled")
            if not isinstance(display_enabled, bool):
                raise SectorIsolationError(f"{location}.display_enabled must be boolean")
            seen.add(sector)
            sectors.append(SectorMapping(sector, role, rationale, display_enabled))
        sectors.sort(key=lambda item: (_ROLE_ORDER[item.role], item.sector))
        narratives.append((narrative, tuple(sectors)))
    return SectorMapConfig(version, tuple(narratives))


def load_sector_map(path: str | Path = DEFAULT_SECTOR_MAP_PATH) -> SectorMapConfig:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SectorIsolationError(f"unable to load narrative sector map: {exc}") from exc
    return validate_sector_map(data)


def classify_sector_participation(*_args: Any, **_kwargs: Any) -> str:
    # Intentional until persisted, sector-level market inputs exist.
    return "UNAVAILABLE"


def compute_sector_breadth(sectors: tuple[dict, ...] | list[dict]) -> dict:
    count = len(sectors)
    category = "Broad" if count >= 4 else "Moderate" if count == 3 else "Concentrated" if count == 2 else "Limited" if count == 1 else "Unavailable"
    roles = {role: sum(item.get("connection_role") == role for item in sectors) for role in _ROLE_ORDER}
    summary = (f"This narrative is structurally connected across {count} sectors." if count else "No curated sector relationships are available for this narrative.")
    return {"category": category, "count": count, "role_counts": roles, "summary": summary, "participation_note": sector_isolation_copy("participation_unavailable")}


def build_sector_isolation_context(narrative: str, config: SectorMapConfig | None = None) -> dict:
    mappings = dict((config or load_sector_map()).narratives).get(narrative, ())
    sectors = []
    encoded_key = quote(f"group:{narrative}", safe=":")
    for mapping in mappings:
        if not mapping.display_enabled:
            continue
        state = classify_sector_participation(narrative, mapping.sector)
        sectors.append({
            "sector_key": mapping.sector, "sector_name": SECTOR_KEYS[mapping.sector],
            "connection_role": mapping.role, "role_label": sector_isolation_copy(f"role_{mapping.role}"),
            "participation_state": state, "participation_label": sector_isolation_copy(f"participation_{state}"),
            "rationale": mapping.rationale, "explanation": sector_isolation_copy("structural_connection"),
            "participation_explanation": sector_isolation_copy("participation_unavailable"),
            "available": False, "evidence_count": 0, "instruments": (),
            "href": f"/research/{encoded_key}/sectors#{mapping.sector}",
        })
    sectors_tuple = tuple(sectors)
    return {"narrative": narrative, "narrative_display_name": narrative, "sectors": sectors_tuple, "breadth": compute_sector_breadth(sectors_tuple), "has_mapping": bool(sectors_tuple), "limitations": (sector_isolation_copy("curated_notice"), sector_isolation_copy("persisted_notice"), sector_isolation_copy("sector_data_unavailable"), sector_isolation_copy("unavailable_not_detached"))}


def build_sector_isolation_preview(run: dict, dominant_narrative: str | None = None, limit: int = 4) -> dict:
    narrative = dominant_narrative or (run.get("dominant_group") if isinstance(run, dict) else None)
    if not narrative:
        return {"narrative": None, "sectors": (), "breadth": compute_sector_breadth(()), "has_mapping": False}
    context = build_sector_isolation_context(narrative)
    return {**context, "sectors": context["sectors"][:max(0, limit)], "total_sector_count": len(context["sectors"])}
