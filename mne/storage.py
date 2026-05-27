import json
from pathlib import Path

from config import HEADLINES_DIR, REPORTS_DIR, RESULTS_DIR


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_headlines(headlines, stamp, headlines_dir=HEADLINES_DIR):
    headlines_dir.mkdir(parents=True, exist_ok=True)
    headlines_file = headlines_dir / f"{stamp}.txt"

    with open(headlines_file, "w", encoding="utf-8") as f:
        for headline in headlines:
            f.write(headline + "\n")

    return headlines_file


def save_run_json(run, stamp, results_dir=RESULTS_DIR):
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / f"{stamp}.json"

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)

    return results_dir, results_file


def save_report(report_text, stamp, reports_dir=REPORTS_DIR):
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"{stamp}.txt"

    with open(report_file, "w", encoding="utf-8") as f:
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
