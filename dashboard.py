import json
import math
from urllib.parse import parse_qs
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import RESULTS_DIR, ensure_data_dir
from mne.config_diagnostics import build_configuration_report, format_startup_report
from mne.dashboard_trust_summary import build_dashboard_trust_summary
from mne.event_lifecycle import load_event_definitions
from mne import historical_replay
from mne.historical_replay_admin import (
    build_replay_admin_summary,
    build_replay_error_context,
    is_valid_replay_id,
    list_recent_replay_summaries,
    load_replay_summary_by_id,
)
from mne.narrative_signals import compute_group_scores
from mne.operations_center import build_operations_center
from mne.platform_observability import stage_by_name
from mne.research_workspace import (
    build_narrative_investigation,
    build_narrative_selector,
    narrative_key,
    select_latest_meaningful_run,
    split_narrative_key,
)
from mne.source_registry import SourceRegistryError, load_source_registry
from mne.storage import get_recent_daily_runs


BASE_DIR = Path(__file__).resolve().parent
RECENT_RUN_LIMIT = 20
REGIME_HISTORY_LIMIT = 30
LEADERSHIP_HISTORY_LIMIT = 10
RECENT_REPLAY_LIMIT = 10
MARKET_SYMBOLS = ("QQQ", "NVDA", "VIX", "DXY")
SCORE_DELTA_THRESHOLD = 2
SHARE_DELTA_THRESHOLD = 0.03
REGIME_SCORE_DELTA_THRESHOLD = 5

app = FastAPI(title="Macro Narrative Engine Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def list_result_files(limit=RECENT_RUN_LIMIT):
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda path: path.name, reverse=True)
    return files[:limit]


def list_regime_history_files():
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda path: path.name, reverse=True)
    return files[:REGIME_HISTORY_LIMIT]


def list_all_result_files():
    return sorted(RESULTS_DIR.glob("*.json"), key=lambda path: path.name, reverse=True)


def get_prior_result_file(current_file):
    files = list_all_result_files()
    for index, path in enumerate(files):
        if path.name == current_file.name:
            if index + 1 < len(files):
                return files[index + 1]
            return None
    return None


def safe_result_path(filename):
    if not filename:
        return None

    candidate = RESULTS_DIR / Path(filename).name
    if candidate.suffix.lower() != ".json" or not candidate.exists():
        return None
    if candidate.parent.resolve() != RESULTS_DIR.resolve():
        return None
    return candidate


