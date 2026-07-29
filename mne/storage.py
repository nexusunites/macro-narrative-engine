import json
import logging
import statistics
from datetime import date, datetime
from pathlib import Path

from config import DATA_DIR, HEADLINES_DIR, REPORTS_DIR, RESULTS_DIR


SNAPSHOTS_DIR = DATA_DIR / "snapshots"
LOGGER = logging.getLogger(__name__)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _open_unique_text_file(directory: Path, stem: str):
    collision_index = 0
    while True:
        suffix = f"_{collision_index:02d}" if collision_index else ""
        path = directory / f"{stem}{suffix}.txt"
        try:
            return path, open(path, "x", encoding="utf-8")
        except FileExistsError:
            collision_index += 1


def save_headlines(headlines, stamp, headlines_dir=HEADLINES_DIR, label=None):
    headlines_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{label}" if label else ""
    headlines_file, file_handle = _open_unique_text_file(
        headlines_dir, f"{stamp}{suffix}"
    )

    with file_handle as f:
        for headline in headlines:
            f.write(headline + "\n")

    return headlines_file


def save_run_json(run, stamp, results_dir=RESULTS_DIR):
    results_dir.mkdir(parents=True, exist_ok=True)
    collision_index = 0

    while True:
        suffix = f"_{collision_index:02d}" if collision_index else ""
        results_file = results_dir / f"{stamp}{suffix}.json"
        try:
            with open(results_file, "x", encoding="utf-8") as f:
                run["run_id"] = results_file.stem
                json.dump(run, f, ensure_ascii=False, indent=2)
            break
        except FileExistsError:
            collision_index += 1

    return results_dir, results_file


def save_report(report_text, stamp, reports_dir=REPORTS_DIR):
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file, file_handle = _open_unique_text_file(reports_dir, stamp)

    with file_handle as f:
        f.write(report_text)

    return report_file


def get_last_two_result_files(results_dir: Path):
    files = sorted(results_dir.glob("*.json"))
    if len(files) < 2:
        return None, None
    return files[-1], files[-2]


def get_recent_runs(results_dir: Path, lookback: int):
    files = sorted(results_dir.glob("*.json"))

    if len(files) == 0:
        return []

    selected = files[-lookback:]
    runs = []

    for f in selected:
        with open(f, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))

    return runs


def get_recent_daily_runs(results_dir: Path, lookback: int):
    files = sorted(results_dir.glob("*.json"))

    if not files:
        return []

    daily_latest = {}

    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            run = json.load(fh)

        timestamp = run.get("timestamp", "")
        day = timestamp[:10]  # YYYY-MM-DD

        if day:
            daily_latest[day] = run

    days = sorted(daily_latest.keys())
    selected_days = days[-lookback:]

    return [daily_latest[day] for day in selected_days]


