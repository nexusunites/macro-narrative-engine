import json
import logging
from datetime import date, datetime
from pathlib import Path

from config import DATA_DIR, ENABLE_AUTO_COMPANY_CATALYSTS, ENABLE_AUTO_MACRO_CATALYSTS
from mne.company_catalysts import get_auto_company_earnings_catalysts
from mne.macro_catalysts import MACRO_CALENDAR_FILE, get_auto_macro_calendar_catalysts


logger = logging.getLogger(__name__)

CATALYSTS_FILE = DATA_DIR / "config" / "catalysts.json"
DEFAULT_LOOKAHEAD_DAYS = 14
INVALID_CALENDAR_REASON = "Catalyst calendar unavailable or invalid."

RED_IMPORTANCE = "red"
ORANGE_IMPORTANCE = "orange"

RED_KEYWORDS = [
    "fomc",
    "cpi",
    "nfp",
    "nonfarm payroll",
    "non-farm payroll",
    "nvda earnings",
    "major ipo",
    "ipo",
    "major ai announcement",
    "ai announcement",
]

ORANGE_KEYWORDS = [
    "ppi",
    "retail sales",
    "consumer confidence",
    "secondary earnings",
]


def load_catalysts(catalysts_file=CATALYSTS_FILE):
    catalysts_file = Path(catalysts_file)

    if not catalysts_file.exists():
        try:
            catalysts_file.parent.mkdir(parents=True, exist_ok=True)
            catalysts_file.write_text("[]\n", encoding="utf-8")
            return []
        except OSError as error:
            logger.warning("Unable to create catalyst calendar %s: %s", catalysts_file, error)
            return None

    try:
        with open(catalysts_file, "r", encoding="utf-8") as f:
            catalysts = json.load(f)
    except json.JSONDecodeError:
        logger.warning("Catalyst calendar is empty or contains invalid JSON: %s", catalysts_file)
        return None
    except OSError as error:
        logger.warning("Unable to read catalyst calendar %s: %s", catalysts_file, error)
        return None

    if not isinstance(catalysts, list):
        logger.warning("Catalyst calendar must contain a JSON array: %s", catalysts_file)
        return None

    if any(not isinstance(catalyst, dict) for catalyst in catalysts):
        logger.warning("Ignoring malformed catalyst calendar entries in %s", catalysts_file)

    missing_required_fields = [
        catalyst
        for catalyst in catalysts
        if isinstance(catalyst, dict)
        and any(not catalyst.get(field) for field in ("date", "name", "importance"))
    ]
    if missing_required_fields:
        logger.warning("Ignoring catalyst entries missing date, name, or importance in %s", catalysts_file)

    valid_catalysts = [
        catalyst
        for catalyst in catalysts
        if isinstance(catalyst, dict)
        and all(catalyst.get(field) for field in ("date", "name", "importance"))
    ]

    if catalysts and not valid_catalysts:
        return []

    return valid_catalysts


def parse_catalyst_date(catalyst):
    date_text = catalyst.get("date")
    if not date_text:
        return None

    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None


def classify_importance(catalyst):
    importance = (catalyst.get("importance") or "").strip().lower()
    if importance in {RED_IMPORTANCE, ORANGE_IMPORTANCE}:
        return importance

    name = (catalyst.get("name") or "").lower()
    if any(keyword in name for keyword in RED_KEYWORDS):
        return RED_IMPORTANCE
    if any(keyword in name for keyword in ORANGE_KEYWORDS):
        return ORANGE_IMPORTANCE

    return None


def normalize_catalyst(catalyst, as_of):
    catalyst_date = parse_catalyst_date(catalyst)
    importance = classify_importance(catalyst)
    name = (catalyst.get("name") or "").strip()

    if catalyst_date is None or importance is None or not name:
        return None

    days_until = (catalyst_date - as_of).days

    normalized = {
        "date": catalyst_date.isoformat(),
        "name": name,
        "importance": importance,
        "days_until": days_until,
        "days_away": days_until,
    }

    source = catalyst.get("source")
    if source:
        normalized["source"] = source

    ticker = catalyst.get("ticker")
    if ticker:
        normalized["ticker"] = ticker

    return normalized


