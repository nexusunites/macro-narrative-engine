"""Validated structural read model for narrative-to-asset exploration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from mne.narrative_signals import NARRATIVE_GROUPS
from mne.presentation_language import asset_exploration_copy
from mne.sector_isolation import SECTOR_KEYS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_REGISTRY_PATH = ROOT / "config" / "asset_registry.json"
DEFAULT_NARRATIVE_ASSET_MAP_PATH = ROOT / "config" / "narrative_asset_map.json"
DEFAULT_SYNTHETIC_CONCEPTS_PATH = ROOT / "config" / "synthetic_market_concepts.json"
ASSET_TYPES = frozenset({"ETF", "EQUITY", "INDEX"})
BROAD_MARKET_ROLES = frozenset({"GROWTH_INDEX", "VOLATILITY", "CURRENCY", "BREADTH", "RATES_DURATION", "CREDIT_SPREAD"})
STRUCTURAL_ROLES = frozenset({"PRIMARY", "SECONDARY", "OFFSET", "CONTEXT"})
_ROLE_ORDER = {"PRIMARY": 0, "SECONDARY": 1, "OFFSET": 2, "CONTEXT": 3}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class AssetRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class AssetMapping:
    ticker: str
    role: str
    rationale: str
    display_enabled: bool
    expected_expression: str | None = None


@dataclass(frozen=True)
class NarrativeAssetMap:
    version: str
    narratives: tuple[tuple[str, tuple[AssetMapping, ...]], ...]


def _text(record: dict, key: str, location: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssetRegistryError(f"{location}.{key} must be a non-empty string")
    return value.strip()


def validate_synthetic_concepts(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("concepts"), dict):
        raise AssetRegistryError("synthetic concept registry must contain a concepts object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise AssetRegistryError("synthetic concept version must use semantic versioning")
    concepts = {}
    for identifier, record in data["concepts"].items():
        key = _text({"identifier": identifier}, "identifier", "concepts").upper()
        if key in concepts or not isinstance(record, dict):
            raise AssetRegistryError(f"concepts.{key} is duplicated or malformed")
        description = _text(record, "description", f"concepts.{key}")
        if record.get("tradable") is not False:
            raise AssetRegistryError(f"concepts.{key}.tradable must be false")
        concepts[key] = {"description": description, "tradable": False}
    return {"version": version, "concepts": concepts}


def load_synthetic_concepts(path: str | Path = DEFAULT_SYNTHETIC_CONCEPTS_PATH) -> dict[str, Any]:
    try:
        return validate_synthetic_concepts(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetRegistryError(f"unable to load synthetic concept registry: {exc}") from exc


def validate_asset_registry(data: Any, synthetic_concepts: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
        raise AssetRegistryError("asset registry must contain an assets object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise AssetRegistryError("version must use MAJOR.MINOR.PATCH semantic versioning")
    assets: dict[str, dict[str, Any]] = {}
    for raw_ticker, record in data["assets"].items():
        ticker = _text({"ticker": raw_ticker}, "ticker", "assets").upper()
        if ticker in assets:
            raise AssetRegistryError(f"duplicate ticker: {ticker}")
        if not isinstance(record, dict):
            raise AssetRegistryError(f"assets.{ticker} must be an object")
        location = f"assets.{ticker}"
        display_name = _text(record, "display_name", location)
        asset_type = _text(record, "asset_type", location)
        if asset_type not in ASSET_TYPES:
            raise AssetRegistryError(f"{location}.asset_type is invalid")
        sector_key, broad_role = record.get("sector_key"), record.get("broad_market_role")
        if sector_key is not None and sector_key not in SECTOR_KEYS:
            raise AssetRegistryError(f"{location}.sector_key is invalid")
        if broad_role is not None and broad_role not in BROAD_MARKET_ROLES:
            raise AssetRegistryError(f"{location}.broad_market_role is invalid")
        if (sector_key is None) == (broad_role is None):
            raise AssetRegistryError(f"{location} must set exactly one of sector_key and broad_market_role")
        if not isinstance(record.get("display_enabled"), bool):
            raise AssetRegistryError(f"{location}.display_enabled must be boolean")
        if not isinstance(record.get("fetched"), bool):
            raise AssetRegistryError(f"{location}.fetched must be boolean")
        if not record["fetched"] and record["display_enabled"]:
            raise AssetRegistryError(f"{location} cannot display an unfetched asset")
        assets[ticker] = {"display_name": display_name, "asset_type": asset_type, "sector_key": sector_key, "broad_market_role": broad_role, "fetched": record["fetched"], "display_enabled": record["display_enabled"]}
    concepts = (synthetic_concepts or {}).get("concepts", {})
    collision = sorted(set(assets) & set(concepts))
    if collision:
        raise AssetRegistryError(f"real assets collide with synthetic concepts: {', '.join(collision)}")
    return {"version": version, "assets": assets}


def load_asset_registry(path: str | Path = DEFAULT_ASSET_REGISTRY_PATH) -> dict[str, Any]:
    try:
        concepts = load_synthetic_concepts() if Path(path) == DEFAULT_ASSET_REGISTRY_PATH else None
        return validate_asset_registry(json.loads(Path(path).read_text(encoding="utf-8")), concepts)
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetRegistryError(f"unable to load asset registry: {exc}") from exc


def validate_narrative_asset_map(data: Any, registry: dict[str, Any] | None = None) -> NarrativeAssetMap:
    registry = registry or load_asset_registry()
    if not isinstance(data, dict) or not isinstance(data.get("narratives"), dict):
        raise AssetRegistryError("narrative asset map must contain a narratives object")
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise AssetRegistryError("version must use MAJOR.MINOR.PATCH semantic versioning")
    narratives = []
    for narrative in sorted(data["narratives"]):
        if narrative not in NARRATIVE_GROUPS:
            raise AssetRegistryError(f"unknown narrative group: {narrative}")
        record = data["narratives"][narrative]
        if not isinstance(record, dict) or not isinstance(record.get("assets"), list):
            raise AssetRegistryError(f"narratives.{narrative}.assets must be a list")
        mappings, seen = [], set()
        for index, item in enumerate(record["assets"]):
            location = f"narratives.{narrative}.assets[{index}]"
            if not isinstance(item, dict):
                raise AssetRegistryError(f"{location} must be an object")
            ticker, role = _text(item, "ticker", location).upper(), _text(item, "role", location)
            rationale = _text(item, "rationale", location)
            if ticker not in registry["assets"] or ticker in seen:
                raise AssetRegistryError(f"{location}.ticker is unknown or duplicated")
            if not registry["assets"][ticker].get("fetched"):
                raise AssetRegistryError(f"{location}.ticker must be a fetched asset")
            if role not in STRUCTURAL_ROLES:
                raise AssetRegistryError(f"{location}.role is invalid")
            expected = item.get("expected_expression")
            if role != "CONTEXT" and expected not in {"UP", "DOWN"}:
                raise AssetRegistryError(f"{location}.expected_expression is required")
            if expected is not None and expected not in {"UP", "DOWN"}:
                raise AssetRegistryError(f"{location}.expected_expression is invalid")
            if not isinstance(item.get("display_enabled"), bool):
                raise AssetRegistryError(f"{location}.display_enabled must be boolean")
            seen.add(ticker)
            mappings.append(AssetMapping(ticker, role, rationale, item["display_enabled"], expected))
        mappings.sort(key=lambda item: (_ROLE_ORDER[item.role], item.ticker))
        narratives.append((narrative, tuple(mappings)))
    return NarrativeAssetMap(version, tuple(narratives))


def load_narrative_asset_map(path: str | Path = DEFAULT_NARRATIVE_ASSET_MAP_PATH, registry: dict[str, Any] | None = None) -> NarrativeAssetMap:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetRegistryError(f"unable to load narrative asset map: {exc}") from exc
    return validate_narrative_asset_map(data, registry)


def compute_asset_breadth(rows: tuple[dict, ...] | list[dict]) -> dict[str, Any]:
    states = [row.get("participation_state") for row in rows]
    confirming = sum(state in {"STRONG", "PARTICIPATING"} for state in states)
    if "CONTRADICTING" in states: state = "CONTRADICTED"
    elif confirming >= 3: state = "BROAD"
    elif confirming == 2: state = "MODERATE"
    elif confirming == 1: state = "CONCENTRATED"
    elif "EMERGING" in states: state = "LIMITED"
    else: state = "UNAVAILABLE"
    return {"state": state, "confirming_count": confirming, "summary": asset_exploration_copy(f"breadth_{state}")}


def build_asset_exploration_context(narrative: str, sector: str, *, registry: dict[str, Any] | None = None, asset_map: NarrativeAssetMap | None = None, participation: dict | None = None, sector_row: dict | None = None, market_expression: dict | None = None) -> dict[str, Any]:
    registry = registry or load_asset_registry()
    asset_map = asset_map or load_narrative_asset_map(registry=registry)
    if sector not in SECTOR_KEYS:
        raise AssetRegistryError(f"unknown sector key: {sector}")
    observed = (participation or {}).get("assets") or {}
    expression_roles = {item.get("asset"): item.get("role") for item in ((market_expression or {}).get("instruments") or ()) if isinstance(item, dict) and item.get("asset")}
    sector_assets, context_assets = [], []
    encoded_key = quote(f"group:{narrative}", safe=":")
    for mapping in dict(asset_map.narratives).get(narrative, ()):
        asset = registry["assets"][mapping.ticker]
        if not mapping.display_enabled or not asset["display_enabled"]:
            continue
        if asset["sector_key"] not in {sector, None}:
            continue
        current = observed.get(mapping.ticker, {})
        state, freshness = current.get("participation_state", "UNAVAILABLE"), current.get("data_freshness", "UNAVAILABLE")
        row = {**asset, "ticker": mapping.ticker, "structural_role": mapping.role, "role_label": asset_exploration_copy(f"role_{mapping.role}"), "expected_expression": mapping.expected_expression, "rationale": mapping.rationale, "participation_state": state, "participation_label": asset_exploration_copy(f"participation_{state}"), "participation_explanation": asset_exploration_copy(f"participation_explanation_{state}"), "data_freshness": freshness, "freshness_label": asset_exploration_copy(f"freshness_{freshness}"), "pct_change": current.get("pct_change"), "market_expression_role": expression_roles.get(mapping.ticker), "research_href": f"/research/{encoded_key}"}
        (context_assets if asset["sector_key"] is None else sector_assets).append(row)
    if sector_row and sector_row.get("instrument"):
        ticker = sector_row["instrument"]
        asset = registry["assets"].get(ticker)
        if asset and asset["display_enabled"] and not any(row["ticker"] == ticker for row in sector_assets):
            state, freshness = sector_row["participation_state"], sector_row["data_freshness"]
            sector_assets.append({**asset, "ticker": ticker, "structural_role": sector_row["structural_role"], "role_label": sector_row["role_label"], "expected_expression": None, "rationale": asset_exploration_copy("sector_etf_rationale"), "participation_state": state, "participation_label": asset_exploration_copy(f"participation_{'MUTED' if state == 'DETACHED' else state}"), "participation_explanation": sector_row["participation_explanation"], "data_freshness": freshness, "freshness_label": sector_row["freshness_label"], "pct_change": sector_row.get("pct_change"), "market_expression_role": expression_roles.get(ticker), "research_href": f"/research/{encoded_key}", "sector_participation_reused": True})
    all_rows = tuple(sector_assets + context_assets)
    return {"narrative": narrative, "sector_key": sector, "sector_name": SECTOR_KEYS[sector], "sector": sector_row, "sector_assets": tuple(sector_assets), "context_assets": tuple(context_assets), "assets": all_rows, "breadth": compute_asset_breadth(all_rows), "has_assets": bool(all_rows), "limitations": tuple(asset_exploration_copy(key) for key in ("curated_notice", "persisted_notice", "unavailable_notice", "not_recommendation"))}
