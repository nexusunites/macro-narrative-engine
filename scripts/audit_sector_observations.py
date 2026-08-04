"""Read-only audit of persisted sector observations for calibration readiness."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mne.sector_market_context import _parse_timestamp, load_sector_instruments


def audit_sector_observations(results_dir: str | Path) -> dict[str, int]:
    sector_keys = frozenset(load_sector_instruments()["sectors"])
    counts = {"run_files": 0, "sector_entries": 0, "valid_sector_observations": 0}
    for path in sorted(Path(results_dir).glob("*.json")):
        counts["run_files"] += 1
        try:
            run: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        snapshot = run.get("market_snapshot") if isinstance(run, dict) else None
        if not isinstance(snapshot, dict):
            continue
        for key in sorted(sector_keys.intersection(snapshot)):
            counts["sector_entries"] += 1
            record = snapshot[key]
            if not isinstance(record, dict) or _parse_timestamp(record.get("observed_at")) is None:
                continue
            try:
                change = float(record.get("pct_change"))
            except (TypeError, ValueError):
                continue
            if math.isfinite(change):
                counts["valid_sector_observations"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_sector_observations(args.results_dir), sort_keys=True))


if __name__ == "__main__":
    main()
