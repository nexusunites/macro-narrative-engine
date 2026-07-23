import asyncio
import hashlib
import importlib
import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, call, patch

import dashboard
from mne import historical_backfill, historical_replay, historical_workflow


@contextmanager
def temporary_mne_data_dir():
    workspace_tmp = Path(".tmp_mne_data")
    workspace_tmp.mkdir(exist_ok=True)
    tmpdir = workspace_tmp / f"historical_workflow_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    old_results_dir = dashboard.RESULTS_DIR
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_workflow.config)
        dashboard.RESULTS_DIR = data_dir / "results"
        try:
            yield data_dir
        finally:
            dashboard.RESULTS_DIR = old_results_dir
            importlib.reload(historical_workflow.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


def manifest_for(source, ready=True):
    backfill_id = f"backfill_2020-01-01_2020-01-07_macro_{source}"
    return {
        "backfill_id": backfill_id,
        "requested_start_date": "2020-01-01",
        "requested_end_date": "2020-01-07",
        "generated_at": "2020-01-08T00:00:00Z",
        "source_id": source,
        "provider": source,
        "category": "Economic Data",
        "records_found": 1 if ready else 0,
        "evidence_count": 1 if ready else 0,
        "replay_ready": ready,
        "warnings": [] if ready else ["No evidence was found."],
        "limitations": ["Partial historical coverage."],
        "status": "COMPLETE" if ready else "PARTIAL",
    }


def persist_fake_backfill(data_dir, source, ready=True):
    manifest = manifest_for(source, ready)
    output = data_dir / "historical_evidence" / manifest["backfill_id"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    evidence = []
    if ready:
        evidence = [{
            "evidence_id": f"evidence-{source}",
            "source_id": "federal-reserve-press-releases",
            "source_name": source,
            "evidence_type": "Headline",
            "timestamp": "2020-01-06T12:00:00Z",
            "title": f"{source} release",
            "url": f"https://example.com/{source}",
            "metadata": {
                "backfill_id": manifest["backfill_id"],
                "connector_source_id": source,
            },
            "accepted": True,
        }]
    (output / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    return output, {"manifest": manifest}


def workflow_manifest(outcomes, replay_id=None):
    manifest = historical_workflow.build_workflow_manifest(
        "2020-01-07", "2020-01-01", "2020-01-07", "macro",
        [item["source"] for item in outcomes], outcomes,
    )
    manifest["replay_id"] = replay_id
    return manifest


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BodyRequest:
    def __init__(self, body):
        self._body = body.encode()

    async def body(self):
        return self._body


class HistoricalWorkflowTests(unittest.TestCase):
    def render(self, template_name, **context):
        original = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            return dashboard.templates.env.get_template(template_name).render(**context)
        finally:
            if original is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original

    def test_form_renders_supported_sources(self):
        html = self.render(
            "historical_workflow.html",
            **dashboard.build_historical_workflow_context(object()),
        )
        self.assertIn('action="/admin/historical-workflow/run-backfills"', html)
        for source in historical_backfill.SUPPORTED_SOURCES:
            self.assertIn(f'value="{source}"', html)

    def test_unsupported_source_rejected_without_calls_or_manifest(self):
        with temporary_mne_data_dir() as data_dir, patch.object(
            historical_backfill, "run_and_persist_historical_backfill"
        ) as runner:
            result = dashboard.execute_admin_workflow_backfills(
                ["arbitrary"], "2020-01-07"
            )
            self.assertEqual(result["error_code"], "invalid_request")
            runner.assert_not_called()
            self.assertFalse((data_dir / "historical_workflows").exists())

    def test_empty_sources_rejected_without_calls(self):
        with patch.object(historical_backfill, "run_and_persist_historical_backfill") as runner:
            result = dashboard.execute_admin_workflow_backfills([], "2020-01-07")
        self.assertEqual(result["error_code"], "invalid_request")
        runner.assert_not_called()

    def test_invalid_dates_rejected_without_calls(self):
        with patch.object(historical_backfill, "run_and_persist_historical_backfill") as runner:
            result = dashboard.execute_admin_workflow_backfills(
                ["fed_fomc"], "not-a-date", "2020-02-01", "2020-01-01"
            )
        self.assertEqual(result["error_code"], "invalid_request")
        runner.assert_not_called()

    def test_sources_run_in_supported_order_and_only_selected(self):
        with temporary_mne_data_dir() as data_dir:
            runner = Mock(side_effect=lambda source, *args, **kwargs: persist_fake_backfill(data_dir, source))
            with patch.object(historical_backfill, "run_and_persist_historical_backfill", runner):
                result = dashboard.execute_admin_workflow_backfills(
                    ["eia_energy", "fed_fomc"], "2020-01-07", "2020-01-01", "2020-01-07"
                )
            self.assertIn("workflow_id", result)
            self.assertEqual([item.args[0] for item in runner.call_args_list], ["fed_fomc", "eia_energy"])

    def test_complete_empty_failed_manifest_and_confirmation_render(self):
        with temporary_mne_data_dir() as data_dir:
            def run(source, *args, **kwargs):
                if source == "bea_gdp_pce":
                    raise RuntimeError("connector unavailable")
                return persist_fake_backfill(data_dir, source, ready=source == "fed_fomc")
            with patch.object(historical_backfill, "run_and_persist_historical_backfill", side_effect=run):
                result = dashboard.execute_admin_workflow_backfills(
                    ["bea_gdp_pce", "bls_cpi", "fed_fomc"],
                    "2020-01-07", "2020-01-01", "2020-01-07",
                )
            saved = historical_workflow.load_workflow_manifest(result["workflow_id"])
            self.assertEqual(
                [item["status"] for item in saved["source_outcomes"]],
                ["COMPLETE", "EMPTY", "FAILED"],
            )
            html = self.render(
                "historical_workflow.html",
                **dashboard.build_historical_workflow_context(object(), result["workflow_id"]),
            )
            for status in ("COMPLETE", "EMPTY", "FAILED"):
                self.assertIn(status, html)
            self.assertIsNone(saved["replay_id"])

    def test_backfill_phase_never_runs_replay(self):
        with temporary_mne_data_dir() as data_dir, patch.object(
            historical_backfill, "run_and_persist_historical_backfill",
            side_effect=lambda source, *args, **kwargs: persist_fake_backfill(data_dir, source),
        ), patch.object(historical_replay, "run_and_persist_historical_replay") as replay:
            dashboard.execute_admin_workflow_backfills(["fed_fomc"], "2020-01-07")
            replay.assert_not_called()

    def test_confirm_revalidates_deleted_backfill(self):
        with temporary_mne_data_dir() as data_dir:
            _, result = persist_fake_backfill(data_dir, "fed_fomc")
            outcome = dict(source="fed_fomc", status="COMPLETE", replay_ready=True,
                           backfill_id=result["manifest"]["backfill_id"])
            manifest = workflow_manifest([outcome])
            historical_workflow.write_workflow_manifest(manifest)
            shutil.rmtree(data_dir / "historical_evidence" / outcome["backfill_id"])
            with patch.object(historical_replay, "run_and_persist_historical_replay") as replay:
                response = dashboard.execute_admin_workflow_confirmation(
                    manifest["workflow_id"], "run_replay"
                )
            self.assertEqual(response["error_code"], "invalid_backfill_selection")
            replay.assert_not_called()

    def test_confirm_uses_exact_complete_ids_in_manifest_order(self):
        with temporary_mne_data_dir() as data_dir:
            outcomes = []
            for source in ("fed_fomc", "bls_cpi"):
                _, result = persist_fake_backfill(data_dir, source)
                outcomes.append(dict(source=source, status="COMPLETE", replay_ready=True,
                                     backfill_id=result["manifest"]["backfill_id"]))
            outcomes.insert(1, dict(source="bea_gdp_pce", status="FAILED", replay_ready=False,
                                    backfill_id=None))
            manifest = workflow_manifest(outcomes)
            historical_workflow.write_workflow_manifest(manifest)
            replay_output = {"replay_id": "replay_2020-01-07_macro"}
            with patch.object(
                historical_replay, "run_and_persist_historical_replay",
                return_value=(data_dir / "replays/x.json", replay_output),
            ) as replay:
                response = dashboard.execute_admin_workflow_confirmation(
                    manifest["workflow_id"], "run_replay"
                )
            self.assertEqual(response["replay_id"], replay_output["replay_id"])
            self.assertEqual(
                replay.call_args.kwargs["backfill_ids"],
                [outcomes[0]["backfill_id"], outcomes[2]["backfill_id"]],
            )

    def test_duplicate_confirm_is_idempotent(self):
        with temporary_mne_data_dir() as data_dir:
            _, result = persist_fake_backfill(data_dir, "fed_fomc")
            outcome = dict(source="fed_fomc", status="COMPLETE", replay_ready=True,
                           backfill_id=result["manifest"]["backfill_id"])
            manifest = workflow_manifest([outcome])
            historical_workflow.write_workflow_manifest(manifest)
            output = {"replay_id": "replay_2020-01-07_macro"}
            with patch.object(
                historical_replay, "run_and_persist_historical_replay",
                return_value=(data_dir / "replays/replay_2020-01-07_macro.json", output),
            ) as replay:
                first = dashboard.execute_admin_workflow_confirmation(manifest["workflow_id"], "run_replay")
                second = dashboard.execute_admin_workflow_confirmation(manifest["workflow_id"], "run_replay")
            self.assertEqual(first, second)
            replay.assert_called_once()

    def test_get_context_has_no_execution_side_effect(self):
        with temporary_mne_data_dir() as data_dir:
            manifest = workflow_manifest([
                dict(source="fed_fomc", status="FAILED", replay_ready=False, backfill_id=None)
            ])
            historical_workflow.write_workflow_manifest(manifest)
            with patch.object(historical_backfill, "run_and_persist_historical_backfill") as backfill, \
                 patch.object(historical_replay, "run_and_persist_historical_replay") as replay:
                for _ in range(3):
                    dashboard.build_historical_workflow_context(object(), manifest["workflow_id"])
            backfill.assert_not_called()
            replay.assert_not_called()

    def test_workflow_writes_nothing_to_live_results(self):
        with temporary_mne_data_dir() as data_dir, patch.object(
            historical_backfill, "run_and_persist_historical_backfill",
            side_effect=lambda source, *args, **kwargs: persist_fake_backfill(data_dir, source),
        ):
            results = data_dir / "results"
            results.mkdir(parents=True)
            dashboard.execute_admin_workflow_backfills(["fed_fomc"], "2020-01-07")
            self.assertEqual(list(results.iterdir()), [])

    def test_cancel_does_not_mutate_manifest(self):
        with temporary_mne_data_dir():
            manifest = workflow_manifest([
                dict(source="fed_fomc", status="FAILED", replay_ready=False, backfill_id=None)
            ])
            path = historical_workflow.write_workflow_manifest(manifest)
            before = path.read_bytes()
            self.assertEqual(
                dashboard.execute_admin_workflow_confirmation(manifest["workflow_id"], "cancel"),
                {"cancelled": True},
            )
            self.assertEqual(path.read_bytes(), before)

    def test_public_templates_do_not_expose_workflow(self):
        dashboard_html = self.render(
            "dashboard.html", request=object(), message="No results",
            results_dir="/tmp/results", recent_runs=[], selected_file=None,
            view=None, notice=None,
        )
        research_html = self.render(
            "research_selector.html", request=object(), message=None, notice=None,
            results_dir="/tmp/results", selected_file=None, selector=[],
        )
        for html in (dashboard_html, research_html):
            self.assertNotIn("/admin/historical-workflow", html)
            self.assertNotIn("Build Historical Replay", html)

    def test_workflow_id_rejects_arbitrary_paths(self):
        with temporary_mne_data_dir():
            for unsafe in ("../../results", "workflow_2020-01-01_bad/child", "arbitrary"):
                with self.assertRaises(ValueError):
                    historical_workflow.load_workflow_manifest(unsafe)

    def test_run_route_redirects_to_confirmation_not_replay(self):
        with patch.object(
            dashboard, "execute_admin_workflow_backfills",
            return_value={"workflow_id": "workflow_2020-01-07_abcdef123456"},
        ):
            response = asyncio.run(dashboard.admin_historical_workflow_backfills(
                BodyRequest("source=fed_fomc&replay_date=2020-01-07")
            ))
        self.assertEqual(response.status_code, 303)
        self.assertIn("/confirm?workflow_id=", response.headers["location"])
        self.assertNotIn("/admin?replay=", response.headers["location"])

    def test_single_date_defaults_backfill_range(self):
        with temporary_mne_data_dir() as data_dir, patch.object(
            historical_backfill, "run_and_persist_historical_backfill",
            side_effect=lambda source, *args, **kwargs: persist_fake_backfill(data_dir, source),
        ) as runner:
            result = dashboard.execute_admin_workflow_backfills(["fed_fomc"], "2020-01-07")
            saved = historical_workflow.load_workflow_manifest(result["workflow_id"])
        self.assertEqual(saved["requested_start_date"], "2020-01-07")
        self.assertEqual(saved["requested_end_date"], "2020-01-07")
        self.assertEqual(runner.call_args.args[1:3], ("2020-01-07", "2020-01-07"))

    def test_workflow_manifest_namespace_is_distinct(self):
        with temporary_mne_data_dir() as data_dir:
            manifest = workflow_manifest([
                dict(source="fed_fomc", status="FAILED", replay_ready=False, backfill_id=None)
            ])
            path = historical_workflow.write_workflow_manifest(manifest)
            self.assertEqual(
                path.parent.parent.resolve(),
                (data_dir / "historical_workflows").resolve(),
            )
            self.assertFalse((data_dir / "replays").exists())
            self.assertFalse((data_dir / "historical_evidence").exists())

    def test_real_confirmation_preserves_backfill_and_replay_logic(self):
        with temporary_mne_data_dir() as data_dir:
            backfill_dir, result = persist_fake_backfill(data_dir, "fed_fomc")
            backfill_id = result["manifest"]["backfill_id"]
            outcome = dict(
                source="fed_fomc", status="COMPLETE", replay_ready=True,
                backfill_id=backfill_id,
            )
            manifest = workflow_manifest([outcome])
            historical_workflow.write_workflow_manifest(manifest)
            before = {
                path.name: (file_digest(path), path.stat().st_mtime_ns)
                for path in backfill_dir.iterdir()
            }
            replay_dir = data_dir / "replays"
            replay_dir.mkdir(parents=True)
            existing = replay_dir / "replay_2019-01-01_macro.json"
            existing.write_text('{"sentinel": true}', encoding="utf-8")
            existing_before = (file_digest(existing), existing.stat().st_mtime_ns)

            direct_request = historical_replay.build_replay_request(
                "2020-01-07", backfill_ids=[backfill_id]
            )
            direct = historical_replay.run_historical_replay(direct_request)
            response = dashboard.execute_admin_workflow_confirmation(
                manifest["workflow_id"], "run_replay"
            )
            workflow_output = json.loads(
                (replay_dir / f"{response['replay_id']}.json").read_text(encoding="utf-8")
            )

            self.assertTrue(
                workflow_output["source_intelligence"]["coverage_intelligence"]
            )
            for field in (
                "theme_scores", "group_scores", "theme_counts",
                "dominant_theme", "dominant_group", "source_intelligence",
            ):
                self.assertEqual(workflow_output[field], direct[field])
            after = {
                path.name: (file_digest(path), path.stat().st_mtime_ns)
                for path in backfill_dir.iterdir()
            }
            self.assertEqual(after, before)
            self.assertEqual(
                (file_digest(existing), existing.stat().st_mtime_ns),
                existing_before,
            )


if __name__ == "__main__":
    unittest.main()
