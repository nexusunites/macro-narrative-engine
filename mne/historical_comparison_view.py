"""Whitelisted presentation models for read-only user historical comparisons."""

from __future__ import annotations

from collections import Counter

from mne.historical_comparison import build_historical_comparison
from mne.historical_research import load_replay_for_historical_research
from mne.historical_research_view import build_user_historical_view
from mne.explanation_layer import explain_historical_comparison
from mne.presentation_language import (
    HISTORICAL_COPY,
    historical_breadth,
    historical_direction,
    historical_origin,
    pluralize,
)


def build_user_historical_comparison(replay_a_id, replay_b_id, replay_dir=None):
    """Build a user-safe comparison by explicitly selecting every output field."""
    artifact_a, _ = load_replay_for_historical_research(replay_a_id, replay_dir=replay_dir)
    if replay_a_id == replay_b_id:
        artifact_b = artifact_a
    else:
        artifact_b, _ = load_replay_for_historical_research(replay_b_id, replay_dir=replay_dir)

    # Also applies the minimum user-facing snapshot validation.
    build_user_historical_view(artifact_a)
    build_user_historical_view(artifact_b)
    if _chronology_key(artifact_b) < _chronology_key(artifact_a):
        replay_a_id, replay_b_id = replay_b_id, replay_a_id
        artifact_a, artifact_b = artifact_b, artifact_a

    comparison = build_historical_comparison(
        replay_a_id,
        replay_b_id,
        replay_dir=replay_dir,
    )
    evidence = comparison.get("evidence_base") or {}
    period_a = _period(artifact_a, evidence, "a")
    period_b = _period(artifact_b, evidence, "b")
    theme_changes = _change_rows(comparison.get("theme_changes"))
    group_changes = _change_rows(comparison.get("group_changes"))
    dominance = _dominance(artifact_a, artifact_b)
    summary = _summary(period_a, period_b, dominance, theme_changes, group_changes)
    coverage_available = bool(period_a["breadth"]["label"] or period_b["breadth"]["label"])

    result = {
        "same_reconstruction": replay_a_id == replay_b_id,
        "period_a": period_a,
        "period_b": period_b,
        "summary": summary,
        "dominance_sentences": dominance,
        "rank_sentences": _rank_sentences(theme_changes),
        "theme_changes": theme_changes,
        "group_changes": group_changes,
        "evidence": {
            "count_a": period_a["evidence_count"],
            "count_b": period_b["evidence_count"],
            "source_count_a": period_a["source_count"],
            "source_count_b": period_b["source_count"],
            "provider_count_a": _number(evidence.get("contributing_provider_count_a")),
            "provider_count_b": _number(evidence.get("contributing_provider_count_b")),
            "category_count_a": _number(evidence.get("contributing_category_count_a")),
            "category_count_b": _number(evidence.get("contributing_category_count_b")),
            "provider_label_a": _count_label(evidence.get("contributing_provider_count_a"), "provider"),
            "provider_label_b": _count_label(evidence.get("contributing_provider_count_b"), "provider"),
            "category_label_a": _count_label(evidence.get("contributing_category_count_a"), "source category", "source categories"),
            "category_label_b": _count_label(evidence.get("contributing_category_count_b"), "source category", "source categories"),
            "origins_a": _origin_mix(artifact_a),
            "origins_b": _origin_mix(artifact_b),
        },
        "coverage_available": coverage_available,
        "earlier_url": f"/history/{replay_a_id}",
        "later_url": f"/history/{replay_b_id}",
        "copy": dict(HISTORICAL_COPY),
    }
    result["explanation"] = explain_historical_comparison(result)
    return result


def _chronology_key(artifact):
    return str(artifact.get("replay_date") or artifact.get("evidence_cutoff") or "")


