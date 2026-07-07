import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.operating_modes import generate_macro_context


class DashboardTrustFixTests(unittest.TestCase):
    def test_macro_context_fallback_does_not_repeat_market_context(self):
        context = generate_macro_context(
            dominant_theme=None,
            dominant_group="AI / Tech Growth",
            narrative_signals={},
            market_environment=None,
            narrative_market_relationship=None,
            breadth_confirmation=None,
            catalyst_environment=None,
            positioning_environment=None,
            regime_alignment=None,
            market_snapshot={},
        )

        self.assertEqual(
            context["read"],
            (
                "AI / Tech Growth is the dominant narrative group, while market "
                "context is unclear and breadth is unclear."
            ),
        )
        self.assertNotIn("market context is market confirmation", context["read"])

    def test_run_options_use_human_readable_labels_with_filename_values(self):
        paths = [
            Path("/tmp/2026-07-07_114250.json"),
            Path("/tmp/manual_run.json"),
        ]

        with patch.object(dashboard, "fmt_file_timestamp", return_value="2026-07-07 12:00"):
            options = dashboard.build_run_options(paths)

        self.assertEqual(
            options,
            [
                {"filename": "2026-07-07_114250.json", "label": "07/07 11:42"},
                {
                    "filename": "manual_run.json",
                    "label": "manual_run (modified 2026-07-07 12:00)",
                },
            ],
        )

    def test_regime_history_summary_names_latest_move_separately(self):
        paths = [
            Path("/tmp/2026-07-04_090000.json"),
            Path("/tmp/2026-07-05_090000.json"),
            Path("/tmp/2026-07-06_090000.json"),
            Path("/tmp/2026-07-07_090000.json"),
        ]
        scores_by_name = {
            "2026-07-04_090000.json": 50,
            "2026-07-05_090000.json": 60,
            "2026-07-06_090000.json": 70,
            "2026-07-07_090000.json": 62,
        }

        def load_result(path):
            return {
                "timestamp": path.stem,
                "regime_alignment": {"score": scores_by_name[path.name]},
            }

        with patch.object(dashboard, "list_regime_history_files", return_value=list(reversed(paths))):
            with patch.object(dashboard, "load_result", side_effect=load_result):
                history = dashboard.build_regime_history()

        self.assertEqual(
            history["summary"],
            "Alignment higher over the recent window; latest move down.",
        )


if __name__ == "__main__":
    unittest.main()
