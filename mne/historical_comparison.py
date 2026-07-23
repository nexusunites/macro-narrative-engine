from pathlib import Path

from mne.historical_replay_admin import normalize_replay_display_path
from mne.historical_research import (
    load_replay_for_historical_research,
    validate_replay_id,
)


UNAVAILABLE = "Unavailable"


def validate_comparison_request(replay_a_id, replay_b_id):
    return validate_replay_id(replay_a_id), validate_replay_id(replay_b_id)


def load_replay_pair(replay_a_id, replay_b_id, replay_dir=None):
    replay_a = load_replay_for_historical_research(replay_a_id, replay_dir=replay_dir)
    replay_b = load_replay_for_historical_research(replay_b_id, replay_dir=replay_dir)
    return replay_a, replay_b


def compare_score_maps(scores_a, scores_b, label_style="theme"):
    map_a = _score_map(scores_a)
    map_b = _score_map(scores_b)
    ranks = compute_rank_changes(map_a, map_b)
    rows = []
    for key in sorted(set(map_a) | set(map_b)):
        score_a = _number(map_a.get(key), default=0)
        score_b = _number(map_b.get(key), default=0)
        if score_a == 0 and score_b == 0:
            continue
        rank = ranks.get(key, {})
        rows.append(
            {
                "key": key,
                "label": _display_label(key, label_style),
                "score_a": score_a,
                "score_b": score_b,
                "score_delta": score_b - score_a,
                "rank_a": rank.get("rank_a"),
                "rank_b": rank.get("rank_b"),
                "rank_delta": rank.get("rank_delta"),
                "direction": _score_direction(score_a, score_b),
            }
        )
    return sorted(rows, key=lambda row: (-row["score_b"], -row["score_a"], row["key"]))


def compute_rank_changes(scores_a, scores_b):
    map_a = _score_map(scores_a)
    map_b = _score_map(scores_b)
    ranks_a = _rank_nonzero(map_a)
    ranks_b = _rank_nonzero(map_b)
    changes = {}
    for key in sorted(set(map_a) | set(map_b)):
        rank_a = ranks_a.get(key)
        rank_b = ranks_b.get(key)
        changes[key] = {
            "rank_a": rank_a,
            "rank_b": rank_b,
            "rank_delta": (rank_a - rank_b) if rank_a is not None and rank_b is not None else None,
        }
    return changes


def compare_dominance(artifact_a, artifact_b):
    artifact_a = artifact_a if isinstance(artifact_a, dict) else {}
    artifact_b = artifact_b if isinstance(artifact_b, dict) else {}
    theme_a = artifact_a.get("dominant_theme")
    theme_b = artifact_b.get("dominant_theme")
    group_a = artifact_a.get("dominant_group")
    group_b = artifact_b.get("dominant_group")
    return {
        "dominant_theme_a": theme_a,
        "dominant_theme_b": theme_b,
        "dominant_theme_changed": theme_a != theme_b,
        "dominant_theme_copy": _dominance_copy("theme", theme_a, theme_b),
        "dominant_group_a": group_a,
        "dominant_group_b": group_b,
        "dominant_group_changed": group_a != group_b,
        "dominant_group_copy": _dominance_copy("group", group_a, group_b),
    }


