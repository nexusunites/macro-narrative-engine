import os
from pathlib import Path


_DEFAULT_DATA_DIR = Path.home() / ".mne" / "data"
_resolved_data_dir = None
_data_dir_created = False


def _resolve_data_dir() -> Path:
    env_value = os.environ.get("MNE_DATA_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return _DEFAULT_DATA_DIR


def get_data_dir() -> Path:
    global _resolved_data_dir
    if _resolved_data_dir is None:
        _resolved_data_dir = _resolve_data_dir()
    return _resolved_data_dir


def ensure_data_dir() -> Path:
    global _data_dir_created
    data_dir = get_data_dir()
    if not _data_dir_created:
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RuntimeError(
                f"Could not create MNE data directory at {data_dir}. "
                "Set MNE_DATA_DIR to a writable location instead. "
                f"({error})"
            ) from error
        _data_dir_created = True
    return data_dir


DATA_DIR = get_data_dir()

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