def load_result(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_source_registry_diagnostics():
    try:
        return load_source_registry().diagnostics()
    except SourceRegistryError as error:
        return {"error": str(error)}


def build_evidence_quality_diagnostics(source_intelligence):
    coverage = (source_intelligence or {}).get("coverage_intelligence") or {}
    per_narrative = list(coverage.get("per_narrative") or [])
    source_totals = {}

    for record in per_narrative:
        for source in record.get("source_contribution_breakdown", []):
            source_id = source.get("source_id")
            if not source_id:
                continue
            row = source_totals.setdefault(
                source_id,
                {
                    "source_id": source_id,
                    "source_name": source.get("source_name"),
                    "evidence_count": 0,
                },
            )
            row["evidence_count"] += int(source.get("evidence_count") or 0)

    return {
        "coverage": coverage,
        "per_narrative": sorted(
            per_narrative,
            key=lambda item: (
                item.get("narrative_level") or "",
                item.get("narrative_id") or "",
            ),
        ),
        "top_contributing_sources": sorted(
            source_totals.values(),
            key=lambda item: (-item["evidence_count"], item["source_id"]),
        ),
        "highest_concentration_narratives": sorted(
            per_narrative,
            key=lambda item: (
                -(item.get("concentration_ratio") or 0),
                item.get("narrative_level") or "",
                item.get("narrative_id") or "",
            ),
        ),
    }


def build_platform_observability_diagnostics(platform_observability):
    platform_observability = platform_observability or {}
    stages = list(platform_observability.get("stages") or [])
    run_metadata = platform_observability.get("run_metadata") or {}

    evidence_flow = {
        "entries_received": _stage_count(platform_observability, "RSS_FETCH", "entries_received"),
        "evidence_created": _stage_count(
            platform_observability,
            "EVIDENCE_NORMALIZATION",
            "evidence_created",
        ),
        "accepted": _stage_count(platform_observability, "EVIDENCE_NORMALIZATION", "accepted"),
        "fresh": _stage_count(platform_observability, "FRESHNESS_VALIDATION", "fresh"),
        "narratives_measured": _stage_count(
            platform_observability,
            "EVIDENCE_QUALITY",
            "narratives_measured",
        ),
    }

    return {
        "run_metadata": run_metadata,
        "stages": stages,
        "stages_by_duration": sorted(
            stages,
            key=lambda item: (-(item.get("duration_ms") or 0), item.get("stage_name") or ""),
        ),
        "engine_versions": run_metadata.get("engine_versions") or {},
        "evidence_flow": evidence_flow,
    }


def _stage_count(platform_observability, stage_name, field):
    stage = stage_by_name(platform_observability, stage_name) or {}
    return (stage.get("result_counts") or {}).get(field)


def pct(value):
    if value is None:
        return None
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return value


def fmt_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def fmt_file_timestamp(path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return None


def fmt_run_label(path):
    label = fmt_history_label(None, path)
    if label != path.stem:
        return label

    modified = fmt_file_timestamp(path)
    if modified:
        return f"{path.stem} (modified {modified})"
    return path.stem


def build_run_options(paths):
    return [
        {
            "filename": path.name,
            "label": fmt_run_label(path),
        }
        for path in paths
    ]


def fmt_history_label(value, path):
    candidates = [value, path.stem]
    for candidate in candidates:
        if not candidate:
            continue
        text = str(candidate)
        for fmt in ("%Y-%m-%d_%H%M%S", "%Y-%m-%d_%H%M", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt).strftime("%m/%d %H:%M")
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(text).strftime("%m/%d %H:%M")
        except ValueError:
            pass
    return path.stem


def fmt_day_label(value):
    if not value:
        return "Unavailable"
    text = str(value)
    day = text[:10]
    for fmt in ("%Y-%m-%d", "%Y-%m-%d_%H%M", "%Y-%m-%d %H:%M"):
        try:
            candidate = text if fmt != "%Y-%m-%d" else day
            return datetime.strptime(candidate, fmt).strftime("%m/%d")
        except ValueError:
            pass
    return day or text


def valid_regime_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score):
        return None
    return score


def score_sort_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def sorted_scores(scores):
    if not isinstance(scores, dict):
        return []
    return sorted(scores.items(), key=lambda item: score_sort_value(item[1]), reverse=True)


def build_replay_result_view(output, output_path):
    replay_dir = output_path.parent if isinstance(output_path, Path) else None
    return build_replay_admin_summary(output, output_path, replay_dir)


def list_recent_replay_files(limit=RECENT_REPLAY_LIMIT):
    try:
        replay_dir = historical_replay.ensure_replay_dir()
    except Exception as error:
        replay_error = build_replay_error_context(error)
        return {
            "replay_dir": "replays/",
            "error": replay_error["message"],
            "files": [],
        }

    return {
        "replay_dir": "replays/",
        "error": None,
        "files": list_recent_replay_summaries(replay_dir, limit=limit),
    }


def build_historical_replay_console(result=None, error=None, form=None, message=None):
    form = form or {}
    return {
        "form": {
            "replay_date": form.get("replay_date", ""),
            "mode": form.get("mode", historical_replay.SUPPORTED_MODE),
        },
        "error": error,
        "message": message,
        "result": result,
        "recent_replays": list_recent_replay_files(),
    }


def run_admin_historical_replay(replay_date, mode=historical_replay.SUPPORTED_MODE):
    request = historical_replay.build_replay_request(replay_date, mode=mode)
    output = historical_replay.run_historical_replay(request)
    path = historical_replay.persist_historical_replay(output)
    return build_replay_result_view(output, path)


def build_admin_replay_context(request, run, replay_date=None, mode=historical_replay.SUPPORTED_MODE, replay_id=None):
    form = {
        "replay_date": (replay_date or "").strip(),
        "mode": (mode or historical_replay.SUPPORTED_MODE).strip() or historical_replay.SUPPORTED_MODE,
    }
    replay_result = None
    replay_error = None
    replay_message = None
    if replay_id:
        try:
            replay_dir = historical_replay.ensure_replay_dir()
            replay_result = load_replay_summary_by_id(replay_dir, replay_id)
            form["replay_date"] = replay_result.get("replay_date") or form["replay_date"]
        except (ValueError, FileNotFoundError):
            replay_error = "The selected replay summary could not be found."
        except Exception as error:
            replay_error = build_replay_error_context(error)["message"]

    context = build_template_context(request, run, meaningful_default=False)
    context["historical_replay_console"] = build_historical_replay_console(
        result=replay_result,
        error=replay_error,
        form=form,
        message=replay_message,
    )
    return context


def execute_admin_replay_form(replay_date, mode):
    normalized_date = (replay_date or "").strip()
    normalized_mode = (mode or historical_replay.SUPPORTED_MODE).strip() or historical_replay.SUPPORTED_MODE
    if not normalized_date:
        return {"error": "Enter a valid replay date.", "error_code": "invalid_date"}
    if normalized_mode != historical_replay.SUPPORTED_MODE:
        return {"error": "The selected replay mode is not supported.", "error_code": "unsupported_mode"}

    try:
        result = run_admin_historical_replay(normalized_date, mode=normalized_mode)
    except ValueError:
        return {
            "error": "The selected replay date could not be processed.",
            "error_code": "invalid_date",
        }
    except Exception as error:
        return {"error": build_replay_error_context(error)["message"], "error_code": "failed"}

    replay_id = result.get("replay_id")
    if not is_valid_replay_id(replay_id):
        return {
            "error": "The replay completed, but the result could not be opened safely.",
            "error_code": "failed",
        }
    return {"replay_id": replay_id}


def numeric_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def fmt_score_value(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return value
    if score.is_integer():
        return int(score)
    return round(score, 1)


def display_state(value):
    if not value:
        return "Unavailable"
    text = str(value).replace("_", " ").replace("-", " ")
    return text.title()


def sentence_state(value):
    return display_state(value)


def normalize_share(value):
    number = numeric_or_none(value)
    if number is None:
        return None
    if number > 1:
        return number / 100
    return number


def format_score(value):
    if value is None:
        return "Unavailable"
    return str(fmt_score_value(value))


def format_share(value):
    if value is None:
        return "Unavailable"
    return f"{value * 100:.1f}%"


def get_nested_state(run, *keys):
    current = run
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def get_crowding_risk(run):
    return get_nested_state(
        run,
        "narrative_dynamics",
        "narrative_crowding",
        "risk",
    )


def add_change(changes, category, text, importance=1):
    changes.setdefault(category, []).append(
        {
            "text": text,
            "importance": importance,
        }
    )


def describe_score_delta(name, previous, current):
    delta = current - previous
    direction = "strengthened" if delta > 0 else "weakened"
    return (
        f"{display_state(name)} {direction}: "
        f"{format_score(previous)} -> {format_score(current)}."
    )


def add_score_changes(changes, category, previous_scores, current_scores):
    if not isinstance(previous_scores, dict) or not isinstance(current_scores, dict):
        return

    names = sorted(set(previous_scores) | set(current_scores))
    for name in names:
        previous = numeric_or_none(previous_scores.get(name)) or 0
        current = numeric_or_none(current_scores.get(name)) or 0
        delta = current - previous
        if abs(delta) >= SCORE_DELTA_THRESHOLD:
            add_change(
                changes,
                category,
                describe_score_delta(name, previous, current),
                abs(delta),
            )


def add_state_change(changes, category, label, previous, current):
    if previous and current and previous != current:
        add_change(
            changes,
            category,
            f"{label} shifted: {sentence_state(previous)} -> {sentence_state(current)}.",
            5,
        )


def build_change_summary(current_run, prior_run, prior_file):
    compared_with = fmt_history_label(prior_run.get("timestamp"), prior_file)
    changes = {
        "major": [],
        "narratives": [],
        "market": [],
        "catalysts": [],
    }

    previous_group = prior_run.get("dominant_group")
    current_group = current_run.get("dominant_group")
    if previous_group and current_group and previous_group != current_group:
        add_change(
            changes,
            "major",
            f"{current_group} took leadership from {previous_group}.",
            10,
        )

    previous_theme = prior_run.get("dominant_theme")
    current_theme = current_run.get("dominant_theme")
    if previous_theme and current_theme and previous_theme != current_theme:
        add_change(
            changes,
            "major",
            f"Dominant theme shifted from {display_state(previous_theme)} to {display_state(current_theme)}.",
            8,
        )

    add_score_changes(
        changes,
        "narratives",
        prior_run.get("theme_scores") or prior_run.get("theme_counts"),
        current_run.get("theme_scores") or current_run.get("theme_counts"),
    )
    add_score_changes(
        changes,
        "narratives",
        prior_run.get("group_scores"),
        current_run.get("group_scores"),
    )

    previous_share = normalize_share(prior_run.get("dominant_share"))
    current_share = normalize_share(current_run.get("dominant_share"))
    if previous_share is not None and current_share is not None:
        share_delta = current_share - previous_share
        if abs(share_delta) >= SHARE_DELTA_THRESHOLD:
            direction = "rose" if share_delta > 0 else "fell"
            add_change(
                changes,
                "narratives",
                (
                    f"Dominant share {direction}: "
                    f"{format_share(previous_share)} -> {format_share(current_share)}."
                ),
                abs(share_delta) * 100,
            )

    previous_gap = numeric_or_none(prior_run.get("concentration_gap"))
    current_gap = numeric_or_none(current_run.get("concentration_gap"))
    if previous_gap is not None and current_gap is not None:
        gap_delta = current_gap - previous_gap
        if abs(gap_delta) >= SCORE_DELTA_THRESHOLD:
            direction = "widened" if gap_delta > 0 else "narrowed"
            add_change(
                changes,
                "narratives",
                (
                    f"Concentration gap {direction}: "
                    f"{format_score(previous_gap)} -> {format_score(current_gap)}."
                ),
                abs(gap_delta),
            )

    previous_crowding = get_crowding_risk(prior_run)
    current_crowding = get_crowding_risk(current_run)
    if previous_crowding and current_crowding and previous_crowding != current_crowding:
        direction = "changed"
        crowding_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
        if previous_crowding in crowding_order and current_crowding in crowding_order:
            direction = (
                "rose"
                if crowding_order[current_crowding] > crowding_order[previous_crowding]
                else "fell"
            )
        add_change(
            changes,
            "narratives",
            (
                f"Crowding {direction}: "
                f"{sentence_state(previous_crowding)} -> {sentence_state(current_crowding)}."
            ),
            4,
        )

    state_fields = (
        ("market", "Market Environment", ("market_environment", "state")),
        (
            "market",
            "Narrative / Market Relationship",
            ("narrative_market_relationship", "state"),
        ),
        ("market", "Breadth", ("breadth_confirmation", "state")),
        ("catalysts", "Catalyst Environment", ("catalyst_environment", "state")),
        ("catalysts", "Positioning", ("positioning_environment", "state")),
    )
    for category, label, keys in state_fields:
        add_state_change(
            changes,
            category,
            label,
            get_nested_state(prior_run, *keys),
            get_nested_state(current_run, *keys),
        )

    previous_regime = get_nested_state(prior_run, "regime_alignment", "score")
    current_regime = get_nested_state(current_run, "regime_alignment", "score")
    previous_regime_score = numeric_or_none(previous_regime)
    current_regime_score = numeric_or_none(current_regime)
    if previous_regime_score is not None and current_regime_score is not None:
        regime_delta = current_regime_score - previous_regime_score
        if abs(regime_delta) >= REGIME_SCORE_DELTA_THRESHOLD:
            direction = "improved" if regime_delta > 0 else "weakened"
            add_change(
                changes,
                "market",
                (
                    f"Regime Alignment {direction}: "
                    f"{format_score(previous_regime_score)} -> {format_score(current_regime_score)}."
                ),
                abs(regime_delta),
            )

    add_state_change(
        changes,
        "market",
        "Regime Alignment",
        get_nested_state(prior_run, "regime_alignment", "state"),
        get_nested_state(current_run, "regime_alignment", "state"),
    )

    has_primary_changes = any(
        changes[category] for category in ("major", "narratives", "market")
    )
    if has_primary_changes and not changes["catalysts"]:
        current_positioning = get_nested_state(current_run, "positioning_environment", "state")
        previous_positioning = get_nested_state(prior_run, "positioning_environment", "state")
        if current_positioning and current_positioning == previous_positioning:
            add_change(
                changes,
                "catalysts",
                f"Positioning stayed {sentence_state(current_positioning)}.",
                1,
            )

    for category in changes:
        changes[category] = sorted(
            changes[category],
            key=lambda item: item["importance"],
            reverse=True,
        )[:5]

    has_changes = any(changes[category] for category in changes)
    return {
        "compared_with": compared_with,
        "changes": changes,
        "has_changes": has_changes,
    }


def get_history_theme_scores(run):
    scores = run.get("theme_scores") or run.get("theme_counts") or {}
    return scores if isinstance(scores, dict) else {}


def get_history_group_scores(run):
    group_scores = run.get("group_scores")
    if isinstance(group_scores, dict) and group_scores:
        return group_scores
    return compute_group_scores(get_history_theme_scores(run))


def build_narrative_leadership_history():
    try:
        runs = get_recent_daily_runs(RESULTS_DIR, LEADERSHIP_HISTORY_LIMIT)
    except (OSError, json.JSONDecodeError):
        runs = []

    points = []
    for run in runs:
        if not isinstance(run, dict):
            continue

        theme_scores = get_history_theme_scores(run)
        group_scores = get_history_group_scores(run)
        sorted_groups = sorted_scores(group_scores)
        sorted_themes = sorted_scores(theme_scores)
        dominant_group = run.get("dominant_group") or (
            sorted_groups[0][0] if sorted_groups else None
        )
        dominant_theme = run.get("dominant_theme") or (
            sorted_themes[0][0] if sorted_themes else None
        )

        if not dominant_group and not dominant_theme:
            continue

        dominant_share = numeric_or_none(run.get("dominant_share"))
        if dominant_share is not None and dominant_share > 1:
            dominant_share = dominant_share / 100

        concentration_gap = numeric_or_none(run.get("concentration_gap"))
        leader_score = score_sort_value(sorted_groups[0][1]) if sorted_groups else None

        points.append(
            {
                "timestamp": run.get("timestamp"),
                "label": fmt_day_label(run.get("timestamp")),
                "dominant_group": dominant_group or "Unavailable",
                "dominant_theme": dominant_theme or "Unavailable",
                "dominant_share": dominant_share,
                "dominant_share_label": pct(dominant_share),
                "concentration_gap": concentration_gap,
                "concentration_gap_label": (
                    fmt_score_value(concentration_gap)
                    if concentration_gap is not None
                    else "Unavailable"
                ),
                "leader_score": fmt_score_value(leader_score) if leader_score is not None else None,
            }
        )

    gap_values = [
        point["concentration_gap"] for point in points if point["concentration_gap"] is not None
    ]

    max_gap = max(gap_values) if gap_values else 0
    for point in points:
        share = point["dominant_share"]
        gap = point["concentration_gap"]
        point["share_width"] = round(max(2, min(100, share * 100)), 1) if share is not None else 0
        point["gap_width"] = (
            round(max(2, min(100, (gap / max_gap) * 100)), 1)
            if gap is not None and max_gap > 0
            else 0
        )

    if len(points) < 2:
        summary = "Not enough daily leadership history yet."
    else:
        latest = points[-1]
        previous = points[-2]
        if latest["dominant_group"] == previous["dominant_group"]:
            summary = f"{latest['dominant_group']} remains the daily narrative leader."
        else:
            summary = (
                f"Leadership shifted from {previous['dominant_group']} "
                f"to {latest['dominant_group']}."
            )

    return {
        "points": points,
        "has_history": bool(points),
        "has_multiple_days": len(points) >= 2,
        "summary": summary,
    }


def build_narrative_leadership(group_scores, narrative_pulse=None, dynamics=None):
    labels = ("Dominant Narrative", "Challenging Leadership", "Secondary Narrative")
    narrative_pulse = narrative_pulse if isinstance(narrative_pulse, dict) else {}
    dynamics = dynamics if isinstance(dynamics, dict) else {}
    dynamic_groups = dynamics.get("groups") if isinstance(dynamics.get("groups"), dict) else {}
    crowding = dynamics.get("narrative_crowding") if isinstance(dynamics.get("narrative_crowding"), dict) else {}
    persistence = dynamics.get("persistence") if isinstance(dynamics.get("persistence"), dict) else {}
    dominant_group = persistence.get("dominant_group")
    top_groups = group_scores[:3]
    if not top_groups:
        return []

    leader_score = score_sort_value(top_groups[0][1])
    leadership = []
    for index, (group, score) in enumerate(top_groups):
        numeric_score = score_sort_value(score)
        pulse = narrative_pulse.get(group) if isinstance(narrative_pulse.get(group), dict) else {}
        group_dynamics = dynamic_groups.get(group) if isinstance(dynamic_groups.get(group), dict) else {}
        crowding_state = crowding.get("risk") if group == dominant_group else None
        relative_width = 100
        if leader_score > 0:
            relative_width = max(8, round((numeric_score / leader_score) * 100))
        leader_gap = leader_score - numeric_score
        leadership.append(
            {
                "rank": index + 1,
                "group": group,
                "score": fmt_score_value(score),
                "label": labels[index],
                "relative_width": relative_width,
                "leader_gap": fmt_score_value(leader_gap),
                "pulse_state": pulse.get("pulse_state"),
                "pulse_confidence": pulse.get("confidence"),
                "pulse_reason": pulse.get("reason"),
                "acceleration": display_state(group_dynamics.get("acceleration")),
                "crowding": display_state(crowding_state),
                "is_close_challenger": (
                    index == 1
                    and leader_score > 0
                    and leader_gap <= max(2, leader_score * 0.1)
                ),
            }
        )
    return leadership


def build_regime_history():
    history = []
    for path in reversed(list_regime_history_files()):
        try:
            result = load_result(path)
        except (OSError, json.JSONDecodeError):
            continue

        regime = result.get("regime_alignment")
        if not isinstance(regime, dict):
            continue

        score = valid_regime_score(regime.get("score"))
        if score is None:
            continue

        history.append(
            {
                "file": path.name,
                "label": fmt_history_label(result.get("timestamp"), path),
                "score": round(score, 1),
                "plot_score": max(0, min(100, score)),
            }
        )

    if len(history) < 2:
        return {
            "points": history,
            "has_chart": False,
            "summary": "Not enough Regime Alignment history yet.",
            "polyline": "",
        }

    width = 640
    height = 180
    pad_x = 34
    pad_y = 22
    plot_width = width - (pad_x * 2)
    plot_height = height - (pad_y * 2)
    x_step = plot_width / (len(history) - 1)

    coordinates = []
    for index, item in enumerate(history):
        x = pad_x + (x_step * index)
        y = pad_y + ((100 - item["plot_score"]) / 100 * plot_height)
        item["x"] = round(x, 2)
        item["y"] = round(y, 2)
        coordinates.append(f"{item['x']},{item['y']}")

    comparison_index = -4 if len(history) >= 4 else 0
    window_delta = history[-1]["score"] - history[comparison_index]["score"]
    latest_delta = history[-1]["score"] - history[-2]["score"]
    if window_delta >= 5:
        window_summary = "higher over the recent window"
    elif window_delta <= -5:
        window_summary = "lower over the recent window"
    else:
        window_summary = "broadly stable over the recent window"

    if latest_delta >= 5:
        latest_summary = "latest move up"
    elif latest_delta <= -5:
        latest_summary = "latest move down"
    else:
        latest_summary = "latest move stable"

    summary = f"Alignment {window_summary}; {latest_summary}."

    return {
        "points": history,
        "has_chart": True,
        "summary": summary,
        "polyline": " ".join(coordinates),
        "latest": history[-1],
        "first": history[0],
    }


def compact_environment(item):
    if not isinstance(item, dict):
        return {"state": item, "confidence": None, "reason": None}
    return {
        "state": item.get("state") or item.get("risk") or item.get("density_state"),
        "confidence": item.get("confidence"),
        "reason": item.get("reason") or item.get("read"),
    }


def get_market_context(run):
    market_data = (
        run.get("market_snapshot")
        or run.get("market_context")
        or run.get("markets")
        or {}
    )
    if not isinstance(market_data, dict):
        return []

    rows = []
    for symbol in MARKET_SYMBOLS:
        data = market_data.get(symbol)
        if isinstance(data, dict):
            rows.append(
                {
                    "symbol": symbol,
                    "ticker": data.get("ticker") or symbol,
                    "latest_close": data.get("latest_close"),
                    "pct_change": data.get("pct_change"),
                }
            )
        elif data is not None:
            rows.append(
                {
                    "symbol": symbol,
                    "ticker": symbol,
                    "latest_close": data,
                    "pct_change": None,
                }
            )
    return rows


def format_event(event):
    if not isinstance(event, dict):
        return str(event)

    name = event.get("name") or "Unnamed event"
    date = event.get("date")
    days = event.get("days_until", event.get("days_away"))
    source = event.get("source") or "manual"
    parts = [name]
    if date:
        parts.append(str(date))
    if days is not None:
        if days == 0:
            parts.append("today")
        elif days == 1:
            parts.append("tomorrow")
        else:
            parts.append(f"{days} days")
    parts.append(str(source))
    return " | ".join(parts)


def format_lifecycle_event(event):
    if not isinstance(event, dict):
        return None

    state = event.get("lifecycle_state") or "Unavailable"
    minutes_until = event.get("minutes_until_release")
    minutes_since = event.get("minutes_since_release")
    countdown = None
    if minutes_until is not None:
        countdown = f"T-{minutes_until} min"
    elif minutes_since is not None:
        countdown = f"T+{minutes_since} min"

    next_transition = event.get("next_transition")
    if not isinstance(next_transition, dict):
        next_transition = {}

    next_label = None
    if next_transition.get("next_state") and next_transition.get("minutes_away") is not None:
        next_label = (
            f"-> {next_transition.get('next_state')} "
            f"in {next_transition.get('minutes_away')} min"
        )

    return {
        "event_id": event.get("event_id"),
        "event_name": event.get("event_name") or "Unnamed event",
        "event_importance": event.get("event_importance"),
        "lifecycle_state": state,
        "state_class": str(state).lower().replace(" ", "-"),
        "countdown": countdown,
        "next_label": next_label,
        "reason": event.get("reason"),
        "confidence": event.get("confidence"),
    }


def format_event_lifecycle(lifecycle):
    if not isinstance(lifecycle, dict):
        return {"current_event": None, "events": []}

    return {
        "run_timestamp_utc": lifecycle.get("run_timestamp_utc"),
        "current_event": lifecycle.get("current_event"),
        "events": [
            formatted
            for formatted in (
                format_lifecycle_event(event)
                for event in lifecycle.get("events", [])
            )
            if formatted
        ],
    }


def build_brief_evidence_rows(narrative_brief):
    if not isinstance(narrative_brief, dict):
        return []

    registry = {
        item.get("evidence_id"): item
        for item in narrative_brief.get("evidence_registry", [])
        if isinstance(item, dict)
    }
    rows = []
    for section in narrative_brief.get("sections", []):
        if not isinstance(section, dict):
            continue
        rows.append(
            {
                "section": section,
                "evidence": [
                    registry[evidence_id]
                    for evidence_id in section.get("evidence", [])
                    if evidence_id in registry
                ],
                "module_names": sorted(
                    {
                        registry[evidence_id].get("source_module")
                        for evidence_id in section.get("evidence", [])
                        if evidence_id in registry
                        and registry[evidence_id].get("source_module")
                    }
                ),
            }
        )
    return rows


def build_view_model(run, current_file):
    regime = run.get("regime_alignment") or {}
    mode_context = run.get("mode_context") or {}
    catalyst = run.get("catalyst_environment") or {}
    event_lifecycle = format_event_lifecycle(run.get("event_lifecycle"))
    catalyst_environment_card = compact_environment(catalyst)
    catalyst_environment_card["macro_calendar_warning"] = catalyst.get(
        "macro_calendar_warning", False
    )
    catalyst_environment_card["macro_calendar_message"] = catalyst.get(
        "macro_calendar_message", ""
    )
    market_environment = run.get("market_environment")
    market_expression = run.get("market_expression")
    positioning_environment = run.get("positioning_environment")
    dynamics = run.get("narrative_dynamics") or {}
    crowding = dynamics.get("narrative_crowding") if isinstance(dynamics, dict) else None
    theme_scores = sorted_scores(run.get("theme_scores") or run.get("theme_counts"))
    group_scores = sorted_scores(run.get("group_scores"))
    examples = run.get("examples") if isinstance(run.get("examples"), dict) else {}
    narrative_brief = (
        run.get("narrative_brief")
        if isinstance(run.get("narrative_brief"), dict)
        else None
    )
    narrative_brief_evidence_rows = build_brief_evidence_rows(narrative_brief)
    top_example_themes = [theme for theme, score in theme_scores[:4] if examples.get(theme)]
    narrative_leadership = build_narrative_leadership(
        group_scores,
        run.get("narrative_pulse"),
        dynamics,
    )
    from analysis.leadership_rotation import get_rotation

    try:
        rotation_results = get_rotation()
    except Exception:
        rotation_results = []
    rotation_map = {r["group"]: r for r in rotation_results}
    for item in narrative_leadership:
        group_name = item["group"]
        item["investigation_key"] = narrative_key("group", group_name)
        rot = rotation_map.get(group_name)
        if rot:
            item["rotation_state"] = rot["rotation_state"]
            item["share_delta"] = rot["share_delta"]
            item["rotation_streak"] = rot["rotation_streak"]
            item["rotation_reason"] = rot["reason"]
        else:
            item["rotation_state"] = None
            item["share_delta"] = None
            item["rotation_streak"] = None
            item["rotation_reason"] = None

    configuration_report = build_configuration_report().to_dict()
    source_registry = build_source_registry_diagnostics()
    operations_center = build_operations_center(
        run,
        {
            "configuration_report": configuration_report,
            "source_registry": source_registry,
        },
    )

    return {
        "run": run,
        "current_file": current_file.name,
        "file_timestamp": fmt_file_timestamp(current_file),
        "last_updated": fmt_timestamp(run.get("timestamp")) or fmt_file_timestamp(current_file),
        "raw_json": json.dumps(run, indent=2, ensure_ascii=False),
        "summary": {
            "Run Timestamp": run.get("timestamp"),
            "Operating Mode": run.get("operating_mode"),
            "Dominant Theme": run.get("dominant_theme"),
            "Dominant Narrative Group": run.get("dominant_group"),
            "Regime Alignment Score": regime.get("score"),
            "Regime Alignment State": regime.get("state"),
        },
        "regime": regime,
        "mode_context": mode_context,
        "market_environment_card": compact_environment(market_environment),
        "market_expression": market_expression if isinstance(market_expression, dict) else None,
        "catalyst_environment_card": catalyst_environment_card,
        "event_lifecycle": event_lifecycle,
        "positioning_environment_card": compact_environment(positioning_environment),
        "environment": {
            "Market Environment": market_environment,
            "Narrative / Market Relationship": run.get("narrative_market_relationship"),
            "Breadth Confirmation": run.get("breadth_confirmation"),
            "Catalyst Environment": catalyst,
            "Positioning Environment": positioning_environment,
            "Narrative Crowding Risk": crowding,
        },
        "theme_scores": theme_scores,
        "group_scores": group_scores,
        "narrative_leadership": narrative_leadership,
        "dominant_share": pct(run.get("dominant_share")),
        "concentration_gap": run.get("concentration_gap"),
        "market_context": get_market_context(run),
        "narrative_brief": narrative_brief,
        "narrative_brief_evidence_rows": narrative_brief_evidence_rows,
        "narrative_brief_error": run.get("narrative_brief_generation_error"),
        "catalyst": catalyst,
        "red_events": [format_event(event) for event in catalyst.get("red_events", [])],
        "orange_events": [format_event(event) for event in catalyst.get("orange_events", [])],
        "examples": {theme: examples.get(theme) for theme in top_example_themes},
        "all_examples": examples,
        "headline_stats": {
            "Raw Headlines": run.get("raw_headline_count"),
            "Deduped Headlines": run.get("deduped_headline_count"),
            "Final Headlines": run.get("headline_count"),
            "Matched Headlines": run.get("matched_headlines"),
            "Coverage": f"{run.get('coverage_pct')}%" if run.get("coverage_pct") is not None else None,
        },
        "source_intelligence": run.get("source_intelligence") or {},
        "evidence_quality": build_evidence_quality_diagnostics(
            run.get("source_intelligence") or {}
        ),
        "platform_observability": build_platform_observability_diagnostics(
            run.get("platform_observability") or {}
        ),
        "configuration_report": configuration_report,
        "source_registry": source_registry,
        "operations_center": operations_center,
        "theme_match_audit": run.get("theme_match_audit"),
        "diagnostics": {
            key: value
            for key, value in run.items()
            if key
            not in {
                "theme_scores",
                "theme_counts",
                "group_scores",
                "examples",
                "theme_match_audit",
                "market_snapshot",
                "market_context",
                "markets",
                "catalyst_environment",
                "positioning_environment",
                "regime_alignment",
                "mode_context",
            }
        },
    }


def build_template_context(
    request: Request,
    run: Optional[str],
    meaningful_default: bool = True,
    replay_id: Optional[str] = None,
):
    recent_files = list_result_files()
    selected_path = safe_result_path(run) if run else None
    selection = (
        None
        if selected_path or not meaningful_default
        else select_latest_meaningful_run(list_all_result_files(), load_result)
    )
    current_file = selected_path or (selection.path if selection else None)
    if current_file is None and recent_files and not meaningful_default:
        current_file = recent_files[0]

    context = {
        "request": request,
        "results_dir": RESULTS_DIR,
        "recent_files": [path.name for path in recent_files],
        "recent_runs": build_run_options(recent_files),
        "selected_file": current_file.name if current_file else None,
        "message": None,
        "notice": selection.notice if selection else None,
        "view": None,
        "regime_history": build_regime_history(),
        "narrative_leadership_history": build_narrative_leadership_history(),
        "historical_replay_console": build_historical_replay_console(),
    }
    if replay_id:
        try:
            replay_dir = historical_replay.ensure_replay_dir()
            context["historical_replay_console"] = build_historical_replay_console(
                result=load_replay_summary_by_id(replay_dir, replay_id),
            )
        except (ValueError, FileNotFoundError):
            context["historical_replay_console"] = build_historical_replay_console(
                error="The selected replay summary could not be found.",
            )
        except Exception as error:
            context["historical_replay_console"] = build_historical_replay_console(
                error=build_replay_error_context(error)["message"],
            )

    if not current_file:
        context["message"] = "No MNE result files found. Run main.py first."
        return context

    try:
        result = load_result(current_file)
    except (OSError, json.JSONDecodeError) as error:
        context["message"] = f"Unable to load {current_file.name}: {error}"
        return context

    view = build_view_model(result, current_file)
    view["dashboard_trust_summary"] = build_dashboard_trust_summary(
        result,
        latest_meaningful_fallback_active=bool(selection and selection.notice),
    )
    if isinstance(result.get("change_summary"), dict):
        view["change_summary"] = result["change_summary"]
    else:
        prior_file = get_prior_result_file(current_file)
        if prior_file:
            try:
                prior_result = load_result(prior_file)
                view["change_summary"] = build_change_summary(
                    result,
                    prior_result,
                    prior_file,
                )
            except (OSError, json.JSONDecodeError):
                view["change_summary"] = None
        else:
            view["change_summary"] = None

    context["view"] = view
    return context


def build_research_context(request: Request):
    selection = select_latest_meaningful_run(list_all_result_files(), load_result)
    run, current_file = selection.run, selection.path
    context = {
        "request": request,
        "results_dir": RESULTS_DIR,
        "selected_file": current_file.name if current_file else None,
        "message": None,
        "notice": selection.notice,
        "selector": [],
    }
    if not run:
        context["message"] = "No completed MNE result files found. Run main.py first."
        return context

    context["selector"] = build_narrative_selector(run)
    return context


def build_investigation_context(request: Request, key: str, admin: bool = False):
    selection = select_latest_meaningful_run(list_all_result_files(), load_result)
    run, current_file = selection.run, selection.path
    context = {
        "request": request,
        "results_dir": RESULTS_DIR,
        "selected_file": current_file.name if current_file else None,
        "message": None,
        "notice": selection.notice,
        "investigation": None,
        "is_admin": admin,
    }
    narrative_level, narrative_id = split_narrative_key(key)
    if not narrative_level:
        context["message"] = "Unknown narrative investigation."
        return context
    if not run:
        context["message"] = "No completed MNE result files found. Run main.py first."
        return context

    try:
        event_definitions = load_event_definitions()
    except Exception:
        event_definitions = []

    context["investigation"] = build_narrative_investigation(
        run,
        narrative_level,
        narrative_id,
        admin=admin,
        event_definitions=event_definitions,
    )
    return context


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, run: Optional[str] = Query(default=None)):
    context = build_template_context(request, run, meaningful_default=True)
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/research", response_class=HTMLResponse)
def research_selector(request: Request):
    context = build_research_context(request)
    return templates.TemplateResponse("research_selector.html", context)


@app.get("/research/{key:path}", response_class=HTMLResponse)
def narrative_investigation(request: Request, key: str):
    context = build_investigation_context(request, key, admin=False)
    return templates.TemplateResponse("narrative_investigation.html", context)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    run: Optional[str] = Query(default=None),
    replay: Optional[str] = Query(default=None),
    replay_error: Optional[str] = Query(default=None),
):
    context = build_template_context(
        request,
        run,
        meaningful_default=False,
        replay_id=replay,
    )
    if replay_error:
        console = context.get("historical_replay_console") or build_historical_replay_console()
        if replay_error == "invalid_date":
            console["error"] = "Enter a valid replay date."
        elif replay_error == "unsupported_mode":
            console["error"] = "The selected replay mode is not supported."
        else:
            console["error"] = "The replay could not be completed. Review the replay diagnostics and try again."
        context["historical_replay_console"] = console
    return templates.TemplateResponse("admin.html", context)


