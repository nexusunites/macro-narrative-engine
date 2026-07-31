"""Pure, deterministic composition for user-facing narrative explanations.

All inputs must already be loaded persisted context.  The rules deliberately
describe observed snapshots rather than continuous calendar coverage.
"""

from __future__ import annotations

from typing import Any

from mne.presentation_language import (
    MARKET_EXPRESSION_COPY,
    confidence,
    historical_breadth,
    narrative_display_name,
    state,
)

SUPPORTING_POINTS_LIMIT = 3
SNAPSHOT_LIMITATION = (
    "Recent behavior reflects available MNE snapshots and may not represent "
    "every calendar day."
)

LIFECYCLE_TEMPLATES = {
    "DOMINANT": "{name} is the leading narrative in the current market conversation.",
    "BUILDING": "Attention around {name} is building.",
    "PERSISTENT": "{name} has remained a consistent part of the market conversation.",
    "FADING": "Attention around {name} has been declining.",
    "RECURRING": "{name} has returned to the market conversation after a quieter period.",
    "RE_ACCELERATING": "Attention around {name} is beginning to build again.",
    "DORMANT": "Attention around {name} has been quiet.",
    "EMERGING": "{name} is beginning to attract more attention, though its history is still limited.",
    "ABSENT": "{name} was not meaningfully present in this snapshot.",
}


