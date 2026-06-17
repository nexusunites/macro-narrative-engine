import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import RESULTS_DIR


BASE_DIR = Path(__file__).resolve().parent
RECENT_RUN_LIMIT = 20
MARKET_SYMBOLS = ("QQQ", "NVDA", "VIX", "DXY")

app = FastAPI(title="Macro Narrative Engine Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def list_result_files(limit=RECENT_RUN_LIMIT):
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda path: path.name, reverse=True)
    return files[:limit]


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


def score_sort_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def sorted_scores(scores):
    if not isinstance(scores, dict):
        return []
    return sorted(scores.items(), key=lambda item: score_sort_value(item[1]), reverse=True)


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


def build_view_model(run, current_file):
    regime = run.get("regime_alignment") or {}
    mode_context = run.get("mode_context") or {}
    catalyst = run.get("catalyst_environment") or {}
    market_environment = run.get("market_environment")
    positioning_environment = run.get("positioning_environment")
    dynamics = run.get("narrative_dynamics") or {}
    crowding = dynamics.get("narrative_crowding") if isinstance(dynamics, dict) else None
    theme_scores = sorted_scores(run.get("theme_scores") or run.get("theme_counts"))
    group_scores = sorted_scores(run.get("group_scores"))
    examples = run.get("examples") if isinstance(run.get("examples"), dict) else {}
    top_example_themes = [theme for theme, score in theme_scores[:4] if examples.get(theme)]

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
        "catalyst_environment_card": compact_environment(catalyst),
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
        "dominant_share": pct(run.get("dominant_share")),
        "concentration_gap": run.get("concentration_gap"),
        "market_context": get_market_context(run),
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


def build_template_context(request: Request, run: Optional[str]):
    recent_files = list_result_files()
    selected_path = safe_result_path(run) if run else None
    current_file = selected_path or (recent_files[0] if recent_files else None)

    context = {
        "request": request,
        "results_dir": RESULTS_DIR,
        "recent_files": [path.name for path in recent_files],
        "selected_file": current_file.name if current_file else None,
        "message": None,
        "view": None,
    }

    if not current_file:
        context["message"] = "No MNE result files found. Run main.py first."
        return context

    try:
        result = load_result(current_file)
    except (OSError, json.JSONDecodeError) as error:
        context["message"] = f"Unable to load {current_file.name}: {error}"
        return context

    context["view"] = build_view_model(result, current_file)
    return context


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, run: Optional[str] = Query(default=None)):
    context = build_template_context(request, run)
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, run: Optional[str] = Query(default=None)):
    context = build_template_context(request, run)
    return templates.TemplateResponse("admin.html", context)


if __name__ == "__main__":
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=False)
