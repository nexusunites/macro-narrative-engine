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
from mne import historical_backfill, historical_comparison, historical_replay


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
    tmpdir = workspace_tmp / f"historical_comparison_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    old_results_dir = dashboard.RESULTS_DIR
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_replay.config)
        importlib.reload(dashboard.historical_replay.config)
        dashboard.RESULTS_DIR = data_dir / "results"
        try:
            yield data_dir
        finally:
            dashboard.RESULTS_DIR = old_results_dir
            importlib.reload(historical_replay.config)
            importlib.reload(dashboard.historical_replay.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


def sample_replay_pair():
    replay_a = {
        "replay_id": "replay_2026-07-01_macro",
        "replay_date": "2026-07-01",
        "generated_at": "2026-07-02T12:00:00Z",
        "evidence_cutoff": "2026-07-01T23:59:59Z",
        "evidence_count": 10,
        "source_count": 3,
        "taxonomy_version": "taxonomy-a",
        "registry_version": "registry-test",
        "theme_scores": {"ai": 22, "rates": 0, "energy": 8, "jobs": 5, "zero": 0},
        "group_scores": {"AI / Tech Growth": 22, "Macro Pressure": 8, "Jobs": 5},
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "replay_metadata": {
            "replay_mode": "HISTORICAL_REPLAY",
            "warnings": ["Replay A warning"],
            "backfilled_evidence_included": False,
            "backfill_ids_used": [],
            "live_persisted_evidence_included": True,
            "evidence_sources_used": ["live_persisted"],
            "backfilled_evidence_count": 0,
            "live_evidence_count": 10,
            "total_evidence_count": 10,
        },
    }
    replay_b = {
        "replay_id": "replay_2026-07-02_macro",
        "replay_date": "2026-07-02",
        "generated_at": "2026-07-03T12:00:00Z",
        "evidence_cutoff": "2026-07-02T23:59:59Z",
        "evidence_count": 14,
        "source_count": 5,
        "taxonomy_version": "taxonomy-b",
        "registry_version": "registry-test",
        "theme_scores": {"ai": 14, "rates": 6, "energy": 12, "jobs": 5, "zero": 0},
        "group_scores": {"AI / Tech Growth": 14, "Macro Pressure": 12, "Rates": 6, "Jobs": 5},
        "dominant_theme": "energy",
        "dominant_group": "Macro Pressure",
        "network_confidence": {"status": "TEST"},
        "replay_metadata": {
            "replay_mode": "HISTORICAL_REPLAY",
            "warnings": ["Replay B warning", "Replay B second warning"],
            "backfilled_evidence_included": True,
            "backfill_ids_used": ["backfill_2026-07-02_macro_fed_fomc"],
            "live_persisted_evidence_included": True,
            "evidence_sources_used": ["live_persisted", "historical_backfill"],
            "backfilled_evidence_count": 4,
            "live_evidence_count": 10,
            "total_evidence_count": 14,
        },
    }
    return replay_a, replay_b


def write_replay(data_dir, replay):
    replay_dir = data_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    path = replay_dir / f"{replay['replay_id']}.json"
    path.write_text(json.dumps(replay, sort_keys=True), encoding="utf-8")
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


class HistoricalComparisonTests(unittest.TestCase):
    def test_route_is_registered_as_get(self):
        methods_by_path = {
            getattr(route, "path", None): getattr(route, "methods", set())
            for route in dashboard.app.routes
        }

        self.assertIn("/admin/replay/compare", methods_by_path)
        self.assertIn("GET", methods_by_path["/admin/replay/compare"])
        self.assertNotIn("POST", methods_by_path["/admin/replay/compare"])

    def test_valid_comparison_route_renders(self):
        replay_a, replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )
            html = render_template("historical_comparison.html", **context)

        self.assertIsNone(context["message"])
        self.assertIn("Historical Comparison View", html)
        self.assertIn("replay_2026-07-01_macro", html)
        self.assertIn("replay_2026-07-02_macro", html)
        self.assertIn("This comparison uses persisted replay artifacts only.", html)

    def test_invalid_ids_and_traversal_are_rejected_calmly(self):
        with temporary_mne_data_dir():
            for replay_a, replay_b in [
                ("", "replay_2026-07-02_macro"),
                ("replay_2026-07-01_macro", "not-valid"),
                ("../../etc/passwd", "replay_2026-07-02_macro"),
                ("replay_2026-07-01_macro", "../results/replay_2026-07-02_macro"),
            ]:
                context = dashboard.build_historical_comparison_route_context(
                    object(), replay_a, replay_b
                )
                self.assertIsNone(context["comparison"])
                self.assertIsNotNone(context["message"])

    def test_unknown_well_formed_ids_are_rejected_calmly(self):
        with temporary_mne_data_dir():
            context = dashboard.build_historical_comparison_route_context(
                object(),
                "replay_2026-07-01_macro",
                "replay_2026-07-02_macro",
            )

        self.assertEqual(context["message"], "Historical replay not found.")

    def test_same_replay_is_successful_without_delta_tables(self):
        replay_a, _replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_a["replay_id"]
            )
            html = render_template("historical_comparison.html", **context)

        self.assertIsNone(context["message"])
        self.assertTrue(context["comparison"]["same_replay"])
        self.assertEqual(context["comparison"]["theme_changes"], [])
        self.assertIn("Replay A and Replay B are the same replay artifact.", html)
        self.assertNotIn("<th>Theme</th><th>Score A</th>", html)

    def test_route_only_reads_replays_and_not_results_fallback(self):
        replay_a, replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            (results_dir / f"{replay_a['replay_id']}.json").write_text(json.dumps(replay_a), encoding="utf-8")
            write_replay(data_dir, replay_b)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )

        self.assertEqual(context["message"], "Historical replay not found.")

    def test_comparison_does_not_execute_replay_backfill_or_network(self):
        replay_a, replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            with (
                patch.object(historical_replay, "run_historical_replay", side_effect=AssertionError("replay executed")) as run,
                patch.object(historical_backfill, "run_historical_backfill", side_effect=AssertionError("backfill executed")) as backfill_run,
                patch.object(historical_backfill, "load_backfilled_evidence", side_effect=AssertionError("backfill read")) as backfill_load,
                patch("requests.get", side_effect=AssertionError("network fetch")) as requests_get,
            ):
                context = dashboard.build_historical_comparison_route_context(
                    object(), replay_a["replay_id"], replay_b["replay_id"]
                )

        self.assertIsNone(context["message"])
        run.assert_not_called()
        backfill_run.assert_not_called()
        backfill_load.assert_not_called()
        requests_get.assert_not_called()

    def test_score_deltas_new_dropped_unchanged_and_ranks(self):
        rows = historical_comparison.compare_score_maps(
            {"ai": 22, "rates": 0, "jobs": 5, "zero": 0},
            {"ai": 14, "rates": 6, "jobs": 5, "zero": 0},
        )
        by_key = {row["key"]: row for row in rows}

        self.assertEqual(by_key["ai"]["direction"], "DECREASED")
        self.assertEqual(by_key["rates"]["direction"], "NEW")
        self.assertEqual(by_key["jobs"]["direction"], "UNCHANGED")
        self.assertNotIn("zero", by_key)
        self.assertEqual(by_key["jobs"]["rank_a"], 2)
        self.assertEqual(by_key["jobs"]["rank_b"], 3)
        self.assertEqual(by_key["jobs"]["rank_delta"], -1)

    def test_group_deltas_and_dropped_detection_use_zero_nonzero(self):
        rows = historical_comparison.compare_score_maps(
            {"AI / Tech Growth": 8, "Rates": 2},
            {"AI / Tech Growth": 9, "Rates": 0, "Macro Pressure": 4},
            label_style="group",
        )
        by_key = {row["key"]: row for row in rows}

        self.assertEqual(by_key["AI / Tech Growth"]["direction"], "INCREASED")
        self.assertEqual(by_key["Rates"]["direction"], "DROPPED")
        self.assertEqual(by_key["Macro Pressure"]["direction"], "NEW")

    def test_rank_ties_break_by_key(self):
        ranks = historical_comparison.compute_rank_changes(
            {"b": 10, "a": 10},
            {"b": 8, "a": 10},
        )

        self.assertEqual(ranks["a"]["rank_a"], 1)
        self.assertEqual(ranks["b"]["rank_a"], 2)
        self.assertEqual(ranks["a"]["rank_b"], 1)
        self.assertEqual(ranks["b"]["rank_b"], 2)

    def test_dominance_copy_matches_template(self):
        replay_a, replay_b = sample_replay_pair()
        dominance = historical_comparison.compare_dominance(replay_a, replay_b)

        self.assertEqual(
            dominance["dominant_theme_copy"],
            "Dominant theme changed from Ai to Energy.",
        )
        self.assertEqual(
            dominance["dominant_group_copy"],
            "Dominant group changed from AI / Tech Growth to Macro Pressure.",
        )

    def test_evidence_base_copy_and_backfill_cases(self):
        replay_a, replay_b = sample_replay_pair()
        evidence = historical_comparison.compare_evidence_base(replay_a, replay_b)

        self.assertEqual(evidence["evidence_count_delta"], 4)
        self.assertEqual(evidence["source_count_delta"], 2)
        self.assertEqual(evidence["warnings_count_delta"], 1)
        self.assertIn("Replay B used 4 more evidence items than Replay A.", evidence["copy"])
        self.assertIn("Replay B included backfilled evidence.", evidence["copy"])

        replay_a["replay_metadata"]["backfilled_evidence_count"] = 3
        replay_a["replay_metadata"]["backfilled_evidence_included"] = True
        replay_b["replay_metadata"]["backfilled_evidence_count"] = 0
        replay_b["replay_metadata"]["backfilled_evidence_included"] = False
        self.assertIn(
            "Replay A included backfilled evidence.",
            historical_comparison.compare_evidence_base(replay_a, replay_b)["copy"],
        )
        replay_b["replay_metadata"]["backfilled_evidence_count"] = 2
        replay_b["replay_metadata"]["backfilled_evidence_included"] = True
        self.assertIn(
            "Both replays included backfilled evidence.",
            historical_comparison.compare_evidence_base(replay_a, replay_b)["copy"],
        )
        replay_a["replay_metadata"]["backfilled_evidence_count"] = 0
        replay_a["replay_metadata"]["backfilled_evidence_included"] = False
        replay_b["replay_metadata"]["backfilled_evidence_count"] = 0
        replay_b["replay_metadata"]["backfilled_evidence_included"] = False
        self.assertIn(
            "Neither replay included backfilled evidence.",
            historical_comparison.compare_evidence_base(replay_a, replay_b)["copy"],
        )

    def test_coverage_intelligence_counts_and_breadth_state_compare_when_present(self):
        replay_a, replay_b = sample_replay_pair()
        replay_a["source_intelligence"] = {
            "coverage_intelligence": {
                "breadth_state": "LIMITED",
                "contributing_source_count": 2,
                "contributing_provider_count": 2,
                "contributing_category_count": 2,
            }
        }
        replay_b["source_intelligence"] = {
            "coverage_intelligence": {
                "breadth_state": "MODERATE",
                "contributing_source_count": 3,
                "contributing_provider_count": 3,
                "contributing_category_count": 3,
            }
        }

        evidence = historical_comparison.compare_evidence_base(replay_a, replay_b)

        self.assertTrue(evidence["coverage_available_a"])
        self.assertTrue(evidence["coverage_available_b"])
        self.assertEqual(evidence["breadth_state_a"], "LIMITED")
        self.assertEqual(evidence["breadth_state_b"], "MODERATE")
        self.assertEqual(evidence["contributing_source_count_a"], 2)
        self.assertEqual(evidence["contributing_source_count_b"], 3)
        self.assertIn("Coverage breadth changed from LIMITED to MODERATE.", evidence["copy"])

    def test_coverage_intelligence_missing_on_one_side_does_not_crash_and_is_not_zero(self):
        replay_a, replay_b = sample_replay_pair()
        replay_b["source_intelligence"] = {
            "coverage_intelligence": {
                "breadth_state": "MODERATE",
                "contributing_source_count": 3,
                "contributing_provider_count": 3,
                "contributing_category_count": 3,
            }
        }

        evidence = historical_comparison.compare_evidence_base(replay_a, replay_b)

        self.assertFalse(evidence["coverage_available_a"])
        self.assertTrue(evidence["coverage_available_b"])
        self.assertIsNone(evidence["breadth_state_a"])
        self.assertIsNone(evidence["contributing_source_count_a"])
        self.assertIn(
            "Coverage breadth could not be compared because it is only available for one replay.",
            evidence["copy"],
        )

    def test_coverage_intelligence_absent_from_both_artifacts_renders_calmly(self):
        replay_a, replay_b = sample_replay_pair()

        evidence = historical_comparison.compare_evidence_base(replay_a, replay_b)

        self.assertFalse(evidence["coverage_available_a"])
        self.assertFalse(evidence["coverage_available_b"])
        self.assertIsNone(evidence["breadth_state_a"])
        self.assertIsNone(evidence["breadth_state_b"])

        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )
            html = render_template("historical_comparison.html", **context)

        self.assertIsNone(context["message"])
        self.assertNotIn("Traceback", html)

    def test_multiple_backfill_ids_used_carry_through_comparison(self):
        replay_a, replay_b = sample_replay_pair()
        replay_b["replay_metadata"]["backfill_ids_used"] = [
            "backfill_2020-01-01_2020-01-31_macro_fed_fomc",
            "backfill_2020-01-01_2020-01-31_macro_bls_cpi",
        ]

        evidence = historical_comparison.compare_evidence_base(replay_a, replay_b)

        # The full multi-element list carries through unchanged, in order.
        self.assertEqual(evidence["backfill_ids_used_a"], [])
        self.assertEqual(
            evidence["backfill_ids_used_b"],
            [
                "backfill_2020-01-01_2020-01-31_macro_fed_fomc",
                "backfill_2020-01-01_2020-01-31_macro_bls_cpi",
            ],
        )
        # Inclusion copy still keys off backfilled_evidence_included/count, not ids.
        self.assertIn("Replay B included backfilled evidence.", evidence["copy"])

        # Route-level render: template joins the multi-id list with ", ".
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )
            html = render_template("historical_comparison.html", **context)

        self.assertIsNone(context["message"])
        self.assertIn(
            "backfill_2020-01-01_2020-01-31_macro_fed_fomc, "
            "backfill_2020-01-01_2020-01-31_macro_bls_cpi",
            html,
        )

    def test_warnings_optional_fields_and_confidence_rendering(self):
        replay_a, replay_b = sample_replay_pair()
        replay_a.pop("replay_metadata")
        replay_a.pop("coverage", None)
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )
            html = render_template("historical_comparison.html", **context)

        self.assertIn("Backfill inclusion could not be compared", html)
        self.assertIn("Comparison: Replay artifacts use different taxonomy versions.", html)
        self.assertIn("Network Confidence", html)
        self.assertIn('"status": "TEST"', html)
        self.assertIn("Source Confidence", html)
        self.assertIn("Unavailable", html)

    def test_admin_page_includes_comparison_form_from_recent_replays(self):
        replay_a, replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            context = dashboard.build_template_context(
                request=object(),
                run=None,
                meaningful_default=False,
            )
            html = render_template("admin.html", **context)

        self.assertIn('id="historical-comparison"', html)
        self.assertIn('action="/admin/replay/compare"', html)
        self.assertIn('name="replay_a"', html)
        self.assertIn('name="replay_b"', html)
        self.assertIn("Compare</button>", html)
        self.assertIn("replay_2026-07-01_macro.json", html)

    def test_public_dashboard_and_standard_research_have_no_comparison_ui(self):
        dashboard_html = render_template(
            "dashboard.html",
            request=object(),
            message="No MNE result files found. Run main.py first.",
            results_dir="/tmp/results",
            recent_runs=[],
            selected_file=None,
            view=None,
            notice=None,
        )
        research_html = render_template(
            "research_selector.html",
            request=object(),
            message=None,
            notice=None,
            results_dir="/tmp/results",
            selected_file=None,
            selector=[],
        )

        self.assertNotIn("/admin/replay/compare", dashboard_html)
        self.assertNotIn("Historical Comparison", dashboard_html)
        self.assertNotIn("/admin/replay/compare", research_html)
        self.assertNotIn("Historical Comparison", research_html)

    def test_comparison_does_not_modify_replay_artifacts_or_live_results(self):
        replay_a, replay_b = sample_replay_pair()
        with temporary_mne_data_dir() as data_dir:
            replay_dir = data_dir / "replays"
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            (results_dir / "2026-07-02_120000.json").write_text(
                json.dumps({"timestamp": "2026-07-02_120000"}),
                encoding="utf-8",
            )
            write_replay(data_dir, replay_a)
            write_replay(data_dir, replay_b)
            replays_before = directory_digest(replay_dir)
            results_before = directory_digest(results_dir)

            context = dashboard.build_historical_comparison_route_context(
                object(), replay_a["replay_id"], replay_b["replay_id"]
            )
            replays_after = directory_digest(replay_dir)
            results_after = directory_digest(results_dir)

        self.assertIsNone(context["message"])
        self.assertEqual(replays_before, replays_after)
        self.assertEqual(results_before, results_after)


if __name__ == "__main__":
    unittest.main()
