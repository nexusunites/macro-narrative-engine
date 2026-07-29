"""Repair daily snapshot Market Support scores from saved run results."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mne.storage import repair_snapshot_support_scores


if __name__ == "__main__":
    repaired = repair_snapshot_support_scores()
    print(f"Repaired {repaired} daily snapshot support score(s).")
