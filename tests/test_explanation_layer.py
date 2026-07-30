import ast
import json
import unittest
from pathlib import Path

from mne.explanation_layer import (
    LIFECYCLE_TEMPLATES,
    SNAPSHOT_LIMITATION,
    SUPPORTING_POINTS_LIMIT,
    build_explanation_limitations,
    explain_evidence_breadth,
    explain_historical_comparison,
    explain_history_pattern,
    explain_lifecycle_state,
    explain_narrative_snapshot,
)
from mne.narrative_memory import (
    STATE_ABSENT,
    STATE_BUILDING,
    STATE_DOMINANT,
    STATE_DORMANT,
    STATE_EMERGING,
    STATE_FADING,
    STATE_PERSISTENT,
    STATE_RE_ACCELERATING,
    STATE_RECURRING,
)


class ExplanationLayerTests(unittest.TestCase):
    def test_all_persisted_memory_states_have_rules(self):
        persisted = {
            STATE_DOMINANT, STATE_BUILDING, STATE_PERSISTENT, STATE_FADING,
            STATE_RECURRING, STATE_RE_ACCELERATING, STATE_DORMANT,
            STATE_EMERGING, STATE_ABSENT,
        }
        self.assertEqual(persisted, set(LIFECYCLE_TEMPLATES))

    def test_fixed_lifecycle_rules(self):
        expected = {
            "DOMINANT": "AI is the leading narrative",
            "PERSISTENT": "AI has remained a consistent",
            "EMERGING": "AI is beginning to attract",
            "FADING": "Attention around AI has been declining",
            "RECURRING": "AI has returned",
            "RE_ACCELERATING": "Attention around AI is beginning to build again",
            "ABSENT": "AI was not meaningfully present",
        }
        for token, phrase in expected.items():
            with self.subTest(token=token):
                self.assertIn(phrase, explain_lifecycle_state("ai", token))

    def test_declining_dominant_rule(self):
        text = explain_lifecycle_state("ai", "DOMINANT", dominant_declining=True)
        self.assertEqual(
            text,
            "AI remains the leading narrative, but its influence has eased from its recent peak.",
        )

    def test_display_name_conversion(self):
        self.assertIn("AI", explain_lifecycle_state("ai", "PERSISTENT"))
        self.assertIn("Big Tech", explain_lifecycle_state("big_tech", "PERSISTENT"))

    def test_primary_copy_excludes_forbidden_language(self):
        context = {
            "display_name": "AI",
            "memory": {"state": "RE_ACCELERATING", "score_delta": "+2", "share_delta": "+8.0 pts"},
            "overview": {"score": 14},
            "coverage": {"coverage_state": "BROAD"},
        }
        result = explain_narrative_snapshot(context)
        primary = " ".join(
            [result["headline"], result["what_changed"] or "", result["why_it_matters"] or ""]
            + result["supporting_points"] + result["limitations"]
        ).lower()
        for forbidden in (
            " run", "score delta", "rank delta", "share delta", "re_accelerating",
            "forecast", "prediction", "buy", "sell", "winner", "loser",
            "bullish", "bearish",
        ):
            self.assertNotIn(forbidden, primary)

    def test_raw_metrics_remain_secondary(self):
        result = explain_narrative_snapshot(
            {"display_name": "AI", "memory": {"state": "PERSISTENT"}, "overview": {"score": 14}}
        )
        self.assertIn("Score: 14", result["technical_details"])
        self.assertIn("Lifecycle state: PERSISTENT", result["technical_details"])

    def test_coverage_translation(self):
        self.assertIn("several distinct", explain_evidence_breadth("BROAD"))
        self.assertIn("narrower", explain_evidence_breadth("LIMITED"))
        self.assertIn("not enough", explain_evidence_breadth("UNKNOWN"))

    def test_missing_and_thin_history_are_calm(self):
        result = explain_history_pattern({"group_key": "AI / Tech Growth", "points": []})
        self.assertIn("not enough history", result["headline"].lower())
        self.assertTrue(any("limited" in item for item in result["limitations"]))

    def test_history_pattern_cooling_after_peak(self):
        result = explain_history_pattern({
            "group_key": "AI / Tech Growth",
            "points": [
                {"score": 2, "dominant": False, "pulse_state": "Emerging"},
                {"score": 8, "dominant": True, "pulse_state": "Dominant"},
                {"score": 4, "dominant": False, "pulse_state": "Building"},
            ],
        })
        self.assertIn("became dominant, then cooled", result["headline"])

    def test_comparison_leadership_shift_and_coverage_caution(self):
        result = explain_historical_comparison({
            "period_a": {"dominant_group": "AI / Tech Growth", "breadth": {"raw": "NARROW"}},
            "period_b": {"dominant_group": "Macro Pressure", "breadth": {"raw": "BROAD"}},
        })
        self.assertIn("shifted from AI / Tech Growth toward Macro Pressure", result["headline"])
        self.assertIn("broader source coverage", result["limitations"][0])

    def test_supporting_points_cap(self):
        self.assertEqual(SUPPORTING_POINTS_LIMIT, 3)
        result = explain_history_pattern({
            "group_key": "Macro Pressure",
            "points": [
                {"score": 1, "dominant": False, "pulse_state": "Building", "memory_state": "Recurring"},
                {"score": None, "dominant": False, "pulse_state": "Absent"},
                {"score": 4, "dominant": True, "pulse_state": "Dominant"},
                {"score": 2, "dominant": False, "pulse_state": "Building"},
            ],
        })
        self.assertLessEqual(len(result["supporting_points"]), 3)

    def test_integrity_limitation(self):
        self.assertIn(SNAPSHOT_LIMITATION, build_explanation_limitations())

    def test_identical_input_is_byte_identical(self):
        context = {"display_name": "AI", "memory": {"state": "PERSISTENT"}}
        left = json.dumps(explain_narrative_snapshot(context), sort_keys=True)
        right = json.dumps(explain_narrative_snapshot(context), sort_keys=True)
        self.assertEqual(left.encode(), right.encode())

    def test_module_imports_no_io_network_or_model_modules(self):
        source = Path("mne/explanation_layer.py").read_text()
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertTrue(imported.isdisjoint(
            {"os", "pathlib", "requests", "httpx", "urllib", "socket", "openai", "anthropic"}
        ))


if __name__ == "__main__":
    unittest.main()
