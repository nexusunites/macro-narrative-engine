import json
import tempfile
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from mne.narrative_history import build_narrative_history
from mne.presentation_language import NARRATIVE_HISTORY_COPY, dashboard_parity_copy
from mne.render_cache import clear


class NarrativeHistoryTests(unittest.TestCase):
    def setUp(self):
        clear()
        self.temporary = tempfile.TemporaryDirectory()
        self.snapshots = Path(self.temporary.name) / "snapshots"
        self.snapshots.mkdir()

    def tearDown(self):
        clear()
        self.temporary.cleanup()

    def write_snapshot(self, day, narratives, **extra):
        payload = {"date": day, "narratives": narratives, **extra}
        (self.snapshots / f"{day}.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def row(self, score, share, rank, pulse="Building"):
        return {
            "group": "AI / Tech Growth",
            "score": score,
            "share": share,
            "rank": rank,
            "pulse_state": pulse,
        }

    def test_snapshot_only_series_preserves_values_and_gaps(self):
        self.write_snapshot("2026-07-01", [self.row(3, 12.5, 2, "Emerging")])
        self.write_snapshot("2026-07-02", [{"group": "Macro Pressure", "score": 4}])
        self.write_snapshot("2026-07-03", [self.row(9, 31.25, 1, "Dominant")])

        history = build_narrative_history(
            "AI / Tech Growth", snapshot_dir=self.snapshots
        )

        self.assertEqual(
            [(point["score"], point["share"], point["rank"]) for point in history["points"]],
            [(3, 12.5, 2), (None, None, None), (9, 31.25, 1)],
        )
        self.assertEqual(history["points"][1]["pulse_state"], "Absent")
        self.assertFalse(history["points"][1]["dominant"])
        self.assertEqual(history["summary"]["appearances"], 2)
        self.assertEqual(history["summary"]["dominance_count"], 1)
        self.assertEqual(history["summary"]["peak_score"], {"value": 9, "date": "2026-07-03"})
        self.assertEqual(history["summary"]["peak_share"], {"value": 31.25, "date": "2026-07-03"})

    def test_malformed_and_non_snapshot_files_are_excluded(self):
        self.write_snapshot("2026-07-01", [self.row(1, 5, 2)])
        (self.snapshots / "2026-07-02.json").write_text("{broken", encoding="utf-8")
        (self.snapshots / "replay.json").write_text(
            json.dumps({"date": "2026-07-02", "narratives": [self.row(99, 99, 1)]}),
            encoding="utf-8",
        )
        (self.snapshots / "2026-07-03.json").write_text(
            json.dumps({"date": "2026-07-09", "narratives": [self.row(99, 99, 1)]}),
            encoding="utf-8",
        )

        history = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)

        self.assertEqual([point["date"] for point in history["points"]], ["2026-07-01"])

    def test_window_uses_latest_valid_snapshot_days(self):
        for day in range(1, 6):
            self.write_snapshot(f"2026-07-0{day}", [self.row(day, day * 2, day)])
        (self.snapshots / "2026-07-06.json").write_text("bad", encoding="utf-8")

        history = build_narrative_history(
            "AI / Tech Growth", window_days=3, snapshot_dir=self.snapshots
        )

        self.assertEqual(
            [point["date"] for point in history["points"]],
            ["2026-07-03", "2026-07-04", "2026-07-05"],
        )

    def test_lifecycle_reuses_only_explicitly_persisted_memory_states(self):
        self.write_snapshot(
            "2026-07-01",
            [self.row(2, 10, 2, "Emerging")],
            narrative_memory={
                "groups": [
                    {
                        "name": "AI / Tech Growth",
                        "memory_state": "recurring",
                    }
                ]
            },
        )
        self.write_snapshot("2026-07-02", [self.row(3, 15, 1, "Strong")])

        history = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)

        self.assertEqual(history["points"][0]["memory_state"], "Recurring")
        self.assertIsNone(history["points"][1]["memory_state"])
        self.assertEqual(
            history["summary"]["latest_memory_event"],
            {"date": "2026-07-01", "state": "Recurring"},
        )

    def test_thin_and_empty_history_are_calm(self):
        empty = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)
        self.assertFalse(empty["has_history"])
        self.assertFalse(empty["has_chart_history"])

        self.write_snapshot("2026-07-01", [self.row(2, None, None)])
        thin = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)
        self.assertTrue(thin["has_history"])
        self.assertFalse(thin["has_chart_history"])
        self.assertFalse(thin["share_chart"]["available"])
        self.assertFalse(thin["rank_chart"]["available"])

    def test_identical_snapshot_input_produces_identical_context(self):
        for day in range(1, 4):
            self.write_snapshot(f"2026-07-0{day}", [self.row(day, day * 3, day)])

        first = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)
        second = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)

        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_full_template_renders_charts_timeline_integrity_and_safe_copy(self):
        for day, pulse in ((1, "Emerging"), (2, "Building"), (3, "Dominant")):
            self.write_snapshot(
                f"2026-07-0{day}",
                [self.row(day * 3, day * 10, 4 - day, pulse)],
            )
        history = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)
        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(["html"]),
        )
        env.globals["url_for"] = lambda endpoint, **values: (
            f"/static/{values['path']}"
            if endpoint == "static"
            else f"/research/{values['key']}"
        )
        env.globals["dashboard_copy"] = {
            key: dashboard_parity_copy(key)
            for key in (
                "brand_short", "brand_full", "nav_overview", "nav_research",
                "nav_preferences", "nav_sign_in",
            )
        }
        html = env.get_template("narrative_history.html").render(
            request=object(),
            message=None,
            history=history,
            copy=NARRATIVE_HISTORY_COPY,
            narrative_key="group:AI / Tech Growth",
        )

        self.assertIn("Share of narrative attention", html)
        self.assertIn("Lifecycle over time", html)
        self.assertIn("History reflects persisted MNE runs.", html)
        self.assertIn("Missing run dates are not interpolated.", html)
        self.assertIn("data-history-chart", html)
        self.assertIn("history-step-line", html)
        self.assertNotIn("/tmp/", html)
        self.assertNotIn("evidence_id", html)
        for forbidden in ("bullish", "bearish", "forecast", "prediction", "buy", "sell"):
            self.assertNotIn(forbidden, html.lower())

    def test_missing_share_and_rank_omit_their_charts(self):
        for day in range(1, 4):
            self.write_snapshot(
                f"2026-07-0{day}",
                [self.row(day, None, None)],
            )
        history = build_narrative_history("AI / Tech Growth", snapshot_dir=self.snapshots)

        self.assertTrue(history["score_chart"]["available"])
        self.assertFalse(history["share_chart"]["available"])
        self.assertFalse(history["rank_chart"]["available"])

    def test_module_has_no_replay_fetch_or_write_dependencies(self):
        source = Path("mne/narrative_history.py").read_text(encoding="utf-8")
        self.assertNotIn("replay", source.lower().replace("replay artifacts", ""))
        self.assertNotIn("requests", source)
        self.assertNotIn("urlopen", source)
        self.assertNotIn("write_text", source)
        self.assertNotIn("open(path, \"w", source)


if __name__ == "__main__":
    unittest.main()
