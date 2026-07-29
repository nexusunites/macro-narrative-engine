import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard


class DashboardContextSplitTests(unittest.TestCase):
    def test_user_context_excludes_admin_only_keys_and_builders(self):
        run_path = Path("/tmp/2026-07-29_120000.json")
        run = {
            "timestamp": "2026-07-29_120000",
            "theme_scores": {"rates": 1},
            "group_scores": {"Macro Pressure": 1},
            "dominant_theme": "rates",
            "dominant_group": "Macro Pressure",
        }
        with (
            patch.object(dashboard, "list_result_files", return_value=[run_path]),
            patch.object(dashboard, "list_all_result_files", return_value=[run_path]),
            patch.object(dashboard, "load_result", return_value=run),
            patch.object(dashboard, "build_regime_history") as regime_history,
            patch.object(
                dashboard,
                "build_narrative_leadership_history",
            ) as leadership_history,
            patch.object(
                dashboard.historical_backfill_admin,
                "list_recent_backfill_summaries",
            ) as backfill_scan,
            patch.object(dashboard, "build_historical_backfill_console") as backfill_console,
            patch.object(dashboard, "build_historical_replay_console") as replay_console,
        ):
            context = dashboard.build_template_context(
                object(),
                run=None,
                include_admin=False,
            )

        for key in (
            "regime_history",
            "narrative_leadership_history",
            "historical_replay_console",
            "historical_backfill_console",
        ):
            self.assertNotIn(key, context)
        regime_history.assert_not_called()
        leadership_history.assert_not_called()
        backfill_scan.assert_not_called()
        backfill_console.assert_not_called()
        replay_console.assert_not_called()

    def test_admin_context_preserves_admin_extensions(self):
        with (
            patch.object(dashboard, "list_result_files", return_value=[]),
            patch.object(dashboard, "list_all_result_files", return_value=[]),
            patch.object(dashboard, "build_regime_history", return_value={"regime": 1}),
            patch.object(
                dashboard,
                "build_narrative_leadership_history",
                return_value={"leadership": 1},
            ),
            patch.object(
                dashboard.historical_backfill_admin,
                "list_recent_backfill_summaries",
                return_value=[{"backfill_id": "example"}],
            ),
            patch.object(
                dashboard,
                "build_historical_replay_console",
                return_value={"replay": 1},
            ),
            patch.object(
                dashboard,
                "build_historical_backfill_console",
                return_value={"backfill": 1},
            ),
        ):
            context = dashboard.build_template_context(
                object(),
                run=None,
                meaningful_default=False,
            )

        self.assertEqual(context["regime_history"], {"regime": 1})
        self.assertEqual(
            context["narrative_leadership_history"],
            {"leadership": 1},
        )
        self.assertEqual(context["historical_replay_console"], {"replay": 1})
        self.assertEqual(context["historical_backfill_console"], {"backfill": 1})