def merge_catalysts(*catalyst_groups):
    merged = []
    seen = set()

    for catalysts in catalyst_groups:
        for catalyst in catalysts or []:
            key = (
                (catalyst.get("date") or "").strip(),
                (catalyst.get("name") or "").strip().lower(),
            )
            if key in seen:
                continue
            merged.append(catalyst)
            seen.add(key)

    return merged


def load_all_catalysts(
    catalysts_file=CATALYSTS_FILE,
    as_of=None,
    enable_auto_company_catalysts=None,
    enable_auto_macro_catalysts=None,
    metadata=None,
):
    manual_catalysts = load_catalysts(catalysts_file)
    if manual_catalysts is None:
        return None

    if enable_auto_company_catalysts is None:
        enable_auto_company_catalysts = ENABLE_AUTO_COMPANY_CATALYSTS
    if enable_auto_macro_catalysts is None:
        enable_auto_macro_catalysts = ENABLE_AUTO_MACRO_CATALYSTS

    if metadata is not None:
        metadata["auto_macro_enabled"] = bool(enable_auto_macro_catalysts)
        metadata["auto_macro_events_found"] = 0

    auto_macro_catalysts = []
    if enable_auto_macro_catalysts:
        try:
            auto_macro_catalysts = get_auto_macro_calendar_catalysts(as_of=as_of)
        except Exception as error:
            logger.warning("Unable to load auto macro calendar catalysts: %s", error)
            auto_macro_catalysts = []

        if metadata is not None:
            metadata["auto_macro_events_found"] = len(auto_macro_catalysts)

    auto_company_catalysts = []
    if not enable_auto_company_catalysts:
        return merge_catalysts(manual_catalysts, auto_macro_catalysts)

    try:
        auto_company_catalysts = get_auto_company_earnings_catalysts(as_of=as_of)
    except Exception as error:
        logger.warning("Unable to load auto company earnings catalysts: %s", error)
        auto_company_catalysts = []

    if not auto_macro_catalysts and not auto_company_catalysts:
        logger.debug("No auto catalysts found. Using manual catalyst calendar only.")

    return merge_catalysts(manual_catalysts, auto_macro_catalysts, auto_company_catalysts)


def get_upcoming_catalysts(
    catalysts=None,
    as_of=None,
    lookahead_days=DEFAULT_LOOKAHEAD_DAYS,
    catalysts_file=CATALYSTS_FILE,
    enable_auto_company_catalysts=None,
    enable_auto_macro_catalysts=None,
    metadata=None,
):
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    if catalysts is None:
        catalysts = load_all_catalysts(
            catalysts_file=catalysts_file,
            as_of=as_of,
            enable_auto_company_catalysts=enable_auto_company_catalysts,
            enable_auto_macro_catalysts=enable_auto_macro_catalysts,
            metadata=metadata,
        )
    if catalysts is None:
        return None

    upcoming = []
    for catalyst in catalysts:
        normalized = normalize_catalyst(catalyst, as_of)
        if normalized is None:
            continue
        if 0 <= normalized["days_until"] <= lookahead_days:
            upcoming.append(normalized)

    return sorted(upcoming, key=lambda event: (event["days_until"], event["name"]))


def density_state_for_score(score):
    if score == 0:
        return "Quiet"
    if score == 1:
        return "Light"
    if score <= 3:
        return "Moderate"
    if score <= 5:
        return "Elevated"
    return "Heavy"


def confidence_for_density(score, calendar_found=True):
    if not calendar_found:
        return "Low"
    if score >= 4:
        return "High"
    if score >= 2:
        return "Moderate"
    return "Low"