def _extract_run_date(run_data: dict, fallback_path: Path | None = None) -> str | None:
    timestamp = run_data.get("timestamp") or run_data.get("run_date")
    if isinstance(timestamp, str) and len(timestamp) >= 10:
        return timestamp[:10]

    if fallback_path is not None:
        name = fallback_path.stem
        if len(name) >= 10:
            candidate = name[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                pass

    return None


def _extract_timestamp(run_data: dict) -> str:
    timestamp = run_data.get("timestamp") or run_data.get("run_date")
    if timestamp:
        return str(timestamp)
    return datetime.now().isoformat(timespec="seconds")


def _extract_run_id(run_data: dict) -> str | None:
    run_id = run_data.get("run_id")
    if run_id:
        return str(run_id)
    return None


def _extract_event_lifecycle(run_data: dict) -> dict | None:
    event_lifecycle = run_data.get("event_lifecycle")
    if isinstance(event_lifecycle, dict):
        return event_lifecycle
    return None


def _extract_regime_alignment(run_data: dict) -> dict:
    regime = run_data.get("regime_alignment")
    if not isinstance(regime, dict):
        return {"score": None, "state": None}

    score = regime.get("score")
    try:
        score = int(round(float(score))) if score is not None else None
    except (TypeError, ValueError):
        score = None
    state = regime.get("state")
    return {
        "score": score,
        "state": str(state) if state is not None else None,
    }


def _representative_regime_alignment(raw_runs: list[dict]) -> dict:
    qualifying = [
        raw_run
        for raw_run in raw_runs
        if isinstance(raw_run, dict)
        and isinstance(raw_run.get("regime_alignment"), dict)
        and raw_run["regime_alignment"].get("score") is not None
    ]
    if not qualifying:
        return {"score": None, "state": None, "source_run_id": None}

    representative = max(
        qualifying,
        key=lambda raw_run: (
            str(raw_run.get("timestamp") or ""),
            str(raw_run.get("run_id") or ""),
        ),
    )
    regime = representative["regime_alignment"]
    return {
        "score": regime.get("score"),
        "state": regime.get("state"),
        "source_run_id": representative.get("run_id"),
    }


def _share_points(value) -> float | None:
    if value is None:
        return None
    try:
        share = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= share <= 1:
        return share * 100
    return share


def _run_narratives(run_data: dict) -> list[dict]:
    narrative_groups = run_data.get("narrative_groups")
    if isinstance(narrative_groups, list):
        rows = []
        for item in narrative_groups:
            if not isinstance(item, dict) or not item.get("group"):
                continue
            share = _share_points(item.get("share"))
            score = item.get("score")
            try:
                score = int(round(float(score)))
            except (TypeError, ValueError):
                score = 0
            rows.append(
                {
                    "group": str(item.get("group")),
                    "share": round(share or 0.0, 1),
                    "score": score,
                    "rank": item.get("rank"),
                    "pulse_state": item.get("pulse_state"),
                }
            )
        return _rank_narratives(rows)

    group_scores = run_data.get("group_scores")
    if not isinstance(group_scores, dict):
        return []

    pulse = run_data.get("narrative_pulse") if isinstance(run_data.get("narrative_pulse"), dict) else {}
    total_score = sum(
        float(score)
        for score in group_scores.values()
        if isinstance(score, (int, float)) or str(score).replace(".", "", 1).isdigit()
    )

    rows = []
    for group, score in group_scores.items():
        try:
            numeric_score = float(score)
        except (TypeError, ValueError):
            numeric_score = 0.0

        group_pulse = pulse.get(group) if isinstance(pulse.get(group), dict) else {}
        inputs = group_pulse.get("inputs") if isinstance(group_pulse.get("inputs"), dict) else {}
        share = _share_points(inputs.get("narrative_share"))
        if share is None and total_score > 0:
            share = (numeric_score / total_score) * 100

        rows.append(
            {
                "group": str(group),
                "share": round(share or 0.0, 1),
                "score": int(round(numeric_score)),
                "rank": None,
                "pulse_state": group_pulse.get("pulse_state"),
            }
        )

    return _rank_narratives(rows)


def _rank_narratives(narratives: list[dict]) -> list[dict]:
    ranked = sorted(narratives, key=lambda item: item.get("share", 0), reverse=True)
    for index, item in enumerate(ranked):
        item["rank"] = index + 1
    return ranked


def _aggregate_raw_runs(raw_runs: list[dict], snapshot_date: str) -> dict:
    groups = {}
    latest_pulse = {}

    for raw_run in raw_runs:
        for narrative in raw_run.get("narratives", []):
            group = narrative.get("group")
            if not group:
                continue
            groups.setdefault(group, {"shares": [], "scores": []})
            groups[group]["shares"].append(float(narrative.get("share") or 0))
            groups[group]["scores"].append(float(narrative.get("score") or 0))
            latest_pulse[group] = narrative.get("pulse_state")

    narratives = []
    for group, values in groups.items():
        narratives.append(
            {
                "group": group,
                "share": round(float(statistics.median(values["shares"])), 1),
                "score": int(round(statistics.median(values["scores"]))),
                "rank": None,
                "pulse_state": latest_pulse.get(group),
            }
        )

    snapshot = {
        "date": snapshot_date,
        "narratives": _rank_narratives(narratives),
        "raw_runs": raw_runs,
        "regime_alignment": _representative_regime_alignment(raw_runs),
    }

    lifecycle_runs = [
        raw_run
        for raw_run in raw_runs
        if isinstance(raw_run, dict) and isinstance(raw_run.get("event_lifecycle"), dict)
    ]
    if lifecycle_runs:
        latest_run = sorted(
            lifecycle_runs,
            key=lambda raw_run: str(raw_run.get("timestamp") or ""),
        )[-1]
        snapshot["latest_run_event_lifecycle"] = {
            "label": "latest_run_only_not_daily_aggregate",
            "run_id": latest_run.get("run_id"),
            "timestamp": latest_run.get("timestamp"),
            "event_lifecycle": latest_run.get("event_lifecycle"),
        }

    return snapshot


def _upsert_raw_run(raw_runs: list[dict], current_raw_run: dict) -> list[dict]:
    current_run_id = current_raw_run.get("run_id")
    current_timestamp = current_raw_run.get("timestamp")
    retained = []

    for raw_run in raw_runs:
        if not isinstance(raw_run, dict):
            continue
        if current_run_id and raw_run.get("run_id") == current_run_id:
            continue
        if (
            not current_run_id
            and not raw_run.get("run_id")
            and raw_run.get("timestamp") == current_timestamp
        ):
            continue
        retained.append(raw_run)

    retained.append(current_raw_run)
    return retained


def _snapshot_from_runs(snapshot_date: str, runs: list[dict]) -> dict:
    raw_runs = [
        {
            "run_id": _extract_run_id(run),
            "timestamp": _extract_timestamp(run),
            "narratives": _run_narratives(run),
            "event_lifecycle": _extract_event_lifecycle(run),
            "regime_alignment": _extract_regime_alignment(run),
        }
        for run in runs
    ]
    return _aggregate_raw_runs(raw_runs, snapshot_date)


def build_daily_snapshot_preview(run_data: dict, snapshot_date: str | None = None) -> dict:
    snapshot_date = snapshot_date or _extract_run_date(run_data) or date.today().isoformat()
    narratives = _run_narratives(run_data)
    return {
        "date": snapshot_date,
        "narratives": narratives,
        "raw_runs": [
            {
                "run_id": _extract_run_id(run_data),
                "timestamp": _extract_timestamp(run_data),
                "narratives": narratives,
                "event_lifecycle": _extract_event_lifecycle(run_data),
                "regime_alignment": _extract_regime_alignment(run_data),
            }
        ],
        "regime_alignment": _representative_regime_alignment(
            [
                {
                    "run_id": _extract_run_id(run_data),
                    "timestamp": _extract_timestamp(run_data),
                    "regime_alignment": _extract_regime_alignment(run_data),
                }
            ]
        ),
    }


def write_daily_snapshot(run_data: dict) -> None:
    snapshot_date = _extract_run_date(run_data) or date.today().isoformat()
    today = date.today().isoformat()
    if snapshot_date != today:
        return

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = SNAPSHOTS_DIR / f"{snapshot_date}.json"
    current_raw_run = {
        "run_id": _extract_run_id(run_data),
        "timestamp": _extract_timestamp(run_data),
        "narratives": _run_narratives(run_data),
        "event_lifecycle": _extract_event_lifecycle(run_data),
        "regime_alignment": _extract_regime_alignment(run_data),
    }

    raw_runs = []
    if snapshot_path.exists():
        existing = load_json(snapshot_path)
        raw_runs = existing.get("raw_runs", [])

    raw_runs = _upsert_raw_run(raw_runs, current_raw_run)
    snapshot = _aggregate_raw_runs(raw_runs, snapshot_date)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def backfill_daily_snapshots() -> int:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    grouped_runs = {}

    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            run = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        run_date = _extract_run_date(run, path)
        if not run_date:
            continue
        grouped_runs.setdefault(run_date, []).append(run)

    created = 0
    for run_date, runs in sorted(grouped_runs.items()):
        snapshot_path = SNAPSHOTS_DIR / f"{run_date}.json"
        if snapshot_path.exists():
            LOGGER.info("Skipped existing daily snapshot: %s", snapshot_path)
            continue

        snapshot = _snapshot_from_runs(run_date, runs)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        LOGGER.info("Created daily snapshot: %s", snapshot_path)
        created += 1

    return created


def repair_snapshot_support_scores() -> int:
    """Repair missing/null snapshot support scores from persisted result files."""
    if not SNAPSHOTS_DIR.exists():
        return 0

    result_runs_by_date = {}
    for result_path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            run = load_json(result_path)
        except (OSError, json.JSONDecodeError):
            continue
        run_date = _extract_run_date(run, result_path)
        if not run_date:
            continue
        result_runs_by_date.setdefault(run_date, []).append(
            {
                "run_id": _extract_run_id(run) or result_path.stem,
                "timestamp": _extract_timestamp(run),
                "regime_alignment": _extract_regime_alignment(run),
            }
        )

    repaired = 0
    for snapshot_path in sorted(SNAPSHOTS_DIR.glob("*.json")):
        try:
            date.fromisoformat(snapshot_path.stem)
            snapshot = load_json(snapshot_path)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        existing = snapshot.get("regime_alignment")
        if isinstance(existing, dict) and existing.get("score") is not None:
            continue

        representative = _representative_regime_alignment(
            result_runs_by_date.get(snapshot_path.stem, [])
        )
        if representative["score"] is None:
            continue

        snapshot["regime_alignment"] = representative
        with open(snapshot_path, "w", encoding="utf-8") as file_handle:
            json.dump(snapshot, file_handle, ensure_ascii=False, indent=2)
        repaired += 1
        LOGGER.info("Repaired snapshot support score: %s", snapshot_path)

    return repaired


def load_daily_snapshots(limit: int = 7) -> list[dict]:
    if not SNAPSHOTS_DIR.exists():
        return []

    snapshot_files = []
    for path in SNAPSHOTS_DIR.glob("*.json"):
        try:
            date.fromisoformat(path.stem)
        except ValueError:
            continue
        snapshot_files.append(path)

    if not snapshot_files:
        return []

    selected = sorted(snapshot_files, key=lambda path: path.stem)[-limit:]
    return [load_json(path) for path in selected]
