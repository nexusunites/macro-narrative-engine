import json
import hashlib
import math
import os
from urllib.parse import parse_qs, urlencode
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import RESULTS_DIR, ensure_data_dir
from mne.config_diagnostics import build_configuration_report, format_startup_report
from mne.dashboard_trust_summary import build_dashboard_trust_summary
from mne.event_lifecycle import load_event_definitions
from mne import historical_backfill, historical_backfill_admin
from mne import historical_replay, historical_request, historical_workflow
from mne.historical_comparison import build_historical_comparison
from mne.historical_comparison_view import build_user_historical_comparison
from mne.historical_research import (
    HistoricalResearchError,
    build_historical_research_context,
    load_replay_for_historical_research,
)
from mne.historical_research_view import (
    build_user_historical_view,
    list_user_replays,
)
from mne.presentation_language import HISTORICAL_COPY, NARRATIVE_HISTORY_COPY, NARRATIVE_RELATIONSHIP_COPY, research_investigation_copy
from mne.presentation_language import historical_request_category
from mne.presentation_language import historical_request_outcome
from mne.historical_replay_admin import (
    build_replay_admin_summary,
    build_replay_error_context,
    is_valid_replay_id,
    list_recent_replay_summaries,
    load_replay_summary_by_id,
    validate_replay_backfill_ids,
)
from mne.narrative_signals import NARRATIVE_GROUPS, compute_group_scores
from mne.narrative_relationships import NarrativeRelationshipError, get_relationships_for_group
from mne.sector_isolation import SECTOR_KEYS, SectorIsolationError, build_sector_isolation_context, build_sector_isolation_preview, load_sector_map
from mne.story_registry import StoryRegistryError, load_story_registry
from mne.sector_market_context import NarrativeSectorInstrumentError, classify_sectors_for_run
from mne.asset_events import AssetEventsError
from mne.asset_exploration import AssetRegistryError, build_asset_execution_context, build_asset_exploration_context, load_asset_registry, load_narrative_asset_map
from mne.asset_price_history import AssetPriceHistoryError, load_asset_price_history_or_empty
from mne.asset_participation import classify_assets_for_run
from mne.presentation_language import asset_execution_copy, asset_execution_copy_bundle
from mne.sector_market_context import build_sector_ticker_map
from main import ASSET_EXPANSION_TICKERS, NASDAQ_TICKERS
from mne.narrative_history import build_narrative_history
from mne.historical_connection import load_current_and_historical_context
from mne.explanation_layer import explain_lifecycle_state
from mne.explanation_layer import explain_market_expression
from mne.ai_analyst import (
    MODE_COMPARISON,
    MODE_HISTORICAL,
    MODE_NARRATIVE,
    MODE_TODAY,
    SUGGESTED_QUESTIONS,
    build_ai_analyst_context,
    build_deterministic_fallback,
    generate_analyst_response,
)
from mne.market_expression import build_market_expression_for_run
from mne.presentation_language import confidence as present_confidence
from mne.presentation_language import AI_ANALYST_COPY, HISTORICAL_CONNECTION_COPY
from mne.presentation_language import compose_sentence
from mne.presentation_language import metric as present_metric
from mne.presentation_language import pluralize
from mne.presentation_language import present_change_summary
from mne.presentation_language import state as present_state
from mne.presentation_language import support as present_support
from mne.presentation_language import PERSONALIZATION_COPY, narrative_display_name
from mne.presentation_language import ACCOUNT_COPY, ENTITLEMENT_COPY, entitlement_denial, usage_summary
from mne.presentation_language import (
    attention_cloud_copy,
    attention_direction_from_share_delta,
    dashboard_attention_summary,
    attention_cloud_evidence,
    attention_cloud_trend,
    attention_cloud_watch_for,
    watchlist_copy,
    attention_cloud_why,
    dashboard_evidence_meta,
    dashboard_parity_copy,
    dashboard_sector_presentation,
    research_finder_copy,
    studio_copy,
)
from mne.personalization import (
    SUPPORTED_ALERT_TYPES,
    build_default_preferences,
    follow_narrative,
    historical_view_url,
    load_preferences,
    remove_historical_view,
    save_historical_view,
    save_story,
    save_preferences,
    set_story_tracked,
    unfollow_narrative,
    unsave_story,
)
from mne.alert_engine import (
    build_default_alert_state,
    build_personalized_dashboard_context,
    evaluate_alert_rules,
    load_alert_state,
    save_alert_state,
)
from mne.operations_center import build_operations_center
from mne.platform_observability import stage_by_name
from mne.research_workspace import (
    build_narrative_investigation,
    build_narrative_selector,
    build_research_index,
    narrative_key,
    select_latest_meaningful_run,
    split_narrative_key,
)
from mne.source_registry import SourceRegistryError, load_source_registry
from mne.storage import get_recent_daily_runs, load_daily_snapshots
from mne import account_repository
from mne.accounts import anonymous_profile_status, decline_anonymous_profile, import_anonymous_profile
from mne.auth import (AUTH_ERROR, SESSION_ABSOLUTE_EXPIRY, SESSION_COOKIE_NAME, authenticate, consume_password_reset,
                      create_account, create_session, invalidate_session, secure_cookies)
from mne.database import Base, engine
from mne.security import csrf_token, get_current_user, require_admin, require_authenticated_user, validate_csrf
from mne.entitlements import EntitlementDenied, HISTORICAL_COMPARISON, HISTORICAL_REQUEST, HISTORICAL_RESEARCH, FOLLOWED_NARRATIVES as FOLLOWED_NARRATIVES_FEATURE, SAVED_HISTORICAL_VIEWS as SAVED_HISTORICAL_VIEWS_FEATURE, SAVED_STORIES as SAVED_STORIES_FEATURE, check_entitlement, require_entitlement
from mne.usage_limits import (FOLLOWED_NARRATIVES, HISTORICAL_COMPARISONS, HISTORICAL_INVESTIGATION_VIEWS,
                              HISTORICAL_REQUESTS, SAVED_HISTORICAL_VIEWS, build_entitlement_context,
                              SAVED_STORIES, consume_usage, require_capacity)


BASE_DIR = Path(__file__).resolve().parent
RECENT_RUN_LIMIT = 20
REGIME_HISTORY_LIMIT = 30
LEADERSHIP_HISTORY_LIMIT = 10
RECENT_REPLAY_LIMIT = 10
MARKET_SYMBOLS = ("QQQ", "NVDA", "VIX", "DXY")
MARKET_NAMES = {
    "QQQ": "Nasdaq 100",
    "NVDA": "Nvidia",
    "VIX": "Volatility Index",
    "DXY": "U.S. Dollar Index",
}
SCORE_DELTA_THRESHOLD = 2
SHARE_DELTA_THRESHOLD = 0.03
REGIME_SCORE_DELTA_THRESHOLD = 5

