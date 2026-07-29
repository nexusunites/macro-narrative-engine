import json
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.historical_research_view import build_user_historical_view
from mne.presentation_language import historical_breadth, historical_copy, historical_origin
from tests.test_historical_research import (
    render_template,
    sample_replay,
    temporary_mne_data_dir,
    write_replay,
)


def render_selector():
    return render_template("historical_selector.html", **dashboard.build_historical_selector_context(object()))


def render_investigation(replay_id="replay_2026-07-06_macro"):
    context = dashboard.build_user_historical_route_context(object(), replay_id)
    return context, render_template("historical_investigation.html", **context)


class HistoricalResearchUserTests(unittest.TestCase):
    def test_01_selector_route_registered(self):
        self.assertIn("/history", {getattr(route, "path", None) for route in dashboard.app.routes})

    def test_02_selector_lists_completed_replay(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            self.assertIn("2026-07-06", render_selector())

    def test_03_selector_excludes_malformed_replay(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"; replay_dir.mkdir(parents=True)
            (replay_dir / "bad.json").write_text("{bad", encoding="utf-8")
            self.assertIn("No historical reconstructions are available yet", render_selector())

    def test_04_selector_empty_state(self):
        with temporary_mne_data_dir():
            self.assertIn("No historical reconstructions are available yet", render_selector())

    def test_05_investigation_route_registered(self):
        self.assertIn("/history/{replay_id}", {getattr(route, "path", None) for route in dashboard.app.routes})

    def test_06_snapshot_zone(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn("Historical Snapshot", html)

    def test_07_explanation_zone(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn("Narrative Explanation", html)

    def test_08_evidence_zone(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn("Supporting Historical Evidence", html)

    def test_09_coverage_and_next_zones(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn("Coverage and Limitations", html); self.assertIn("Where to Look Next", html)

    def test_10_future_exclusion_copy_and_record_filter(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn(historical_copy("coverage_cutoff"), html); self.assertNotIn("Future evidence should not render", html)

    def test_11_historical_not_current_banner(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn(historical_copy("not_current"), html); self.assertIn(historical_copy("read_only"), html)

    def test_12_replay_id_not_used_as_visible_heading(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertNotIn("<h1>replay_", html)

    def test_13_no_backfill_id(self):
        replay = sample_replay(backfill_id="backfill_secret")
        self.assertNotIn("backfill_secret", render_template("historical_investigation.html", request=object(), historical=build_user_historical_view(replay), not_found=False, copy=dashboard.HISTORICAL_COPY))

    def test_14_no_workflow_id(self):
        replay = sample_replay(workflow_id="workflow_secret")
        self.assertNotIn("workflow_secret", str(build_user_historical_view(replay)))

    def test_15_no_evidence_or_source_ids(self):
        view = build_user_historical_view(sample_replay())
        text = json.dumps(view)
        self.assertNotIn('"evidence_id"', text); self.assertNotIn('"source_id"', text)

    def test_16_no_filesystem_paths(self):
        self.assertNotIn("MNE_DATA_DIR", json.dumps(build_user_historical_view(sample_replay())))

    def test_17_no_admin_controls(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertNotIn("<form", html); self.assertNotIn("Run Backfill", html)

    def test_18_source_link_present(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir); _, html = render_investigation()
            self.assertIn("https://example.com/e1", html); self.assertIn(historical_copy("read_original"), html)

    def test_19_missing_link_calm(self):
        replay = sample_replay()
        replay["source_intelligence"]["accepted_evidence"][0].pop("url")
        html = render_template("historical_investigation.html", request=object(), historical=build_user_historical_view(replay), not_found=False, copy=dashboard.HISTORICAL_COPY)
        self.assertIn(historical_copy("missing_link"), html)

    def test_20_missing_coverage_omits_breadth_block(self):
        html = render_template("historical_investigation.html", request=object(), historical=build_user_historical_view(sample_replay()), not_found=False, copy=dashboard.HISTORICAL_COPY)
        self.assertNotIn('class="coverage-state"', html)

    def test_21_zero_evidence_is_listed_and_renders_calmly(self):
        replay = sample_replay(evidence_count=0, source_count=0)
        replay["source_intelligence"] = {"accepted_evidence_count": 0, "accepted_evidence": []}
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay=replay)
            self.assertIn(historical_copy("limited_badge"), render_selector())
            _, html = render_investigation(); self.assertIn(historical_copy("zero_evidence_title"), html)

    def test_22_dashboard_entry_point(self):
        self.assertIn("Explore historical narratives", Path("templates/dashboard.html").read_text(encoding="utf-8"))

    def test_23_admin_route_unchanged(self):
        self.assertIn("/admin/replay/{replay_id}/research", {getattr(route, "path", None) for route in dashboard.app.routes})

    def test_24_user_route_performs_no_writes(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            before = (data_dir / "replays" / "replay_2026-07-06_macro.json").read_bytes()
            render_investigation()
            self.assertEqual(before, (data_dir / "replays" / "replay_2026-07-06_macro.json").read_bytes())

    def test_25_user_route_does_not_run_replay(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            with patch.object(dashboard.historical_replay, "run_historical_replay", side_effect=AssertionError):
                render_investigation()

    def test_26_user_route_does_not_run_backfill(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            with patch.object(dashboard.historical_backfill, "run_historical_backfill", side_effect=AssertionError):
                render_investigation()

    def test_27_user_route_does_not_fetch_live(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            with patch("mne.rss_fetch.fetch_headlines_from_rss", side_effect=AssertionError):
                render_investigation()

    def test_28_presentation_dictionary_covers_historical_vocabulary(self):
        self.assertFalse(historical_breadth("MINIMAL")["untranslated"])
        self.assertIn("Federal Reserve", historical_origin("historical_backfill", "fed_fomc"))
        for key in ("coverage_supported", "coverage_incomplete", "coverage_cutoff"):
            self.assertTrue(historical_copy(key))


if __name__ == "__main__":
    unittest.main()
