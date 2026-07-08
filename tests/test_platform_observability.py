import io
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main
from mne_test_utils import temporary_mne_data_dir
from mne.platform_observability import (
    FAILED,
    SKIPPED,
    STAGE_NAMES,
    SUCCESS,
    PipelineTelemetryRecorder,
)


def healthy_source_health():
    return [
        {
            "source_id": "cnbc-top-news",
            "source_name": "CNBC Top News",
            "state": "HEALTHY",
            "severity": "INFO",
            "reason": "Feed parsed successfully; 1 entries parsed",
            "recommended_action": "No action needed.",
            "http_status": 200,
            "entries_seen": 1,
            "entries_parsed": 1,
            "fetch_error": None,
            "checked_at": "2026-07-06T12:00:00+00:00",
        }
    ]


class PlatformObservabilityTests(unittest.TestCase):
    def test_stage_observer_records_failure_and_reraises_original_exception(self):
        recorder = PipelineTelemetryRecorder(engine_versions=main.engine_versions())
        original = RuntimeError("stage exploded")

        try:
            with recorder.observe("RSS_FETCH"):
                raise original
        except RuntimeError as error:
            self.assertIs(error, original)
        else:
            self.fail("Expected RuntimeError to propagate")

        stage = recorder.to_block()["stages"][0]
        self.assertEqual(stage["stage_name"], "RSS_FETCH")
        self.assertEqual(stage["status"], FAILED)
        self.assertIn("stage exploded", stage["diagnostic_message"])
        self.assertIsNotNone(stage["start_time"])
        self.assertIsNotNone(stage["end_time"])
        self.assertGreater(stage["duration_ms"], 0)

    def test_normal_run_persists_complete_platform_observability_block(self):
        source_health = healthy_source_health()
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
                            "feed_url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
                        }
                    ],
                    "source_health": source_health,
                },
            ))
            stack.enter_context(patch.object(main, "save_headlines", return_value=Path("/tmp/headlines.txt")))
            stack.enter_context(patch.object(main, "load_themes", return_value=({}, "test-taxonomy")))
            stack.enter_context(patch.object(
                main,
                "analyze_themes",
                return_value=({}, {}, 0, {}, {}, [{"headline": "No theme here", "themes": []}]),
            ))
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
            stack.enter_context(
                patch.object(main, "evaluate_event_lifecycle_run", return_value={"current_event": None, "events": []})
            )
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
            stack.enter_context(patch.object(main, "generate_narrative_brief", return_value={"sections": []}))
            save_run_json = stack.enter_context(patch.object(
                main,
                "save_run_json",
                return_value=(Path("/tmp/results"), Path("/tmp/results/run.json")),
            ))
            stack.enter_context(patch("mne.storage.write_daily_snapshot"))
            stack.enter_context(patch.object(main, "build_daily_report", return_value="report"))
            stack.enter_context(patch.object(main, "save_report", return_value=Path("/tmp/report.txt")))
            stack.enter_context(patch.object(main, "print_momentum"))
            stack.enter_context(patch.object(main, "print_daily_count_trends"))
            stack.enter_context(patch.object(main, "print_daily_share_trends"))
            stack.enter_context(redirect_stdout(io.StringIO()))
            main.main([])

        run = save_run_json.call_args.args[0]
        telemetry = run["platform_observability"]
        self.assertEqual(len(telemetry["stages"]), 10)
        self.assertEqual([stage["stage_name"] for stage in telemetry["stages"]], list(STAGE_NAMES))
        self.assertEqual(set(telemetry["run_metadata"]["engine_versions"]), set(main.engine_versions()))
        self.assertEqual(telemetry["run_metadata"]["execution_mode"], "LIVE")
        self.assertGreater(telemetry["run_metadata"]["run_duration_ms"], 0)

        stages = {stage["stage_name"]: stage for stage in telemetry["stages"]}
        self.assertEqual(stages["RSS_FETCH"]["status"], SUCCESS)
        self.assertEqual(stages["RSS_FETCH"]["result_counts"]["entries_received"], 1)
        self.assertEqual(stages["EVIDENCE_NORMALIZATION"]["result_counts"]["accepted"], 1)
        self.assertEqual(stages["EVENT_LIFECYCLE"]["status"], SKIPPED)
        self.assertEqual(stages["REPORT_GENERATION"]["status"], SUCCESS)

        observed_times = [
            stage["start_time"]
            for stage in telemetry["stages"]
            if stage["start_time"] is not None
        ]
        self.assertEqual(observed_times, sorted(observed_times))
        for stage in telemetry["stages"]:
            if stage["status"] != SKIPPED:
                self.assertIsNotNone(stage["start_time"])
                self.assertIsNotNone(stage["end_time"])
                self.assertGreater(stage["duration_ms"], 0)


if __name__ == "__main__":
    unittest.main()
