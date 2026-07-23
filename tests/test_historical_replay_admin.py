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


def backfill_evidence(
    evidence_id,
    title,
    published_at,
    backfill_id,
    source_id="fed_fomc",
    provider="Federal Reserve",
    accepted=True,
):
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_name": provider,
        "evidence_type": "Headline",
        "timestamp": published_at,
        "title": title,
        "summary": None,
        "url": f"https://example.com/{evidence_id}",
        "metadata": {
            "evidence_origin": "HISTORICAL_BACKFILL",
            "backfill_id": backfill_id,
            "connector_source_id": source_id,
            "raw_id": evidence_id,
            "retrieval_timestamp": "2020-04-01T00:00:00Z",
            "usage_storage_rights": "NORMALIZED_EVIDENCE",
            "provider": provider,
            "category": "Central Bank Communications",
            "source_type": "official_central_bank_statement",
        },
        "accepted": accepted,
        "rejection_reason": None,
        "freshness_state": "UNKNOWN",
        "freshness_age_minutes": None,
        "freshness_checked_at": None,
    }


def backfill_manifest(
    backfill_id,
    source_id="fed_fomc",
    provider="Federal Reserve",
    evidence_count=1,
    replay_ready=True,
    start="2020-03-01",
    end="2020-03-31",
):
    return {
        "backfill_id": backfill_id,
        "source_id": source_id,
        "provider": provider,
        "category": "Central Bank Communications",
        "requested_start_date": start,
        "requested_end_date": end,
        "records_found": evidence_count,
        "evidence_count": evidence_count,
        "replay_ready": replay_ready,
        "status": "COMPLETE",
        "generated_at": "2020-04-01T00:00:00Z",
    }