def compare_evidence_base(artifact_a, artifact_b):
    artifact_a = artifact_a if isinstance(artifact_a, dict) else {}
    artifact_b = artifact_b if isinstance(artifact_b, dict) else {}
    metadata_a = _metadata(artifact_a)
    metadata_b = _metadata(artifact_b)
    warnings_a = _warnings(metadata_a)
    warnings_b = _warnings(metadata_b)
    evidence_count_a = _int_or_none(artifact_a.get("evidence_count"))
    evidence_count_b = _int_or_none(artifact_b.get("evidence_count"))
    source_count_a = _int_or_none(artifact_a.get("source_count"))
    source_count_b = _int_or_none(artifact_b.get("source_count"))
    backfill_available_a = _has_backfill_metadata(metadata_a)
    backfill_available_b = _has_backfill_metadata(metadata_b)
    backfill_available = backfill_available_a and backfill_available_b
    backfilled_a = metadata_a.get("backfilled_evidence_count") if backfill_available_a else None
    backfilled_b = metadata_b.get("backfilled_evidence_count") if backfill_available_b else None
    coverage_a = _coverage_intelligence(artifact_a)
    coverage_b = _coverage_intelligence(artifact_b)
    coverage_available_a = coverage_a is not None
    coverage_available_b = coverage_b is not None
    result = {
        "evidence_count_a": evidence_count_a,
        "evidence_count_b": evidence_count_b,
        "evidence_count_delta": _delta(evidence_count_a, evidence_count_b),
        "source_count_a": source_count_a,
        "source_count_b": source_count_b,
        "source_count_delta": _delta(source_count_a, source_count_b),
        "warnings_count_a": len(warnings_a),
        "warnings_count_b": len(warnings_b),
        "warnings_count_delta": len(warnings_b) - len(warnings_a),
        "backfilled_evidence_count_a": _int_or_none(backfilled_a) if backfill_available_a else None,
        "backfilled_evidence_count_b": _int_or_none(backfilled_b) if backfill_available_b else None,
        "backfilled_evidence_included_a": metadata_a.get("backfilled_evidence_included") if backfill_available_a else None,
        "backfilled_evidence_included_b": metadata_b.get("backfilled_evidence_included") if backfill_available_b else None,
        "live_evidence_count_a": _int_or_none(metadata_a.get("live_evidence_count")) if backfill_available_a else None,
        "live_evidence_count_b": _int_or_none(metadata_b.get("live_evidence_count")) if backfill_available_b else None,
        "total_evidence_count_a": _int_or_none(metadata_a.get("total_evidence_count")) if backfill_available_a else None,
        "total_evidence_count_b": _int_or_none(metadata_b.get("total_evidence_count")) if backfill_available_b else None,
        "evidence_sources_used_a": metadata_a.get("evidence_sources_used") if backfill_available_a else None,
        "evidence_sources_used_b": metadata_b.get("evidence_sources_used") if backfill_available_b else None,
        "backfill_ids_used_a": metadata_a.get("backfill_ids_used") if backfill_available_a else None,
        "backfill_ids_used_b": metadata_b.get("backfill_ids_used") if backfill_available_b else None,
        "backfill_metadata_available_a": backfill_available_a,
        "backfill_metadata_available_b": backfill_available_b,
        "coverage_available_a": coverage_available_a,
        "coverage_available_b": coverage_available_b,
        "breadth_state_a": coverage_a.get("breadth_state") if coverage_available_a else None,
        "breadth_state_b": coverage_b.get("breadth_state") if coverage_available_b else None,
        "contributing_source_count_a": coverage_a.get("contributing_source_count") if coverage_available_a else None,
        "contributing_source_count_b": coverage_b.get("contributing_source_count") if coverage_available_b else None,
        "contributing_provider_count_a": coverage_a.get("contributing_provider_count") if coverage_available_a else None,
        "contributing_provider_count_b": coverage_b.get("contributing_provider_count") if coverage_available_b else None,
        "contributing_category_count_a": coverage_a.get("contributing_category_count") if coverage_available_a else None,
        "contributing_category_count_b": coverage_b.get("contributing_category_count") if coverage_available_b else None,
    }
    result["copy"] = _evidence_copy(result, backfill_available)
    return result


