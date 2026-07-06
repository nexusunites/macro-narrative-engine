import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main


class FailedHeadlineCollectionTest(unittest.TestCase):
    def test_normal_headline_counts_do_not_abort(self):
        deduplication = {
            "raw_headline_count": 2,
            "deduped_headline_count": 1,
            "duplicate_count": 1,
        }

        self.assertFalse(main.should_abort_for_failed_headline_collection(deduplication))
        self.assertIsNone(main.headline_collection_failure_reason(deduplication))

    def test_zero_raw_headlines_abort(self):
        deduplication = {
            "raw_headline_count": 0,
            "deduped_headline_count": 0,
            "duplicate_count": 0,
        }

        self.assertTrue(main.should_abort_for_failed_headline_collection(deduplication))
        self.assertEqual(
            main.headline_collection_failure_reason(deduplication),
            "0 raw headlines",
        )

    def test_zero_deduped_headlines_abort(self):
        deduplication = {
            "raw_headline_count": 1,
            "deduped_headline_count": 0,
            "duplicate_count": 1,
        }

        self.assertTrue(main.should_abort_for_failed_headline_collection(deduplication))
        self.assertEqual(
            main.headline_collection_failure_reason(deduplication),
            "0 deduped headlines",
        )

    def test_zero_headline_run_persists_source_diagnostics_only(self):
        output = io.StringIO()

        with (
            patch.object(main, "fetch_headlines_from_rss", return_value=[]),
            patch.object(main, "save_headlines") as save_headlines,
            patch.object(
                main,
                "save_run_json",
                return_value=(Path("/tmp/results"), Path("/tmp/results/run.json")),
            ) as save_run_json,
            patch.object(main, "save_report") as save_report,
            patch.object(main, "calculate_narrative_dynamics") as calculate_dynamics,
            patch.object(main, "print_momentum") as print_momentum,
            patch.object(main, "print_daily_count_trends") as print_count_trends,
            patch.object(main, "print_daily_share_trends") as print_share_trends,
            redirect_stdout(output),
        ):
            main.main([])

        self.assertIn("RSS fetch failed or returned zero headlines.", output.getvalue())
        self.assertIn("Narrative run will not be generated.", output.getvalue())
        save_headlines.assert_not_called()
        save_run_json.assert_called_once()
        persisted_run = save_run_json.call_args.args[0]
        self.assertEqual(
            persisted_run["source_intelligence"],
            {
                "evidence_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
            },
        )
        self.assertEqual(
            persisted_run["narrative_run_status"],
            "skipped_failed_headline_collection",
        )
        save_report.assert_not_called()
        calculate_dynamics.assert_not_called()
        print_momentum.assert_not_called()
        print_count_trends.assert_not_called()
        print_share_trends.assert_not_called()

    def test_nonzero_headline_run_continues_to_normal_persistence_and_trends(self):
        with (
            patch.object(main, "fetch_headlines_from_rss", return_value=["No theme here"]),
            patch.object(main, "save_headlines", return_value=Path("/tmp/headlines.txt")) as save_headlines,
            patch.object(main, "load_themes", return_value=({}, "test-taxonomy")),
            patch.object(main, "analyze_themes", return_value=({}, {}, 0, {}, {})),
            patch.object(main, "compute_group_scores", return_value={}),
            patch.object(main, "get_dominant_group", return_value=(None, 0)),
            patch.object(
                main,
                "compute_narrative_concentration",
                return_value={
                    "dominant_theme": None,
                    "dominant_count": 0,
                    "total_mentions": 0,
                    "dominant_share": 0,
                    "concentration_gap": 0,
                },
            ),
            patch.object(
                main,
                "classify_catalyst_environment",
                return_value={
                    "state": "Neutral",
                    "confidence": "Low",
                    "density_score": 0,
                    "density_state": "Low",
                    "red_events": [],
                    "orange_events": [],
                    "reason": "No catalysts.",
                    "macro_calendar_status": "loaded_empty",
                    "macro_calendar_event_count": 0,
                    "macro_calendar_message": "No events.",
                    "macro_calendar_warning": False,
                },
            ),
            patch.object(
                main,
                "classify_positioning_environment",
                return_value={
                    "state": "Neutral",
                    "confidence": "Low",
                    "reason": "No positioning signal.",
                },
            ),
            patch.object(main, "calculate_narrative_dynamics", return_value={}),
            patch.object(main, "calculate_narrative_pulse", return_value={}),
            patch.object(
                main,
                "calculate_regime_alignment",
                return_value={
                    "score": 0,
                    "state": "Neutral",
                    "confidence": "Low",
                    "reason": "No regime signal.",
                },
            ),
            patch.object(
                main,
                "generate_mode_context",
                return_value={
                    "state": "Neutral",
                    "confidence": "Low",
                    "read": "No active read.",
                    "action": "No action.",
                    "risk": "No risk.",
                },
            ),
            patch.object(
                main,
                "save_run_json",
                return_value=(Path("/tmp/results"), Path("/tmp/results/run.json")),
            ) as save_run_json,
            patch("mne.storage.write_daily_snapshot") as write_daily_snapshot,
            patch.object(main, "build_daily_report", return_value="report"),
            patch.object(main, "save_report", return_value=Path("/tmp/report.txt")) as save_report,
            patch.object(main, "print_momentum") as print_momentum,
            patch.object(main, "print_daily_count_trends") as print_count_trends,
            patch.object(main, "print_daily_share_trends") as print_share_trends,
            redirect_stdout(io.StringIO()),
        ):
            main.main([])

        self.assertEqual(save_headlines.call_count, 2)
        save_run_json.assert_called_once()
        persisted_run = save_run_json.call_args.args[0]
        self.assertEqual(
            persisted_run["source_intelligence"],
            {
                "evidence_count": 1,
                "accepted_count": 1,
                "rejected_count": 0,
            },
        )
        write_daily_snapshot.assert_called_once()
        save_report.assert_called_once()
        print_momentum.assert_called_once()
        print_count_trends.assert_called_once()
        print_share_trends.assert_called_once()


if __name__ == "__main__":
    unittest.main()