app = FastAPI(title="Macro Narrative Engine Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
TOPBAR_COPY_KEYS = (
    "brand_short", "brand_full", "nav_overview", "nav_research",
    "nav_studio", "nav_preferences", "nav_sign_in",
)
templates = Jinja2Templates(directory=BASE_DIR / "templates", context_processors=[
    lambda request: {
        "current_user": get_current_user(request),
        "csrf_token": csrf_token(request),
        "account_copy": ACCOUNT_COPY,
    }
])
templates.env.globals["dashboard_copy"] = {
    key: dashboard_parity_copy(key) for key in TOPBAR_COPY_KEYS
}
templates.env.globals["research_finder_copy"] = research_finder_copy()


@app.middleware("http")
async def enforce_allowed_origins(request: Request, call_next):
    if request.method not in {"GET","HEAD","OPTIONS"}:
        origin=request.headers.get("origin")
        allowed={item.strip() for item in os.getenv("MNE_ALLOWED_ORIGINS","").split(",") if item.strip()}
        if origin and allowed and origin not in allowed:
            return HTMLResponse("<h1>Request unavailable</h1><p>This request origin is not allowed.</p>",status_code=403)
    return await call_next(request)


@app.on_event("startup")
def verify_database_schema():
    """Fail clearly when migrations have not been applied; never create tables here."""
    from sqlalchemy import inspect
    if "users" not in inspect(engine).get_table_names():
        raise RuntimeError("Account database is not migrated. Run: alembic upgrade head")


@app.exception_handler(HTTPException)
async def calm_authorization_error(request: Request, error: HTTPException):
    if error.status_code == 401 and not request.url.path.startswith("/api/"):
        return RedirectResponse(f"/login?next={error.detail}", status_code=303)
    if error.status_code in {401, 403}:
        return HTMLResponse("<h1>Access unavailable</h1><p>" + str(error.detail) + "</p>", status_code=error.status_code)
    return JSONResponse({"detail": error.detail}, status_code=error.status_code)


@app.exception_handler(EntitlementDenied)
async def calm_entitlement_error(request: Request, error: EntitlementDenied):
    message = entitlement_denial(error.reason, error.metric)
    return templates.TemplateResponse(
        request,
        "entitlement_denied.html",
        {
            "message": message,
            "upgrade_prompt": ENTITLEMENT_COPY["upgrade_prompt"],
            "usage_lines": (),
        },
        status_code=403,
    )


def _form(body: bytes):
    return parse_qs(body.decode("utf-8"), keep_blank_values=True)


def _csrf(request: Request, form: dict):
    validate_csrf(request, (form.get("csrf_token") or [""])[0])


def build_analyst_panel(mode, context, scope=""):
    return {
        "mode": mode,
        "scope": scope,
        "copy": AI_ANALYST_COPY,
        "suggested_questions": SUGGESTED_QUESTIONS[mode],
        "initial": build_deterministic_fallback(context, mode),
    }


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


def _previous_meaningful_run(current_file):
    """Return the prior meaningful live run without recomputing engine output."""
    found_current = False
    for path in list_all_result_files():
        if path.name == current_file.name:
            found_current = True
            continue
        if not found_current:
            continue
        try:
            candidate = load_result(path)
        except (OSError, json.JSONDecodeError):
            continue
        selected = select_latest_meaningful_run([path], lambda _path: candidate)
        if selected.run:
            return candidate
    return None


def build_personalization_context(current_run=None, current_file=None, user_id=None):
    """Lazily evaluate a run and shape either account-owned or anonymous context."""
    preferences = account_repository.load_preferences(user_id) if user_id else build_default_preferences()
    state = account_repository.load_alert_state(user_id) if user_id else build_default_alert_state()
    if user_id and current_run and current_file:
        evaluated = evaluate_alert_rules(
            current_run,
            _previous_meaningful_run(current_file),
            preferences,
            state,
        )
        if evaluated != state:
            account_repository.save_alert_state(user_id, evaluated)
        state = evaluated
    context = build_personalized_dashboard_context(current_run, preferences, state)
    context.update(
        {
            "preferences": preferences,
            "alert_state": state,
            "personalization_copy": PERSONALIZATION_COPY,
            "saved_views": [
                {**item, "url": historical_view_url(item)}
                for item in preferences["saved_historical_views"]
            ],
        }
    )
    return context
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
    parsed = None
    for fmt in ("%Y-%m-%d_%H%M%S", "%Y-%m-%d_%H%M"):
        try:
            parsed = datetime.strptime(path.stem, fmt)
            break
        except ValueError:
            pass
    if parsed:
        now = datetime.now()
        if parsed.date() == now.date():
            return f"Today {parsed.strftime('%-I:%M %p')}"
        if parsed.year == now.year:
            return parsed.strftime("%b %-d")
        return parsed.strftime("%b %-d, %Y")

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


def build_historical_replay_console(
    result=None, error=None, form=None, message=None, backfill_choices=None
):
    form = form or {}
    return {
        "form": {
            "replay_date": form.get("replay_date", ""),
            "mode": form.get("mode", historical_replay.SUPPORTED_MODE),
            "backfill_ids": form.get("backfill_ids", []),
        },
        "error": error,
        "message": message,
        "result": result,
        "recent_replays": list_recent_replay_files(),
        "backfill_choices": backfill_choices if backfill_choices is not None else [],
    }


def build_historical_backfill_console(result=None, error=None, form=None, message=None):
    form = form or {}
    return {
        "form": {
            "source": form.get("source", ""),
            "start_date": form.get("start_date", ""),
            "end_date": form.get("end_date", ""),
        },
        "error": error,
        "message": message,
        "result": result,
        "supported_sources": list(historical_backfill.SUPPORTED_SOURCES),
        "recent_backfills": historical_backfill_admin.list_recent_backfill_summaries(),
    }


def execute_admin_backfill_form(source, start_date, end_date, fetch=None):
    normalized_source = (source or "").strip()
    normalized_start = (start_date or "").strip()
    normalized_end = (end_date or "").strip()
    if normalized_source not in historical_backfill.SUPPORTED_SOURCES:
        return {
            "error": "The selected source is not supported.",
            "error_code": "unsupported_source",
        }
    if not normalized_start or not normalized_end:
        return {
            "error": "Enter a valid start and end date.",
            "error_code": "invalid_date_range",
        }

    try:
        _, result = historical_backfill.run_and_persist_historical_backfill(
            normalized_source,
            normalized_start,
            normalized_end,
            fetch=fetch,
            data_dir=None,
        )
    except ValueError:
        return {
            "error": "The requested date range could not be processed.",
            "error_code": "invalid_date_range",
        }
    except Exception as error:
        return {
            "error": historical_backfill_admin.build_backfill_error_context(error)["message"],
            "error_code": "failed",
        }

    backfill_id = (result.get("manifest") or {}).get("backfill_id")
    if not historical_backfill_admin.is_valid_backfill_id(backfill_id):
        return {
            "error": "The backfill completed, but the result could not be opened safely.",
            "error_code": "failed",
        }
    return {"backfill_id": backfill_id}


def execute_admin_workflow_backfills(
    sources, replay_date, start_date=None, end_date=None
):
    normalized_replay_date = str(replay_date or "").strip()
    normalized_start = str(start_date or "").strip() or normalized_replay_date
    normalized_end = str(end_date or "").strip() or normalized_replay_date
    try:
        # Building the manifest first validates the complete request before any
        # selected connector can run.
        draft = historical_workflow.build_workflow_manifest(
            normalized_replay_date,
            normalized_start,
            normalized_end,
            historical_workflow.SUPPORTED_MODE,
            sources,
            [],
        )
        outcomes = historical_workflow.run_workflow_backfills(
            draft["requested_sources"],
            draft["requested_start_date"],
            draft["requested_end_date"],
        )
        draft["source_outcomes"] = outcomes
        historical_workflow.write_workflow_manifest(draft)
    except ValueError:
        return {
            "error": "Select supported sources and enter valid replay and range dates.",
            "error_code": "invalid_request",
        }
    except Exception:
        return {
            "error": "The workflow results could not be saved.",
            "error_code": "failed",
        }
    return {"workflow_id": draft["workflow_id"]}


def execute_admin_workflow_confirmation(workflow_id, action):
    if action == "cancel":
        return {"cancelled": True}
    if action != "run_replay":
        return {"error": "Choose a valid workflow action.", "error_code": "invalid_action"}
    try:
        manifest = historical_workflow.load_workflow_manifest(workflow_id)
    except (ValueError, FileNotFoundError, json.JSONDecodeError):
        return {"error": "The selected workflow could not be found.", "error_code": "invalid_workflow"}
    except Exception:
        return {"error": "The selected workflow could not be opened.", "error_code": "failed"}
    if not manifest:
        return {"error": "The selected workflow could not be found.", "error_code": "invalid_workflow"}
    if manifest.get("replay_id"):
        replay_id = manifest["replay_id"]
        if is_valid_replay_id(replay_id):
            return {"replay_id": replay_id}
        return {"error": "The workflow replay reference is invalid.", "error_code": "failed"}

    backfill_ids = [
        outcome.get("backfill_id")
        for outcome in manifest.get("source_outcomes") or []
        if outcome.get("status") == "COMPLETE"
        and outcome.get("replay_ready") is True
        and outcome.get("backfill_id")
    ]
    if not backfill_ids:
        return {
            "error": "No completed backfills are available for replay.",
            "error_code": "no_complete_backfills",
        }
    valid_ids, invalid_ids = validate_replay_backfill_ids(backfill_ids)
    if invalid_ids or valid_ids != backfill_ids:
        return {
            "error": "One or more completed backfills are no longer available.",
            "error_code": "invalid_backfill_selection",
        }
    try:
        _, output = historical_replay.run_and_persist_historical_replay(
            replay_date=manifest["requested_replay_date"],
            mode=manifest["mode"],
            backfill_ids=valid_ids,
        )
        replay_id = output.get("replay_id")
        if not is_valid_replay_id(replay_id):
            raise ValueError("Replay returned an invalid identifier.")
        historical_workflow.mark_workflow_replay(workflow_id, replay_id)
    except ValueError:
        return {"error": "The selected replay date could not be processed.", "error_code": "invalid_date"}
    except Exception as error:
        return {"error": build_replay_error_context(error)["message"], "error_code": "failed"}
    return {"replay_id": replay_id}


def build_historical_workflow_context(
    request, workflow_id=None, error_code=None
):
    context = {
        "request": request,
        "supported_sources": list(historical_backfill.SUPPORTED_SOURCES),
        "mode": historical_workflow.SUPPORTED_MODE,
        "workflow": None,
        "error": None,
    }
    if error_code:
        context["error"] = (
            "Select at least one supported source and enter valid dates."
            if error_code == "invalid_request"
            else "The historical workflow could not be completed."
        )
    if not workflow_id:
        return context
    try:
        manifest = historical_workflow.load_workflow_manifest(workflow_id)
        if manifest is None:
            raise FileNotFoundError("Workflow manifest was not found.")
        display_outcomes = []
        for outcome in manifest.get("source_outcomes") or []:
            display = dict(outcome)
            if outcome.get("backfill_id"):
                summary = historical_backfill_admin.load_backfill_summary_by_id(
                    outcome["backfill_id"]
                )
                display.update(summary)
                display["status"] = outcome.get("status")
                display["error_message"] = outcome.get("error_message")
            display_outcomes.append(display)
        manifest = dict(manifest)
        manifest["source_outcomes"] = display_outcomes
        manifest["replay_backfill_ids"] = [
            item.get("backfill_id")
            for item in display_outcomes
            if item.get("status") == "COMPLETE"
            and item.get("replay_ready") is True
            and item.get("backfill_id")
        ]
        context["workflow"] = manifest
    except (ValueError, FileNotFoundError, json.JSONDecodeError):
        context["error"] = "The selected historical workflow could not be found."
    except Exception:
        context["error"] = "The selected historical workflow could not be opened."
    return context


def run_admin_historical_replay(replay_date, mode=historical_replay.SUPPORTED_MODE, backfill_ids=None):
    request = historical_replay.build_replay_request(replay_date, mode=mode, backfill_ids=backfill_ids)
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
        backfill_choices=historical_backfill_admin.list_recent_backfill_summaries(),
    )
    return context


def execute_admin_replay_form(replay_date, mode, backfill_ids=None):
    normalized_date = (replay_date or "").strip()
    normalized_mode = (mode or historical_replay.SUPPORTED_MODE).strip() or historical_replay.SUPPORTED_MODE
    if not normalized_date:
        return {"error": "Enter a valid replay date.", "error_code": "invalid_date"}
    if normalized_mode != historical_replay.SUPPORTED_MODE:
        return {"error": "The selected replay mode is not supported.", "error_code": "unsupported_mode"}

    backfill_ids = backfill_ids or ()
    valid_ids, invalid_ids = validate_replay_backfill_ids(backfill_ids)
    if invalid_ids:
        return {
            "error": f"The following backfill selection(s) could not be used: {', '.join(invalid_ids)}.",
            "error_code": "invalid_backfill_selection",
        }

    try:
        result = run_admin_historical_replay(
            normalized_date, mode=normalized_mode, backfill_ids=valid_ids
        )
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
                "acceleration": group_dynamics.get("acceleration"),
                "crowding": crowding_state,
                "is_close_challenger": (
                    index == 1
                    and leader_score > 0
                    and leader_gap <= max(2, leader_score * 0.1)
                ),
            }
        )
    return leadership


ATTENTION_CLOUD_COPY_KEYS = (
    "eyebrow", "title", "framing", "research", "why_label", "tape_label",
    "driving_label", "watch_label", "connected_label", "empty_title", "empty", "none",
)


DASHBOARD_PARITY_COPY_KEYS = (
    "brand_short", "brand_full", "nav_overview", "nav_research", "nav_studio", "nav_history",
    "nav_preferences", "nav_sign_in", "big_picture_eyebrow", "big_picture_title",
    "big_picture_intro", "rank", "focus", "steady", "cooling", "strengthening",
    "strength", "momentum", "attention", "share", "investigate", "sector_eyebrow",
    "sector_title", "sector_intro", "sector_driving", "sector_steady",
    "sector_detached", "sector_unavailable", "evidence_eyebrow", "evidence_title",
    "evidence_intro", "evidence_why", "evidence_empty", "source_unavailable",
)