def _schema(
    headline: str,
    *,
    what_changed: str | None = None,
    why_it_matters: str | None = None,
    supporting_points: list[str] | None = None,
    limitations: list[str] | None = None,
    technical_details: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "headline": headline,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "supporting_points": list(supporting_points or [])[:SUPPORTING_POINTS_LIMIT],
        "limitations": list(limitations or []),
        "technical_details": list(technical_details or []),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _signed_display_number(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace("pts", "").strip()
    return _number(value)


def _memory_state(context: dict[str, Any]) -> Any:
    memory = context.get("memory")
    return memory.get("state") if isinstance(memory, dict) else context.get("memory_state")


def explain_lifecycle_state(
    name: Any,
    lifecycle_state: Any,
    *,
    dominant_declining: bool = False,
) -> str:
    """Explain every persisted Narrative Memory state with a fixed template."""
    display_name = narrative_display_name(name) or "This narrative"
    if dominant_declining:
        return (
            f"{display_name} remains the leading narrative, but its influence "
            "has eased from its recent peak."
        )
    raw = str(lifecycle_state or "").strip()
    key = raw.upper().replace("-", "_").replace(" ", "_")
    template = LIFECYCLE_TEMPLATES.get(key)
    if template:
        return template.format(name=display_name)
    translated = state(raw)
    marker = translated["label"] if translated["untranslated"] else translated["meaning"]
    return marker or f"{display_name} has an untranslated lifecycle state: {raw or 'Unavailable'}."


def explain_narrative_change(context: dict[str, Any]) -> str | None:
    name = narrative_display_name(context.get("display_name") or context.get("name"))
    memory = context.get("memory") if isinstance(context.get("memory"), dict) else context
    share_delta = _signed_display_number(
        memory.get("share_delta_raw", memory.get("share_delta"))
    )
    score_delta = _signed_display_number(
        memory.get("score_delta_raw", memory.get("score_delta"))
    )
    rank_delta = _signed_display_number(
        memory.get("rank_delta_raw", memory.get("rank_delta"))
    )
    if share_delta is not None and share_delta < 0:
        return f"{name} still matters, but it no longer commands as much attention as it recently did."
    if rank_delta is not None and rank_delta < 0:
        return f"{name} moved closer to the center of the market conversation."
    if share_delta is not None and share_delta > 0 or score_delta is not None and score_delta > 0:
        return f"Attention around {name} has strengthened recently."
    if score_delta is not None and score_delta < 0:
        return f"Attention around {name} has eased recently."
    return None


def explain_evidence_breadth(value: Any) -> str:
    raw = str(value or "").upper()
    if raw in {"BROAD", "ROBUST"}:
        return "The reconstruction draws from several distinct historical source categories."
    if raw in {"LIMITED", "MINIMAL", "NARROW"}:
        return "The reconstruction is based on a narrower set of historical evidence."
    if raw == "MODERATE":
        return historical_breadth(raw)["meaning"]
    return "There is not enough information to describe the breadth of the evidence."


def explain_confidence_state(value: Any) -> str:
    translated = confidence(value)
    return translated["meaning"] or translated["label"]


def build_supporting_detail_labels(context: dict[str, Any]) -> list[str]:
    details = []
    for label, key in (
        ("Score", "score"),
        ("Share", "share"),
        ("Rank", "rank"),
        ("Lifecycle state", "memory_state"),
    ):
        value = context.get(key)
        if value not in (None, ""):
            details.append(f"{label}: {value}")
    return details


def build_explanation_limitations(*, recent: bool = True, thin_history: bool = False) -> list[str]:
    limitations = [SNAPSHOT_LIMITATION] if recent else []
    if thin_history:
        limitations.append(
            "The available history is still limited, so the pattern may become clearer as more snapshots accumulate."
        )
    return limitations


def explain_narrative_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    name = narrative_display_name(context.get("display_name") or context.get("name"))
    lifecycle = _memory_state(context)
    change = explain_narrative_change(context)
    declining = str(lifecycle or "").upper() == "DOMINANT" and bool(
        change and "no longer commands" in change
    )
    headline = explain_lifecycle_state(name, lifecycle, dominant_declining=declining)
    coverage = context.get("coverage")
    coverage_state = coverage.get("coverage_state") if isinstance(coverage, dict) else None
    points = []
    if lifecycle:
        points.append(explain_lifecycle_state(name, lifecycle, dominant_declining=declining))
    if coverage_state:
        points.append(explain_evidence_breadth(coverage_state))
    technical = build_supporting_detail_labels(
        {
            "score": (context.get("overview") or {}).get("score"),
            "memory_state": lifecycle,
        }
    )
    return _schema(
        headline,
        what_changed=change,
        why_it_matters=(
            f"{name} is a meaningful part of the current market explanation."
            if str(lifecycle or "").upper() != "ABSENT"
            else None
        ),
        supporting_points=points,
        limitations=build_explanation_limitations(),
        technical_details=technical,
    )


def explain_market_expression(expression: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compose a deterministic plain-language explanation of observed expression."""
    if not isinstance(expression, dict):
        return None
    raw_state = str(expression.get("state") or "UNAVAILABLE").upper()
    if raw_state not in MARKET_EXPRESSION_COPY["headlines"]:
        raw_state = "UNAVAILABLE"
    name = narrative_display_name(expression.get("narrative_key")) or "current"
    instruments = expression.get("instruments")
    instruments = instruments if isinstance(instruments, list) else []
    confirming = [
        item.get("label")
        for item in instruments
        if isinstance(item, dict) and item.get("status") in {"CONFIRMING", "ALIGNED"}
    ]
    diverging = [
        item.get("label")
        for item in instruments
        if isinstance(item, dict) and item.get("status") in {"DIVERGING", "PRESSURE"}
    ]
    muted = [
        item.get("label")
        for item in instruments
        if isinstance(item, dict) and item.get("status") == "MUTED"
    ]

    if confirming and diverging:
        what_changed = (
            f"{', '.join(confirming[:2]).capitalize()} showed alignment while "
            f"{', '.join(diverging[:2])} provided counter-pressure."
        )
    elif confirming:
        what_changed = (
            f"{', '.join(confirming[:2]).capitalize()} reflected the narrative "
            "in the available snapshot."
        )
    elif diverging:
        what_changed = (
            f"{', '.join(diverging[:2]).capitalize()} moved against the mapped "
            "narrative expression."
        )
    elif muted:
        what_changed = "The available mapped indicators showed no meaningful move."
    else:
        what_changed = "Available primary market indicators were insufficient."

    points = []
    if confirming:
        points.append(f"Confirming context: {', '.join(confirming[:3])}.")
    if diverging:
        points.append(f"Contrary context: {', '.join(diverging[:3])}.")
    breadth = expression.get("expression_breadth")
    if breadth and breadth != "unavailable":
        points.append(f"Expression breadth is {breadth}.")
    limitations = list(expression.get("limitations") or [])
    limitations.append(MARKET_EXPRESSION_COPY["context_note"])
    return _schema(
        MARKET_EXPRESSION_COPY["headlines"][raw_state].format(name=name),
        what_changed=what_changed,
        why_it_matters=MARKET_EXPRESSION_COPY["why"][raw_state],
        supporting_points=points,
        limitations=limitations,
        technical_details=[
            f"{item.get('asset')}: {item.get('move')} / {item.get('status')}"
            for item in instruments
            if isinstance(item, dict)
        ],
    )


def explain_history_pattern(context: dict[str, Any]) -> dict[str, Any]:
    name = narrative_display_name(context.get("group_key"))
    points = context.get("points") if isinstance(context.get("points"), list) else []
    present = [point for point in points if point.get("score") is not None]
    if not present:
        return _schema(
            f"There is not enough history to describe {name} yet.",
            limitations=build_explanation_limitations(thin_history=True),
        )
    scores = [_number(point.get("score")) for point in present]
    scores = [value for value in scores if value is not None]
    peak_index = scores.index(max(scores))
    ever_dominant = any(point.get("dominant") for point in present)
    gaps = any(point.get("pulse_state") == "Absent" for point in points)
    recurring = any(
        str(point.get("memory_state") or "").lower() in {"recurring", "re-accelerating"}
        for point in points
    )
    if len(scores) < 3:
        headline = f"{name} is present, but its available history is still limited."
    elif peak_index < len(scores) - 1 and scores[-1] < scores[peak_index]:
        lead = f"{name} built"
        if ever_dominant:
            lead += ", became dominant"
        headline = f"{lead}, then cooled from its recent peak."
    elif scores[-1] > scores[0]:
        headline = f"Attention around {name} has built across the available history."
    elif scores[-1] < scores[0]:
        headline = f"Attention around {name} has eased across the available history."
    else:
        headline = f"{name} has remained broadly steady across the available history."
    supporting = []
    if recurring:
        supporting.append(f"{name} returned after a quieter stretch.")
    if gaps:
        supporting.append("Some available snapshots show this narrative absent from the conversation.")
    if ever_dominant:
        supporting.append(f"{name} led the market conversation during part of the available history.")
    return _schema(
        headline,
        why_it_matters="The pattern shows how attention evolved, without implying what happens next.",
        supporting_points=supporting,
        limitations=build_explanation_limitations(thin_history=len(scores) < 3),
        technical_details=[
            f"Appearances: {len(present)}",
            f"Peak score: {max(scores):g}",
            f"Dominant snapshots: {sum(bool(point.get('dominant')) for point in present)}",
        ],
    )


def explain_dominance_change(context: dict[str, Any]) -> str:
    earlier = narrative_display_name(context.get("earlier"))
    later = narrative_display_name(context.get("later"))
    if earlier and later and earlier != later:
        return f"The market conversation shifted from {earlier} toward {later}."
    if later:
        if context.get("weakened"):
            return f"The dominant narrative remained {later}, but its influence weakened."
        return f"The dominant narrative remained {later}."
    return "There is not enough information to describe a change in narrative leadership."


def explain_historical_comparison(context: dict[str, Any]) -> dict[str, Any]:
    period_a = context.get("period_a") or {}
    period_b = context.get("period_b") or {}
    earlier = period_a.get("dominant_group") or period_a.get("dominant_theme")
    later = period_b.get("dominant_group") or period_b.get("dominant_theme")
    headline = explain_dominance_change({"earlier": earlier, "later": later})
    breadth_a = str((period_a.get("breadth") or {}).get("raw") or "").upper()
    breadth_b = str((period_b.get("breadth") or {}).get("raw") or "").upper()
    order = {"": 0, "UNKNOWN": 0, "MINIMAL": 1, "LIMITED": 1, "NARROW": 1, "MODERATE": 2, "BROAD": 3, "ROBUST": 3}
    limitations = []
    if order.get(breadth_b, 0) > order.get(breadth_a, 0):
        limitations.append(
            "Part of the difference may reflect broader source coverage in the later reconstruction."
        )
    return _schema(
        headline,
        what_changed=headline,
        why_it_matters="The comparison describes a shift in attention during the selected historical period.",
        supporting_points=[
            explain_evidence_breadth(breadth_a),
            explain_evidence_breadth(breadth_b),
        ],
        limitations=limitations,
    )
