import io
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main
from mne_test_utils import temporary_mne_data_dir


def sample_source_health(entries_seen=0, entries_parsed=0, state="EMPTY"):
    return [
        {
            "source_id": "wsj-markets",
            "source_name": "WSJ Markets",
            "state": state,
            "severity": "WARNING" if state == "EMPTY" else "INFO",
            "reason": "Zero entries present in feed",
            "recommended_action": "Confirm whether the source is expected to publish entries.",
            "http_status": 200,
            "entries_seen": entries_seen,
            "entries_parsed": entries_parsed,
            "fetch_error": None,
            "checked_at": "2026-07-06T12:00:00+00:00",
        }
    ]


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
        source_health = sample_source_health()

        with (
            temporary_mne_data_dir(),
            patch.object(
                main,
                "fetch_headlines_from_rss",
                return_value={"entries": [], "source_health": source_health},
            ),
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
        source_intelligence = persisted_run["source_intelligence"]
        self.assertEqual(source_intelligence["registry_version"], "1.0.0")
        self.assertEqual(source_intelligence["evidence_count"], 0)
        self.assertEqual(source_intelligence["accepted_count"], 0)
        self.assertEqual(source_intelligence["rejected_count"], 0)
        self.assertEqual(source_intelligence["source_health"], source_health)
        self.assertEqual(source_intelligence["evidence_freshness"]["fresh_count"], 0)
        self.assertIn("source_freshness", source_intelligence)
        self.assertEqual(source_intelligence["rejected_evidence_preview"], [])
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
        source_health = sample_source_health(
            entries_seen=1,
            entries_parsed=1,
            state="HEALTHY",
        )
        source_health[0]["reason"] = "Feed parsed successfully; 1 entries parsed"
        source_health[0]["recommended_action"] = "No action needed."
        with ExitStack() as stack:
            stack.enter_context(temporary_mne_data_dir())
            stack.enter_context(patch.object(
                main,
                "fetch_headlines_from_rss",
                return_value={
                    "entries": [
                        {
                            "title": "No theme here",
                            "timestamp": "2026-07-06T11:45:00+00:00",
                            "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
                        }
                    ],
                    "source_health": source_health,
                },
            ))
            save_headlines = stack.enter_context(
                patch.object(main, "save_headlines", return_value=Path("/tmp/headlines.txt"))
            )
            stack.enter_context(patch.object(main, "load_themes", return_value=({}, "test-taxonomy")))
            stack.enter_context(patch.object(main, "analyze_themes", return_value=({}, {}, 0, {}, {})))
            stack.enter_context(patch.object(main, "compute_group_scores", return_value={}))
            stack.enter_context(patch.object(main, "get_dominant_group", return_value=(None, 0)))
            stack.enter_context(patch.object(
                main,
                "compute_narrative_concentration",
                return_value={
                    "dominant_theme": None,
                    "dominant_count": 0,
                    "total_mentions": 0,
                    "dominant_share": 0,
                    "concentration_gap": 0,
                },
            ))
            stack.enter_context(patch.object(
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
            ))
            stack.enter_context(patch.object(
                main,
                "classify_positioning_environment",
                return_value={
                    "state": "Neutral",
                    "confidence": "Low",
                    "reason": "No positioning signal.",
                },
            ))
            stack.enter_context(patch.object(main, "calculate_narrative_dynamics", return_value={}))
            stack.enter_context(patch.object(main, "calculate_narrative_pulse", return_value={}))
            stack.enter_context(patch.object(
                main,
                "calculate_regime_alignment",
                return_value={
                    "score": 0,
                    "state": "Neutral",
                    "confidence": "Low",
                    "reason": "No regime signal.",
                },
            ))
            stack.enter_context(patch.object(
                main,
                "generate_mode_context",
                return_value={
                    "state": "Neutral",
                    "confidence": "Low",
                    "read": "No active read.",
                    "action": "No action.",
                    "risk": "No risk.",
                },
            ))
            save_run_json = stack.enter_context(patch.object(
                main,
                "save_run_json",
                return_value=(Path("/tmp/results"), Path("/tmp/results/run.json")),
            ))
            write_daily_snapshot = stack.enter_context(patch("mne.storage.write_daily_snapshot"))
            stack.enter_context(patch.object(main, "build_daily_report", return_value="report"))
            save_report = stack.enter_context(
                patch.object(main, "save_report", return_value=Path("/tmp/report.txt"))
            )
            print_momentum = stack.enter_context(patch.object(main, "print_momentum"))
            print_count_trends = stack.enter_context(patch.object(main, "print_daily_count_trends"))
            print_share_trends = stack.enter_context(patch.object(main, "print_daily_share_trends"))
            stack.enter_context(redirect_stdout(io.StringIO()))
            main.main([])

        self.assertEqual(save_headlines.call_count, 2)
        save_run_json.assert_called_once()
        persisted_run = save_run_json.call_args.args[0]
        source_intelligence = persisted_run["source_intelligence"]
        self.assertEqual(source_intelligence["registry_version"], "1.0.0")
        self.assertEqual(source_intelligence["evidence_count"], 1)
        self.assertEqual(source_intelligence["accepted_count"], 1)
        self.assertEqual(source_intelligence["rejected_count"], 0)
        self.assertEqual(source_intelligence["source_health"], source_health)
        self.assertEqual(source_intelligence["evidence_freshness"]["fresh_count"], 1)
        self.assertEqual(source_intelligence["rejected_evidence_preview"], [])
        write_daily_snapshot.assert_called_once()
        save_report.assert_called_once()
        print_momentum.assert_called_once()
        print_count_trends.assert_called_once()
        print_share_trends.assert_called_once()


if __name__ == "__main__":
    unittest.main()