@app.post("/admin/historical-replay")
async def admin_replay(request: Request, run: Optional[str] = Query(default=None)):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    replay_date = (form_data.get("replay_date") or [""])[0].strip()
    mode = (form_data.get("mode") or [historical_replay.SUPPORTED_MODE])[0].strip()
    result = execute_admin_replay_form(replay_date, mode)
    query = f"?run={Path(run).name}" if run else ""
    separator = "&" if query else "?"
    if result.get("replay_id"):
        return RedirectResponse(
            url=f"/admin{query}{separator}replay={result['replay_id']}",
            status_code=303,
        )
    error_code = result.get("error_code") or "failed"
    return RedirectResponse(
        url=f"/admin{query}{separator}replay_error={error_code}",
        status_code=303,
    )


@app.post("/admin/replay")
async def admin_replay_legacy(request: Request, run: Optional[str] = Query(default=None)):
    return await admin_replay(request, run=run)


@app.get("/admin/research/{key:path}", response_class=HTMLResponse)
def admin_narrative_investigation(request: Request, key: str):
    context = build_investigation_context(request, key, admin=True)
    return templates.TemplateResponse("narrative_investigation.html", context)


if __name__ == "__main__":
    ensure_data_dir()
    print(format_startup_report(build_configuration_report()))
    print()
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=False)