def write_backfill(data_dir, backfill_id, evidence_payload, manifest=None):
    backfill_dir = data_dir / "historical_evidence" / backfill_id
    backfill_dir.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        manifest = backfill_manifest(backfill_id)
    (backfill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (backfill_dir / "evidence.json").write_text(json.dumps(evidence_payload), encoding="utf-8")
    return backfill_dir


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
        self.assertIn('action="/admin/historical-replay', html)
        self.assertIn("Replay uses persisted evidence only.", html)
        self.assertIn("No live source fetching occurs.", html)

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
                result = dashboard.execute_admin_replay_form("2026-07-06", "macro")

        self.assertEqual(result["replay_id"], "replay_2026-07-06_macro")
        # No-selection path now threads an (empty) backfill_ids list through to the
        # engine; behaviorally identical since the engine normalizes [] -> ().
        build.assert_called_once_with("2026-07-06", mode="macro", backfill_ids=[])
        run.assert_called_once_with(request)
        persist.assert_called_once_with(output)

    def test_replay_output_is_displayed(self):
        output = replay_output(
            replay_metadata={"warnings": ["Only 2 evidence objects were available at this cutoff."]}
        )
        result = dashboard.build_replay_result_view(output, Path("/tmp/replays/replay_2026-07-06_macro.json"))
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )

        self.assertIn("Historical Replay — 2026-07-06", html)
        self.assertIn("replay_2026-07-06_macro", html)
        self.assertIn("2026-07-06T23:59:59.999999Z", html)
        self.assertIn("AI Infrastructure", html)
        self.assertIn("Only 2 evidence objects were available at this cutoff.", html)
        self.assertIn("replays/replay_2026-07-06_macro.json", html)
        self.assertNotIn("/tmp/replays/replay_2026-07-06_macro.json", html)

    def test_invalid_date_is_calm_and_does_not_attempt_replay(self):
        with temporary_mne_data_dir():
            with patch.object(dashboard.historical_replay, "run_historical_replay") as run:
                result = dashboard.execute_admin_replay_form("July 6", "macro")

        self.assertEqual(result["error"], "The selected replay date could not be processed.")
        self.assertEqual(result["error_code"], "invalid_date")
        run.assert_not_called()

    def test_missing_date_is_calm_and_does_not_attempt_replay(self):
        with temporary_mne_data_dir():
            with patch.object(dashboard.historical_replay, "run_historical_replay") as run:
                result = dashboard.execute_admin_replay_form("", "macro")

        self.assertEqual(result["error"], "Enter a valid replay date.")
        self.assertEqual(result["error_code"], "invalid_date")
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
        result = dashboard.build_replay_result_view(output, Path("/tmp/replays/replay_2026-07-06_macro.json"))
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

            result = dashboard.execute_admin_replay_form("2026-07-06", "macro")
            context = dashboard.build_template_context(
                request=object(),
                run=None,
                meaningful_default=False,
                replay_id=result["replay_id"],
            )
            html = self.render_context(context)

            after = directory_digest(results_dir)
            replay_path = data_dir / "replays" / "replay_2026-07-06_macro.json"
            replay_exists = replay_path.exists()

        self.assertEqual(before, after)
        self.assertTrue(replay_exists)
        self.assertIn("replays/replay_2026-07-06_macro.json", html)
        self.assertNotIn(str(replay_path), html)

    def test_get_replay_summary_does_not_rerun_replay_on_refresh(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            replay_dir.mkdir(parents=True)
            replay_path = replay_dir / "replay_2026-07-06_macro.json"
            replay_path.write_text(json.dumps(replay_output()), encoding="utf-8")

            with patch.object(dashboard.historical_replay, "run_historical_replay") as run:
                context = dashboard.build_template_context(
                    request=object(),
                    run=None,
                    meaningful_default=False,
                    replay_id="replay_2026-07-06_macro",
                )
                html = self.render_context(context)

        self.assertIn("Historical Replay — 2026-07-06", html)
        run.assert_not_called()

    def test_replay_artifacts_do_not_appear_in_live_result_files(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            replay_dir = data_dir / "replays"
            results_dir.mkdir(parents=True)
            replay_dir.mkdir(parents=True)
            live_path = write_run(results_dir, "2026-07-06_100000", [])
            (replay_dir / "replay_2026-07-06_macro.json").write_text(
                json.dumps(replay_output()),
                encoding="utf-8",
            )

            files = dashboard.list_result_files()

        self.assertEqual(files, [live_path])

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
        self.assertNotIn('name="backfill_id"', html)

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
        self.assertNotIn('name="backfill_id"', html)

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
                result = dashboard.execute_admin_replay_form("2026-07-06", "macro")
                context = dashboard.build_template_context(
                    request=object(),
                    run=None,
                    meaningful_default=False,
                    replay_id=result["replay_id"],
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
                result = dashboard.execute_admin_replay_form("2026-07-06", "macro")
                context = dashboard.build_template_context(
                    request=object(),
                    run=None,
                    meaningful_default=False,
                    replay_id=result["replay_id"],
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
        self.assertIn("could not be read", listing["files"][0]["error"])

    def test_recent_replay_list_is_bounded_and_sorted_newest_first(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            replay_dir.mkdir(parents=True)
            for index in range(12):
                day = f"2026-07-{index + 1:02d}"
                path = replay_dir / f"replay_{day}_macro.json"
                path.write_text(json.dumps(replay_output(replay_id=path.stem, replay_date=day)), encoding="utf-8")

            listing = dashboard.list_recent_replay_files(limit=10)

        self.assertEqual(len(listing["files"]), 10)
        self.assertEqual(listing["files"][0]["replay_date"], "2026-07-12")

    def test_invalid_replay_identifier_is_rejected_calmly(self):
        with temporary_mne_data_dir():
            context = dashboard.build_template_context(
                request=object(),
                run=None,
                meaningful_default=False,
                replay_id="../secrets",
            )
            html = self.render_context(context)

        self.assertIn("The selected replay summary could not be found.", html)
        self.assertNotIn("Traceback", html)


class AdminReplayMultiSelectTests(unittest.TestCase):
    FED_ID = "backfill_2020-03-01_2020-03-31_macro_fed_fomc"
    BLS_ID = "backfill_2020-03-01_2020-03-31_macro_bls_cpi"
    REPLAY_DATE = "2020-03-31"
    REPLAY_ID = "replay_2020-03-31_macro"

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

    def _read_persisted_replay(self, data_dir, replay_id=None):
        replay_id = replay_id or self.REPLAY_ID
        path = data_dir / "replays" / f"{replay_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_fed(self, data_dir, evidence_ids=("f1",)):
        write_backfill(
            data_dir,
            self.FED_ID,
            [
                backfill_evidence(
                    eid, "FOMC statement", "2020-03-15T19:00:00Z", backfill_id=self.FED_ID
                )
                for eid in evidence_ids
            ],
        )

    def _write_bls(self, data_dir, evidence_ids=("c1",)):
        write_backfill(
            data_dir,
            self.BLS_ID,
            [
                backfill_evidence(
                    eid,
                    "CPI report",
                    "2020-03-11T13:30:00Z",
                    backfill_id=self.BLS_ID,
                    source_id="bls_cpi",
                    provider="BLS",
                )
                for eid in evidence_ids
            ],
            manifest=backfill_manifest(self.BLS_ID, source_id="bls_cpi", provider="BLS"),
        )

    # 1. Replay form renders backfill choices.
    def test_replay_form_renders_backfill_choices(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            console = dashboard.build_historical_replay_console(
                backfill_choices=dashboard.historical_backfill_admin.list_recent_backfill_summaries()
            )
            html = self.render_admin_template(historical_replay_console=console)

        self.assertIn('name="backfill_id"', html)
        self.assertIn(self.FED_ID, html)

    # 2. Choices come from valid backfill manifests only.
    def test_malformed_manifest_is_not_offered_as_choice(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            broken_dir = data_dir / "historical_evidence" / self.BLS_ID
            broken_dir.mkdir(parents=True)
            (broken_dir / "manifest.json").write_text("{not json", encoding="utf-8")
            (broken_dir / "evidence.json").write_text("[]", encoding="utf-8")

            choices = dashboard.historical_backfill_admin.list_recent_backfill_summaries()
            console = dashboard.build_historical_replay_console(backfill_choices=choices)
            html = self.render_admin_template(historical_replay_console=console)

        self.assertIn(self.FED_ID, html)
        self.assertNotIn(self.BLS_ID, html)

    # 3. Replay-ready vs non-ready states render honestly.
    def test_replay_ready_and_non_ready_states_render(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            write_backfill(
                data_dir,
                self.BLS_ID,
                [
                    backfill_evidence(
                        "c1", "CPI report", "2020-03-11T13:30:00Z",
                        backfill_id=self.BLS_ID, source_id="bls_cpi", provider="BLS",
                    )
                ],
                manifest=backfill_manifest(
                    self.BLS_ID, source_id="bls_cpi", provider="BLS", replay_ready=False
                ),
            )
            choices = dashboard.historical_backfill_admin.list_recent_backfill_summaries()
            console = dashboard.build_historical_replay_console(backfill_choices=choices)
            html = self.render_admin_template(historical_replay_console=console)

        # The non-ready backfill's checkbox is disabled and labelled.
        self.assertIn("(not replay-ready)", html)
        non_ready = html.split(self.BLS_ID)[1].split("</li>")[0]
        self.assertIn("disabled", non_ready)
        # The ready backfill's checkbox is not disabled.
        ready = html.split(self.FED_ID)[0].rsplit("<li", 1)[1]
        self.assertNotIn("disabled", ready)

    # 4. No arbitrary path/ID values accepted.
    def test_path_traversal_id_is_rejected_without_running_replay(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            before = directory_digest(replay_dir)
            with patch.object(dashboard, "run_admin_historical_replay") as run:
                result = dashboard.execute_admin_replay_form(
                    self.REPLAY_DATE, "macro", backfill_ids=["../../etc/passwd"]
                )
            after = directory_digest(replay_dir)

        self.assertEqual(result["error_code"], "invalid_backfill_selection")
        run.assert_not_called()
        self.assertEqual(before, after)

    # 5. One selected backfill reaches replay correctly.
    def test_single_selected_backfill_reaches_replay(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID]
            )
            persisted = self._read_persisted_replay(data_dir, result["replay_id"])

        self.assertEqual(result["replay_id"], self.REPLAY_ID)
        self.assertIn(self.FED_ID, persisted["replay_metadata"]["backfill_ids_used"])

    # 6. Multiple selected backfills reach replay in order.
    def test_multiple_selected_backfills_preserve_order(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            self._write_bls(data_dir)
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=[self.BLS_ID, self.FED_ID]
            )
            persisted = self._read_persisted_replay(data_dir, result["replay_id"])

        self.assertEqual(
            persisted["replay_metadata"]["backfill_ids_requested"],
            [self.BLS_ID, self.FED_ID],
        )

    # 7. Duplicate selections are deduped.
    def test_duplicate_selections_are_deduped(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            self._write_bls(data_dir)
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE,
                "macro",
                backfill_ids=[self.FED_ID, self.FED_ID, self.BLS_ID],
            )
            persisted = self._read_persisted_replay(data_dir, result["replay_id"])

        requested = persisted["replay_metadata"]["backfill_ids_requested"]
        self.assertEqual(requested, [self.FED_ID, self.BLS_ID])
        self.assertEqual(len(requested), len(set(requested)))

    # 8. No selection preserves existing replay behavior.
    def test_no_selection_matches_two_arg_behavior(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2020-03-15_100000",
                [evidence("e1", "AI data center investment", "2020-03-15T09:00:00Z")],
            )
            baseline = dashboard.execute_admin_replay_form(self.REPLAY_DATE, "macro")
            baseline_artifact = self._read_persisted_replay(data_dir, baseline["replay_id"])

        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2020-03-15_100000",
                [evidence("e1", "AI data center investment", "2020-03-15T09:00:00Z")],
            )
            explicit = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=None
            )
            explicit_artifact = self._read_persisted_replay(data_dir, explicit["replay_id"])

        self.assertEqual(set(baseline_artifact.keys()), set(explicit_artifact.keys()))
        self.assertEqual(
            baseline_artifact["replay_metadata"]["backfill_ids_requested"], []
        )
        self.assertEqual(
            explicit_artifact["replay_metadata"]["backfill_ids_requested"], []
        )
        self.assertFalse(
            baseline_artifact["replay_metadata"]["backfilled_evidence_included"]
        )
        self.assertFalse(
            explicit_artifact["replay_metadata"]["backfilled_evidence_included"]
        )

    # 9. Missing selected backfill fails calmly.
    def test_missing_backfill_fails_calmly(self):
        missing = "backfill_2020-03-01_2020-03-31_macro_missing_source"
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            before = directory_digest(replay_dir)
            with patch.object(dashboard, "run_admin_historical_replay") as run:
                result = dashboard.execute_admin_replay_form(
                    self.REPLAY_DATE, "macro", backfill_ids=[missing]
                )
            after = directory_digest(replay_dir)

        self.assertEqual(result["error_code"], "invalid_backfill_selection")
        self.assertIn(missing, result["error"])
        run.assert_not_called()
        self.assertEqual(before, after)

    # 10. Malformed selected backfill fails calmly (2+ ids, one corrupt evidence.json).
    def test_malformed_backfill_in_multi_id_fails_calmly(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            bad_dir = data_dir / "historical_evidence" / self.BLS_ID
            bad_dir.mkdir(parents=True)
            (bad_dir / "manifest.json").write_text(
                json.dumps(backfill_manifest(self.BLS_ID, source_id="bls_cpi", provider="BLS")),
                encoding="utf-8",
            )
            (bad_dir / "evidence.json").write_text("{not valid json", encoding="utf-8")

            replay_dir = data_dir / "replays"
            before = directory_digest(replay_dir)
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID, self.BLS_ID]
            )
            after = directory_digest(replay_dir)

        # Passes existence validation, fails inside the engine's multi-id path.
        self.assertEqual(result["error_code"], "failed")
        self.assertIn(self.BLS_ID, result["error"])
        self.assertEqual(before, after)

    # 11. Multi-backfill failure produces no replay artifact.
    def test_multi_backfill_failure_writes_no_artifact(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            # Second backfill validates (manifest loads) but has corrupt evidence,
            # so the engine's multi-id load path raises HistoricalReplayError.
            bad_dir = data_dir / "historical_evidence" / self.BLS_ID
            bad_dir.mkdir(parents=True)
            (bad_dir / "manifest.json").write_text(
                json.dumps(backfill_manifest(self.BLS_ID, source_id="bls_cpi", provider="BLS")),
                encoding="utf-8",
            )
            (bad_dir / "evidence.json").write_text("{not valid json", encoding="utf-8")

            replay_dir = data_dir / "replays"
            before = sorted(
                str(p.relative_to(data_dir)) for p in replay_dir.rglob("*")
            ) if replay_dir.exists() else []
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID, self.BLS_ID]
            )
            after = sorted(
                str(p.relative_to(data_dir)) for p in replay_dir.rglob("*")
            ) if replay_dir.exists() else []

        self.assertNotIn("replay_id", result)
        self.assertEqual(before, after)

    # 12. Replay summary displays requested and used IDs.
    def test_replay_summary_displays_requested_and_used_ids(self):
        output = replay_output(
            replay_id=self.REPLAY_ID,
            replay_date=self.REPLAY_DATE,
            replay_metadata={
                "warnings": [],
                "backfill_ids_requested": [self.FED_ID, self.BLS_ID],
                "backfill_ids_used": [self.FED_ID, self.BLS_ID],
                "backfilled_evidence_counts_by_id": {self.FED_ID: 1, self.BLS_ID: 2},
                "live_evidence_count": 3,
                "backfilled_evidence_count": 3,
                "total_evidence_count": 6,
                "evidence_sources_used": ["live_persisted", "historical_backfill"],
            },
        )
        result = dashboard.build_replay_result_view(
            output, Path(f"/tmp/replays/{self.REPLAY_ID}.json")
        )
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )

        self.assertIn("Backfills Used", html)
        self.assertIn(self.FED_ID, html)
        self.assertIn(self.BLS_ID, html)

    # 13. Per-backfill evidence counts render.
    def test_per_backfill_evidence_counts_render(self):
        output = replay_output(
            replay_id=self.REPLAY_ID,
            replay_date=self.REPLAY_DATE,
            replay_metadata={
                "warnings": [],
                "backfill_ids_requested": [self.FED_ID, self.BLS_ID],
                "backfill_ids_used": [self.FED_ID, self.BLS_ID],
                "backfilled_evidence_counts_by_id": {self.FED_ID: 1, self.BLS_ID: 2},
                "live_evidence_count": 0,
                "backfilled_evidence_count": 3,
                "total_evidence_count": 3,
                "evidence_sources_used": ["historical_backfill"],
            },
        )
        result = dashboard.build_replay_result_view(
            output, Path(f"/tmp/replays/{self.REPLAY_ID}.json")
        )
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )

        self.assertIn(f"{self.FED_ID}</code>: 1 evidence", html)
        self.assertIn(f"{self.BLS_ID}</code>: 2 evidence", html)

    # 14. Live/backfilled/total counts reconcile (real engine output).
    def test_live_backfilled_total_counts_reconcile(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2020-03-15_100000",
                [evidence("live1", "AI data center investment", "2020-03-15T09:00:00Z")],
            )
            self._write_fed(data_dir)
            result = dashboard.execute_admin_replay_form(
                self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID]
            )
            metadata = self._read_persisted_replay(data_dir, result["replay_id"])[
                "replay_metadata"
            ]

        self.assertIsNotNone(metadata["live_evidence_count"])
        self.assertIsNotNone(metadata["backfilled_evidence_count"])
        self.assertEqual(
            metadata["total_evidence_count"],
            metadata["live_evidence_count"] + metadata["backfilled_evidence_count"],
        )
        self.assertGreaterEqual(metadata["live_evidence_count"], 1)
        self.assertGreaterEqual(metadata["backfilled_evidence_count"], 1)

    # 15. No backfill connector is executed during replay.
    def test_no_backfill_connector_is_executed(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            with (
                patch.object(
                    dashboard.historical_backfill,
                    "run_historical_backfill",
                    side_effect=AssertionError("backfill connector invoked"),
                ),
                patch.object(
                    dashboard.historical_backfill,
                    "run_and_persist_historical_backfill",
                    side_effect=AssertionError("backfill connector invoked"),
                ),
            ):
                result = dashboard.execute_admin_replay_form(
                    self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID]
                )

        self.assertEqual(result["replay_id"], self.REPLAY_ID)

    # 16. No RSS/live fetch occurs during replay.
    def test_no_live_rss_fetch_during_replay(self):
        with temporary_mne_data_dir() as data_dir:
            self._write_fed(data_dir)
            with patch(
                "mne.rss_fetch.fetch_headlines_from_rss",
                side_effect=AssertionError("network fetch called"),
            ):
                result = dashboard.execute_admin_replay_form(
                    self.REPLAY_DATE, "macro", backfill_ids=[self.FED_ID]
                )

        self.assertEqual(result["replay_id"], self.REPLAY_ID)

    # 17. User dashboard exposes no replay backfill controls.
    def test_user_dashboard_has_no_backfill_controls(self):
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
        self.assertNotIn('name="backfill_id"', html)

    # 18. Standard /research exposes no replay backfill controls.
    def test_research_selector_has_no_backfill_controls(self):
        html = self.render_template(
            "research_selector.html",
            request=object(),
            message=None,
            notice=None,
            results_dir="/tmp/results",
            selected_file=None,
            selector=[],
        )
        self.assertNotIn('name="backfill_id"', html)

    # No-backfill result hides the backfill summary block entirely.
    def test_no_backfill_result_hides_backfill_summary(self):
        output = replay_output(replay_metadata={"warnings": []})
        result = dashboard.build_replay_result_view(
            output, Path("/tmp/replays/replay_2026-07-06_macro.json")
        )
        html = self.render_admin_template(
            historical_replay_console=dashboard.build_historical_replay_console(result=result)
        )
        self.assertNotIn("Backfills Used", html)
        self.assertNotIn("replay-backfill-summary", html)


if __name__ == "__main__":
    unittest.main()