def build_comparison_summary(artifact_a, artifact_b, replay_a_id, replay_b_id):
    artifact_a = artifact_a if isinstance(artifact_a, dict) else {}
    artifact_b = artifact_b if isinstance(artifact_b, dict) else {}
    metadata_a = _metadata(artifact_a)
    metadata_b = _metadata(artifact_b)
    fields = (
        "replay_date",
        "evidence_cutoff",
        "generated_at",
        "evidence_count",
        "source_count",
        "dominant_theme",
        "dominant_group",
        "taxonomy_version",
        "registry_version",
    )
    summary = {
        "replay_id_a": replay_a_id,
        "replay_id_b": replay_b_id,
        "mode_a": artifact_a.get("mode") or _display_mode(metadata_a),
        "mode_b": artifact_b.get("mode") or _display_mode(metadata_b),
        "network_confidence_a": artifact_a.get("network_confidence"),
        "network_confidence_b": artifact_b.get("network_confidence"),
        "source_confidence_a": artifact_a.get("source_confidence"),
        "source_confidence_b": artifact_b.get("source_confidence"),
    }
    for field in fields:
        summary[f"{field}_a"] = artifact_a.get(field)
        summary[f"{field}_b"] = artifact_b.get(field)
    return summary


def build_comparison_warnings(artifact_a, artifact_b):
    artifact_a = artifact_a if isinstance(artifact_a, dict) else {}
    artifact_b = artifact_b if isinstance(artifact_b, dict) else {}
    comparison = []
    if artifact_a.get("taxonomy_version") != artifact_b.get("taxonomy_version"):
        comparison.append("Replay artifacts use different taxonomy versions.")
    return {
        "replay_a": _warnings(_metadata(artifact_a)),
        "replay_b": _warnings(_metadata(artifact_b)),
        "comparison": comparison,
    }


def build_historical_comparison(replay_a_id, replay_b_id, replay_dir=None):
    replay_a_id, replay_b_id = validate_comparison_request(replay_a_id, replay_b_id)
    same_replay = replay_a_id == replay_b_id
    if same_replay:
        artifact_a, path_a = load_replay_for_historical_research(replay_a_id, replay_dir=replay_dir)
        artifact_b, path_b = artifact_a, path_a
    else:
        (artifact_a, path_a), (artifact_b, path_b) = load_replay_pair(
            replay_a_id,
            replay_b_id,
            replay_dir=replay_dir,
        )

    replay_dir_path = Path(path_a).parent.resolve() if path_a else None
    return {
        "replay_a_id": replay_a_id,
        "replay_b_id": replay_b_id,
        "same_replay": same_replay,
        "summary": build_comparison_summary(artifact_a, artifact_b, replay_a_id, replay_b_id),
        "dominance": compare_dominance(artifact_a, artifact_b),
        "theme_changes": []
        if same_replay
        else compare_score_maps(artifact_a.get("theme_scores"), artifact_b.get("theme_scores"), "theme"),
        "group_changes": []
        if same_replay
        else compare_score_maps(artifact_a.get("group_scores"), artifact_b.get("group_scores"), "group"),
        "evidence_base": compare_evidence_base(artifact_a, artifact_b),
        "warnings": build_comparison_warnings(artifact_a, artifact_b),
        "artifact_a_display_path": normalize_replay_display_path(path_a, replay_dir_path),
        "artifact_b_display_path": normalize_replay_display_path(path_b, replay_dir_path),
    }


def _score_map(value):
    if not isinstance(value, dict):
        return {}
    return {str(key): _number(score, default=0) for key, score in value.items()}


