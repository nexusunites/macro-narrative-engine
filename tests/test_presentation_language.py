import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.presentation_language import (
    attention_direction_from_share_delta,
    dashboard_attention_summary,
    compose_sentence,
    confidence,
    metric,
    pluralize,
    present_change_summary,
    state,
    support,
    dashboard_evidence_meta,
    dashboard_sector_presentation,
)


class PresentationLanguageTests(unittest.TestCase):
    def test_coverage_share_delta_has_one_direction_vocabulary(self):
        self.assertEqual(attention_direction_from_share_delta(1.2)["direction"], "up")
        self.assertEqual(attention_direction_from_share_delta(-0.4)["label"], "Fading")
        self.assertEqual(attention_direction_from_share_delta(None)["direction"], "steady")

    def test_card_summary_language_matches_unified_direction_state(self):
        cases = {
            "up": "Attention around Macro Pressure is building.",
            "down": "Attention around Macro Pressure has been declining.",
            "steady": "Attention around Macro Pressure is holding steady.",
        }
        for direction, expected in cases.items():
            with self.subTest(direction=direction):
                self.assertEqual(
                    dashboard_attention_summary("Macro Pressure", direction), expected
                )

    def test_card_summary_matches_card_direction_from_coverage_share_delta(self):
        run = {
            "timestamp": "2026-08-05_120000",
            "group_scores": {
                "Energy / Commodities": 15,
                "Macro Pressure": 11,
                "AI / Tech Growth": 3,
            },
            "theme_scores": {"energy": 15, "rates": 7, "inflation": 4, "ai": 3},
            "dominant_group": "Energy / Commodities",
            "dominant_theme": "energy",
        }
        rotation = [
            {"group": "Energy / Commodities", "rotation_state": "Emerging", "share_delta": 1, "rotation_streak": 1, "reason": "x"},
            {"group": "Macro Pressure", "rotation_state": "Emerging", "share_delta": 2, "rotation_streak": 1, "reason": "x"},
            {"group": "AI / Tech Growth", "rotation_state": "Fading", "share_delta": -3, "rotation_streak": 1, "reason": "x"},
        ]
        with (
            patch("analysis.leadership_rotation.get_rotation", return_value=rotation),
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = {}
            view = dashboard.build_view_model(run, Path("2026-08-05_120000.json"))

        cards = {item["group"]: item for item in view["narrative_leadership"]}
        self.assertEqual(cards["Macro Pressure"]["direction"], "up")
        self.assertEqual(cards["Macro Pressure"]["status_label"], "Strengthening")
        self.assertIn("is building", cards["Macro Pressure"]["presentation"]["explanation"])
        self.assertEqual(cards["AI / Tech Growth"]["direction"], "down")
        self.assertEqual(cards["AI / Tech Growth"]["status_label"], "Cooling")
        self.assertIn("has been declining", cards["AI / Tech Growth"]["presentation"]["explanation"])

    def test_dashboard_sector_states_preserve_unavailable_data(self):
        self.assertEqual(
            dashboard_sector_presentation("UNAVAILABLE", "Current participation unavailable"),
            {"state": "steady", "label": "No fresh data this session"},
        )
        self.assertEqual(dashboard_sector_presentation("STRONG")["state"], "driving")
        self.assertEqual(dashboard_sector_presentation("DETACHED")["state"], "detached")

    def test_dashboard_evidence_meta_uses_persisted_attribution(self):
        self.assertEqual(
            dashboard_evidence_meta("Reuters", "2026-08-04T18:54:56+00:00"),
            "Reuters · Aug 4, 6:54 PM",
        )
        self.assertEqual(dashboard_evidence_meta(None, None), "Source unavailable")

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
