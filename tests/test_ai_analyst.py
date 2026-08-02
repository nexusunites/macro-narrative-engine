import json
import os
import unittest

from mne.ai_analyst import (
    CONTEXT_CHARACTER_CAP,
    EVIDENCE_ITEM_CAP,
    MODE_COMPARISON,
    MODE_HISTORICAL,
    MODE_NARRATIVE,
    MODE_TODAY,
    SYSTEM_PROMPT,
    build_ai_analyst_context,
    build_deterministic_fallback,
    classify_analyst_intent,
    generate_analyst_response,
    sanitize_ai_context,
    validate_analyst_response,
)
from mne.ai_provider import (
    DisabledProvider,
    MockProvider,
    ProviderTimeoutError,
    provider_from_environment,
)


def evidence(index=1):
    return {
        "title": f"Persisted headline {index}",
        "source_name": "Source",
        "provider": "Provider",
        "timestamp": "2026-07-31",
        "url": f"https://example.com/{index}",
        "evidence_id": f"secret-{index}",
        "raw_path": "/private/data.json",
    }


def explanation():
    return {
        "headline": "AI remains the leading narrative.",
        "what_changed": "Attention strengthened recently.",
        "why_it_matters": "It is meaningful in the current explanation.",
        "supporting_points": ["Persisted point."],
        "limitations": ["Available snapshots are incomplete."],
    }


def change_summary():
    return {
        "compared_with": "2026-07-31_150412",
        "changes": {
            "major": [{
                "text": "Energy / Commodities took leadership from Macro Pressure.",
                "importance": 10,
                "direction": "up",
            }],
            "narratives": [{
                "text": "AI / Tech Growth strengthened recently.",
                "importance": 7,
                "direction": "up",
            }],
            "market": [],
            "catalysts": [],
        },
        "has_changes": True,
    }


