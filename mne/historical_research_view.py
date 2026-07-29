"""Whitelisted, read-only presentation models for user historical research."""

from __future__ import annotations

import logging
from pathlib import Path

from mne.historical_research import (
    HistoricalResearchError,
    build_historical_evidence_context,
    load_replay_for_historical_research,
)
from mne.presentation_language import (
    HISTORICAL_COPY,
    historical_breadth,
    historical_copy,
    historical_origin,
    pluralize,
)

LOGGER = logging.getLogger(__name__)


def list_user_replays(replay_dir=None):
    base = Path(replay_dir) if replay_dir is not None else None
    if base is None:
        from mne.historical_research import default_replay_dir
        base = default_replay_dir()
    if not base.exists():
        return []

    cards = []
    for path in sorted(base.glob("*.json"), key=lambda item: item.name, reverse=True):
        try:
            view = load_replay_card_summary(path)
        except (HistoricalResearchError, ValueError, TypeError) as error:
            LOGGER.warning("Excluded historical reconstruction %s: %s", path.name, type(error).__name__)
            continue
        cards.append({
            "url_id": path.stem,
            "date": view["date"],
            "dominant_group": view["dominant_group"],
            "dominant_theme": view["dominant_theme"],
            "evidence_label": view["evidence_label"],
            "breadth": view["breadth"],
            "summary": view["summary"],
            "limited": view["evidence_count"] == 0,
        })
    return cards


def load_replay_card_summary(path):
    """Load and validate only the fields required by replay selector cards."""
    replay_path = Path(path)
    artifact, _ = load_replay_for_historical_research(
        replay_path.stem,
        replay_dir=replay_path.parent,
    )
    _validate_user_historical_artifact(artifact)

    coverage = _coverage(artifact)
    evidence_count = _number(
        artifact.get("evidence_count"),
        default=_number(
            _source_intelligence(artifact).get("accepted_evidence_count"),
            _lightweight_evidence_count(artifact),
        ),
    )
    dominant_group = _plain_group(artifact.get("dominant_group"))
    dominant_theme = _plain_theme(artifact.get("dominant_theme"))
    breadth = historical_breadth(coverage.get("breadth_state"))
    summary_parts = []
    if dominant_group:
        summary_parts.append(f"{dominant_group} led the historical narrative")
    elif dominant_theme:
        summary_parts.append(f"{dominant_theme} led the historical narrative")
    if evidence_count is not None:
        summary_parts.append(
            f"based on {pluralize(evidence_count, historical_copy('evidence_singular'), historical_copy('evidence_plural'))}"
        )
    if breadth["label"]:
        summary_parts.append(f"with {breadth['label'].lower()}")
    summary = " ".join(summary_parts).strip()
    if summary:
        summary += "."

    return {
        "date": str(artifact["replay_date"]),
        "dominant_group": dominant_group,
        "dominant_theme": dominant_theme,
        "evidence_label": pluralize(
            evidence_count,
            historical_copy("evidence_singular"),
            historical_copy("evidence_plural"),
        ) if evidence_count is not None else None,
        "breadth": breadth,
        "summary": summary,
        "evidence_count": evidence_count,
    }


def build_user_historical_view(artifact):
    _validate_user_historical_artifact(artifact)

    evidence = [
        _safe_evidence(row)
        for row in build_historical_evidence_context(artifact)
    ]
    coverage = _coverage(artifact)
    evidence_count = _number(
        artifact.get("evidence_count"),
        default=_number(_source_intelligence(artifact).get("accepted_evidence_count"), len(evidence)),
    )
    source_count = _number(
        artifact.get("source_count"),
        default=coverage.get("source_count"),
    )
    dominant_group = _plain_group(artifact.get("dominant_group"))
    dominant_theme = _plain_theme(artifact.get("dominant_theme"))
    theme_score = _score(artifact.get("theme_scores"), artifact.get("dominant_theme"))
    group_score = _score(artifact.get("group_scores"), artifact.get("dominant_group"))
    breadth = historical_breadth(coverage.get("breadth_state"))
    summary_parts = []
    if dominant_group:
        summary_parts.append(f"{dominant_group} led the historical narrative")
    elif dominant_theme:
        summary_parts.append(f"{dominant_theme} led the historical narrative")
    if evidence_count is not None:
        summary_parts.append(f"based on {pluralize(evidence_count, historical_copy('evidence_singular'), historical_copy('evidence_plural'))}")
    if breadth["label"]:
        summary_parts.append(f"with {breadth['label'].lower()}")
    summary = " ".join(summary_parts).strip()
    if summary:
        summary += "."

    return {
        "date": str(artifact["replay_date"]),
        "cutoff": str(artifact["evidence_cutoff"]),
        "dominant_group": dominant_group,
        "dominant_theme": dominant_theme,
        "theme_score": theme_score,
        "group_score": group_score,
        "theme_score_label": pluralize(theme_score, historical_copy("story_singular"), historical_copy("story_plural")) if theme_score is not None else None,
        "group_score_label": pluralize(group_score, historical_copy("story_singular"), historical_copy("story_plural")) if group_score is not None else None,
        "evidence_count": evidence_count,
        "evidence_label": pluralize(evidence_count, historical_copy("evidence_singular"), historical_copy("evidence_plural")) if evidence_count is not None else None,
        "source_count": source_count,
        "source_label": pluralize(source_count, "source") if source_count is not None else None,
        "breadth": breadth,
        "summary": summary,
        "evidence": evidence,
        "coverage": coverage if breadth["label"] or any(value is not None for value in coverage.values()) else None,
        "copy": dict(HISTORICAL_COPY),
        "why": {
            "dominant_theme": artifact.get("dominant_theme"),
            "dominant_group": artifact.get("dominant_group"),
            "theme_score": theme_score,
            "group_score": group_score,
            "evidence_count": evidence_count,
            "source_count": source_count,
            "breadth_state": coverage.get("breadth_state"),
        },
    }


