import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mne import storage


class SnapshotSupportScoreTests(unittest.TestCase):
    def test_preview_enriches_raw_run_and_top_level_score(self):
        preview = storage.build_daily_snapshot_preview(
            {
                "run_id": "run-1",
                "timestamp": "2026-07-29T10:00:00",
                "regime_alignment": {"score": 61, "state": "Supportive"},
            },
            "2026-07-29",
        )
        self.assertEqual(
            preview["raw_runs"][0]["regime_alignment"],
            {"score": 61, "state": "Supportive"},
        )
        self.assertEqual(
            preview["regime_alignment"],
            {"score": 61, "state": "Supportive", "source_run_id": "run-1"},
        )

    def test_preview_persists_explicit_null_when_regime_is_absent(self):
        preview = storage.build_daily_snapshot_preview(
            {"run_id": "run-1", "timestamp": "2026-07-29T10:00:00"},
            "2026-07-29",
        )
        self.assertEqual(
            preview["raw_runs"][0]["regime_alignment"],
            {"score": None, "state": None},
        )
        self.assertEqual(
            preview["regime_alignment"],
            {"score": None, "state": None, "source_run_id": None},
        )

    def test_representative_is_latest_run_with_non_null_score(self):
        snapshot = storage._snapshot_from_runs(
            "2026-07-29",
            [
                {
                    "run_id": "early",
                    "timestamp": "2026-07-29T09:00:00",
                    "regime_alignment": {"score": 52, "state": "Mixed"},
                },
                {
                    "run_id": "late-null",
                    "timestamp": "2026-07-29T15:00:00",
                    "regime_alignment": {"score": None, "state": None},
                },
                {
                    "run_id": "latest-score",
                    "timestamp": "2026-07-29T14:00:00",
                    "regime_alignment": {"score": 64, "state": "Supportive"},
                },
            ],
        )
        self.assertEqual(
            snapshot["regime_alignment"],
            {
                "score": 64,
                "state": "Supportive",
                "source_run_id": "latest-score",
            },
        )

    def test_repair_is_idempotent_and_preserves_other_snapshot_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshots_dir = root / "snapshots"
            results_dir = root / "results"
            snapshots_dir.mkdir()
            results_dir.mkdir()
            snapshot_path = snapshots_dir / "2026-07-29.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "date": "2026-07-29",
                        "narratives": [{"group": "AI / Tech Growth"}],
                        "custom": {"untouched": True},
                    }
                ),
                encoding="utf-8",
            )
            (results_dir / "2026-07-29_090000.json").write_text(
                json.dumps(
                    {
                        "run_id": "morning",
                        "timestamp": "2026-07-29T09:00:00",
                        "regime_alignment": {"score": 51, "state": "Mixed"},
                    }
                ),
                encoding="utf-8",
            )
            (results_dir / "2026-07-29_150000.json").write_text(
                json.dumps(
                    {
                        "run_id": "afternoon",
                        "timestamp": "2026-07-29T15:00:00",
                        "regime_alignment": {"score": 67, "state": "Supportive"},
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(storage, "SNAPSHOTS_DIR", snapshots_dir),
                patch.object(storage, "RESULTS_DIR", results_dir),
            ):
                self.assertEqual(storage.repair_snapshot_support_scores(), 1)
                self.assertEqual(storage.repair_snapshot_support_scores(), 0)

            repaired = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(
                repaired["regime_alignment"],
                {
                    "score": 67,
                    "state": "Supportive",
                    "source_run_id": "afternoon",
                },
            )
            self.assertEqual(repaired["custom"], {"untouched": True})
            self.assertEqual(
                repaired["narratives"],
                [{"group": "AI / Tech Growth"}],
            )


if __name__ == "__main__":
    unittest.main()
