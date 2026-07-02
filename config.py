import os
from pathlib import Path


CUSTOM_DATA_DIR = os.getenv("MNE_DATA_DIR")

if CUSTOM_DATA_DIR:
    DATA_DIR = Path(CUSTOM_DATA_DIR).expanduser()
else:
    DATA_DIR = Path.home() / "Google Drive" / "MNE-data"

CONFIG_DIR = DATA_DIR / "config"
HEADLINES_DIR = DATA_DIR / "headlines"
RESULTS_DIR = DATA_DIR / "results"
REPORTS_DIR = DATA_DIR / "reports"
EVENTS_DIR = DATA_DIR / "events"
EVENTS_FILE = EVENTS_DIR / "events.json"
EVENT_LIFECYCLE_EVENTS_FILE = CONFIG_DIR / "event_lifecycle_events.json"
ENABLE_AUTO_COMPANY_CATALYSTS = True
ENABLE_AUTO_MACRO_CATALYSTS = True
OPERATING_MODE = "macro"

for folder in [CONFIG_DIR, HEADLINES_DIR, RESULTS_DIR, REPORTS_DIR, EVENTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)
