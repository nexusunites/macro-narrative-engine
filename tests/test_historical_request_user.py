import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import dashboard
from mne import historical_request
from mne.presentation_language import (
    HISTORICAL_COPY,
    historical_request_category,
    historical_request_outcome,
)


def render(template_name, **context):
    original = dashboard.templates.env.globals.get("url_for")
    dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
    try:
        return dashboard.templates.env.get_template(template_name).render(**context)
    finally:
        if original is None:
            dashboard.templates.env.globals.pop("url_for", None)
        else:
            dashboard.templates.env.globals["url_for"] = original


def outcome(source, status="COMPLETE", count=3):
    return {
        "source": source,
        "status": status,
        "evidence_count": count,
        "replay_ready": status == "COMPLETE",
    }


class BodyRequest:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    async def body(self):
        return self._body


class HistoricalRequestUserTests(unittest.TestCase):
    def test_01_routes_registered(self):
        routes = {getattr(route, "path", None) for route in dashboard.app.routes}
        self.assertIn("/history/request", routes)
        self.assertIn("/history/request/{request_id}", routes)

    def test_02_form_uses_product_categories(self):
        html = render(
            "historical_request.html",
            **dashboard.build_historical_request_form_context(object()),
        )
        for token in historical_request.CATEGORY_ORDER:
            self.assertIn(historical_request_category(token)["label"], html)
            self.assertIn(f'value="{token}"', html)

    def test_03_form_hides_internal_sources(self):
        html = render(
            "historical_request.html",
            **dashboard.build_historical_request_form_context(object()),
        )
        for source in historical_request.CATEGORY_SOURCES.values():
            self.assertNotIn(source, html)

    def test_04_invalid_dates_rejected(self):
        with self.assertRaises(historical_request.HistoricalRequestValidationError) as raised:
            historical_request.validate_request(
                "2020-02-02", "2020-01-01", ["inflation"]
            )
        self.assertEqual(raised.exception.code, "invalid_dates")

    def test_05_empty_category_rejected(self):
        with self.assertRaises(historical_request.HistoricalRequestValidationError):
            historical_request.validate_request("2020-01-01", "2020-01-02", [])

    def test_06_mapping_is_server_owned(self):
        validated = historical_request.validate_request(
            "2020-01-01", "2020-01-02", ["energy_commodities", "monetary_policy"]
        )
        self.assertEqual(validated["sources"], ["fed_fomc", "eia_energy"])

    def test_07_arbitrary_source_and_path_rejected(self):
        for value in ("fed_fomc", "../../fed_fomc"):
            with self.assertRaises(historical_request.HistoricalRequestValidationError):
                historical_request.validate_request(
                    "2020-01-01", "2020-01-02", [value]
                )

    def test_08_internal_identifier_fields_rejected(self):
        for name in ("backfill_id", "replay_id", "workflow_id", "path"):
            with self.assertRaises(historical_request.HistoricalRequestValidationError):
                historical_request.validate_form_fields(
                    ["start_date", "end_date", "category", name]
                )

    def test_09_success_runs_backfills_then_replay_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            manifest = {"source_outcomes": [outcome("fed_fomc")]}
            backfills = Mock(return_value={"workflow_id": "workflow_2020-01-02_abcdef123456"})
            replay = Mock(return_value={"replay_id": "replay_2020-01-02_macro"})
            with patch.object(
                historical_request.historical_workflow,
                "load_workflow_manifest",
                return_value=manifest,
            ):
                result = historical_request.execute_request(
                    "2020-01-01",
                    "2020-01-02",
                    ["monetary_policy"],
                    run_backfills=backfills,
                    run_replay=replay,
                    data_dir=data_dir,
                )
            record = historical_request.load_request(result["request_id"], data_dir)
            self.assertEqual(record["state"], "COMPLETE")
            backfills.assert_called_once()
            replay.assert_called_once()

    def test_10_partial_is_calm_and_specific(self):
        record = self._record(
            "PARTIAL",
            [
                {"category": "monetary_policy", "outcome": "RECONSTRUCTED", "record_count": 3},
                {"category": "inflation", "outcome": "NO_RECORDS", "record_count": 0},
            ],
            replay="replay_2020-01-02_macro",
        )
        html = self._render_status(record)
        self.assertIn("no records available in this period", html)
        self.assertIn(HISTORICAL_COPY["request_no_records_note"], html)

    def test_11_failed_is_calm_without_exception(self):
        record = self._record(
            "FAILED",
            [{"category": "inflation", "outcome": "FAILED", "record_count": 0}],
        )
        html = self._render_status(record)
        self.assertIn("could not be reconstructed", html)
        self.assertNotIn("Traceback", html)

    def test_12_complete_duplicate_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            request_id = historical_request.build_request_id(
                "2020-01-01", "2020-01-02", ["inflation"]
            )
            record = self._record("COMPLETE", [], request_id=request_id)
            historical_request._write_request(record, data_dir)
            backfills = Mock()
            result = historical_request.execute_request(
                "2020-01-01",
                "2020-01-02",
                ["inflation"],
                run_backfills=backfills,
                run_replay=Mock(),
                data_dir=data_dir,
            )
            self.assertTrue(result["reused"])
            backfills.assert_not_called()

    def test_13_status_refresh_performs_no_work(self):
        record = self._record("COMPLETE", [])
        with patch.object(historical_request, "load_request", return_value=record), patch.object(
            dashboard, "execute_admin_workflow_backfills"
        ) as runner:
            dashboard.build_historical_request_status_context(
                object(), record["request_id"]
            )
            dashboard.build_historical_request_status_context(
                object(), record["request_id"]
            )
        runner.assert_not_called()

    def test_14_completion_links_to_investigation(self):
        html = self._render_status(
            self._record("COMPLETE", [], replay="replay_2020-01-02_macro")
        )
        self.assertIn('href="/history/replay_2020-01-02_macro"', html)
        self.assertIn(HISTORICAL_COPY["request_view_result"], html)

    def test_15_comparison_entry_is_available(self):
        html = self._render_status(
            self._record("COMPLETE", [], replay="replay_2020-01-02_macro")
        )
        self.assertIn('href="/history/compare"', html)

    def test_16_internal_ids_are_not_product_labels(self):
        html = self._render_status(
            self._record("COMPLETE", [], replay="replay_2020-01-02_macro")
        )
        self.assertNotIn("<h1>replay_", html)
        self.assertNotIn("workflow_", html)

    def test_17_raw_exceptions_never_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            result = historical_request.execute_request(
                "2020-01-01",
                "2020-01-02",
                ["inflation"],
                run_backfills=Mock(side_effect=RuntimeError("secret connector failure")),
                run_replay=Mock(),
                data_dir=data_dir,
            )
            text = json.dumps(historical_request.load_request(result["request_id"], data_dir))
            self.assertNotIn("secret connector failure", text)

    def test_18_no_admin_controls_or_links(self):
        html = render(
            "historical_request.html",
            **dashboard.build_historical_request_form_context(object()),
        )
        self.assertNotIn('href="/admin"', html)
        self.assertNotIn("Run Backfill", html)

    def test_19_research_route_remains(self):
        self.assertIn(
            "/research",
            {getattr(route, "path", None) for route in dashboard.app.routes},
        )

    def test_20_admin_workflow_route_remains(self):
        self.assertIn(
            "/admin/historical-workflow",
            {getattr(route, "path", None) for route in dashboard.app.routes},
        )

    def test_21_submission_does_not_fetch_rss(self):
        with patch(
            "mne.rss_fetch.fetch_headlines_from_rss", side_effect=AssertionError
        ), patch.object(
            historical_request, "execute_request", return_value={"request_id": "request_" + "a" * 24}
        ):
            response = asyncio.run(
                dashboard.submit_historical_request(
                    BodyRequest(
                        "start_date=2020-01-01&end_date=2020-01-02&category=inflation"
                    )
                )
            )
        self.assertEqual(response.status_code, 303)

    def test_22_request_module_does_not_import_scoring_or_taxonomy(self):
        source = Path("mne/historical_request.py").read_text(encoding="utf-8")
        self.assertNotIn("narrative_signals", source)
        self.assertNotIn("theme_taxonomy", source)

    def test_23_selector_has_request_entry_points(self):
        source = Path("templates/historical_selector.html").read_text(encoding="utf-8")
        self.assertIn('href="/history/request"', source)
        self.assertIn("request_empty_entry", source)

    def test_24_max_range_rejected_calmly(self):
        with self.assertRaises(historical_request.HistoricalRequestValidationError) as raised:
            historical_request.validate_request(
                "2020-01-01", "2020-04-02", ["inflation"]
            )
        self.assertEqual(raised.exception.code, "range_too_large")
        context = dashboard.build_historical_request_form_context(
            object(), raised.exception.code
        )
        self.assertEqual(context["error"], HISTORICAL_COPY["request_range_too_large"])

    def test_25_presentation_dictionary_covers_request_vocabulary(self):
        for token in historical_request.CATEGORY_ORDER:
            self.assertTrue(historical_request_category(token)["label"])
            self.assertTrue(historical_request_category(token)["description"])
        for state in ("RECONSTRUCTED", "NO_RECORDS", "FAILED"):
            self.assertTrue(historical_request_outcome(state, 2))
        for key in (
            "request_pacing",
            "request_coverage_supported",
            "request_coverage_partial",
            "request_coverage_incomplete",
            "request_coverage_cutoff",
        ):
            self.assertTrue(HISTORICAL_COPY[key])

    def _record(self, state, outcomes, replay=None, request_id=None):
        return {
            "request_id": request_id or "request_" + "a" * 24,
            "requested_period": {
                "start_date": "2020-01-01",
                "end_date": "2020-01-02",
            },
            "requested_product_categories": ["monetary_policy", "inflation"],
            "category_outcomes": outcomes,
            "state": state,
            "resulting_replay_reference": replay,
        }

    def _render_status(self, record):
        with patch.object(historical_request, "load_request", return_value=record):
            context = dashboard.build_historical_request_status_context(
                object(), record["request_id"]
            )
        return render("historical_request_status.html", **context)


if __name__ == "__main__":
    unittest.main()
