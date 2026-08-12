import json
import tempfile
import unittest
from pathlib import Path

from mne.historical_comparison_view import build_user_historical_comparison


def replay(replay_id, replay_date):
    return {
        "replay_id": replay_id,
        "replay_date": replay_date,
        "evidence_cutoff": f"{replay_date}T23:59:59Z",
        "evidence_count": 4,
        "source_count": 2,
        "theme_scores": {"rates": 4},
        "group_scores": {"Macro Pressure": 4},
        "dominant_theme": "rates",
        "dominant_group": "Macro Pressure",
        "artifact_path": "/private/secret/replay.json",
        "workflow_id": "workflow_secret",
        "replay_metadata": {
            "backfill_ids_used": ["backfill_secret"],
            "workflow_id": "workflow_metadata_secret",
        },
    }


class UserHistoricalComparisonBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.replay_dir = Path(self.temporary_directory.name)
        self.earlier_id = "replay_2026-07-01_macro"
        self.later_id = "replay_2026-07-02_macro"
        self._write_replay(replay(self.earlier_id, "2026-07-01"))
        self._write_replay(replay(self.later_id, "2026-07-02"))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_replay(self, artifact):
        path = self.replay_dir / f"{artifact['replay_id']}.json"
        path.write_text(json.dumps(artifact), encoding="utf-8")

    def _build(self, replay_a, replay_b):
        return build_user_historical_comparison(
            replay_a,
            replay_b,
            replay_dir=self.replay_dir,
        )

    def test_auto_orders_periods_chronologically(self):
        comparison = self._build(self.later_id, self.earlier_id)

        self.assertEqual(comparison["period_a"]["date"], "2026-07-01")
        self.assertEqual(comparison["period_b"]["date"], "2026-07-02")

    def test_equal_replay_ids_mark_same_reconstruction(self):
        comparison = self._build(self.earlier_id, self.earlier_id)

        self.assertTrue(comparison["same_reconstruction"])

    def test_output_omits_raw_ids_paths_and_workflow_metadata(self):
        comparison = self._build(self.earlier_id, self.later_id)
        serialized = json.dumps(comparison, sort_keys=True)

        self.assertFalse(
            {"replay_id", "replay_id_a", "replay_id_b"} & set(_all_keys(comparison))
        )
        for unsafe_value in (
            "/private/secret/replay.json",
            "backfill_secret",
            "workflow_secret",
            "workflow_metadata_secret",
            str(self.replay_dir),
        ):
            self.assertNotIn(unsafe_value, serialized)


def _all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


if __name__ == "__main__":
    unittest.main()