class AIAnalystTests(unittest.TestCase):
    def test_dashboard_context_builds_safely(self):
        context = build_ai_analyst_context(MODE_TODAY, view={
            "run": {"dominant_theme": "AI", "dominant_group": "Growth"},
            "theme_scores": [("AI", 4)], "group_scores": [("Growth", 4)],
            "presentation": {"hero_explanation": "AI leads."},
            "source_intelligence": {"accepted_evidence": [evidence()]},
        })
        self.assertEqual(context["dominant_theme"], "AI")
        self.assertEqual(context["evidence"][0]["title"], "Persisted headline 1")

    def test_dashboard_what_changed_composes_plain_english(self):
        context = build_ai_analyst_context(
            MODE_TODAY, view={"change_summary": change_summary()}
        )
        what_changed = context["explanation"]["what_changed"]
        self.assertEqual(
            what_changed,
            "Energy / Commodities took leadership from Macro Pressure. "
            "AI / Tech Growth strengthened recently.",
        )
        for leaked_repr in ("{", "'compared_with'", "'importance'"):
            self.assertNotIn(leaked_repr, what_changed)

    def test_dashboard_what_changed_empty_state(self):
        no_changes = {
            "has_changes": False,
            "changes": {
                "major": [], "narratives": [], "market": [], "catalysts": [],
            },
            "compared_with": "2026-07-31_150412",
        }
        for summary in (no_changes, None):
            with self.subTest(change_summary=summary):
                context = build_ai_analyst_context(
                    MODE_TODAY, view={"change_summary": summary}
                )
                self.assertEqual(
                    context["explanation"]["what_changed"],
                    "No major changes since the last update.",
                )

    def test_dashboard_what_changed_feeds_deterministic_fallback(self):
        context = build_ai_analyst_context(
            MODE_TODAY, view={"change_summary": change_summary()}
        )
        fallback = build_deterministic_fallback(context, MODE_TODAY)
        self.assertEqual(
            fallback["what_changed"],
            "Energy / Commodities took leadership from Macro Pressure. "
            "AI / Tech Growth strengthened recently.",
        )

    def test_narrative_context_builds_safely(self):
        context = build_ai_analyst_context(MODE_NARRATIVE, investigation={
            "display_name": "AI / Tech Growth", "overview": {"score": 7},
            "explanation": explanation(), "supporting_evidence_display": [evidence()],
        })
        self.assertEqual(context["dominant_group"], "AI / Tech Growth")

    def test_historical_context_builds_safely(self):
        context = build_ai_analyst_context(MODE_HISTORICAL, historical={
            "dominant_group": "Macro Pressure", "explanation": explanation(),
            "evidence": [evidence()], "summary": "Historical summary.",
        })
        self.assertEqual(context["history_summary"], "Historical summary.")

    def test_comparison_context_builds_safely(self):
        context = build_ai_analyst_context(MODE_COMPARISON, comparison={
            "explanation": explanation(), "summary": "Periods differ.",
            "period_a": {"date": "2026-01-01"}, "period_b": {"date": "2026-02-01"},
        })
        self.assertEqual(len(context["periods"]), 2)

    def test_sensitive_fields_never_enter_context(self):
        context = sanitize_ai_context({
            "mode": MODE_TODAY, "memory": {
                "run_id": "abc", "telemetry": "secret", "raw_path": "/private/x",
                "state": "BUILDING",
            }, "evidence": [evidence()],
            "credentials": "secret",
        })
        encoded = json.dumps(context)
        for forbidden in ("run_id", "telemetry", "raw_path", "/private", "credentials", "secret-1"):
            self.assertNotIn(forbidden, encoded)

    def test_evidence_and_context_are_bounded(self):
        context = sanitize_ai_context({
            "mode": MODE_TODAY, "evidence": [evidence(i) for i in range(30)],
            "history_summary": "x" * (CONTEXT_CHARACTER_CAP * 2),
        })
        self.assertLessEqual(len(context["evidence"]), EVIDENCE_ITEM_CAP)
        self.assertLessEqual(len(json.dumps(context)), CONTEXT_CHARACTER_CAP)

    def test_supported_and_unsupported_intents(self):
        self.assertEqual(classify_analyst_intent("What changed recently?", MODE_TODAY), "explain_change")
        self.assertEqual(classify_analyst_intent("Compare these periods", MODE_COMPARISON), "compare_periods")
        self.assertIsNone(classify_analyst_intent("Tell me a joke", MODE_TODAY))
        self.assertIsNone(classify_analyst_intent("Should I buy NVDA?", MODE_TODAY))

    def test_unsupported_intent_makes_no_provider_call(self):
        provider = MockProvider(response={})
        result = generate_analyst_response({"mode": MODE_TODAY}, MODE_TODAY, "Tell me a joke", provider)
        self.assertTrue(result["boundary"])
        self.assertEqual(provider.call_count, 0)

    def test_prompt_contract(self):
        self.assertIn("only the supplied persisted MNE context", SYSTEM_PROMPT)
        self.assertIn("Do not predict", SYSTEM_PROMPT)
        self.assertIn("Do not provide trade recommendations", SYSTEM_PROMPT)

    def test_mock_response_validates_and_preserves_citation(self):
        context = sanitize_ai_context({"mode": MODE_NARRATIVE, "evidence": [evidence()]})
        citation = context["evidence"][0]
        response = {
            "headline": "Persisted evidence explains the narrative.",
            "summary": "The supplied headline supports the current explanation.",
            "why_it_matters": "The narrative is prominent in the supplied context.",
            "supporting_evidence": [citation],
            "limitations": ["The evidence set is limited."],
        }
        provider = MockProvider(response=response)
        result = generate_analyst_response(context, MODE_NARRATIVE, "Explain the evidence", provider)
        self.assertFalse(result.get("fallback", False))
        self.assertEqual(result["supporting_evidence"], [citation])
        self.assertEqual(provider.call_count, 1)

    def test_invalid_fabricated_and_prohibited_responses_fall_back(self):
        context = sanitize_ai_context({
            "mode": MODE_NARRATIVE, "explanation": explanation(), "evidence": [evidence()]
        })
        fabricated = {
            "headline": "Analysis", "summary": "Summary", "why_it_matters": "Context",
            "supporting_evidence": [{**context["evidence"][0], "title": "Invented"}],
            "limitations": ["Limited"],
        }
        self.assertIsNone(validate_analyst_response(fabricated, MODE_NARRATIVE, context))
        prohibited = {**fabricated, "supporting_evidence": [], "summary": "You should buy it."}
        self.assertIsNone(validate_analyst_response(prohibited, MODE_NARRATIVE, context))
        result = generate_analyst_response(context, MODE_NARRATIVE, "Explain evidence", MockProvider(response="{bad"))
        self.assertTrue(result["fallback"])

    def test_disabled_missing_and_timeout_fall_back(self):
        context = sanitize_ai_context({"mode": MODE_TODAY, "explanation": explanation()})
        for provider in (DisabledProvider(), MockProvider(error=ProviderTimeoutError())):
            result = generate_analyst_response(context, MODE_TODAY, "What is driving today?", provider)
            self.assertTrue(result["fallback"])

    def test_disabled_provider_is_environment_default(self):
        previous = os.environ.get("MNE_AI_ANALYST_PROVIDER")
        try:
            os.environ.pop("MNE_AI_ANALYST_PROVIDER", None)
            self.assertIsInstance(provider_from_environment(), DisabledProvider)
            os.environ["MNE_AI_ANALYST_PROVIDER"] = "paid-provider"
            self.assertIsInstance(provider_from_environment(), DisabledProvider)
        finally:
            if previous is None:
                os.environ.pop("MNE_AI_ANALYST_PROVIDER", None)
            else:
                os.environ["MNE_AI_ANALYST_PROVIDER"] = previous

    def test_fallback_is_deterministic_and_matches_explanation(self):
        context = sanitize_ai_context({"mode": MODE_TODAY, "explanation": explanation()})
        first = build_deterministic_fallback(context, MODE_TODAY)
        second = build_deterministic_fallback(context, MODE_TODAY)
        self.assertEqual(first, second)
        self.assertEqual(first["headline"], explanation()["headline"])
        self.assertNotRegex(json.dumps(first).lower(), r"\b(buy|sell|predict)\b")

    def test_missing_evidence_adds_limitation(self):
        fallback = build_deterministic_fallback({"mode": MODE_HISTORICAL}, MODE_HISTORICAL)
        self.assertTrue(any("No supporting headline" in item for item in fallback["limitations"]))


if __name__ == "__main__":
    unittest.main()
