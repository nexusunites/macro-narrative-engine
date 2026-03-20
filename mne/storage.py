import json
from pathlib import Path

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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