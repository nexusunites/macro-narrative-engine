import importlib
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne import historical_backfill, historical_backfill_admin, historical_replay


FIXTURE = Path(__file__).parent / "fixtures" / "fed_fomc_historical_2020.html"


@contextmanager
def temporary_mne_data_dir():
    workspace_tmp = Path(".tmp_mne_data")
    workspace_tmp.mkdir(exist_ok=True)
    tmpdir = workspace_tmp / f"historical_backfill_admin_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    old_results_dir = dashboard.RESULTS_DIR
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_backfill.config)
        dashboard.RESULTS_DIR = data_dir / "results"
        try:
            yield data_dir
        finally:
            dashboard.RESULTS_DIR = old_results_dir
            importlib.reload(historical_backfill.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


def fake_get(url, timeout, headers):
    class Response:
        text = FIXTURE.read_text(encoding="utf-8")

        def raise_for_status(self):
            return None

    return Response()


class HistoricalBackfillAdminTests(unittest.TestCase):
    def render_template(self, template_name, **context):
        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            return dashboard.templates.env.get_template(template_name).render(**context)
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

    def render_admin(self, **context):
        defaults = {
            "request": object(),
            "results_dir": "/tmp/results",
            "recent_runs": [],
            "selected_file": None,
            "message": None,
            "view": None,
            "historical_replay_console": dashboard.build_historical_replay_console(),
            "historical_backfill_console": dashboard.build_historical_backfill_console(),
        }
        defaults.update(context)
        return self.render_template("admin.html", **defaults)

    def run_backfill(self):
        return dashboard.execute_admin_backfill_form(
            "fed_fomc", "2020-01-01", "2020-01-31", fetch=fake_get
        )

    def test_form_and_allowed_source_choices_render(self):
        with temporary_mne_data_dir():
            context = dashboard.build_template_context(
                object(), None, meaningful_default=False
            )
            html = self.render_admin(**context)
        self.assertIn('action="/admin/historical-backfill', html)
        self.assertIn('name="source"', html)
        self.assertIn('name="start_date"', html)
        self.assertIn('name="end_date"', html)
        for source in historical_backfill.SUPPORTED_SOURCES:
            self.assertIn(f'<option value="{source}"', html)

    def test_invalid_source_is_calm_and_does_not_fetch(self):
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            result = dashboard.execute_admin_backfill_form(
                "not_a_real_source", "2020-01-01", "2020-01-31"
            )
        self.assertEqual(result["error_code"], "unsupported_source")

    def test_invalid_date_range_is_calm_and_does_not_fetch(self):
        with patch("requests.get", side_effect=AssertionError("network fetch called")):
            result = dashboard.execute_admin_backfill_form(
                "fed_fomc", "2020-02-01", "2020-01-01"
            )
        self.assertEqual(result["error_code"], "invalid_date_range")

    def test_valid_trigger_persists_manifest_and_evidence(self):
        with temporary_mne_data_dir() as data_dir:
            with patch.object(
                historical_backfill,
                "run_historical_backfill",
                wraps=historical_backfill.run_historical_backfill,
            ) as runner:
                result = self.run_backfill()
            output = data_dir / "historical_evidence" / result["backfill_id"]
            self.assertTrue((output / "manifest.json").exists())
            self.assertTrue((output / "evidence.json").exists())
            runner.assert_called_once()

    def test_result_summary_renders_with_safe_relative_path(self):
        with temporary_mne_data_dir() as data_dir:
            result = self.run_backfill()
            summary = historical_backfill_admin.load_backfill_summary_by_id(
                result["backfill_id"]
            )
            html = self.render_admin(
                historical_backfill_console=dashboard.build_historical_backfill_console(
                    result=summary
                )
            )
            self.assertIn(result["backfill_id"], html)
            for value in ("fed_fomc", "Federal Reserve", "Central Bank Communications"):
                self.assertIn(value, html)
            self.assertIn("Records Found", html)
            self.assertIn("Evidence Count", html)
            self.assertIn("Replay Ready", html)
            self.assertIn("Warnings", html)
            self.assertIn("Limitations", html)
            self.assertIn(f"historical_evidence/{result['backfill_id']}/", html)
            self.assertNotIn(str(data_dir.resolve()), html)

    def test_recent_backfills_are_newest_first_and_bounded(self):
        with temporary_mne_data_dir():
            first = self.run_backfill()["backfill_id"]
            first_manifest = historical_backfill.backfill_output_dir(first) / "manifest.json"
            os.utime(first_manifest, (1, 1))
            second = dashboard.execute_admin_backfill_form(
                "fed_fomc", "2020-02-01", "2020-02-29", fetch=fake_get
            )["backfill_id"]
            rows = historical_backfill_admin.list_recent_backfill_summaries(limit=2)
            limited = historical_backfill_admin.list_recent_backfill_summaries(limit=1)
            html = self.render_admin(
                historical_backfill_console=dashboard.build_historical_backfill_console()
            )
        self.assertEqual([row["backfill_id"] for row in rows], [second, first])
        self.assertEqual(len(limited), 1)
        self.assertIn(first, html)
        self.assertIn(second, html)

    def test_user_dashboard_does_not_expose_backfill_ui(self):
        html = self.render_template(
            "dashboard.html",
            request=object(),
            message="No results",
            results_dir="/tmp/results",
            recent_runs=[],
            selected_file=None,
            view=None,
            notice=None,
        )
        self.assertNotIn("Historical Backfill", html)
        self.assertNotIn('action="/admin/historical-backfill', html)

    def test_research_does_not_expose_backfill_ui(self):
        html = self.render_template(
            "research_selector.html",
            request=object(),
            message=None,
            notice=None,
            results_dir="/tmp/results",
            selected_file=None,
            selector=[],
        )
        self.assertNotIn("Historical Backfill", html)
        self.assertNotIn('action="/admin/historical-backfill', html)

    def test_trigger_writes_neither_live_results_nor_replays_and_runs_no_replay(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            replay_dir = data_dir / "replays"
            results_dir.mkdir(parents=True)
            replay_dir.mkdir(parents=True)
            with patch.object(historical_replay, "run_historical_replay") as replay:
                self.run_backfill()
            self.assertEqual(list(results_dir.iterdir()), [])
            self.assertEqual(list(replay_dir.iterdir()), [])
            replay.assert_not_called()

    def test_lookup_rejects_unsafe_backfill_id(self):
        with temporary_mne_data_dir():
            with self.assertRaises(ValueError):
                historical_backfill_admin.load_backfill_summary_by_id("../../results")


if __name__ == "__main__":
    unittest.main()
