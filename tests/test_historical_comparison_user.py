import json
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.historical_comparison_view import build_user_historical_comparison
from mne.presentation_language import HISTORICAL_DIRECTIONS, historical_direction
from tests.test_historical_comparison import (
    directory_digest,
    render_template,
    sample_replay_pair,
    temporary_mne_data_dir,
    write_replay,
)


def pair():
    replay_a, replay_b = sample_replay_pair()
    replay_a["theme_scores"]["vanished"] = 3
    replay_b["theme_scores"]["vanished"] = 0
    replay_a["source_intelligence"] = {
        "coverage_intelligence": {
            "breadth_state": "NARROW",
            "contributing_source_count": 3,
            "contributing_provider_count": 2,
            "contributing_category_count": 2,
        },
        "accepted_evidence": [{"origin": "live_persisted", "source_id": "source_secret"}],
    }
    replay_b["source_intelligence"] = {
        "coverage_intelligence": {
            "breadth_state": "BROAD",
            "contributing_source_count": 5,
            "contributing_provider_count": 3,
            "contributing_category_count": 3,
        },
        "accepted_evidence": [{"origin": "historical_backfill", "source_id": "fed_fomc"}],
    }
    return replay_a, replay_b


def render_compare(replay_a=None, replay_b=None):
    context = dashboard.build_user_historical_comparison_context(
        object(), replay_a or "", replay_b or ""
    )
    return context, render_template("historical_comparison_user.html", **context)


class HistoricalComparisonUserTests(unittest.TestCase):
    def setUp(self):
        self.replay_a, self.replay_b = pair()

    def _write_pair(self, data_dir):
        write_replay(data_dir, self.replay_a)
        write_replay(data_dir, self.replay_b)

    def _render_valid(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            return render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])

    def test_01_selector_route_and_page_render(self):
        self.assertIn("/history/compare", {getattr(route, "path", None) for route in dashboard.app.routes})
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            self.assertIn("Compare narratives", render_compare()[1])

    def test_02_selector_lists_user_safe_replays(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            html = render_compare()[1]
            self.assertIn("2026-07-01", html); self.assertIn("2026-07-02", html)

    def test_03_selector_excludes_malformed_artifacts(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"; replay_dir.mkdir(parents=True)
            (replay_dir / "bad.json").write_text("{bad", encoding="utf-8")
            self.assertIn("Two historical reconstructions are needed", render_compare()[1])

    def test_04_selector_needs_two_replays(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, self.replay_a)
            self.assertIn("Two historical reconstructions are needed", render_compare()[1])

    def test_05_valid_comparison_auto_orders_chronologically(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            context, _ = render_compare(self.replay_b["replay_id"], self.replay_a["replay_id"])
            self.assertEqual("2026-07-01", context["comparison"]["period_a"]["date"])

    def test_06_same_reconstruction_is_calm(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, self.replay_a)
            self.assertIn("nothing to compare", render_compare(self.replay_a["replay_id"], self.replay_a["replay_id"])[1])

    def test_07_comparison_snapshot_renders(self):
        self.assertIn("Comparison Snapshot", self._render_valid()[1])

    def test_08_dominance_changes_render(self):
        self.assertIn("Dominance Changes", self._render_valid()[1])

    def test_09_theme_changes_render(self):
        self.assertIn("Theme Changes", self._render_valid()[1])

    def test_10_group_changes_render(self):
        self.assertIn("Narrative Group Changes", self._render_valid()[1])

    def test_11_increased_label_renders(self):
        self.assertIn(">Increased<", self._render_valid()[1])

    def test_12_decreased_label_renders(self):
        self.assertIn(">Decreased<", self._render_valid()[1])

    def test_13_unchanged_label_renders(self):
        self.assertIn(">Unchanged<", self._render_valid()[1])

    def test_14_new_label_renders(self):
        self.assertIn(">New<", self._render_valid()[1])

    def test_15_dropped_label_renders(self):
        self.assertIn(">No longer present<", self._render_valid()[1])

    def test_16_evidence_base_section_renders(self):
        self.assertIn("Evidence Base Changes", self._render_valid()[1])

    def test_17_coverage_and_explore_sections_render(self):
        html = self._render_valid()[1]
        self.assertIn("Historical Coverage and Limitations", html); self.assertIn("Explore Each Period", html)

    def test_18_missing_coverage_is_calm(self):
        self.replay_a.pop("source_intelligence"); self.replay_b.pop("source_intelligence")
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            html = render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])[1]
            self.assertIn("Differences may partly reflect", html); self.assertNotIn("Unavailable", html)

    def test_19_both_investigation_links_render(self):
        html = self._render_valid()[1]
        self.assertIn(f'href="/history/{self.replay_a["replay_id"]}"', html)
        self.assertIn(f'href="/history/{self.replay_b["replay_id"]}"', html)

    def test_20_replay_ids_are_not_primary_labels(self):
        html = self._render_valid()[1]
        self.assertNotIn(f"<h1>{self.replay_a['replay_id']}", html)

    def test_21_backfill_ids_do_not_leak(self):
        self.assertNotIn("backfill_2026", json.dumps(self._render_valid()[0]["comparison"]))

    def test_22_workflow_ids_do_not_leak(self):
        self.replay_a["workflow_id"] = "workflow_secret"
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            self.assertNotIn("workflow_secret", render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])[1])

    def test_23_evidence_and_source_ids_do_not_leak(self):
        text = json.dumps(self._render_valid()[0]["comparison"])
        self.assertNotIn("evidence_id", text); self.assertNotIn("source_secret", text)

    def test_24_filesystem_paths_do_not_leak(self):
        self.assertNotIn("MNE_DATA_DIR", json.dumps(self._render_valid()[0]["comparison"]))

    def test_25_admin_controls_do_not_render(self):
        html = self._render_valid()[1]
        self.assertNotIn("Run Backfill", html); self.assertNotIn("/admin/replay/compare", html)

    def test_26_comparison_performs_no_writes(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir); before = directory_digest(data_dir)
            render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])
            self.assertEqual(before, directory_digest(data_dir))

    def test_27_comparison_does_not_run_replay(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            with patch.object(dashboard.historical_replay, "run_historical_replay", side_effect=AssertionError):
                render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])

    def test_28_comparison_does_not_run_backfill(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            with patch.object(dashboard.historical_backfill, "run_historical_backfill", side_effect=AssertionError):
                render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])

    def test_29_comparison_does_not_fetch_live(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_pair(data_dir)
            with patch("mne.rss_fetch.fetch_headlines_from_rss", side_effect=AssertionError):
                render_compare(self.replay_a["replay_id"], self.replay_b["replay_id"])

    def test_30_admin_comparison_unchanged(self):
        self.assertIn("/admin/replay/compare", {getattr(route, "path", None) for route in dashboard.app.routes})

    def test_31_historical_research_entry_point_remains(self):
        self.assertIn("Explore historical narratives", Path("templates/dashboard.html").read_text(encoding="utf-8"))

    def test_32_presentation_dictionary_covers_directions_and_copy(self):
        self.assertEqual(5, len(HISTORICAL_DIRECTIONS))
        for key in HISTORICAL_DIRECTIONS:
            self.assertFalse(historical_direction(key)["untranslated"])
        self.assertTrue(dashboard.HISTORICAL_COPY["compare_coverage_difference"])


if __name__ == "__main__":
    unittest.main()