def build_dashboard_evidence(run, leadership):
    """Group persisted example headlines and attribution for the three visible narratives."""
    examples = run.get("examples") if isinstance(run.get("examples"), dict) else {}
    source = run.get("source_intelligence") if isinstance(run.get("source_intelligence"), dict) else {}
    accepted = source.get("accepted_evidence") if isinstance(source.get("accepted_evidence"), list) else []
    by_title = {
        str(item.get("title") or ""): item
        for item in accepted
        if isinstance(item, dict) and item.get("title")
    }
    groups = []
    for item in leadership[:3]:
        headlines = []
        for theme in NARRATIVE_GROUPS.get(item["group"], ()):
            for headline in examples.get(theme) or []:
                if not isinstance(headline, str) or not headline.strip():
                    continue
                record = by_title.get(headline, {})
                headlines.append({
                    "headline": attention_cloud_evidence(headline),
                    "meta": dashboard_evidence_meta(
                        record.get("provider") or record.get("source_name"),
                        record.get("published_at") or record.get("timestamp"),
                    ),
                })
                if len(headlines) == 3:
                    break
            if len(headlines) == 3:
                break
        if headlines:
            groups.append({"name": narrative_display_name(item["group"]), "items": headlines})
    return groups


def build_attention_cloud(run, rotation_map=None):
    """Build the honest group-level interim cloud from persisted run inputs."""
    watchlist = {
        key: watchlist_copy(key)
        for key in (
            "title", "count_singular", "count_plural", "open", "close", "add",
            "remove", "empty", "history", "investigate",
        )
    }
    story_extraction = run.get("story_extraction")
    story_rows = story_extraction.get("stories") if isinstance(story_extraction, dict) else None
    if isinstance(story_rows, dict) and story_rows:
        try:
            registry = load_story_registry()
        except StoryRegistryError:
            registry = None
        if registry is not None:
            registry_by_slug = {story.slug: story for story in registry.stories}
            visible_slugs = {
                slug for slug, item in story_rows.items()
                if slug in registry_by_slug and isinstance(item, dict)
                and score_sort_value(item.get("score")) > 0
            }
            ranked = sorted(
                visible_slugs,
                key=lambda slug: (-score_sort_value(story_rows[slug].get("score")), slug),
            )
            if ranked:
                total = sum(score_sort_value(story_rows[slug].get("score")) for slug in ranked)
                maximum = max(score_sort_value(story_rows[slug].get("score")) for slug in ranked)
                catalyst = run.get("catalyst_environment")
                catalyst = catalyst if isinstance(catalyst, dict) else {}
                catalyst_events = [
                    event for key in ("red_events", "orange_events")
                    for event in catalyst.get(key, [])
                    if isinstance(event, dict) and isinstance(event.get("name"), str)
                ]
                catalyst_by_name = {
                    event["name"].strip().lower(): event["name"].strip()
                    for event in catalyst_events
                }
                entries = []
                for slug in ranked:
                    row = story_rows[slug]
                    story = registry_by_slug[slug]
                    score = score_sort_value(row.get("score"))
                    share = (score / total) * 100 if total else 0
                    presented_direction = attention_direction_from_share_delta(row.get("share_delta"))
                    resolved_catalysts = [
                        catalyst_by_name[name.lower()]
                        for name in story.catalyst_names
                        if name.lower() in catalyst_by_name
                    ][:2]
                    examples = row.get("examples") if isinstance(row.get("examples"), list) else []
                    first_example = examples[0] if examples and isinstance(examples[0], dict) else {}
                    entries.append({
                        "name": story.display_name,
                        "weight": max(1, min(5, math.ceil((score / maximum) * 5))),
                        "direction": presented_direction["direction"],
                        "why": attention_cloud_why(story.display_name, presented_direction["label"], share),
                        "driving": [SECTOR_KEYS[key] for key in story.driving_sectors],
                        "watch_for": resolved_catalysts or [attention_cloud_watch_for(story.display_name)],
                        "connected": [
                            registry_by_slug[connected].display_name
                            for connected in story.connected if connected in visible_slugs
                        ],
                        "tape": attention_cloud_evidence(first_example.get("title")),
                        "trend": attention_cloud_trend(presented_direction["label"]),
                    })
                return {
                    "has_data": True,
                    "entries": entries,
                    "copy": {key: attention_cloud_copy(key) for key in ATTENTION_CLOUD_COPY_KEYS},
                    "watchlist_copy": watchlist,
                }

    raw_scores = run.get("group_scores") if isinstance(run.get("group_scores"), dict) else {}
    groups = []
    for group, raw_score in raw_scores.items():
        if group not in NARRATIVE_GROUPS or not NARRATIVE_GROUPS[group]:
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(score) or score <= 0:
            continue
        groups.append((group, score))
    groups.sort(key=lambda item: (-item[1], item[0]))
    groups = groups[:3]

    copy = {key: attention_cloud_copy(key) for key in ATTENTION_CLOUD_COPY_KEYS}
    if not groups:
        return {"has_data": False, "entries": [], "copy": copy, "watchlist_copy": watchlist}

    total = sum(score for _, score in groups)
    maximum = max(score for _, score in groups)
    visible_groups = {group for group, _ in groups}
    theme_scores = run.get("theme_scores") or run.get("theme_counts")
    theme_scores = theme_scores if isinstance(theme_scores, dict) else {}
    rotation_map = rotation_map or {}
    examples = run.get("examples") if isinstance(run.get("examples"), dict) else {}

    entries = []
    for group, score in groups:
        rotation = rotation_map.get(group) if isinstance(rotation_map.get(group), dict) else {}
        presented_direction = attention_direction_from_share_delta(rotation.get("share_delta"))
        positive_themes = []
        for theme in NARRATIVE_GROUPS[group]:
            try:
                theme_score = float(theme_scores.get(theme, 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(theme_score) and theme_score > 0:
                positive_themes.append((theme, theme_score))
        positive_themes.sort(key=lambda item: (-item[1], item[0]))
        driving = [narrative_display_name(theme) for theme, _ in positive_themes]
        watch_for = [attention_cloud_watch_for(name) for name in driving[:2]]

        connected = []
        try:
            relationships = get_relationships_for_group(group)
        except NarrativeRelationshipError:
            relationships = ()
        for relationship in relationships:
            related = relationship.get("related_group")
            if related in visible_groups:
                display_name = narrative_display_name(related)
                if display_name and display_name not in connected:
                    connected.append(display_name)

        tape = ""
        for theme, _ in positive_themes:
            headlines = examples.get(theme)
            if isinstance(headlines, list):
                tape = next(
                    (attention_cloud_evidence(headline) for headline in headlines if attention_cloud_evidence(headline)),
                    "",
                )
            if tape:
                break

        name = narrative_display_name(group)
        share = (score / total) * 100 if total else 0
        entries.append({
            "name": name,
            "weight": max(1, min(5, math.ceil((score / maximum) * 5))),
            "direction": presented_direction["direction"],
            "why": attention_cloud_why(name, presented_direction["label"], share),
            "driving": driving,
            "watch_for": watch_for,
            "connected": connected,
            "tape": tape,
            "trend": attention_cloud_trend(presented_direction["label"]),
        })
    return {"has_data": bool(entries), "entries": entries, "copy": copy, "watchlist_copy": watchlist}


def _snapshot_support_score(snapshot):
    if not isinstance(snapshot, dict):
        return None
    candidates = (
        get_nested_state(snapshot, "regime_alignment", "score"),
        get_nested_state(snapshot, "market_support", "score"),
        snapshot.get("market_support_score"),
        snapshot.get("support_score"),
    )
    for candidate in candidates:
        score = valid_regime_score(candidate)
        if score is not None:
            return score
    return None


def build_daily_support_history(as_of=None):
    """Build chart data exclusively from persisted daily snapshots."""
    try:
        snapshots = load_daily_snapshots(limit=3660)
    except (OSError, json.JSONDecodeError):
        snapshots = []

    history = []
    cutoff = str(as_of or "")[:10]
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        score = _snapshot_support_score(snapshot)
        if score is None:
            continue
        day = str(snapshot.get("date") or "")
        if cutoff and day and day > cutoff:
            continue
        try:
            parsed_day = datetime.fromisoformat(day)
            label = parsed_day.strftime("%b %-d")
            iso_date = parsed_day.date().isoformat()
        except ValueError:
            label = day or "Unavailable"
            iso_date = day
        history.append(
            {
                "date": iso_date,
                "label": label,
                "score": round(score, 1),
                "plot_score": max(0, min(100, score)),
            }
        )

    if len(history) < 2:
        return {
            "points": history,
            "has_chart": False,
            "summary": "Not enough market support history yet.",
            "polyline": "",
            "area_polygon": "",
            "chart_points": history,
        }

    width = 640
    height = 180
    pad_x = 34
    pad_y = 22
    plot_width = width - (pad_x * 2)
    plot_height = height - (pad_y * 2)
    x_step = plot_width / (len(history) - 1)
    plot_scores = [item["plot_score"] for item in history]
    chart_min = min(plot_scores)
    chart_max = max(plot_scores)
    domain_padding = max(5, (chart_max - chart_min) * 0.15)
    domain_min = max(0, chart_min - domain_padding)
    domain_max = min(100, chart_max + domain_padding)
    if domain_max == domain_min:
        domain_min = max(0, domain_min - 5)
        domain_max = min(100, domain_max + 5)

    coordinates = []
    for index, item in enumerate(history):
        x = pad_x + (x_step * index)
        y = pad_y + (
            (domain_max - item["plot_score"])
            / (domain_max - domain_min)
            * plot_height
        )
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

    summary = f"Support is {window_summary}; {latest_summary}."

    return {
        "points": history,
        "has_chart": True,
        "summary": summary,
        "polyline": " ".join(coordinates),
        "area_polygon": (
            f"{history[0]['x']},{height - pad_y} "
            + " ".join(coordinates)
            + f" {history[-1]['x']},{height - pad_y}"
        ),
        "chart_points": [
            {"date": item["date"], "label": item["label"], "score": item["score"]}
            for item in history
        ],
        "min_score": round(chart_min, 1),
        "max_score": round(chart_max, 1),
        "domain_min": domain_min,
        "domain_max": domain_max,
        "latest": history[-1],
        "first": history[0],
    }


def build_regime_history():
    """Preserve the existing per-run history used by shared Admin context."""
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
            "summary": "Not enough market support history yet.",
            "polyline": "",
        }

    width, height, pad_x, pad_y = 640, 180, 34, 22
    plot_width = width - (pad_x * 2)
    plot_height = height - (pad_y * 2)
    x_step = plot_width / (len(history) - 1)
    coordinates = []
    for index, item in enumerate(history):
        item["x"] = round(pad_x + (x_step * index), 2)
        item["y"] = round(
            pad_y + ((100 - item["plot_score"]) / 100 * plot_height),
            2,
        )
        coordinates.append(f"{item['x']},{item['y']}")

    comparison_index = -4 if len(history) >= 4 else 0
    window_delta = history[-1]["score"] - history[comparison_index]["score"]
    latest_delta = history[-1]["score"] - history[-2]["score"]
    window_summary = (
        "higher over the recent window" if window_delta >= 5
        else "lower over the recent window" if window_delta <= -5
        else "broadly stable over the recent window"
    )
    latest_summary = (
        "latest move up" if latest_delta >= 5
        else "latest move down" if latest_delta <= -5
        else "latest move stable"
    )
    return {
        "points": history,
        "has_chart": True,
        "summary": f"Support is {window_summary}; {latest_summary}.",
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
            change = numeric_or_none(data.get("pct_change"))
            rows.append(
                {
                    "symbol": symbol,
                    "ticker": data.get("ticker") or symbol,
                    "name": MARKET_NAMES.get(symbol, symbol),
                    "latest_close": data.get("latest_close"),
                    "pct_change": data.get("pct_change"),
                    "change_label": (
                        f"{change:+.2f}%" if change is not None else "Unavailable"
                    ),
                    "direction": (
                        "up" if change is not None and change > 0
                        else "down" if change is not None and change < 0
                        else "flat"
                    ),
                }
            )
        elif data is not None:
            rows.append(
                {
                    "symbol": symbol,
                    "ticker": symbol,
                    "name": MARKET_NAMES.get(symbol, symbol),
                    "latest_close": data,
                    "pct_change": None,
                    "change_label": "Unavailable",
                    "direction": "flat",
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

    translated_state = present_state(state)
    next_state = next_transition.get("next_state")
    translated_next_state = present_state(next_state) if next_state else None
    if translated_next_state and next_transition.get("minutes_away") is not None:
        next_label = (
            f"Next: {translated_next_state['label']} "
            f"in {next_transition.get('minutes_away')} min"
        )

    return {
        "event_id": event.get("event_id"),
        "event_name": event.get("event_name") or "Unnamed event",
        "event_importance": event.get("event_importance"),
        "lifecycle_state": state,
        "presentation_state": translated_state,
        "state_class": str(state).lower().replace(" ", "-"),
        "countdown": countdown,
        "next_label": next_label,
        "reason": event.get("reason"),
        "confidence": event.get("confidence"),
        "presentation_confidence": present_confidence(event.get("confidence")),
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
    positioning_environment = run.get("positioning_environment")
    dynamics = run.get("narrative_dynamics") or {}
    narrative_memory = run.get("narrative_memory") or {}
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
    sector_map = load_sector_map()
    sector_participation = classify_sectors_for_run(
        run, sector_map, run.get("dominant_group"), now=datetime.now().astimezone()
    ) if run.get("dominant_group") else None
    sector_isolation_preview = build_sector_isolation_preview(
        run, run.get("dominant_group"), participation=sector_participation, config=sector_map
    )
    from analysis.leadership_rotation import get_rotation

    try:
        rotation_results = get_rotation()
    except Exception:
        rotation_results = []
    rotation_map = {r["group"]: r for r in rotation_results}
    total_group_score = sum(score_sort_value(item[1]) for item in group_scores[:3])
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
        item["presentation"] = {
            "pulse": present_state(item["pulse_state"], category="Pulse"),
            "acceleration": present_state(item["acceleration"], category="Acceleration"),
            "crowding": present_state(item["crowding"], category="Crowding"),
            "confidence": present_confidence(item["pulse_confidence"]),
            "rotation": (
                attention_direction_from_share_delta(item["share_delta"])
                if item["rotation_state"]
                else None
            ),
        }
        item["presentation"]["summary"] = compose_sentence(
            item["presentation"]["pulse"],
            item["presentation"]["acceleration"],
            item["presentation"]["crowding"] if item["crowding"] else None,
        )
        explanation_state = "DOMINANT" if item["rank"] == 1 else (
            "FADING" if str(item["acceleration"] or "").lower() == "cooling"
            else "EMERGING" if str(item["rotation_state"] or "").lower() == "emerging"
            else "PERSISTENT" if str(item["acceleration"] or "").lower() == "stable"
            else "BUILDING"
        )
        item["presentation"]["explanation"] = explain_lifecycle_state(
            group_name,
            explanation_state,
            dominant_declining=item["rank"] == 1 and (item["share_delta"] or 0) < 0,
        )
        item["story_count_label"] = pluralize(item["score"], "story")
        item["leader_gap_label"] = pluralize(item["leader_gap"], "story")
        movement = item["presentation"]["rotation"] or attention_direction_from_share_delta(None)
        item["display_name"] = narrative_display_name(group_name)
        item["direction"] = movement["direction"]
        item["momentum_label"] = movement["label"]
        item["presentation"]["explanation"] = dashboard_attention_summary(
            item["display_name"], item["direction"]
        )
        item["attention_share"] = (
            round((score_sort_value(item["score"]) / total_group_score) * 100, 1)
            if total_group_score > 0 else 0
        )
        item["attention_label"] = f"{item['attention_share']:g}%"
        item["status_label"] = (
            dashboard_parity_copy("focus") if item["rank"] == 1
            else dashboard_parity_copy("cooling") if item["direction"] == "down"
            else dashboard_parity_copy("steady") if item["direction"] == "steady"
            else dashboard_parity_copy("strengthening")
        )
        item["status_state"] = "focus" if item["rank"] == 1 else item["direction"]

    cloud = build_attention_cloud(run, rotation_map)

    sector_rows = []
    for sector in sector_isolation_preview.get("sectors", ()):
        presented_sector = dashboard_sector_presentation(
            sector.get("participation_state"), sector.get("participation_label")
        )
        sector_rows.append({**sector, "dashboard": presented_sector})
    sector_isolation_preview = {**sector_isolation_preview, "sectors": sector_rows}
    dashboard_evidence = build_dashboard_evidence(run, narrative_leadership)

    configuration_report = build_configuration_report().to_dict()
    source_registry = build_source_registry_diagnostics()
    operations_center = build_operations_center(
        run,
        {
            "configuration_report": configuration_report,
            "source_registry": source_registry,
        },
    )

    market_environment_card = compact_environment(market_environment)
    positioning_environment_card = compact_environment(positioning_environment)
    presentation = {
        "metrics": {name: present_metric(name) for name in (
            "Regime Alignment", "Dominant Narrative", "Narrative Leadership",
            "Narrative Pulse", "Acceleration", "Crowding", "Market Environment",
            "Narrative Direction", "Recent Movement", "X-Ray View", "Market Reaction",
            "Catalyst Environment", "Positioning", "Change Summary",
            "Market Snapshot", "Example Headlines / Top Theme Evidence",
            "Regime Alignment History", "Data Quality",
        )},
        "regime": present_support(regime.get("score"), regime.get("state")),
        "hero_explanation": (
            narrative_leadership[0]["presentation"]["explanation"]
            if narrative_leadership else ""
        ),
        "mode_context": present_state(mode_context.get("state")),
        "mode_confidence": present_confidence(mode_context.get("confidence")),
        "market_environment": present_state(market_environment_card.get("state")),
        "catalyst_environment": present_state(catalyst_environment_card.get("state")),
        "catalyst_confidence": present_confidence(
            catalyst_environment_card.get("confidence")
        ),
        "positioning_environment": present_state(positioning_environment_card.get("state")),
    }
    evaluated_market_expression = (
        run.get("market_expression_context")
        if isinstance(run.get("market_expression_context"), dict)
        else build_market_expression_for_run(run)
    )
    market_expression_explanation = explain_market_expression(
        evaluated_market_expression
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
        "presentation": presentation,
        "dashboard_copy": {
            key: dashboard_parity_copy(key) for key in DASHBOARD_PARITY_COPY_KEYS
        },
        "market_environment_card": market_environment_card,
        "market_expression_context": evaluated_market_expression,
        "market_expression_sentence": (
            market_expression_explanation.get("headline")
            if market_expression_explanation
            and evaluated_market_expression.get("state") != "UNAVAILABLE"
            else None
        ),
        "catalyst_environment_card": catalyst_environment_card,
        "event_lifecycle": event_lifecycle,
        "positioning_environment_card": positioning_environment_card,
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
        "cloud": cloud,
        "sector_isolation_preview": sector_isolation_preview,
        "dashboard_evidence": dashboard_evidence,
        "dominant_share": pct(run.get("dominant_share")),
        "concentration_gap": run.get("concentration_gap"),
        "market_context": get_market_context(run),
        "narrative_brief": narrative_brief,
        "narrative_memory": narrative_memory if isinstance(narrative_memory, dict) else {},
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
    backfill_id: Optional[str] = None,
    include_admin: bool = True,
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
    }
    if include_admin:
        context.update(
            {
                "regime_history": build_regime_history(),
                "narrative_leadership_history": build_narrative_leadership_history(),
                "historical_replay_console": build_historical_replay_console(
                    backfill_choices=(
                        historical_backfill_admin.list_recent_backfill_summaries()
                    ),
                ),
                "historical_backfill_console": build_historical_backfill_console(),
            }
        )
    if include_admin and replay_id:
        replay_backfill_choices = historical_backfill_admin.list_recent_backfill_summaries()
        try:
            replay_dir = historical_replay.ensure_replay_dir()
            context["historical_replay_console"] = build_historical_replay_console(
                result=load_replay_summary_by_id(replay_dir, replay_id),
                backfill_choices=replay_backfill_choices,
            )
        except (ValueError, FileNotFoundError):
            context["historical_replay_console"] = build_historical_replay_console(
                error="The selected replay summary could not be found.",
                backfill_choices=replay_backfill_choices,
            )
        except Exception as error:
            context["historical_replay_console"] = build_historical_replay_console(
                error=build_replay_error_context(error)["message"],
                backfill_choices=replay_backfill_choices,
            )
    if include_admin and backfill_id:
        try:
            context["historical_backfill_console"] = build_historical_backfill_console(
                result=historical_backfill_admin.load_backfill_summary_by_id(backfill_id),
            )
        except (ValueError, FileNotFoundError):
            context["historical_backfill_console"] = build_historical_backfill_console(
                error="The selected backfill summary could not be found.",
            )
        except Exception as error:
            context["historical_backfill_console"] = build_historical_backfill_console(
                error=historical_backfill_admin.build_backfill_error_context(error)["message"],
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
    historical_connection = load_current_and_historical_context(result)
    view["historical_context_sentence"] = historical_connection.get(
        "dashboard_sentence"
    )
    view["dashboard_trust_summary"] = build_dashboard_trust_summary(
        result,
        latest_meaningful_fallback_active=bool(selection and selection.notice),
    )
    trust_summary = view["dashboard_trust_summary"]
    if trust_summary:
        trust_summary["presentation_confidence"] = present_confidence(
            trust_summary.get("confidence")
        )
    prior_file = get_prior_result_file(current_file)
    prior_result = None
    if prior_file:
        try:
            prior_result = load_result(prior_file)
        except (OSError, json.JSONDecodeError):
            prior_result = None

    current_support = valid_regime_score(
        get_nested_state(result, "regime_alignment", "score")
    )
    prior_support = valid_regime_score(
        get_nested_state(prior_result, "regime_alignment", "score")
    )
    view["support_delta"] = None
    if current_support is not None and prior_support is not None:
        delta = round(current_support - prior_support, 1)
        if float(delta).is_integer():
            delta = int(delta)
        current_day = str(result.get("timestamp") or "")[:10]
        prior_day = str(prior_result.get("timestamp") or "")[:10]
        comparison = "since the last update"
        try:
            if (
                datetime.fromisoformat(current_day)
                - datetime.fromisoformat(prior_day)
            ).days == 1:
                comparison = "since yesterday"
        except ValueError:
            pass
        view["support_delta"] = {
            "value": delta,
            "label": f"{delta:+g} {comparison}",
            "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
        }

    if isinstance(result.get("change_summary"), dict):
        view["change_summary"] = present_change_summary(result["change_summary"])
    else:
        if prior_file and prior_result:
            view["change_summary"] = present_change_summary(
                build_change_summary(result, prior_result, prior_file)
            )
        else:
            view["change_summary"] = None

    context["view"] = view
    return context


def build_research_context(request: Request):
    selection = select_latest_meaningful_run(list_all_result_files(), load_result)
    run, current_file = selection.run, selection.path
    copy = research_finder_copy()
    context = {
        "request": request,
        "results_dir": RESULTS_DIR,
        "selected_file": current_file.name if current_file else None,
        "run_label": fmt_run_label(current_file) if current_file else None,
        "message": None,
        "notice": selection.notice,
        "selector": [],
        "research_index": {"narratives": [], "stories": {}},
        "research_finder_copy": copy,
        "can_follow_narratives": False,
        "can_save_stories": False,
    }
    if not run:
        context["message"] = copy["no_run_title"]
        return context

    context["selector"] = build_narrative_selector(run)
    user = get_current_user(request)
    preferences = (
        account_repository.load_preferences(user.user_id)
        if user
        else build_default_preferences()
    )
    context["can_follow_narratives"] = check_entitlement(
        user, FOLLOWED_NARRATIVES_FEATURE
    )
    context["can_save_stories"] = check_entitlement(user, SAVED_STORIES_FEATURE)
    try:
        context["research_index"] = build_research_index(
            run,
            followed_narratives=preferences.get("followed_narratives", ()),
        )
        saved_by_slug = {
            item["story_slug"]: item for item in preferences.get("saved_stories", ())
        }
        for narrative in context["research_index"]["narratives"]:
            for story in narrative.get("stories", ()):
                saved = saved_by_slug.get(story["slug"])
                story["saved"] = saved is not None
                story["tracked"] = bool(saved and saved["tracked"])
    except StoryRegistryError:
        context["message"] = copy["no_run_title"]
    return context


def build_studio_context(request: Request):
    """Build the presentation-only Studio shell context from persisted saved stories."""
    user = get_current_user(request)
    saved_preferences = (
        account_repository.load_preferences(user.user_id).get("saved_stories", ())
        if user
        else ()
    )
    try:
        registry_stories = load_story_registry().stories
    except StoryRegistryError:
        registry_stories = ()
    registry_by_slug = {story.slug: story for story in registry_stories}

    selection = select_latest_meaningful_run(list_all_result_files(), load_result)
    selector = build_narrative_selector(selection.run) if selection.run else ()
    current_by_slug = {
        story["slug"]: story
        for narrative in selector
        for story in narrative.get("stories", ())
    }

    saved = []
    for item in saved_preferences:
        registry_story = registry_by_slug.get(item.get("story_slug"))
        if not registry_story:
            continue
        current = current_by_slug.get(registry_story.slug, {})
        direction = current.get("direction")
        if direction not in {"up", "down", "steady"}:
            direction = "steady"
        saved.append(
            {
                "display_name": registry_story.display_name,
                "direction": direction,
                "direction_label": current.get("direction_label") or dashboard_parity_copy("steady"),
                "tracked": bool(item.get("tracked")),
            }
        )

    return {
        "request": request,
        "active_tier": "studio",
        "copy": studio_copy(),
        "saved": saved,
        "watchlist": [item for item in saved if item["tracked"]],
        "signed_in": user is not None,
    }


def build_studio_compare_context(
    request: Request,
    replay_a: str = "",
    replay_b: str = "",
):
    context = build_studio_context(request)
    historical = build_user_historical_comparison_context(request, replay_a, replay_b)
    context.update(
        {
            "replays": historical["replays"],
            "comparison": historical["comparison"],
            "invalid": historical["invalid"],
            "replay_a": historical["replay_a"],
            "replay_b": historical["replay_b"],
            "historical_copy": historical["copy"],
        }
    )
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
        "_run": run,
        "run_label": fmt_run_label(current_file) if current_file else None,
        "investigation_copy": research_investigation_copy(),
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
    user = get_current_user(request)
    preferences = (
        account_repository.load_preferences(user.user_id)
        if user
        else build_default_preferences()
    )
    saved_by_slug = {
        item["story_slug"]: item for item in preferences.get("saved_stories", ())
    }
    for story in context["investigation"].get("stories", ()):
        saved = saved_by_slug.get(story["slug"])
        story["saved"] = saved is not None
        story["tracked"] = bool(saved and saved["tracked"])
    context["can_save_stories"] = check_entitlement(user, SAVED_STORIES_FEATURE)
    context["lead_instrument_candle"] = _build_lead_instrument_candle(
        context["investigation"], key
    )
    context["investigation_sectors"] = {
        "sectors": (), "has_mapping": False
    }
    if narrative_level == "group":
        try:
            sector_map = load_sector_map()
            participation = classify_sectors_for_run(
                run, sector_map, narrative_id, now=datetime.now().astimezone()
            )
            sector_context = build_sector_isolation_context(
                narrative_id, sector_map, participation
            )
            context["investigation_sectors"] = {
                **sector_context,
                "sectors": tuple(
                    {
                        **row,
                        "visual": dashboard_sector_presentation(
                            row.get("participation_state"),
                            row.get("participation_label"),
                        ),
                    }
                    for row in sector_context["sectors"]
                ),
            }
        except (SectorIsolationError, NarrativeSectorInstrumentError):
            pass
    context["history"] = (
        build_narrative_history(narrative_id)
        if narrative_level == "group"
        else None
    )
    context["historical_connection"] = load_current_and_historical_context(
        run,
        narrative_name=narrative_id,
        history=context["history"],
    )
    context["historical_connection_copy"] = HISTORICAL_CONNECTION_COPY
    context["narrative_relationship_copy"] = NARRATIVE_RELATIONSHIP_COPY
    try:
        context["related_narratives"] = (
            get_relationships_for_group(narrative_id)
            if narrative_level == "group"
            else ()
        )
    except NarrativeRelationshipError:
        context["related_narratives"] = ()
    context["history_copy"] = NARRATIVE_HISTORY_COPY
    context["narrative_key"] = key
    return context


def _build_lead_instrument_candle(investigation, narrative_key):
    """Build a compact, read-only candle teaser from the persisted price store."""
    expression = investigation.get("market_expression") if isinstance(investigation, dict) else None
    instruments = expression.get("instruments") if isinstance(expression, dict) else None
    lead = next(
        (
            item for item in (instruments or ())
            if isinstance(item, dict) and str(item.get("role") or "").lower() == "primary"
        ),
        None,
    )
    if not lead or not lead.get("asset"):
        return None

    ticker = str(lead["asset"]).upper()
    ticker_symbols = {
        **NASDAQ_TICKERS,
        **ASSET_EXPANSION_TICKERS,
        **build_sector_ticker_map(),
    }
    symbol = ticker_symbols.get(ticker, ticker)
    history = load_asset_price_history_or_empty(symbol)
    candles = history.candles[-24:]
    result = {
        "ticker": ticker,
        "label": lead.get("label") or ticker,
        "symbol": symbol,
        "available": bool(candles),
        # Market Expression does not own a unique sector. The sector index is the
        # honest route until that relationship is explicitly carried by the model.
        "href": f"/research/{narrative_key}/sectors",
        "candles": (),
    }
    if not candles:
        return result

    low = min(item.low for item in candles)
    high = max(item.high for item in candles)
    span = high - low or 1.0
    width, height, pad = 480.0, 140.0, 8.0
    slot = (width - (2 * pad)) / len(candles)

    def chart_y(value):
        return round(pad + ((high - value) / span) * (height - (2 * pad)), 2)

    rows = []
    for index, candle in enumerate(candles):
        center = round(pad + (slot * index) + (slot / 2), 2)
        open_y, close_y = chart_y(candle.open), chart_y(candle.close)
        body_y = min(open_y, close_y)
        rows.append(
            {
                "x": center,
                "wick_y": chart_y(candle.high),
                "wick_height": max(1.0, round(chart_y(candle.low) - chart_y(candle.high), 2)),
                "body_x": round(center - max(2.0, slot * 0.25), 2),
                "body_y": body_y,
                "body_width": round(max(4.0, slot * 0.5), 2),
                "body_height": max(2.0, round(abs(close_y - open_y), 2)),
                "direction": "up" if candle.close >= candle.open else "down",
            }
        )
    result["candles"] = tuple(rows)
    return result


def build_narrative_history_context(request: Request, key: str):
    context = {
        "request": request,
        "message": None,
        "history": None,
        "copy": NARRATIVE_HISTORY_COPY,
        "narrative_key": key,
    }
    narrative_level, narrative_id = split_narrative_key(key)
    if narrative_level != "group" or not narrative_id:
        context["message"] = (
            NARRATIVE_HISTORY_COPY["groups_only"]
            if narrative_level == "theme"
            else NARRATIVE_HISTORY_COPY["not_found"]
        )
        return context
    context["history"] = build_narrative_history(narrative_id)
    return context


def build_historical_research_route_context(request: Request, replay_id: str):
    context = {
        "request": request,
        "message": None,
        "historical_research": None,
    }
    try:
        artifact, replay_path = load_replay_for_historical_research(replay_id)
        replay_dir = replay_path.parent.resolve()
        context["historical_research"] = build_historical_research_context(
            artifact,
            replay_path=replay_path,
            replay_dir=replay_dir,
        )
    except HistoricalResearchError as error:
        context["message"] = error.message
    except Exception:
        context["message"] = "The selected replay artifact could not be loaded."
    return context


def build_historical_selector_context(request: Request):
    return {
        "request": request,
        "replays": list_user_replays(),
        "copy": HISTORICAL_COPY,
    }


def build_historical_request_form_context(request: Request, error_code=None):
    error_keys = {
        "invalid_dates": "request_invalid_dates",
        "empty_categories": "request_empty_categories",
        "invalid_categories": "request_invalid_categories",
        "invalid_submission": "request_invalid_submission",
        "range_too_large": "request_range_too_large",
    }
    return {
        "request": request,
        "copy": HISTORICAL_COPY,
        "categories": [
            {"token": token, **historical_request_category(token)}
            for token in historical_request.CATEGORY_ORDER
        ],
        "error": HISTORICAL_COPY.get(error_keys.get(error_code, ""))
        if error_code
        else None,
    }


def build_historical_request_status_context(request: Request, request_id: str):
    context = {
        "request": request,
        "copy": HISTORICAL_COPY,
        "historical_request": None,
        "not_found": False,
    }
    try:
        record = historical_request.load_request(request_id)
        if record is None:
            raise FileNotFoundError
        view = historical_request.build_user_request_view(record)
        view["category_labels"] = [
            historical_request_category(token)["label"]
            for token in view["categories"]
        ]
        for outcome in view["outcomes"]:
            outcome["category_label"] = historical_request_category(
                outcome["category"]
            )["label"]
            outcome["message"] = historical_request_outcome(
                outcome["outcome"], outcome["record_count"]
            )
        context["historical_request"] = view
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError):
        context["not_found"] = True
    except Exception:
        context["not_found"] = True
    return context


def build_user_historical_route_context(request: Request, replay_id: str):
    context = {
        "request": request,
        "historical": None,
        "not_found": False,
        "copy": HISTORICAL_COPY,
        "saved_replay_id": replay_id,
    }
    try:
        artifact, _ = load_replay_for_historical_research(replay_id)
        context["historical"] = build_user_historical_view(artifact)
    except (HistoricalResearchError, ValueError, TypeError):
        context["not_found"] = True
    except Exception:
        context["not_found"] = True
    return context


def build_user_historical_comparison_context(
    request: Request,
    replay_a: str = "",
    replay_b: str = "",
):
    replays = list_user_replays()
    context = {
        "request": request,
        "replays": replays,
        "comparison": None,
        "invalid": False,
        "copy": HISTORICAL_COPY,
        "replay_a": replay_a,
        "replay_b": replay_b,
    }
    replay_a = (replay_a or "").strip()
    replay_b = (replay_b or "").strip()
    context["replay_a"] = replay_a
    context["replay_b"] = replay_b
    if not replay_a and not replay_b:
        return context
    if not replay_a or not replay_b:
        context["invalid"] = True
        return context
    try:
        context["comparison"] = build_user_historical_comparison(replay_a, replay_b)
    except (HistoricalResearchError, ValueError, TypeError):
        context["invalid"] = True
    except Exception:
        context["invalid"] = True
    return context


def build_historical_comparison_route_context(request: Request, replay_a: str, replay_b: str):
    context = {
        "request": request,
        "message": None,
        "comparison": None,
    }
    replay_a = (replay_a or "").strip()
    replay_b = (replay_b or "").strip()
    if not replay_a or not replay_b:
        context["message"] = "Select two replay artifacts to compare."
        return context
    try:
        context["comparison"] = build_historical_comparison(replay_a, replay_b)
    except HistoricalResearchError as error:
        context["message"] = error.message
    except Exception:
        context["message"] = "The selected replay artifacts could not be compared."
    return context


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = Query(default="/"), error: str | None = Query(default=None)):
    if get_current_user(request): return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request":request,"next":next if next.startswith("/") else "/","error":error})


@app.post("/login")
async def login_submit(request: Request):
    form=_form(await request.body())
    user=authenticate((form.get("email") or [""])[0],(form.get("password") or [""])[0],request.client.host if request.client else "unknown")
    if not user: return templates.TemplateResponse("login.html",{"request":request,"next":"/","error":AUTH_ERROR},status_code=400)
    # A successful login always retires any presented session before issuing a
    # fresh opaque identifier (session-fixation prevention).
    invalidate_session(request.cookies.get(SESSION_COOKIE_NAME))
    session=create_session(user.user_id)
    target=(form.get("next") or ["/"])[0]
    if not target.startswith("/") or target.startswith("//"): target="/"
    response=RedirectResponse(target,status_code=303)
    response.set_cookie(SESSION_COOKIE_NAME,session.session_id,max_age=int(SESSION_ABSOLUTE_EXPIRY.total_seconds()),
                        httponly=True,samesite="lax",secure=secure_cookies(),path="/")
    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html",{"request":request,"error":None})


@app.post("/signup")
async def signup_submit(request: Request):
    form=_form(await request.body())
    try:
        create_account((form.get("email") or [""])[0],(form.get("password") or [""])[0],(form.get("display_name") or [""])[0],
                       accepted_terms=(form.get("accept_terms") or [""])[0]=="yes",accepted_privacy=(form.get("accept_privacy") or [""])[0]=="yes")
    except ValueError as error:
        return templates.TemplateResponse("signup.html",{"request":request,"error":str(error)},status_code=400)
    return RedirectResponse("/login",status_code=303)


@app.post("/logout")
async def logout(request: Request):
    require_authenticated_user(request); form=_form(await request.body()); _csrf(request,form)
    invalidate_session(request.cookies.get(SESSION_COOKIE_NAME))
    response=RedirectResponse("/",status_code=303); response.delete_cookie(SESSION_COOKIE_NAME,path="/"); return response


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    user=require_authenticated_user(request)
    entitlements = build_entitlement_context(user)
    return templates.TemplateResponse("account.html",{"request":request,"account":user,"migration":anonymous_profile_status(user.user_id),"message":None,
                                                       "entitlements":entitlements,"usage_summary":usage_summary(entitlements),"entitlement_copy":ENTITLEMENT_COPY})


@app.post("/account/profile")
async def account_profile(request: Request):
    user=require_authenticated_user(request); form=_form(await request.body()); _csrf(request,form)
    account_repository.update_display_name(user.user_id,(form.get("display_name") or [""])[0])
    return RedirectResponse("/account",status_code=303)


@app.post("/account/import")
async def account_import(request: Request):
    user=require_authenticated_user(request); form=_form(await request.body()); _csrf(request,form)
    action=(form.get("action") or [""])[0]
    if action=="import": import_anonymous_profile(user.user_id)
    elif action=="decline": decline_anonymous_profile(user.user_id)
    return RedirectResponse("/account",status_code=303)


@app.get("/reset-password", response_class=HTMLResponse)
def reset_page(request: Request, token: str = Query(default="")):
    return templates.TemplateResponse("reset_password.html",{"request":request,"token":token,"error":None})


@app.post("/reset-password")
async def reset_submit(request: Request):
    form=_form(await request.body()); token=(form.get("token") or [""])[0]
    try: success=consume_password_reset(token,(form.get("password") or [""])[0])
    except ValueError as error: return templates.TemplateResponse("reset_password.html",{"request":request,"token":token,"error":str(error)},status_code=400)
    if not success: return templates.TemplateResponse("reset_password.html",{"request":request,"token":"","error":"This reset link is invalid or expired."},status_code=400)
    return RedirectResponse("/login",status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, run: Optional[str] = Query(default=None)):
    context = build_template_context(
        request,
        run,
        meaningful_default=True,
        include_admin=False,
    )
    context["dashboard_copy"] = {
        key: dashboard_parity_copy(key) for key in DASHBOARD_PARITY_COPY_KEYS
    }
    selected_timestamp = (
        context["view"]["run"].get("timestamp")
        if context.get("view")
        else None
    )
    context["regime_history"] = build_daily_support_history(selected_timestamp)
    if context.get("view"):
        selected_path = safe_result_path(context.get("selected_file"))
        user = get_current_user(request)
        context["personalization"] = build_personalization_context(
            context["view"]["run"], selected_path, user.user_id if user else None)
        followed_names = {
            item.get("display_name")
            for item in context["personalization"].get("items", [])
            if item.get("narrative_level") == "group"
        }
        for entry in context["view"].get("cloud", {}).get("entries", []):
            entry["watched"] = entry.get("name") in followed_names
    if context.get("view"):
        analyst_context = build_ai_analyst_context(MODE_TODAY, view=context["view"])
        context["ai_analyst"] = build_analyst_panel(
            MODE_TODAY, analyst_context, context.get("selected_file") or ""
        )
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/preferences", response_class=HTMLResponse)
def preferences_page(request: Request):
    user = require_authenticated_user(request)
    selection = select_latest_meaningful_run(list_all_result_files(), load_result)
    personalization = build_personalization_context(selection.run, selection.path, user.user_id)
    selector = build_narrative_selector(selection.run) if selection.run else []
    try:
        story_names = {
            story.slug: story.display_name for story in load_story_registry().stories
        }
    except StoryRegistryError:
        story_names = {}
    return templates.TemplateResponse(
        "preferences.html",
        {
            "request": request,
            "personalization": personalization,
            "narratives": selector,
            "supported_alert_types": SUPPORTED_ALERT_TYPES,
            "display_name": narrative_display_name,
            "story_names": story_names,
            "migration": anonymous_profile_status(user.user_id),
        },
    )


@app.post("/preferences/narratives")
async def change_followed_narrative(request: Request):
    user = require_authenticated_user(request)
    form = _form(await request.body()); _csrf(request, form)
    level = (form.get("narrative_level") or [""])[0]
    key = (form.get("narrative_key") or [""])[0]
    action = (form.get("action") or [""])[0]
    return_to = (form.get("return_to") or ["/preferences"])[0]
    if return_to not in {"/preferences", "/research"}:
        return_to = "/preferences"
    profile = account_repository.load_preferences(user.user_id)
    try:
        existing = {x["narrative_level"] + ":" + x["narrative_key"] for x in profile["followed_narratives"]}
        if action == "follow" and level + ":" + key not in existing:
            require_entitlement(user, FOLLOWED_NARRATIVES_FEATURE)
            require_capacity(user, FOLLOWED_NARRATIVES)
        profile = (
            follow_narrative(profile, level, key)
            if action == "follow"
            else unfollow_narrative(profile, level, key)
        )
        account_repository.save_preferences(user.user_id, profile)
    except ValueError:
        pass
    return RedirectResponse(return_to, status_code=303)


@app.post("/preferences/stories")
async def change_saved_story(request: Request):
    user = require_authenticated_user(request)
    form = _form(await request.body()); _csrf(request, form)
    story_slug = (form.get("story_slug") or [""])[0]
    action = (form.get("action") or [""])[0]
    return_to = (form.get("return_to") or ["/preferences"])[0]
    if return_to not in {"/preferences", "/research", "/studio"}:
        return_to = "/preferences"
    profile = account_repository.load_preferences(user.user_id)
    try:
        existing = {item["story_slug"] for item in profile["saved_stories"]}
        if action == "save" and story_slug not in existing:
            require_entitlement(user, SAVED_STORIES_FEATURE)
            require_capacity(user, SAVED_STORIES)
        if action == "save":
            profile = save_story(profile, story_slug)
        elif action == "unsave":
            profile = unsave_story(profile, story_slug)
        elif action in {"track", "untrack"}:
            profile = set_story_tracked(profile, story_slug, action == "track")
        else:
            raise ValueError("Invalid saved story action.")
        account_repository.save_preferences(user.user_id, profile)
    except (EntitlementDenied, ValueError):
        pass
    return RedirectResponse(return_to, status_code=303)


@app.post("/preferences/alerts")
async def change_alert_preferences(request: Request):
    user = require_authenticated_user(request)
    form = _form(await request.body()); _csrf(request, form)
    selected = set(form.get("alert_type") or [])
    profile = account_repository.load_preferences(user.user_id)
    profile["preferred_alert_types"] = [
        item for item in SUPPORTED_ALERT_TYPES if item in selected
    ]
    account_repository.save_preferences(user.user_id, profile)
    return RedirectResponse("/preferences", status_code=303)


@app.post("/preferences/history")
async def change_saved_history(request: Request):
    user = require_authenticated_user(request)
    form = _form(await request.body()); _csrf(request, form)
    view_type = (form.get("view_type") or [""])[0]
    replay_ids = form.get("replay_id") or []
    action = (form.get("action") or [""])[0]
    label = (form.get("label") or [None])[0]
    profile = account_repository.load_preferences(user.user_id)
    try:
        existing = {(x["view_type"], tuple(x["replay_ids"])) for x in profile["saved_historical_views"]}
        if action == "save" and (view_type, tuple(replay_ids)) not in existing:
            require_entitlement(user, SAVED_HISTORICAL_VIEWS_FEATURE)
            require_capacity(user, SAVED_HISTORICAL_VIEWS)
        profile = (
            save_historical_view(profile, view_type, replay_ids, label=label)
            if action == "save"
            else remove_historical_view(profile, view_type, replay_ids)
        )
        account_repository.save_preferences(user.user_id, profile)
    except ValueError:
        pass
    return RedirectResponse(request.headers.get("referer") or "/preferences", status_code=303)


@app.get("/research", response_class=HTMLResponse)
def research_selector(request: Request):
    context = build_research_context(request)
    return templates.TemplateResponse("research_selector.html", context)


@app.get("/studio", response_class=HTMLResponse)
def studio_page(request: Request):
    return templates.TemplateResponse("studio.html", build_studio_compare_context(request))


@app.get("/studio/compare", response_class=HTMLResponse)
def studio_compare(
    request: Request,
    replay_a: str = Query(default=""),
    replay_b: str = Query(default=""),
):
    context = build_studio_compare_context(request, replay_a, replay_b)
    if context.get("comparison"):
        user = get_current_user(request)
        if user:
            require_entitlement(user, HISTORICAL_COMPARISON)
            consume_usage(
                user,
                HISTORICAL_COMPARISONS,
                object_reference="|".join(sorted((replay_a, replay_b))),
            )
    return templates.TemplateResponse("studio.html", context)


@app.post("/api/ai-analyst")
async def ask_ai_analyst(request: Request):
    """Handle one explicit, stateless Analyst question."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": AI_ANALYST_COPY["error"]}, status_code=400)
    mode = payload.get("mode") if isinstance(payload, dict) else None
    scope = str(payload.get("scope") or "") if isinstance(payload, dict) else ""
    question = str(payload.get("question") or "") if isinstance(payload, dict) else ""
    try:
        if mode == MODE_TODAY:
            page = build_template_context(
                request, scope or None, meaningful_default=True, include_admin=False
            )
            analyst_context = build_ai_analyst_context(
                mode, view=page.get("view")
            )
        elif mode == MODE_NARRATIVE:
            page = build_investigation_context(request, scope, admin=False)
            analyst_context = build_ai_analyst_context(
                mode,
                investigation=page.get("investigation"),
                history=page.get("history"),
                historical_connections=page.get("historical_connection"),
            )
        elif mode == MODE_HISTORICAL:
            page = build_user_historical_route_context(request, scope)
            analyst_context = build_ai_analyst_context(
                mode, historical=page.get("historical")
            )
        elif mode == MODE_COMPARISON:
            replay_a, separator, replay_b = scope.partition("|")
            if not separator:
                raise ValueError("Missing comparison scope.")
            page = build_user_historical_comparison_context(
                request, replay_a, replay_b
            )
            analyst_context = build_ai_analyst_context(
                mode, comparison=page.get("comparison")
            )
        else:
            raise ValueError("Unsupported Analyst mode.")
    except Exception:
        return JSONResponse({"error": AI_ANALYST_COPY["error"]}, status_code=400)
    return JSONResponse(
        generate_analyst_response(analyst_context, mode, question)
    )


@app.get("/research/{key:path}/history", response_class=HTMLResponse)
def narrative_history(request: Request, key: str):
    context = build_narrative_history_context(request, key)
    return templates.TemplateResponse("narrative_history.html", context)


@app.get("/research/{key:path}/sectors", response_class=HTMLResponse)
def sector_isolation(request: Request, key: str):
    context = build_investigation_context(request, key, admin=False)
    narrative_level, narrative_id = split_narrative_key(key)
    context["narrative_key"] = key
    if narrative_level != "group" or not narrative_id:
        context["message"] = "Sector Isolation is available for narrative groups."
        context["sector_isolation"] = None
    else:
        try:
            sector_map = load_sector_map()
            participation = classify_sectors_for_run(
                context.get("_run") or {}, sector_map, narrative_id, now=datetime.now().astimezone()
            )
            context["sector_isolation"] = build_sector_isolation_context(narrative_id, sector_map, participation)
        except (SectorIsolationError, NarrativeSectorInstrumentError):
            context["message"] = "Sector relationships are temporarily unavailable."
            context["sector_isolation"] = None
    return templates.TemplateResponse("sector_isolation.html", context)


@app.get("/research/{key:path}/sectors/{sector}/assets", response_class=HTMLResponse)
def asset_exploration(request: Request, key: str, sector: str):
    context = build_investigation_context(request, key, admin=False)
    narrative_level, narrative_id = split_narrative_key(key)
    context["narrative_key"] = key
    if narrative_level != "group" or not narrative_id:
        context["message"] = "Asset Exploration is available for narrative groups."
        context["asset_exploration"] = None
    else:
        try:
            sector_map = load_sector_map()
            sector_participation = classify_sectors_for_run(context.get("_run") or {}, sector_map, narrative_id, now=datetime.now().astimezone())
            sector_context = build_sector_isolation_context(narrative_id, sector_map, sector_participation)
            sector_row = next((row for row in sector_context["sectors"] if row["sector_key"] == sector), None)
            if sector_row is None:
                context["message"] = "This sector is not mapped to the selected narrative."
                context["asset_exploration"] = None
            else:
                registry = load_asset_registry()
                asset_map = load_narrative_asset_map(registry=registry)
                participation = classify_assets_for_run(context.get("_run") or {}, asset_map, registry, narrative_id, now=datetime.now().astimezone())
                context["asset_exploration"] = build_asset_exploration_context(narrative_id, sector, registry=registry, asset_map=asset_map, participation=participation, sector_row=sector_row, market_expression=(context.get("_run") or {}).get("market_expression_context"))
        except (AssetRegistryError, SectorIsolationError, NarrativeSectorInstrumentError):
            context["message"] = "Asset relationships are temporarily unavailable."
            context["asset_exploration"] = None
    return templates.TemplateResponse("asset_exploration.html", context)


@app.get("/research/{key:path}/sectors/{sector}/assets/{ticker}", response_class=HTMLResponse)
def asset_execution(request: Request, key: str, sector: str, ticker: str):
    context = build_investigation_context(request, key, admin=False)
    narrative_level, narrative_id = split_narrative_key(key)
    context["narrative_key"] = key
    context["asset_execution"] = None
    context["asset_execution_copy"] = asset_execution_copy_bundle()
    if narrative_level != "group" or not narrative_id:
        context["message"] = asset_execution_copy("group_only")
    else:
        try:
            sector_map = load_sector_map()
            sector_participation = classify_sectors_for_run(context.get("_run") or {}, sector_map, narrative_id, now=datetime.now().astimezone())
            sector_context = build_sector_isolation_context(narrative_id, sector_map, sector_participation)
            sector_row = next((row for row in sector_context["sectors"] if row["sector_key"] == sector), None)
            if sector_row is None:
                context["message"] = asset_execution_copy("sector_unmapped")
            else:
                registry = load_asset_registry()
                canonical_ticker = ticker.upper()
                if canonical_ticker not in registry["assets"]:
                    context["message"] = asset_execution_copy("unmapped_ticker")
                else:
                    asset_map = load_narrative_asset_map(registry=registry)
                    run = context.get("_run") or {}
                    participation = classify_assets_for_run(run, asset_map, registry, narrative_id, now=datetime.now().astimezone())
                    ticker_symbols = {**NASDAQ_TICKERS, **ASSET_EXPANSION_TICKERS, **build_sector_ticker_map()}
                    catalyst_environment = run.get("catalyst_environment") or {}
                    upcoming_catalysts = [
                        *(catalyst_environment.get("red_events") or []),
                        *(catalyst_environment.get("orange_events") or []),
                    ]
                    context["asset_execution"] = build_asset_execution_context(
                        narrative_id,
                        sector,
                        canonical_ticker,
                        registry=registry,
                        asset_map=asset_map,
                        participation=participation,
                        sector_row=sector_row,
                        market_expression=run.get("market_expression_context"),
                        market_snapshot=run.get("market_snapshot"),
                        ticker_symbols=ticker_symbols,
                        upcoming_loader=lambda: upcoming_catalysts,
                    )
        except AssetRegistryError as exc:
            if "not mapped to sector" in str(exc):
                context["message"] = asset_execution_copy("instrument_sector_unmapped")
            else:
                context["message"] = asset_execution_copy("unavailable_relationships")
        except (AssetEventsError, AssetPriceHistoryError, SectorIsolationError, NarrativeSectorInstrumentError):
            context["message"] = asset_execution_copy("unavailable_relationships")
    return templates.TemplateResponse("asset_execution.html", context)


@app.get("/research/{key:path}", response_class=HTMLResponse)
def narrative_investigation(request: Request, key: str):
    context = build_investigation_context(request, key, admin=False)
    if context.get("investigation"):
        analyst_context = build_ai_analyst_context(
            MODE_NARRATIVE,
            investigation=context["investigation"],
            history=context.get("history"),
            historical_connections=context.get("historical_connection"),
        )
        context["ai_analyst"] = build_analyst_panel(
            MODE_NARRATIVE, analyst_context, key
        )
    return templates.TemplateResponse("narrative_investigation.html", context)


@app.get("/history", response_class=HTMLResponse)
def historical_selector(request: Request):
    return templates.TemplateResponse(
        "historical_selector.html",
        build_historical_selector_context(request),
    )


@app.get("/history/request", response_class=HTMLResponse)
def historical_request_form(
    request: Request,
    error: Optional[str] = Query(default=None),
):
    require_authenticated_user(request)
    return templates.TemplateResponse(
        "historical_request.html",
        build_historical_request_form_context(request, error),
    )


@app.post("/history/request")
async def submit_historical_request(request: Request):
    user = None
    if hasattr(request, "state"):
        user = require_authenticated_user(request)
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    if hasattr(request, "state"):
        _csrf(request, form_data)
    try:
        if user:
            require_entitlement(user, HISTORICAL_REQUEST)
        historical_request.validate_form_fields(form_data)
        if len(form_data.get("start_date", [])) != 1 or len(
            form_data.get("end_date", [])
        ) != 1:
            raise historical_request.HistoricalRequestValidationError(
                "invalid_submission"
            )
        request_identity = json.dumps({
            "start_date": form_data["start_date"][0],
            "end_date": form_data["end_date"][0],
            "category": sorted(set(form_data.get("category", []))),
        }, sort_keys=True, separators=(",", ":"))
        if user:
            consume_usage(user, HISTORICAL_REQUESTS, object_reference=hashlib.sha256(request_identity.encode()).hexdigest())
        result = historical_request.execute_request(
            form_data["start_date"][0],
            form_data["end_date"][0],
            form_data.get("category", []),
            run_backfills=execute_admin_workflow_backfills,
            run_replay=execute_admin_workflow_confirmation,
        )
        if user:
            account_repository.claim_historical_request(user.user_id, result["request_id"])
    except EntitlementDenied:
        raise
    except historical_request.HistoricalRequestValidationError as error:
        return RedirectResponse(
            url=f"/history/request?error={error.code}",
            status_code=303,
        )
    except Exception:
        return RedirectResponse(
            url="/history/request?error=invalid_submission",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/history/request/{result['request_id']}",
        status_code=303,
    )


@app.get("/history/request/{request_id}", response_class=HTMLResponse)
def historical_request_status(request: Request, request_id: str):
    user=require_authenticated_user(request)
    if not account_repository.owns_historical_request(user.user_id,request_id):
        raise HTTPException(status_code=404,detail="That historical request was not found.")
    context = build_historical_request_status_context(request, request_id)
    return templates.TemplateResponse(
        "historical_request_status.html",
        context,
        status_code=404 if context["not_found"] else 200,
    )


@app.get("/history/compare", response_class=HTMLResponse)
def user_historical_comparison(
    replay_a: str = Query(default=""),
    replay_b: str = Query(default=""),
):
    query = urlencode(
        {
            key: value
            for key, value in (("replay_a", replay_a), ("replay_b", replay_b))
            if value
        }
    )
    target = f"/studio/compare?{query}" if query else "/studio/compare"
    return RedirectResponse(target, status_code=307)


@app.get("/history/{replay_id}", response_class=HTMLResponse)
def historical_investigation(request: Request, replay_id: str):
    context = build_user_historical_route_context(request, replay_id)
    if context.get("historical"):
        user = get_current_user(request)
        if user:
            require_entitlement(user, HISTORICAL_RESEARCH)
            consume_usage(user, HISTORICAL_INVESTIGATION_VIEWS, object_reference=replay_id)
        analyst_context = build_ai_analyst_context(
            MODE_HISTORICAL, historical=context["historical"]
        )
        context["ai_analyst"] = build_analyst_panel(
            MODE_HISTORICAL, analyst_context, replay_id
        )
    return templates.TemplateResponse(
        "historical_investigation.html",
        context,
        status_code=404 if context["not_found"] else 200,
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    run: Optional[str] = Query(default=None),
    replay: Optional[str] = Query(default=None),
    replay_error: Optional[str] = Query(default=None),
    backfill: Optional[str] = Query(default=None),
    backfill_error: Optional[str] = Query(default=None),
):
    require_admin(request)
    context = build_template_context(
        request,
        run,
        meaningful_default=False,
        replay_id=replay,
        backfill_id=backfill,
    )
    if replay_error:
        console = context.get("historical_replay_console") or build_historical_replay_console()
        if replay_error == "invalid_date":
            console["error"] = "Enter a valid replay date."
        elif replay_error == "unsupported_mode":
            console["error"] = "The selected replay mode is not supported."
        elif replay_error == "invalid_backfill_selection":
            console["error"] = "One or more selected backfills could not be used. Review your selection and try again."
        else:
            console["error"] = "The replay could not be completed. Review the replay diagnostics and try again."
        context["historical_replay_console"] = console
    if backfill_error:
        console = context.get("historical_backfill_console") or build_historical_backfill_console()
        if backfill_error == "unsupported_source":
            console["error"] = "The selected source is not supported."
        elif backfill_error == "invalid_date_range":
            console["error"] = "Enter a valid start and end date."
        else:
            console["error"] = "The backfill could not be completed. Review the backfill diagnostics and try again."
        context["historical_backfill_console"] = console
    return templates.TemplateResponse("admin.html", context)


@app.get("/admin/historical-workflow", response_class=HTMLResponse)
def admin_historical_workflow(
    request: Request,
    workflow_error: Optional[str] = Query(default=None),
):
    require_admin(request)
    return templates.TemplateResponse(
        "historical_workflow.html",
        build_historical_workflow_context(request, error_code=workflow_error),
    )


@app.post("/admin/historical-workflow/run-backfills")
async def admin_historical_workflow_backfills(request: Request):
    admin_user = None
    if hasattr(request, "state"):
        admin_user = require_admin(request)
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    if hasattr(request, "state"):
        _csrf(request, form_data)
    result = execute_admin_workflow_backfills(
        form_data.get("source", []),
        (form_data.get("replay_date") or [""])[0],
        (form_data.get("start_date") or [""])[0],
        (form_data.get("end_date") or [""])[0],
    )
    if admin_user: account_repository.record_admin_action(admin_user.user_id,"HISTORICAL_WORKFLOW_BACKFILLS",result.get("workflow_id"))
    if result.get("workflow_id"):
        return RedirectResponse(
            url=(
                "/admin/historical-workflow/confirm"
                f"?workflow_id={result['workflow_id']}"
            ),
            status_code=303,
        )
    return RedirectResponse(
        url=(
            "/admin/historical-workflow"
            f"?workflow_error={result.get('error_code') or 'failed'}"
        ),
        status_code=303,
    )


@app.get("/admin/historical-workflow/confirm", response_class=HTMLResponse)
def admin_historical_workflow_confirm(
    request: Request,
    workflow_id: Optional[str] = Query(default=None),
    workflow_error: Optional[str] = Query(default=None),
):
    require_admin(request)
    return templates.TemplateResponse(
        "historical_workflow.html",
        build_historical_workflow_context(
            request, workflow_id=workflow_id, error_code=workflow_error
        ),
    )


@app.post("/admin/historical-workflow/confirm")
async def admin_historical_workflow_confirmation(request: Request):
    admin_user=require_admin(request)
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    _csrf(request, form_data)
    workflow_id = (form_data.get("workflow_id") or [""])[0].strip()
    action = (form_data.get("action") or [""])[0].strip()
    result = execute_admin_workflow_confirmation(workflow_id, action)
    account_repository.record_admin_action(admin_user.user_id,"HISTORICAL_WORKFLOW_CONFIRMATION",workflow_id)
    if result.get("cancelled"):
        return RedirectResponse(url="/admin/historical-workflow", status_code=303)
    if result.get("replay_id"):
        return RedirectResponse(
            url=f"/admin?replay={result['replay_id']}", status_code=303
        )
    error_code = result.get("error_code") or "failed"
    safe_workflow_id = (
        workflow_id if historical_workflow.is_valid_workflow_id(workflow_id) else ""
    )
    if safe_workflow_id:
        url = (
            "/admin/historical-workflow/confirm"
            f"?workflow_id={safe_workflow_id}&workflow_error={error_code}"
        )
    else:
        url = f"/admin/historical-workflow?workflow_error={error_code}"
    return RedirectResponse(url=url, status_code=303)


@app.post("/admin/historical-replay")
async def admin_replay(request: Request, run: Optional[str] = Query(default=None)):
    admin_user=require_admin(request)
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    _csrf(request, form_data)
    replay_date = (form_data.get("replay_date") or [""])[0].strip()
    mode = (form_data.get("mode") or [historical_replay.SUPPORTED_MODE])[0].strip()
    selected_backfill_ids = form_data.get("backfill_id", [])
    result = execute_admin_replay_form(replay_date, mode, backfill_ids=selected_backfill_ids)
    account_repository.record_admin_action(admin_user.user_id,"HISTORICAL_REPLAY",result.get("replay_id"))
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


@app.post("/admin/historical-backfill")
async def admin_historical_backfill(request: Request, run: Optional[str] = Query(default=None)):
    admin_user=require_admin(request)
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    _csrf(request, form_data)
    source = (form_data.get("source") or [""])[0].strip()
    start_date = (form_data.get("start_date") or [""])[0].strip()
    end_date = (form_data.get("end_date") or [""])[0].strip()
    result = execute_admin_backfill_form(source, start_date, end_date)
    account_repository.record_admin_action(admin_user.user_id,"HISTORICAL_BACKFILL",result.get("backfill_id"))
    query = f"?run={Path(run).name}" if run else ""
    separator = "&" if query else "?"
    if result.get("backfill_id"):
        return RedirectResponse(
            url=f"/admin{query}{separator}backfill={result['backfill_id']}",
            status_code=303,
        )
    error_code = result.get("error_code") or "failed"
    return RedirectResponse(
        url=f"/admin{query}{separator}backfill_error={error_code}",
        status_code=303,
    )


@app.post("/admin/replay")
async def admin_replay_legacy(request: Request, run: Optional[str] = Query(default=None)):
    return await admin_replay(request, run=run)


@app.get("/admin/research/{key:path}", response_class=HTMLResponse)
def admin_narrative_investigation(request: Request, key: str):
    require_admin(request)
    context = build_investigation_context(request, key, admin=True)
    return templates.TemplateResponse("narrative_investigation.html", context)


@app.get("/admin/replay/{replay_id}/research", response_class=HTMLResponse)
def admin_historical_research(request: Request, replay_id: str):
    require_admin(request)
    context = build_historical_research_route_context(request, replay_id)
    return templates.TemplateResponse("historical_research.html", context)


@app.get("/admin/replay/compare", response_class=HTMLResponse)
def admin_historical_comparison(
    request: Request,
    replay_a: Optional[str] = Query(default=None),
    replay_b: Optional[str] = Query(default=None),
):
    require_admin(request)
    context = build_historical_comparison_route_context(request, replay_a, replay_b)
    return templates.TemplateResponse("historical_comparison.html", context)


if __name__ == "__main__":
    ensure_data_dir()
    print(format_startup_report(build_configuration_report()))
    print()
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=False)
