import json
from datetime import date, datetime
from pathlib import Path

from config import DATA_DIR


CATALYSTS_FILE = DATA_DIR / "config" / "catalysts.json"
DEFAULT_LOOKAHEAD_DAYS = 14

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
        return None

    with open(catalysts_file, "r", encoding="utf-8") as f:
        catalysts = json.load(f)

    if not isinstance(catalysts, list):
        return []

    return catalysts


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

    return {
        "date": catalyst_date.isoformat(),
        "name": name,
        "importance": importance,
        "days_until": days_until,
        "days_away": days_until,
    }


def get_upcoming_catalysts(
    catalysts=None,
    as_of=None,
    lookahead_days=DEFAULT_LOOKAHEAD_DAYS,
    catalysts_file=CATALYSTS_FILE,
):
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    if catalysts is None:
        catalysts = load_catalysts(catalysts_file)
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
):
    upcoming = get_upcoming_catalysts(catalysts, as_of, lookahead_days, catalysts_file)

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
            "reason": "No catalyst calendar file found.",
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
        "reason": reason_for_density(density_score, red_events, orange_events),
    }
