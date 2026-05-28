import json
from datetime import datetime, time, timedelta

from config import EVENTS_FILE


MAJOR_CATALYST_KEYWORDS = [
    "FOMC",
    "Federal Reserve",
    "Fed Chair",
    "Powell",
    "CPI",
    "PCE",
    "Nonfarm Payrolls",
    "NFP",
    "Unemployment Rate",
    "Rate Decision",
    "Interest Rate",
    "GDP",
    "Retail Sales",
    "ISM",
    "NVDA Earnings",
    "Treasury Auction",
]


def load_events(events_file=EVENTS_FILE):
    if not events_file.exists():
        return None

    with open(events_file, "r", encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list):
        return []

    return events


def parse_event_datetime(event):
    date_text = event.get("date")
    time_text = event.get("time") or "00:00"

    if not date_text:
        return None

    try:
        return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def timing_bucket(event_dt):
    if event_dt.time() < time(12, 0):
        return "morning"
    if event_dt.time() < time(17, 0):
        return "afternoon"
    return "evening"


def event_output(event, event_dt):
    return {
        "date": event.get("date"),
        "time": event.get("time"),
        "currency": event.get("currency"),
        "event": event.get("event"),
        "category": event.get("category"),
        "timing": timing_bucket(event_dt),
    }


def event_sort_key(event):
    return (
        event.get("date") or "",
        event.get("time") or "",
        event.get("currency") or "",
        event.get("event") or "",
    )


def is_major_catalyst(event):
    text = f"{event.get('event', '')} {event.get('category', '')}".lower()

    return any(keyword.lower() in text for keyword in MAJOR_CATALYST_KEYWORDS)


def split_events(events, now):
    today = now.date()
    tomorrow = today + timedelta(days=1)
    filtered = {
        "red_today": [],
        "orange_today": [],
        "red_tomorrow": [],
        "orange_tomorrow": [],
        "other": [],
    }

    for event in events:
        event_dt = parse_event_datetime(event)
        if event_dt is None or event_dt.date() not in {today, tomorrow}:
            continue

        impact = (event.get("impact") or "").lower().strip()
        output = event_output(event, event_dt)
        output["_dt"] = event_dt
        output["_major"] = is_major_catalyst(event)

        if impact == "red" and event_dt.date() == today:
            filtered["red_today"].append(output)
        elif impact == "orange" and event_dt.date() == today:
            filtered["orange_today"].append(output)
        elif impact == "red" and event_dt.date() == tomorrow:
            filtered["red_tomorrow"].append(output)
        elif impact == "orange" and event_dt.date() == tomorrow:
            filtered["orange_tomorrow"].append(output)
        else:
            filtered["other"].append(output)

    for key in filtered:
        filtered[key] = sorted(filtered[key], key=event_sort_key)

    return filtered


def public_events(events):
    cleaned = []

    for event in events:
        cleaned.append(
            {
                "date": event.get("date"),
                "time": event.get("time"),
                "currency": event.get("currency"),
                "event": event.get("event"),
                "category": event.get("category"),
            }
        )

    return cleaned


def first_major(events):
    for event in events:
        if event.get("_major"):
            return event
    return None


def pending_major_today(red_today, now):
    return [
        event
        for event in red_today
        if event.get("_major") and event.get("_dt") and event["_dt"] > now
    ]


def morning_red_released(red_today, now):
    return [
        event
        for event in red_today
        if event.get("_dt")
        and event["_dt"] <= now
        and event["_dt"].time() < time(9, 30)
    ]


def confidence_for_state(state, event=None, red_count=0):
    if state in {
        "Pre-Event Compression",
        "Afternoon Caution",
        "Post-News Liquidity",
        "Major Event Pending",
    }:
        if event and event.get("_major"):
            return "HIGH"
        return "MODERATE"

    if state == "Moderate Catalyst Environment":
        return "MODERATE"

    if red_count > 0:
        return "MODERATE"

    return "LOW"


def classify_catalyst_environment(events_file=EVENTS_FILE, now=None):
    now = now or datetime.now()
    events = load_events(events_file)

    if events is None:
        return {
            "state": "No Scheduled Catalyst Environment",
            "confidence": "LOW",
            "red_events": [],
            "orange_events": [],
            "reason": "No catalyst calendar file found.",
        }

    filtered = split_events(events, now)
    red_today = filtered["red_today"]
    orange_today = filtered["orange_today"]
    red_tomorrow = filtered["red_tomorrow"]
    orange_tomorrow = filtered["orange_tomorrow"]
    red_events = public_events(red_today + red_tomorrow)
    orange_events = public_events(orange_today + orange_tomorrow)
    later_major_today = pending_major_today(red_today, now)
    released_morning_red = morning_red_released(red_today, now)
    major_tomorrow = first_major(red_tomorrow)

    afternoon_pending = [
        event for event in later_major_today if event.get("timing") in {"afternoon", "evening"}
    ]
    if afternoon_pending:
        event = afternoon_pending[0]
        return {
            "state": "Afternoon Caution",
            "confidence": confidence_for_state("Afternoon Caution", event),
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": (
                "A major afternoon catalyst is pending. The open may still be "
                "tradable, but participation may slow from lunch onward until after "
                "the event."
            ),
        }

    if later_major_today:
        event = later_major_today[0]
        return {
            "state": "Pre-Event Compression",
            "confidence": confidence_for_state("Pre-Event Compression", event),
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": (
                "A major red-folder catalyst is still pending later today. Market "
                "participation may compress ahead of the release, especially as the "
                "event approaches."
            ),
        }

    if released_morning_red:
        event = released_morning_red[0]
        return {
            "state": "Post-News Liquidity",
            "confidence": confidence_for_state("Post-News Liquidity", event, len(red_events)),
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": (
                "A major morning catalyst has already occurred, meaning liquidity has "
                "entered the market before the open. Price action may show stronger "
                "conviction after the open."
            ),
        }

    if major_tomorrow:
        timing = major_tomorrow.get("timing")
        if timing in {"afternoon", "evening"}:
            reason = (
                f"A major red-folder catalyst is scheduled tomorrow at "
                f"{major_tomorrow.get('time')}. Today and tomorrow morning may still "
                "be tradable, but caution may increase as the event approaches."
            )
        else:
            reason = (
                f"A major red-folder catalyst is scheduled tomorrow at "
                f"{major_tomorrow.get('time')}. Today may show lower volume, lower "
                "volatility, or compression as participants wait for the event."
            )

        return {
            "state": "Major Event Pending",
            "confidence": confidence_for_state("Major Event Pending", major_tomorrow),
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": reason,
        }

    if orange_today or orange_tomorrow:
        return {
            "state": "Moderate Catalyst Environment",
            "confidence": "MODERATE",
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": (
                "Orange-folder catalysts are scheduled, creating moderate event "
                "awareness without major red-folder pressure."
            ),
        }

    if filtered["other"]:
        return {
            "state": "Low Catalyst Environment",
            "confidence": "LOW",
            "red_events": red_events,
            "orange_events": orange_events,
            "reason": "Only low or unknown impact events are scheduled today or tomorrow.",
        }

    return {
        "state": "No Scheduled Catalyst Environment",
        "confidence": "LOW",
        "red_events": [],
        "orange_events": [],
        "reason": "No scheduled catalysts found for today or tomorrow.",
    }
