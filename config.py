import os
from pathlib import Path


CUSTOM_DATA_DIR = os.getenv("MNE_DATA_DIR")

if CUSTOM_DATA_DIR:
    DATA_DIR = Path(CUSTOM_DATA_DIR).expanduser()
else:
    DATA_DIR = Path.home() / "Google Drive" / "MNE-data"

HEADLINES_DIR = DATA_DIR / "headlines"
RESULTS_DIR = DATA_DIR / "results"
REPORTS_DIR = DATA_DIR / "reports"
EVENTS_DIR = DATA_DIR / "events"
EVENTS_FILE = EVENTS_DIR / "events.json"

for folder in [HEADLINES_DIR, RESULTS_DIR, REPORTS_DIR, EVENTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)