def _auto_macro_enabled_metadata_value(enable_auto_macro_catalysts):
    if enable_auto_macro_catalysts is None:
        return bool(ENABLE_AUTO_MACRO_CATALYSTS)
    return bool(enable_auto_macro_catalysts)


def _auto_company_enabled_value(enable_auto_company_catalysts):
    if enable_auto_company_catalysts is None:
        return bool(ENABLE_AUTO_COMPANY_CATALYSTS)
    return bool(enable_auto_company_catalysts)


def catalyst_sources_metadata(catalysts_file, enable_auto_company_catalysts):
    return {
        "manual": str(Path(catalysts_file).expanduser()),
        "macro": str(Path(MACRO_CALENDAR_FILE).expanduser()),
        "company_earnings": (
            "enabled"
            if _auto_company_enabled_value(enable_auto_company_catalysts)
            else "disabled"
        ),
    }


def reason_for_density(score, red_events, orange_events):
    if score == 0:
        return "No high-impact or medium-impact catalysts are approaching."
    if len(red_events) >= 2:
        return "Multiple high-impact catalysts are approaching."
    if red_events and orange_events:
        return "High-impact and medium-impact catalysts are approaching."
    if red_events:
        return "A high-impact catalyst is approaching."
    return "Medium-impact catalysts are approaching."


def calculate_catalyst_density(
    catalysts=None,
    as_of=None,
    lookahead_days=DEFAULT_LOOKAHEAD_DAYS,
    catalysts_file=CATALYSTS_FILE,
    enable_auto_company_catalysts=None,
    enable_auto_macro_catalysts=None,
):
    catalyst_source = str(Path(catalysts_file).expanduser())
    catalyst_sources = catalyst_sources_metadata(
        catalysts_file,
        enable_auto_company_catalysts,
    )
    metadata = {}
    upcoming = get_upcoming_catalysts(
        catalysts,
        as_of,
        lookahead_days,
        catalysts_file,
        enable_auto_company_catalysts,
        enable_auto_macro_catalysts,
        metadata,
    )

    if upcoming is None:
        return {
            "state": "No Scheduled Catalyst Environment",
            "confidence": "Low",
            "density_score": 0,
            "density_state": "Quiet",
            "red_events": [],
            "orange_events": [],
            "days_to_next_red": None,
            "days_to_next_orange": None,
            "calendar_found": False,
            "catalyst_source": catalyst_source,
            "catalyst_sources": catalyst_sources,
            "reason": INVALID_CALENDAR_REASON,
            "auto_macro_enabled": metadata.get(
                "auto_macro_enabled",
                _auto_macro_enabled_metadata_value(enable_auto_macro_catalysts),
            ),
            "auto_macro_events_found": metadata.get("auto_macro_events_found", 0),
        }

    red_events = [event for event in upcoming if event["importance"] == RED_IMPORTANCE]
    orange_events = [event for event in upcoming if event["importance"] == ORANGE_IMPORTANCE]
    density_score = (len(red_events) * 2) + len(orange_events)
    density_state = density_state_for_score(density_score)

    return {
        "state": density_state,
        "confidence": confidence_for_density(density_score),
        "density_score": density_score,
        "density_state": density_state,
        "red_events": red_events,
        "orange_events": orange_events,
        "days_to_next_red": red_events[0]["days_until"] if red_events else None,
        "days_to_next_orange": orange_events[0]["days_until"] if orange_events else None,
        "calendar_found": True,
        "catalyst_source": catalyst_source,
        "catalyst_sources": catalyst_sources,
        "reason": reason_for_density(density_score, red_events, orange_events),
        "auto_macro_enabled": metadata.get(
            "auto_macro_enabled",
            _auto_macro_enabled_metadata_value(enable_auto_macro_catalysts),
        ),
        "auto_macro_events_found": metadata.get("auto_macro_events_found", 0),
    }