def _period(artifact, evidence, suffix):
    breadth = historical_breadth(evidence.get(f"breadth_state_{suffix}"))
    evidence_count = _number(evidence.get(f"evidence_count_{suffix}"))
    source_count = _number(
        evidence.get(f"contributing_source_count_{suffix}"),
        default=_number(evidence.get(f"source_count_{suffix}")),
    )
    return {
        "date": str(artifact.get("replay_date") or ""),
        "dominant_theme": _plain_theme(artifact.get("dominant_theme")),
        "dominant_group": _plain_group(artifact.get("dominant_group")),
        "evidence_count": evidence_count,
        "evidence_label": pluralize(evidence_count, "piece of evidence", "pieces of evidence") if evidence_count is not None else None,
        "source_count": source_count,
        "source_label": pluralize(source_count, "source") if source_count is not None else None,
        "breadth": breadth,
    }


def _change_rows(rows):
    safe = []
    for row in rows if isinstance(rows, list) else []:
        direction = historical_direction(row.get("direction"))
        delta = _number(row.get("score_delta"), default=0)
        safe.append({
            "name": str(row.get("label") or ""),
            "score_a": _number(row.get("score_a"), default=0),
            "score_b": _number(row.get("score_b"), default=0),
            "delta": delta,
            "delta_label": f"{delta:+g}",
            "arrow": "▲" if delta > 0 else "▼" if delta < 0 else "—",
            "direction": direction,
            "rank_a": _number(row.get("rank_a")),
            "rank_b": _number(row.get("rank_b")),
            "rank_label": _rank_label(row.get("rank_a"), row.get("rank_b")),
        })
    return safe


def _dominance(artifact_a, artifact_b):
    sentences = []
    for label, key, display in (
        ("dominant theme", "dominant_theme", _plain_theme),
        ("dominant narrative group", "dominant_group", _plain_group),
    ):
        value_a = display(artifact_a.get(key))
        value_b = display(artifact_b.get(key))
        if not value_a or not value_b:
            continue
        if value_a == value_b:
            sentences.append(f"The {label} remained {value_a}.")
        else:
            sentences.append(f"The {label} changed from {value_a} to {value_b}.")
    return sentences


def _summary(period_a, period_b, dominance, theme_changes, group_changes):
    parts = list(dominance)
    changed_themes = sum(row["direction"]["raw"] != "UNCHANGED" for row in theme_changes)
    changed_groups = sum(row["direction"]["raw"] != "UNCHANGED" for row in group_changes)
    if changed_themes:
        parts.append(f"{pluralize(changed_themes, 'theme')} changed.")
    if changed_groups:
        parts.append(f"{pluralize(changed_groups, 'narrative group')} changed.")
    if not parts and period_a["date"] and period_b["date"]:
        parts.append("No scored narrative changes were available across these periods.")
    return " ".join(parts)


def _rank_sentences(rows):
    sentences = []
    for row in rows:
        if row["rank_a"] is not None and row["rank_b"] is not None and row["rank_a"] != row["rank_b"]:
            sentences.append(f"{row['name']} moved from rank {row['rank_a']} to rank {row['rank_b']}.")
    return sentences[:3]


def _origin_mix(artifact):
    source = artifact.get("source_intelligence")
    source = source if isinstance(source, dict) else {}
    rows = source.get("accepted_evidence")
    rows = rows if isinstance(rows, list) else []
    labels = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        labels[historical_origin(row.get("origin") or row.get("evidence_origin"), row.get("source_id"))] += 1
    return [{"label": label, "count": count, "count_label": pluralize(count, "piece of evidence", "pieces of evidence")} for label, count in sorted(labels.items())]


def _rank_label(rank_a, rank_b):
    left = str(rank_a) if rank_a is not None else "—"
    right = str(rank_b) if rank_b is not None else "—"
    return f"{left} → {right}"


def _count_label(value, singular, plural=None):
    number = _number(value)
    return pluralize(number, singular, plural) if number is not None else None


def _plain_theme(value):
    if not value:
        return None
    text = str(value).replace("_", " ").replace("-", " ").title()
    return text.replace("Ai", "AI").replace("Gdp", "GDP").replace("Pce", "PCE")


def _plain_group(value):
    return str(value) if value else None


def _number(value, default=None):
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return int(number) if number.is_integer() else number
