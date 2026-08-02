import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.presentation_language import (
    compose_sentence,
    confidence,
    metric,
    pluralize,
    present_change_summary,
    state,
    support,
)


class PresentationLanguageTests(unittest.TestCase):
    def test_canonical_copy_is_exact(self):
        self.assertEqual(metric("Regime Alignment")["label"], "Market Support")
        self.assertEqual(metric("Narrative Pulse")["label"], "Strength")
        self.assertEqual(metric("Narrative Direction")["label"], "Narrative Direction")
        self.assertEqual(metric("Recent Movement")["label"], "Recent Movement")
        self.assertEqual(metric("X-Ray View")["label"], "X-Ray View")
        self.assertEqual(metric("Market Reaction")["label"], "Market Reaction")
        self.assertEqual(
            state("Fragile Risk-On"),
            {
                "label": "Confident, but on edge",
                "meaning": "Markets are rising, but the gains are narrow and easily shaken.",
                "tone": "caution",
                "raw": "Fragile Risk-On",
                "untranslated": False,
            },
        )
        self.assertEqual(confidence("Medium")["label"], "Based on solid data")

    def test_unknown_state_passes_through_and_is_flagged(self):
        translated = state("A Newly Added Engine State")
        self.assertEqual(translated["label"], "A Newly Added Engine State")
        self.assertTrue(translated["untranslated"])

    def test_support_bands_are_presentation_only(self):
        self.assertEqual(support(55)["label"], "Mixed support")
        self.assertEqual(support(83)["label"], "Strongly supportive")

    def test_today_run_label_keeps_filename_as_value(self):
        path = Path("/tmp/2026-07-29_144500.json")
        with patch.object(dashboard, "datetime", wraps=datetime) as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 7, 29, 16, 0)
            options = dashboard.build_run_options([path])
        self.assertEqual(
            options,
            [{"filename": path.name, "label": "Today 2:45 PM"}],
        )

    def test_chart_history_uses_daily_snapshots_only(self):
        snapshots = [
            {"date": "2026-07-01", "market_support_score": 48},
            {"date": "2026-07-02", "market_support": {"score": 55}},
        ]
        with patch.object(dashboard, "load_daily_snapshots", return_value=snapshots):
            with patch.object(
                dashboard,
                "list_regime_history_files",
                side_effect=AssertionError("per-run history must not be read"),
            ):
                history = dashboard.build_daily_support_history()

        self.assertTrue(history["has_chart"])
        self.assertEqual([point["score"] for point in history["chart_points"]], [48.0, 55.0])
        self.assertTrue(history["area_polygon"])

    def test_chart_history_gracefully_handles_snapshots_without_scores(self):
        with patch.object(
            dashboard,
            "load_daily_snapshots",
            return_value=[{"date": "2026-07-01", "narratives": []}],
        ):
            history = dashboard.build_daily_support_history()
        self.assertFalse(history["has_chart"])
        self.assertEqual(history["chart_points"], [])

    def test_daily_chart_excludes_snapshots_after_selected_run(self):
        snapshots = [
            {"date": "2026-07-01", "support_score": 48},
            {"date": "2026-07-02", "support_score": 55},
            {"date": "2026-07-03", "support_score": 61},
        ]
        with patch.object(dashboard, "load_daily_snapshots", return_value=snapshots):
            history = dashboard.build_daily_support_history("2026-07-02_140000")
        self.assertEqual(
            [point["date"] for point in history["chart_points"]],
            ["2026-07-01", "2026-07-02"],
        )

    def test_summary_sentence_skips_unavailable_parts(self):
        self.assertEqual(
            compose_sentence(state("Building", category="Pulse"), state("Cooling", category="Acceleration"), state(None, category="Crowding")),
            "Gaining traction and cooling off.",
        )
        self.assertEqual(
            compose_sentence(state("Building", category="Pulse")),
            "Gaining traction.",
        )
        self.assertNotIn("unavailable", compose_sentence(state(None)).lower())

    def test_pluralize_handles_numeric_strings(self):
        self.assertEqual(pluralize("1", "story"), "1 story")
        self.assertEqual(pluralize("2", "story"), "2 stories")

    def test_change_summary_translates_and_deduplicates_parent_theme_move(self):
        summary = {
            "has_changes": True,
            "changes": {
                "major": [],
                "narratives": [
                    {"text": "energy weakened: 29 -> 13.", "importance": 16},
                    {"text": "Energy / Commodities weakened: 35 -> 19.", "importance": 16},
                    {"text": "Concentration gap narrowed: 12 -> 6.", "importance": 6},
                ],
                "market": [],
                "catalysts": [],
            },
        }
        presented = present_change_summary(summary)
        texts = [item["text"] for item in presented["changes"]["narratives"]]
        self.assertNotIn("Energy weakened: 29 stories → 13 stories.", texts)
        self.assertIn(
            "Energy / Commodities weakened: 35 stories → 19 stories.",
            texts,
        )
        self.assertIn("Lead over #2 narrowed: 12 → 6.", texts)
        self.assertTrue(all(item["direction"] == "down" for item in presented["changes"]["narratives"]))


if __name__ == "__main__":
    unittest.main()
