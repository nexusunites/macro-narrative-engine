import hashlib
import importlib
import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import dashboard
from mne import historical_replay


def evidence(evidence_id, title, published_at, source_id="cnbc-top-news"):
    return {
        "evidence_id": evidence_id,
        "title": title,
        "source_id": source_id,
        "source_name": source_id,
        "evidence_type": "Headline",
        "published_at": published_at,
        "timestamp": published_at,
        "url": f"https://example.com/{evidence_id}",
        "accepted": True,
    }


def write_run(results_dir, stamp, accepted_evidence):
    path = results_dir / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "timestamp": stamp,
                "source_intelligence": {
                    "accepted_evidence": accepted_evidence,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def directory_digest(path):
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


@contextmanager
def temporary_mne_data_dir():
    workspace_tmp = Path(".tmp_mne_data")
    workspace_tmp.mkdir(exist_ok=True)
    tmpdir = workspace_tmp / f"historical_replay_admin_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    old_results_dir = dashboard.RESULTS_DIR
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_replay.config)
        dashboard.RESULTS_DIR = data_dir / "results"
        try:
            yield data_dir
        finally:
            dashboard.RESULTS_DIR = old_results_dir
            importlib.reload(historical_replay.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


def replay_output(**overrides):
    output = {
        "replay_id": "replay_2026-07-06_macro",
        "replay_date": "2026-07-06",
        "generated_at": "2026-07-10T12:00:00Z",
        "evidence_cutoff": "2026-07-06T23:59:59.999999Z",
        "evidence_count": 2,
        "source_count": 1,
        "theme_scores": {"ai": 2, "rates": 1},
        "group_scores": {"AI Infrastructure": 2},
        "dominant_theme": "ai",
        "dominant_group": "AI Infrastructure",
        "replay_metadata": {"warnings": []},
    }
    output.update(overrides)
    return output


class HistoricalReplayAdminTests(unittest.TestCase):
    def render_admin_template(self, **context):
        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            defaults = {
                "request": object(),
                "results_dir": "/tmp/results",
                "recent_runs": [],
                "selected_file": None,
                "message": None,
                "view": None,
                "historical_replay_console": dashboard.build_historical_replay_console(),
            }
            defaults.update(context)
            return dashboard.templates.env.get_template("admin.html").render(**defaults)
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

    def render_context(self, context):
        return self.render_admin_template(**context)

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

    def test_admin_replay_form_renders_on_admin(self):
        with temporary_mne_data_dir():
            context = dashboard.build_template_context(
                request=object(),
                run=None,
                meaningful_default=False,
            )
            html = self.render_context(context)

        self.assertIn("Admin Replay Console", html)
        self.assertIn('name="replay_date"', html)
        self.assertIn('action="/admin/replay', html)

    def test_valid_replay_date_invokes_foundation_functions(self):
        request = Mock(name="ReplayRequest")
        output = replay_output()
        with temporary_mne_data_dir() as data_dir:
            output_path = data_dir / "replays" / "replay_2026-07-06_macro.json"
            with (
                patch.object(dashboard.historical_replay, "build_replay_request", return_value=request) as build,
                patch.object(dashboard.historical_replay, "run_historical_replay", return_value=output) as run,
                patch.object(dashboard.historical_replay, "persist_historical_replay", return_value=output_path) as persist,
            ):
                context = dashboard.build_admin_replay_context(
                    request=object(),
                    run=None,
                    replay_date="2026-07-06",
                    mode="macro",
                )
                html = self.render_context(context)

        self.assertIn("Historical Replay — 2026-07-06", html)
        build.assert_called_once_with("2026-07-06", mode="macro")
        run.assert_called_once_with(request)
        persist.assert_called_once_with(output)

    def test_replay_output_is_displayed(self):
        output = replay_output(
            replay_metadata={"warnings": ["Only 2 evidence objects were available at this cutoff."]}
        )
        result = dashboard.build_replay_result_view(output, "/tmp/replays/replay_2026-07-06_macro.json")
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )

        self.assertIn("Historical Replay — 2026-07-06", html)
        self.assertIn("replay_2026-07-06_macro", html)
        self.assertIn("2026-07-06T23:59:59.999999Z", html)
        self.assertIn("AI Infrastructure", html)
        self.assertIn("Only 2 evidence objects were available at this cutoff.", html)
        self.assertIn("/tmp/replays/replay_2026-07-06_macro.json", html)

    def test_invalid_date_is_calm_and_does_not_attempt_replay(self):
        with temporary_mne_data_dir():
            with patch.object(dashboard.historical_replay, "run_historical_replay") as run:
                context = dashboard.build_admin_replay_context(
                    request=object(),
                    run=None,
                    replay_date="July 6",
                    mode="macro",
                )
                html = self.render_context(context)

        self.assertIn("Enter a valid date in YYYY-MM-DD format.", html)
        run.assert_not_called()

    def test_no_evidence_replay_shows_warning_result(self):
        output = replay_output(
            evidence_count=0,
            source_count=0,
            theme_scores={"ai": 0},
            group_scores={},
            dominant_theme=None,
            dominant_group=None,
            replay_metadata={
                "warnings": ["No accepted evidence objects were available at this cutoff."]
            },
        )
        result = dashboard.build_replay_result_view(output, "/tmp/replays/replay_2026-07-06_macro.json")
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )

        self.assertIn("Evidence Count</th><td>0", html)
        self.assertIn("No accepted evidence objects were available at this cutoff.", html)
        self.assertNotIn("Traceback", html)

    def test_console_trigger_persists_under_replays_without_modifying_live_results(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2026-07-06_100000",
                [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
            )
            before = directory_digest(results_dir)

            context = dashboard.build_admin_replay_context(
                request=object(),
                run=None,
                replay_date="2026-07-06",
                mode="macro",
            )
            html = self.render_context(context)

            after = directory_digest(results_dir)
            replay_path = data_dir / "replays" / "replay_2026-07-06_macro.json"
            replay_exists = replay_path.exists()

        self.assertEqual(before, after)
        self.assertTrue(replay_exists)
        self.assertIn(str(replay_path), html)

    def test_user_dashboard_does_not_show_replay_controls(self):
        html = self.render_template(
            "dashboard.html",
            request=object(),
            message="No MNE result files found. Run main.py first.",
            results_dir="/tmp/results",
            recent_runs=[],
            selected_file=None,
            view=None,
            notice=None,
        )

        self.assertNotIn("Admin Replay Console", html)
        self.assertNotIn('name="replay_date"', html)

    def test_research_workspace_does_not_show_replay_controls(self):
        html = self.render_template(
            "research_selector.html",
            request=object(),
            message=None,
            notice=None,
            results_dir="/tmp/results",
            selected_file=None,
            selector=[],
        )

        self.assertNotIn("Admin Replay Console", html)
        self.assertNotIn('name="replay_date"', html)

    def test_console_trigger_does_not_call_live_rss_fetch(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2026-07-06_100000",
                [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
            )
            with patch(
                "mne.rss_fetch.fetch_headlines_from_rss",
                side_effect=AssertionError("network fetch called"),
            ):
                context = dashboard.build_admin_replay_context(
                    request=object(),
                    run=None,
                    replay_date="2026-07-06",
                    mode="macro",
                )
                html = self.render_context(context)

        self.assertIn("Historical Replay — 2026-07-06", html)

    def test_console_does_not_change_foundation_scoring_output(self):
        accepted = [
            evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z"),
            evidence("e2", "Nvidia AI chips demand", "2026-07-06T09:05:00Z"),
            evidence("e3", "Fed rate cut and interest rates", "2026-07-06T09:10:00Z"),
        ]
        records = [
            {
                "run": {
                    "timestamp": "2026-07-06_100000",
                    "source_intelligence": {"accepted_evidence": accepted},
                }
            }
        ]
        request = historical_replay.build_replay_request("2026-07-06")
        expected = historical_replay.run_historical_replay(
            request,
            historical_records=records,
            generated_at="2026-07-10T12:00:00Z",
        )

        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(results_dir, "2026-07-06_100000", accepted)
            with patch.object(
                dashboard.historical_replay,
                "run_historical_replay",
                return_value=expected,
            ):
                context = dashboard.build_admin_replay_context(
                    request=object(),
                    run=None,
                    replay_date="2026-07-06",
                    mode="macro",
                )
                html = self.render_context(context)
            persisted = json.loads(
                (data_dir / "replays" / "replay_2026-07-06_macro.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn("Historical Replay — 2026-07-06", html)
        self.assertEqual(
            json.dumps(persisted, sort_keys=True),
            json.dumps(expected, sort_keys=True),
        )

    def test_malformed_replay_file_is_listed_as_unreadable(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            replay_dir.mkdir(parents=True)
            (replay_dir / "broken.json").write_text("{not json", encoding="utf-8")

            listing = dashboard.list_recent_replay_files()

        self.assertEqual(listing["files"][0]["filename"], "broken.json")
        self.assertTrue(listing["files"][0]["unreadable"])
        self.assertIn("Unreadable replay file", listing["files"][0]["error"])


if __name__ == "__main__":
    unittest.main()
