import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from mne.event_lifecycle import (
    ACTIVE_RELEASE,
    COMPLETE,
    IMMEDIATE_PRE_EVENT,
    INITIAL_DIGESTION,
    NARRATIVE_REPRICING,
    PRE_POSITIONING,
    UPCOMING,
    calculate_event_timing,
    evaluate_event_lifecycle_run,
)
from mne.storage import _snapshot_from_runs


def et_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(
        tzinfo=ZoneInfo("America/New_York")
    ).astimezone(timezone.utc)


def cpi_event(**overrides):
    event = {
        "event_id": "cpi_2026_07",
        "event_name": "CPI (Core, YoY)",
        "event_type": "CPI",
        "date": "2026-07-14",
        "release_time": "08:30",
        "release_timezone": "America/New_York",
        "importance": "HIGH",
        "source": "manual-entry:test",
        "notes": None,
    }
    event.update(overrides)
    return event


class EventLifecycleTests(unittest.TestCase):
    def evaluate_single(self, now_et: str, event=None):
        result = evaluate_event_lifecycle_run(
            events=[event or cpi_event()],
            now_utc=et_timestamp(now_et),
        )
        return result, result["events"][0]

    def test_high_importance_default_verification_scenarios(self):
        scenarios = [
            ("2026-07-13T12:00:00", UPCOMING, 1230, None, None),
            ("2026-07-14T07:45:00", PRE_POSITIONING, 45, None, "cpi_2026_07"),
            ("2026-07-14T08:16:00", IMMEDIATE_PRE_EVENT, 14, None, "cpi_2026_07"),
            ("2026-07-14T08:29:00", IMMEDIATE_PRE_EVENT, 1, None, "cpi_2026_07"),
            ("2026-07-14T08:30:00", ACTIVE_RELEASE, None, 0, "cpi_2026_07"),
            ("2026-07-14T08:45:00", INITIAL_DIGESTION, None, 15, "cpi_2026_07"),
            ("2026-07-14T10:30:00", NARRATIVE_REPRICING, None, 120, "cpi_2026_07"),
            ("2026-07-14T15:30:00", NARRATIVE_REPRICING, None, 420, "cpi_2026_07"),
            ("2026-07-15T08:30:00", COMPLETE, None, None, None),
        ]

        for now_et, state, until, since, current_event in scenarios:
            with self.subTest(now_et=now_et):
                result, event = self.evaluate_single(now_et)
                self.assertEqual(event["lifecycle_state"], state)
                self.assertEqual(event["minutes_until_release"], until)
                self.assertEqual(event["minutes_since_release"], since)
                self.assertEqual(event["confidence"], "MEDIUM")
                self.assertEqual(result["current_event"], current_event)
                self.assertTrue(event["reason"])

    def test_next_transition_at_829_points_to_active_release(self):
        _, event = self.evaluate_single("2026-07-14T08:29:00")

        self.assertEqual(event["next_transition"]["next_state"], ACTIVE_RELEASE)
        self.assertEqual(event["next_transition"]["minutes_away"], 1)
        self.assertEqual(event["next_transition"]["at_utc"], "2026-07-14T12:30:00Z")

    def test_explicit_windows_raise_confidence_to_high(self):
        event = cpi_event(
            pre_positioning_window_minutes=120,
            immediate_pre_event_window_minutes=15,
            active_release_window_minutes=15,
            digestion_window_minutes=90,
            repricing_window_minutes=345,
        )

        for now_et, state in [
            ("2026-07-14T08:29:00", IMMEDIATE_PRE_EVENT),
            ("2026-07-14T08:30:00", ACTIVE_RELEASE),
            ("2026-07-14T08:45:00", INITIAL_DIGESTION),
        ]:
            with self.subTest(now_et=now_et):
                _, evaluated = self.evaluate_single(now_et, event=event)
                self.assertEqual(evaluated["lifecycle_state"], state)
                self.assertEqual(evaluated["confidence"], "HIGH")

    def test_dst_edge_uses_iana_timezone_conversion(self):
        timing = calculate_event_timing(
            cpi_event(
                event_id="cpi_2026_11",
                date="2026-11-02",
                release_time="08:30",
                release_timezone="America/New_York",
            )
        )

        self.assertEqual(
            timing.release_at_utc.isoformat().replace("+00:00", "Z"),
            "2026-11-02T13:30:00Z",
        )
        self.assertEqual(
            timing.repricing_end_utc.isoformat().replace("+00:00", "Z"),
            "2026-11-02T21:00:00Z",
        )

    def test_snapshot_retains_run_specific_lifecycle_outputs(self):
        morning = evaluate_event_lifecycle_run(
            events=[cpi_event()],
            now_utc=et_timestamp("2026-07-14T08:29:00"),
        )
        afternoon = evaluate_event_lifecycle_run(
            events=[cpi_event()],
            now_utc=et_timestamp("2026-07-14T15:30:00"),
        )

        snapshot = _snapshot_from_runs(
            "2026-07-14",
            [
                {"run_id": "morning", "timestamp": "2026-07-14_082900", "event_lifecycle": morning},
                {"run_id": "afternoon", "timestamp": "2026-07-14_153000", "event_lifecycle": afternoon},
            ],
        )

        raw_lifecycles = [run["event_lifecycle"] for run in snapshot["raw_runs"]]
        self.assertEqual(
            raw_lifecycles[0]["events"][0]["lifecycle_state"],
            IMMEDIATE_PRE_EVENT,
        )
        self.assertEqual(
            raw_lifecycles[1]["events"][0]["lifecycle_state"],
            NARRATIVE_REPRICING,
        )
        self.assertEqual(
            snapshot["latest_run_event_lifecycle"]["label"],
            "latest_run_only_not_daily_aggregate",
        )


if __name__ == "__main__":
    unittest.main()