def _number(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _delta(value_a, value_b):
    if value_a is None or value_b is None:
        return None
    return value_b - value_a


def _rank_nonzero(scores):
    rows = sorted(
        ((key, score) for key, score in scores.items() if _number(score, default=0) > 0),
        key=lambda item: (-item[1], item[0]),
    )
    return {key: index + 1 for index, (key, _score) in enumerate(rows)}


def _score_direction(score_a, score_b):
    if score_a == 0 and score_b > 0:
        return "NEW"
    if score_a > 0 and score_b == 0:
        return "DROPPED"
    if score_a > 0 and score_b > 0 and score_b > score_a:
        return "INCREASED"
    if score_a > 0 and score_b > 0 and score_b < score_a:
        return "DECREASED"
    return "UNCHANGED"


def _display_label(key, label_style):
    if label_style == "group":
        return str(key)
    return str(key).replace("_", " ").title()


def _dominance_copy(label, value_a, value_b):
    if value_a is None and value_b is None:
        return f"Dominant {label} is unavailable for this comparison."
    if value_a == value_b:
        return f"Dominant {label} remained {_dominance_display(label, value_a)}."
    return (
        f"Dominant {label} changed from {_dominance_display(label, value_a)} "
        f"to {_dominance_display(label, value_b)}."
    )


def _dominance_display(label, value):
    if value is None:
        return UNAVAILABLE
    if label == "theme":
        return _display_label(value, "theme")
    return str(value)


def _metadata(artifact):
    metadata = artifact.get("replay_metadata") if isinstance(artifact, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _warnings(metadata):
    warnings = metadata.get("warnings") if isinstance(metadata, dict) else []
    return list(warnings) if isinstance(warnings, list) else []


def _coverage_intelligence(artifact):
    source_intelligence = artifact.get("source_intelligence") if isinstance(artifact, dict) else None
    coverage = (
        source_intelligence.get("coverage_intelligence")
        if isinstance(source_intelligence, dict)
        else None
    )
    return coverage if isinstance(coverage, dict) else None


def _has_backfill_metadata(metadata):
    return any(
        key in metadata
        for key in (
            "backfilled_evidence_included",
            "backfill_ids_used",
            "live_persisted_evidence_included",
            "evidence_sources_used",
            "backfilled_evidence_count",
            "live_evidence_count",
            "total_evidence_count",
        )
    )


def _evidence_copy(result, backfill_available):
    copy = [
        _count_delta_copy("evidence item", "used", result.get("evidence_count_delta")),
        _count_delta_copy("source", "used", result.get("source_count_delta")),
        _count_delta_copy("warning", "had", result.get("warnings_count_delta")),
    ]
    if not backfill_available:
        copy.append(
            "Backfill inclusion could not be compared because one replay predates backfill metadata tracking."
        )
        return copy

    a_included = _backfill_included(result, "a")
    b_included = _backfill_included(result, "b")
    if a_included and b_included:
        copy.append("Both replays included backfilled evidence.")
    elif a_included:
        copy.append("Replay A included backfilled evidence.")
    elif b_included:
        copy.append("Replay B included backfilled evidence.")
    else:
        copy.append("Neither replay included backfilled evidence.")

    if result.get("coverage_available_a") and result.get("coverage_available_b"):
        state_a = result.get("breadth_state_a")
        state_b = result.get("breadth_state_b")
        if state_a == state_b:
            copy.append(f"Coverage breadth remained {state_a}.")
        else:
            copy.append(f"Coverage breadth changed from {state_a} to {state_b}.")
    elif result.get("coverage_available_a") or result.get("coverage_available_b"):
        copy.append("Coverage breadth could not be compared because it is only available for one replay.")
    return copy


def _backfill_included(result, side):
    included = result.get(f"backfilled_evidence_included_{side}")
    if included is not None:
        return bool(included)
    count = result.get(f"backfilled_evidence_count_{side}")
    sources = result.get(f"evidence_sources_used_{side}")
    if count is not None:
        return count > 0
    if isinstance(sources, list):
        return "historical_backfill" in sources
    return False


def _count_delta_copy(metric, verb, delta):
    metric_label = metric if abs(delta or 0) == 1 else f"{metric}s"
    metric_title = metric.replace(" item", "").title()
    if delta is None:
        return f"{metric_title} count could not be compared."
    if delta == 0:
        return f"{metric_title} count was unchanged."
    if delta > 0:
        return f"Replay B {verb} {delta} more {metric_label} than Replay A."
    return f"Replay A {verb} {abs(delta)} more {metric_label} than Replay B."


def _display_mode(metadata):
    replay_mode = metadata.get("replay_mode")
    if replay_mode == "HISTORICAL_REPLAY":
        return "macro"
    return replay_mode
