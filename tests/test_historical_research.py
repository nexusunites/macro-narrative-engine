import hashlib
import importlib
import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne import historical_replay, historical_research


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
    tmpdir = workspace_tmp / f"historical_research_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    old_results_dir = dashboard.RESULTS_DIR
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_replay.config)
        importlib.reload(historical_research.config)
        dashboard.RESULTS_DIR = data_dir / "results"
        try:
            yield data_dir
        finally:
            dashboard.RESULTS_DIR = old_results_dir
            importlib.reload(historical_replay.config)
            importlib.reload(historical_research.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


def sample_replay(**overrides):
    replay = {
        "replay_id": "replay_2026-07-06_macro",
        "replay_date": "2026-07-06",
        "generated_at": "2026-07-10T12:00:00Z",
        "evidence_cutoff": "2026-07-06T23:59:59.999999Z",
        "evidence_count": 2,
        "source_count": 2,
        "taxonomy_version": "taxonomy-test",
        "registry_version": "registry-test",
        "theme_scores": {"ai": 4, "rates": 1},
        "group_scores": {"AI / Tech Growth": 4, "Macro Pressure": 1},
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "source_intelligence": {
            "accepted_evidence_count": 2,
            "accepted_evidence": [
                {
                    "evidence_id": "e1",
                    "title": "AI data center expansion",
                    "source_id": "source-one",
                    "source_name": "Source One",
                    "provider": "Provider One",
                    "evidence_type": "Headline",
                    "published_at": "2026-07-06T09:00:00Z",
                    "timestamp": "2026-07-06T09:00:00Z",
                    "url": "https://example.com/e1",
                    "accepted": True,
                    "themes": ["ai"],
                    "groups": ["AI / Tech Growth"],
                },
                {
                    "evidence_id": "future",
                    "title": "Future evidence should not render",
                    "source_name": "Future Source",
                    "published_at": "2026-07-07T09:00:00Z",
                    "timestamp": "2026-07-07T09:00:00Z",
                    "accepted": True,
                    "themes": ["ai"],
                    "groups": ["AI / Tech Growth"],
                },
            ],
        },
        "replay_metadata": {
            "replay_mode": "HISTORICAL_REPLAY",
            "live_run_source": False,
            "future_evidence_excluded": True,
            "evidence_selection_rule": "publication_and_knowledge_boundary",
            "replay_engine_version": "test-engine",
            "warnings": ["Only 2 evidence objects were available at this cutoff."],
        },
    }
    replay.update(overrides)
    return replay


def write_replay(data_dir, replay=None, replay_id="replay_2026-07-06_macro"):
    replay_dir = data_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    path = replay_dir / f"{replay_id}.json"
    path.write_text(json.dumps(replay or sample_replay(replay_id=replay_id)), encoding="utf-8")
    return path


def render_template(name, **context):
    original_url_for = dashboard.templates.env.globals.get("url_for")
    dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
    try:
        return dashboard.templates.env.get_template(name).render(**context)
    finally:
        if original_url_for is None:
            dashboard.templates.env.globals.pop("url_for", None)
        else:
            dashboard.templates.env.globals["url_for"] = original_url_for


class HistoricalResearchTests(unittest.TestCase):
    def test_admin_historical_research_route_is_registered(self):
        paths = {getattr(route, "path", None) for route in dashboard.app.routes}

        self.assertIn("/admin/replay/{replay_id}/research", paths)

    def test_valid_route_context_renders_historical_research_page(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            context = dashboard.build_historical_research_route_context(
                request=object(),
                replay_id="replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIsNone(context["message"])
        self.assertIn("Historical Research View", html)
        self.assertIn("This is a historical replay.", html)
        self.assertIn("The replay uses persisted evidence only.", html)
        self.assertIn("Evidence published after the cutoff is excluded.", html)
        self.assertIn("No live source fetching occurs.", html)
        self.assertIn("Historical coverage may be incomplete", html)

    def test_invalid_replay_id_is_rejected_calmly(self):
        with temporary_mne_data_dir():
            context = dashboard.build_historical_research_route_context(object(), "")
            html = render_template("historical_research.html", **context)

        self.assertIn("The replay identifier is invalid.", html)
        self.assertNotIn("Traceback", html)

    def test_path_traversal_is_rejected_calmly(self):
        traversal_ids = [
            "../results/example",
            "..\\results\\example",
            "/tmp/replay_2026-07-06_macro",
            "%2e%2e%2fresults%2fexample",
        ]
        with temporary_mne_data_dir():
            for replay_id in traversal_ids:
                context = dashboard.build_historical_research_route_context(object(), replay_id)
                self.assertEqual(context["message"], "The replay identifier is invalid.")

    def test_unknown_replay_id_is_rejected_calmly(self):
        with temporary_mne_data_dir():
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("Historical replay not found.", html)
        self.assertNotIn("Traceback", html)

    def test_malformed_artifact_is_handled_calmly(self):
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            replay_dir.mkdir(parents=True)
            (replay_dir / "replay_2026-07-06_macro.json").write_text("{not json", encoding="utf-8")

            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("The selected replay artifact could not be loaded.", html)
        self.assertNotIn("Traceback", html)

    def test_route_reads_only_replay_directory_and_does_not_fallback_to_results(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            (results_dir / "replay_2026-07-06_macro.json").write_text(
                json.dumps(sample_replay()),
                encoding="utf-8",
            )

            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )

        self.assertEqual(context["message"], "Historical replay not found.")

    def test_route_does_not_trigger_replay_execution_or_fetch_sources(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            with (
                patch.object(dashboard.historical_replay, "run_historical_replay", side_effect=AssertionError("replay executed")) as run,
                patch("mne.rss_fetch.fetch_headlines_from_rss", side_effect=AssertionError("network fetch called")) as rss,
            ):
                context = dashboard.build_historical_research_route_context(
                    object(),
                    "replay_2026-07-06_macro",
                )

        self.assertIsNone(context["message"])
        run.assert_not_called()
        rss.assert_not_called()

    def test_user_dashboard_has_no_historical_research_link(self):
        html = render_template(
            "dashboard.html",
            request=object(),
            message="No MNE result files found. Run main.py first.",
            results_dir="/tmp/results",
            recent_runs=[],
            selected_file=None,
            view=None,
            notice=None,
        )

        self.assertNotIn("Open historical research view", html)
        self.assertNotIn("/admin/replay/", html)

    def test_standard_research_has_no_replay_artifacts(self):
        html = render_template(
            "research_selector.html",
            request=object(),
            message=None,
            notice=None,
            results_dir="/tmp/results",
            selected_file=None,
            selector=[],
        )

        self.assertNotIn("Open historical research view", html)
        self.assertNotIn("replay_2026-07-06_macro", html)
        self.assertNotIn("/admin/replay/", html)

    def test_admin_console_links_to_historical_research_view(self):
        with temporary_mne_data_dir() as data_dir:
            replay_path = write_replay(data_dir)
            result = dashboard.build_replay_result_view(sample_replay(), replay_path)
            html = render_template(
                "admin.html",
                request=object(),
                results_dir="/tmp/results",
                recent_runs=[],
                selected_file=None,
                message=None,
                view=None,
                notice=None,
                historical_replay_console=dashboard.build_historical_replay_console(result=result),
            )

        self.assertIn("Open historical research view", html)
        self.assertIn("/admin/replay/replay_2026-07-06_macro/research", html)

    def test_context_fields_scores_warnings_metadata_and_safe_path_render(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("replay_2026-07-06_macro", html)
        self.assertIn("2026-07-06", html)
        self.assertIn("2026-07-06T23:59:59.999999Z", html)
        self.assertIn("2026-07-10T12:00:00Z", html)
        self.assertIn("AI / Tech Growth", html)
        self.assertIn("Macro Pressure", html)
        self.assertIn("Only 2 evidence objects were available at this cutoff.", html)
        self.assertIn("taxonomy-test", html)
        self.assertIn("registry-test", html)
        self.assertIn("test-engine", html)
        self.assertIn("future_evidence_excluded", html)
        self.assertIn("True", html)
        self.assertIn("replays/replay_2026-07-06_macro.json", html)
        self.assertNotIn(str(data_dir), html)

    def test_renders_historical_coverage_intelligence_calmly(self):
        replay = sample_replay()
        replay["source_intelligence"]["coverage_intelligence"] = {
            "accepted_evidence_count": 2,
            "contributing_source_count": 1,
            "contributing_provider_count": 1,
            "contributing_category_count": 1,
            "evidence_count_by_source": {"fed_fomc": 2},
            "evidence_count_by_provider": {"Federal Reserve": 2},
            "evidence_count_by_category": {"Central Bank Communications": 2},
            "source_concentration": 1.0,
            "provider_concentration": 1.0,
            "category_concentration": 1.0,
            "breadth_state": "MINIMAL",
            "evidence_origins_used": ["historical_backfill"],
            "coverage_limitations": [
                "Historical coverage reflects supported backfill sources only.",
                "This is not complete historical market-news coverage.",
                "Coverage breadth is measured within the evidence available to this replay.",
            ],
        }
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay=replay)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("MINIMAL", html)
        self.assertIn("This is not complete historical market-news coverage.", html)
        self.assertNotIn("Traceback", html)

    def test_missing_coverage_intelligence_renders_without_crash(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("Historical Research View", html)
        self.assertNotIn("Traceback", html)

    def test_build_historical_coverage_display_context_reads_source_intelligence(self):
        replay = sample_replay()
        replay["source_intelligence"]["coverage_intelligence"] = {
            "breadth_state": "LIMITED",
            "evidence_origins_used": ["historical_backfill"],
            "coverage_limitations": ["This is not complete historical market-news coverage."],
            "contributing_source_count": 2,
            "contributing_provider_count": 2,
            "contributing_category_count": 2,
        }
        coverage = historical_research.build_historical_coverage_display_context(replay)
        self.assertEqual(coverage["breadth_state"], "LIMITED")
        self.assertEqual(coverage["contributing_source_count"], 2)

    def test_build_historical_coverage_display_context_returns_none_when_absent(self):
        self.assertIsNone(historical_research.build_historical_coverage_display_context(sample_replay()))

    def test_historical_evidence_renders_and_future_evidence_is_excluded(self):
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("AI data center expansion", html)
        self.assertIn("https://example.com/e1", html)
        self.assertIn("Headline-level summary", html)
        self.assertNotIn("Future evidence should not render", html)

    def test_live_results_are_not_modified(self):
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            live_path = results_dir / "2026-07-06_100000.json"
            live_path.write_text(json.dumps({"timestamp": "2026-07-06_100000"}), encoding="utf-8")
            write_replay(data_dir)
            before = directory_digest(results_dir)

            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            after = directory_digest(results_dir)

        self.assertIsNone(context["message"])
        self.assertEqual(before, after)

    def test_renders_backfilled_evidence_from_replay_artifact_without_code_changes(self):
        replay = sample_replay()
        replay["source_intelligence"]["accepted_evidence"].append(
            {
                "evidence_id": "b1",
                "title": "Federal Reserve issues FOMC statement",
                "source_id": "fed_fomc",
                "source_name": "Federal Reserve",
                "provider": "Federal Reserve",
                "evidence_type": "Headline",
                "published_at": "2026-07-06T19:00:00Z",
                "timestamp": "2026-07-06T19:00:00Z",
                "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260706a.htm",
                "accepted": True,
                "themes": ["ai"],
                "groups": ["AI / Tech Growth"],
                "evidence_origin": "HISTORICAL_BACKFILL",
                "backfill_id": "backfill_2026-07-06_macro_fed_fomc",
            }
        )
        replay["source_intelligence"]["accepted_evidence_count"] = len(
            replay["source_intelligence"]["accepted_evidence"]
        )
        replay["replay_metadata"]["backfilled_evidence_included"] = True
        replay["replay_metadata"]["backfill_ids_used"] = ["backfill_2026-07-06_macro_fed_fomc"]

        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay=replay)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        self.assertIn("Federal Reserve issues FOMC statement", html)
        self.assertIn(
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260706a.htm",
            html,
        )

    def test_renders_evidence_from_multiple_backfill_ids_without_cross_contamination(self):
        replay = sample_replay()
        replay["source_intelligence"]["accepted_evidence"].append(
            {
                "evidence_id": "b_fed",
                "title": "Federal Reserve issues FOMC statement",
                "source_id": "fed_fomc",
                "source_name": "Federal Reserve",
                "provider": "Federal Reserve",
                "category": "Central Bank Communications",
                "evidence_type": "Headline",
                "published_at": "2026-07-06T19:00:00Z",
                "timestamp": "2026-07-06T19:00:00Z",
                "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260706a.htm",
                "accepted": True,
                "themes": ["ai"],
                "groups": ["AI / Tech Growth"],
                "evidence_origin": "HISTORICAL_BACKFILL",
                "backfill_id": "backfill_2020-01-01_2020-01-31_macro_fed_fomc",
            }
        )
        replay["source_intelligence"]["accepted_evidence"].append(
            {
                "evidence_id": "b_bls",
                "title": "BLS reports monthly CPI print",
                "source_id": "bls_cpi",
                "source_name": "BLS",
                "provider": "BLS",
                "category": "Inflation / Economic Data",
                "evidence_type": "Headline",
                "published_at": "2026-07-06T13:30:00Z",
                "timestamp": "2026-07-06T13:30:00Z",
                "url": "https://www.bls.gov/news.release/cpi.nr0.htm",
                "accepted": True,
                "themes": ["rates"],
                "groups": ["Macro Pressure"],
                "evidence_origin": "HISTORICAL_BACKFILL",
                "backfill_id": "backfill_2020-01-01_2020-01-31_macro_bls_cpi",
            }
        )
        replay["source_intelligence"]["accepted_evidence_count"] = len(
            replay["source_intelligence"]["accepted_evidence"]
        )
        replay["replay_metadata"]["backfilled_evidence_included"] = True
        replay["replay_metadata"]["backfill_ids_used"] = [
            "backfill_2020-01-01_2020-01-31_macro_fed_fomc",
            "backfill_2020-01-01_2020-01-31_macro_bls_cpi",
        ]

        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay=replay)
            context = dashboard.build_historical_research_route_context(
                object(),
                "replay_2026-07-06_macro",
            )
            html = render_template("historical_research.html", **context)

        # Both distinct-backfill records render with their own title, url, and provider.
        self.assertIsNone(context["message"])
        self.assertIn("Federal Reserve issues FOMC statement", html)
        self.assertIn("BLS reports monthly CPI print", html)
        self.assertIn(
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260706a.htm",
            html,
        )
        self.assertIn("https://www.bls.gov/news.release/cpi.nr0.htm", html)
        self.assertIn("Federal Reserve", html)
        self.assertIn("BLS", html)

        # No cross-contamination: each record keeps its own provider/source paired
        # with its own title in the rendered context evidence.
        provider_by_title = {
            row["title"]: row["provider"]
            for row in context["historical_research"]["evidence"]
        }
        self.assertEqual(
            provider_by_title["Federal Reserve issues FOMC statement"],
            "Federal Reserve",
        )
        self.assertEqual(provider_by_title["BLS reports monthly CPI print"], "BLS")


if __name__ == "__main__":
    unittest.main()
