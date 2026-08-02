"""Constrained interpretation of persisted, user-safe MNE outputs."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from mne.ai_provider import AnalystProvider, provider_from_environment

MODE_TODAY = "todays_market"
MODE_NARRATIVE = "selected_narrative"
MODE_HISTORICAL = "historical_period"
MODE_COMPARISON = "historical_comparison"
ANALYST_MODES = (MODE_TODAY, MODE_NARRATIVE, MODE_HISTORICAL, MODE_COMPARISON)

CONTEXT_CHARACTER_CAP = 16000
EVIDENCE_ITEM_CAP = 8
OUTPUT_TOKEN_CAP = 700
REQUEST_TIMEOUT_SECONDS = 12
PROMPT_VERSION = "mne-ai-analyst-path-a-v1"

MODE_REQUIRED_FIELDS = {
    MODE_TODAY: {"headline", "summary", "why_it_matters", "limitations"},
    MODE_NARRATIVE: {
        "headline", "summary", "why_it_matters", "supporting_evidence", "limitations"
    },
    MODE_HISTORICAL: {
        "headline", "summary", "supporting_evidence", "limitations"
    },
    MODE_COMPARISON: {
        "headline", "summary", "what_changed", "limitations"
    },
}
RESPONSE_FIELDS = {
    "headline", "summary", "what_changed", "why_it_matters",
    "market_confirmation", "supporting_evidence", "limitations",
    "follow_up_questions",
}

INTENT_KEYWORDS = {
    "compare_periods": ("compare", "comparison", "versus", " vs ", "difference"),
    "explain_market": ("confirm", "confirmation", "diverge", "divergence", "market"),
    "explain_limitations": ("limit", "missing", "coverage", "confidence", "uncertain"),
    "explain_change": ("change", "changed", "recently", "different", "shift"),
    "explain_evidence": ("evidence", "headline", "source", "support", "why"),
    "summarize": ("summary", "summarize", "driving", "today", "explain", "what"),
}
MODE_INTENTS = {
    MODE_TODAY: {
        "summarize", "explain_change", "explain_evidence",
        "explain_market", "explain_limitations",
    },
    MODE_NARRATIVE: {
        "summarize", "explain_change", "explain_evidence",
        "explain_market", "explain_limitations",
    },
    MODE_HISTORICAL: {"summarize", "explain_evidence", "explain_limitations"},
    MODE_COMPARISON: {"summarize", "compare_periods", "explain_limitations"},
}
PROHIBITED_QUESTION_PATTERNS = (
    r"\bshould\s+i\s+(buy|sell|short)\b", r"\b(entry|target|stop[- ]?loss)\b",
    r"\bwill\s+.+\s+(rise|fall|go up|go down)\b", r"\bprice prediction\b",
)
PROHIBITED_RESPONSE_PATTERNS = (
    r"\b(buy|sell|short)\b", r"\b(entry|price target|stop[- ]?loss)\b",
    r"\bwill (rise|fall|rally|drop|increase|decrease)\b",
    r"\bguaranteed\b", r"\bcertain(?:ly)?\b", r"\bdefinitely\b",
)

SYSTEM_PROMPT = """MNE AI Analyst contract ({version})
Use only the supplied persisted MNE context. Do not fetch or imply access to new information.
Separate persisted fact from interpretation and state when evidence is missing.
Do not predict market direction or future outcomes. Do not provide trade recommendations,
including buying, selling, entries, targets, or stops. Do not use certainty language.
Do not invent evidence, citations, or causes, and do not claim complete market coverage.
Treat historical similarity as descriptive context, never as a future outcome.
Explain in plain English and lead with meaning, not metrics.
Return only the requested JSON schema. Every supporting_evidence item must exactly match
an evidence item supplied in context.
""".format(version=PROMPT_VERSION)

SUGGESTED_QUESTIONS = {
    MODE_TODAY: [
        "What is driving the market narrative today?",
        "What changed recently?",
        "Is the market confirming the narrative?",
    ],
    MODE_NARRATIVE: [
        "What does MNE's evidence say about this narrative?",
        "What changed recently?",
        "What are the evidence limits?",
    ],
    MODE_HISTORICAL: [
        "What shaped this historical period?",
        "What evidence supports this reconstruction?",
        "What are the evidence limits?",
    ],
    MODE_COMPARISON: [
        "How do these historical periods compare?",
        "What changed between the periods?",
        "How do their evidence limits differ?",
    ],
}


def _text(value: Any, limit: int = 3000) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result[:limit] if result else None


def _compose_what_changed(change_summary: Any) -> str:
    empty_state = "No major changes since the last update."
    if not isinstance(change_summary, dict) or not change_summary.get("has_changes"):
        return empty_state
    changes = change_summary.get("changes")
    changes = changes if isinstance(changes, dict) else {}
    texts = [
        str(item.get("text"))
        for key in ("major", "narratives", "market", "catalysts")
        for item in (changes.get(key) or [])
        if isinstance(item, dict) and item.get("text")
    ]
    return " ".join(texts) if texts else empty_state


def _safe_evidence(rows: Any) -> list[dict[str, Any]]:
    safe = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        url = _text(row.get("url") or row.get("article_url"), 1000)
        if url and not url.lower().startswith(("https://", "http://")):
            url = None
        item = {
            "title": _text(row.get("title") or row.get("headline"), 500),
            "source": _text(row.get("source") or row.get("source_name"), 200),
            "provider": _text(row.get("provider"), 200),
            "published_at": _text(
                row.get("published_at") or row.get("timestamp"), 100
            ),
            "url": url,
        }
        if item["title"]:
            safe.append(item)
        if len(safe) >= EVIDENCE_ITEM_CAP:
            break
    return safe


def _explanation(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    return {
        key: deepcopy(value.get(key))
        for key in (
            "headline", "what_changed", "why_it_matters",
            "supporting_points", "limitations",
        )
        if value.get(key) not in (None, "", [])
    }


def sanitize_ai_context(context: Any) -> dict[str, Any]:
    """Rebuild from an allowlist; never serialize arbitrary input objects."""
    source = context if isinstance(context, dict) else {}
    safe: dict[str, Any] = {
        "mode": source.get("mode") if source.get("mode") in ANALYST_MODES else None,
        "dominant_theme": _text(source.get("dominant_theme"), 300),
        "dominant_group": _text(source.get("dominant_group"), 300),
        "scores": deepcopy(source.get("scores")) if isinstance(source.get("scores"), dict) else {},
        "shares": deepcopy(source.get("shares")) if isinstance(source.get("shares"), dict) else {},
        "explanation": _explanation(source.get("explanation")),
        "memory": deepcopy(source.get("memory")) if isinstance(source.get("memory"), dict) else {},
        "history_summary": _text(source.get("history_summary")),
        "historical_connections": deepcopy(source.get("historical_connections"))
        if isinstance(source.get("historical_connections"), (dict, list)) else None,
        "market_expression": _explanation(source.get("market_expression")),
        "trust_summary": deepcopy(source.get("trust_summary"))
        if isinstance(source.get("trust_summary"), dict) else {},
        "coverage": deepcopy(source.get("coverage"))
        if isinstance(source.get("coverage"), dict) else {},
        "periods": deepcopy(source.get("periods"))
        if isinstance(source.get("periods"), list) else [],
        "limitations": [
            text for text in (_text(item, 500) for item in source.get("limitations", [])
            if isinstance(source.get("limitations"), list)) if text
        ],
        "evidence": _safe_evidence(source.get("evidence")),
    }
    # Named structures above can still contain nested diagnostics, so recursively
    # retain only scalar/list/dict values under explicit safe subfield names.
    safe = _prune_named(safe)
    encoded = json.dumps(safe, sort_keys=True, ensure_ascii=False)
    if len(encoded) > CONTEXT_CHARACTER_CAP:
        safe["evidence"] = []
        safe["limitations"].append(
            "Some supporting detail was omitted to keep the Analyst context bounded."
        )
        encoded = json.dumps(safe, sort_keys=True, ensure_ascii=False)
        if len(encoded) > CONTEXT_CHARACTER_CAP:
            safe["historical_connections"] = None
            safe["memory"] = {}
    return safe


_BLOCKED_KEYS = re.compile(
    r"(?:^|_)(?:id|path|telemetry|diagnostic|credential|token|secret|key)(?:$|_)",
    re.IGNORECASE,
)


def _prune_named(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _prune_named(item)
            for key, item in value.items()
            if not _BLOCKED_KEYS.search(str(key))
        }
    if isinstance(value, list):
        return [_prune_named(item) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _text(value)


def build_ai_analyst_context(
    mode: str,
    *,
    view: dict[str, Any] | None = None,
    investigation: dict[str, Any] | None = None,
    historical: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    history: dict[str, Any] | None = None,
    historical_connections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in ANALYST_MODES:
        raise ValueError("Unsupported Analyst mode.")
    source: dict[str, Any] = {"mode": mode, "limitations": []}
    if mode == MODE_TODAY and isinstance(view, dict):
        run = view.get("run") if isinstance(view.get("run"), dict) else {}
        source.update({
            "dominant_theme": run.get("dominant_theme"),
            "dominant_group": run.get("dominant_group"),
            "scores": {"themes": view.get("theme_scores"), "groups": view.get("group_scores")},
            "shares": {"dominant": view.get("dominant_share")},
            "explanation": {
                "headline": (view.get("presentation") or {}).get("hero_explanation"),
                "what_changed": _compose_what_changed(view.get("change_summary"))[:3000],
            },
            "memory": view.get("narrative_memory"),
            "market_expression": (view.get("market_expression_context") or {}).get("explanation"),
            "trust_summary": view.get("dashboard_trust_summary"),
            "coverage": (view.get("source_intelligence") or {}).get("coverage_intelligence"),
            "evidence": (view.get("source_intelligence") or {}).get("accepted_evidence"),
        })
    elif mode == MODE_NARRATIVE and isinstance(investigation, dict):
        source.update({
            "dominant_group": investigation.get("display_name"),
            "scores": investigation.get("overview"),
            "explanation": investigation.get("explanation"),
            "memory": investigation.get("memory"),
            "history_summary": (history or {}).get("summary"),
            "historical_connections": historical_connections,
            "market_expression": (investigation.get("market_expression") or {}).get("explanation"),
            "coverage": investigation.get("coverage"),
            "evidence": investigation.get("supporting_evidence_display"),
        })
    elif mode == MODE_HISTORICAL and isinstance(historical, dict):
        source.update({
            "dominant_theme": historical.get("dominant_theme"),
            "dominant_group": historical.get("dominant_group"),
            "scores": {"theme": historical.get("theme_score"), "group": historical.get("group_score")},
            "explanation": historical.get("explanation"),
            "history_summary": historical.get("summary"),
            "coverage": historical.get("coverage"),
            "evidence": historical.get("evidence"),
            "limitations": (historical.get("explanation") or {}).get("limitations", []),
        })
    elif mode == MODE_COMPARISON and isinstance(comparison, dict):
        source.update({
            "explanation": comparison.get("explanation"),
            "history_summary": comparison.get("summary"),
            "periods": [comparison.get("period_a"), comparison.get("period_b")],
            "coverage": {"available": comparison.get("coverage_available")},
        })
    return sanitize_ai_context(source)


def classify_analyst_intent(question: Any, mode: str) -> str | None:
    text = f" {_text(question, 1000) or ''} ".lower()
    if not text.strip() or any(re.search(pattern, text) for pattern in PROHIBITED_QUESTION_PATTERNS):
        return None
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent in MODE_INTENTS.get(mode, set()) and any(word in text for word in keywords):
            return intent
    return None


def build_analyst_prompt(
    context: dict[str, Any], mode: str, question: str
) -> dict[str, str]:
    return {
        "system": SYSTEM_PROMPT,
        "user": json.dumps(
            {"mode": mode, "question": question, "context": sanitize_ai_context(context)},
            sort_keys=True, ensure_ascii=False,
        ),
    }


def build_analyst_limitations(context: dict[str, Any]) -> list[str]:
    limitations = list(context.get("limitations") or [])
    if not context.get("evidence"):
        limitations.append("No supporting headline citations were available in the supplied MNE context.")
    if not context.get("coverage"):
        limitations.append("Coverage detail was unavailable in the supplied MNE context.")
    return list(dict.fromkeys(limitations))


def build_deterministic_fallback(
    context: dict[str, Any], mode: str
) -> dict[str, Any]:
    explanation = context.get("explanation") or {}
    supporting = explanation.get("supporting_points") or []
    result = {
        "headline": explanation.get("headline") or "MNE's persisted explanation is limited for this view.",
        "summary": explanation.get("why_it_matters") or context.get("history_summary") or explanation.get("headline") or "",
        "what_changed": explanation.get("what_changed") or "",
        "why_it_matters": explanation.get("why_it_matters") or "",
        "market_confirmation": (context.get("market_expression") or {}).get("headline", ""),
        "supporting_evidence": context.get("evidence", [])[:EVIDENCE_ITEM_CAP],
        "limitations": build_analyst_limitations(context),
        "follow_up_questions": list(SUGGESTED_QUESTIONS[mode]),
        "fallback": True,
        "note": "Showing MNE's built-in explanation.",
    }
    if supporting and not result["summary"]:
        result["summary"] = " ".join(str(item) for item in supporting)
    return result


def _citation_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(str(item.get(key) or "") for key in (
        "title", "source", "provider", "published_at", "url"
    ))


def validate_analyst_response(
    response: Any, mode: str, context: dict[str, Any]
) -> dict[str, Any] | None:
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (TypeError, ValueError):
            return None
    if not isinstance(response, dict) or mode not in MODE_REQUIRED_FIELDS:
        return None
    if set(response) - RESPONSE_FIELDS:
        return None
    if any(response.get(field) in (None, "", []) for field in MODE_REQUIRED_FIELDS[mode]):
        return None
    for field in ("headline", "summary", "what_changed", "why_it_matters", "market_confirmation"):
        value = response.get(field)
        if value not in (None, "") and not isinstance(value, str):
            return None
    for field in ("supporting_evidence", "limitations", "follow_up_questions"):
        if field in response and not isinstance(response[field], list):
            return None
    searchable = json.dumps(response, ensure_ascii=False).lower()
    if any(re.search(pattern, searchable) for pattern in PROHIBITED_RESPONSE_PATTERNS):
        return None
    allowed = {_citation_key(item) for item in context.get("evidence", [])}
    citations = response.get("supporting_evidence") or []
    if any(not isinstance(item, dict) or _citation_key(item) not in allowed for item in citations):
        return None
    return {field: deepcopy(response.get(field, [] if field in {
        "supporting_evidence", "limitations", "follow_up_questions"
    } else "")) for field in RESPONSE_FIELDS}


def boundary_response(mode: str) -> dict[str, Any]:
    return {
        "boundary": True,
        "message": "I can explain MNE's current evidence and analysis, but that question is outside what the Analyst covers.",
        "follow_up_questions": list(SUGGESTED_QUESTIONS.get(mode, [])),
    }


def generate_analyst_response(
    context: dict[str, Any],
    mode: str,
    question: str,
    provider: AnalystProvider | None = None,
) -> dict[str, Any]:
    safe_context = sanitize_ai_context(context)
    if classify_analyst_intent(question, mode) is None:
        return boundary_response(mode)
    selected = provider or provider_from_environment()
    try:
        response = selected.generate_analysis(safe_context, mode, question)
        validated = validate_analyst_response(response, mode, safe_context)
    except Exception:
        validated = None
    return validated or build_deterministic_fallback(safe_context, mode)