def _validate_user_historical_artifact(artifact):
    if not isinstance(artifact, dict) or not _minimum_snapshot_present(artifact):
        raise ValueError("missing minimum historical snapshot")
    status = str(artifact.get("status") or "completed").lower()
    if status not in {"complete", "completed", "success"}:
        raise ValueError("historical reconstruction is not complete")


def _minimum_snapshot_present(artifact):
    return bool(
        artifact.get("replay_id")
        and artifact.get("replay_date")
        and artifact.get("evidence_cutoff")
        and (artifact.get("dominant_group") or artifact.get("dominant_theme"))
        and isinstance(artifact.get("theme_scores"), dict)
        and isinstance(artifact.get("group_scores"), dict)
    )


def _source_intelligence(artifact):
    value = artifact.get("source_intelligence")
    return value if isinstance(value, dict) else {}


def _lightweight_evidence_count(artifact):
    source_intelligence = _source_intelligence(artifact)
    evidence = source_intelligence.get("accepted_evidence")
    if not isinstance(evidence, list):
        evidence = source_intelligence.get("evidence_objects")
    if not isinstance(evidence, list):
        evidence = artifact.get("evidence")
    if not isinstance(evidence, list):
        return 0
    return sum(
        1
        for row in evidence
        if isinstance(row, dict)
        and row.get("accepted", True) is True
        and not row.get("rejection_state")
        and not row.get("rejection_reason")
    )


def _coverage(artifact):
    value = _source_intelligence(artifact).get("coverage_intelligence")
    value = value if isinstance(value, dict) else {}
    return {
        "breadth_state": value.get("breadth_state"),
        "source_count": _number(value.get("contributing_source_count")),
        "provider_count": _number(value.get("contributing_provider_count")),
        "category_count": _number(value.get("contributing_category_count")),
    }


def _safe_evidence(row):
    matched_group = _plain_group(row.get("matched_group"))
    matched_theme = _plain_theme(row.get("matched_theme"))
    raw = row.get("_raw") if isinstance(row.get("_raw"), dict) else {}
    origin = row.get("origin") or raw.get("origin") or raw.get("evidence_origin")
    source_id = row.get("source_id") or raw.get("source_id")
    return {
        "title": row.get("title"),
        "source_name": row.get("source_name") or row.get("provider"),
        "provider": row.get("provider"),
        "published_at": row.get("published_at") or row.get("timestamp"),
        "url": row.get("url") if row.get("article_link_available") else None,
        "matched_group": matched_group,
        "matched_theme": matched_theme,
        "attribution": matched_group or matched_theme,
        "origin_explanation": historical_origin(origin, source_id),
        "reader_summary": row.get("reader_summary"),
    }


def _plain_theme(value):
    if not value:
        return None
    text = str(value).replace("_", " ").replace("-", " ").title()
    return text.replace("Ai", "AI").replace("Gdp", "GDP").replace("Pce", "PCE")


def _plain_group(value):
    return str(value) if value else None


def _score(scores, key):
    if not isinstance(scores, dict) or key not in scores:
        return None
    return _number(scores.get(key))


def _number(value, default=None):
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return int(number) if number.is_integer() else number
