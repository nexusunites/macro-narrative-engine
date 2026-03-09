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