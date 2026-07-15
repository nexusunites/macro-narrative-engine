import copy
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.dashboard_trust_summary import build_dashboard_trust_summary
from mne.operations_center import (
    build_operations_center,
    evaluate_component_status,
    rollup_overall_status,
)


def component(key, status, confidence="HIGH"):
    return {
        "key": key,
        "title": key,
        "status": status,
        "confidence": confidence,
        "reason": f"{key} reason",
        "recommendation": "No action needed.",
    }


def registry_context(error=None):
    return {
        "configuration_report": {
            "active_data_dir": "/tmp/mne",
            "results_dir": "/tmp/mne/results",
            "headlines_dir": "/tmp/mne/headlines",
            "registry_version": None if error else "1.4.0",
            "registry_error": error,
        },
        "source_registry": {} if not error else {"error": error},
    }


def network_confidence_block(state="HIGH"):
    return {
        "network_confidence_state": state,
        "confidence_level": None,
        "reason": "2 source(s) were marked QUARANTINE_RECOMMENDED from persisted NETWORK_CRITICAL.",
        "recommended_action": "Review WATCH and NETWORK_DEGRADED diagnostics.",
        "supporting_factors": ["persisted healthy source diagnostics"],
        "limiting_factors": ["WATCH source concentration"],
        "thresholds_used": {"watch_count_threshold": 2},
    }


def clean_run(network_confidence_state="HIGH", network_confidence=None):
    run = {
        "timestamp": "2026-07-09_120000",
        "theme_scores": {"AI": 5},
        "source_intelligence": {
            "source_health": [
                {
                    "source_id": "s1",
                    "source_name": "Source One",
                    "state": "HEALTHY",
                    "severity": "INFO",
                }
            ],
            "source_freshness": [
                {
                    "source_id": "s1",
                    "source_name": "Source One",
                    "status": "FRESH",
                }
            ],
            "network_health": {
                "network_status": "NETWORK_HEALTHY",
                "categories": [
                    {
                        "category": "Rates",
                        "category_state": "HEALTHY",
                        "single_provider_dependency": False,
                    }
                ],
                "concentration": {"concentration_flag": False},
            },
            "source_confidence": {
                "confidence_state": "HIGH",
                "reason": "Source confidence is high.",
                "recommended_action": "No action needed.",
            },
            "source_reliability": {
                "summary": {
                    "stable_count": 1,
                    "watch_count": 0,
                    "repeated_failure_count": 0,
                    "quarantine_recommended_count": 0,
                    "unknown_count": 0,
                }
            },
            "coverage_intelligence": {
                "per_narrative": [
                    {
                        "narrative_id": "AI",
                        "narrative_level": "theme",
                        "coverage_state": "MODERATE",
                        "evidence_count": 1,
                        "unique_source_count": 1,
                        "unique_provider_count": 1,
                        "concentration_ratio": 1.0,
                        "source_contribution_breakdown": [],
                    }
                ]
            },
        },
        "platform_observability": {
            "run_metadata": {"run_id": "run-1"},
            "stages": [
                {"stage_name": "RSS_FETCH", "status": "SUCCESS"},
                {"stage_name": "EVIDENCE_NORMALIZATION", "status": "SUCCESS"},
            ],
        },
    }
    if network_confidence is not None:
        run["source_intelligence"]["network_confidence"] = network_confidence
    elif network_confidence_state is not None:
        run["source_intelligence"]["network_confidence"] = network_confidence_block(
            network_confidence_state
        )
    return run


class OperationsCenterTests(unittest.TestCase):
    def test_overall_rollup_worst_component_wins(self):
        status, _contributing = rollup_overall_status(
            [
                component("configuration", "EXCELLENT"),
                component("pipeline", "EXCELLENT"),
                component("evidence_network", "DEGRADED"),
                component("source_confidence", "EXCELLENT"),
            ]
        )

        self.assertEqual(status, "DEGRADED")

    def test_overall_rollup_status_levels(self):
        self.assertEqual(
            rollup_overall_status(
                [component("configuration", "EXCELLENT"), component("pipeline", "GOOD")]
            )[0],
            "GOOD",
        )
        self.assertEqual(
            rollup_overall_status(
                [component("configuration", "EXCELLENT"), component("pipeline", "LIMITED")]
            )[0],
            "LIMITED",
        )
        self.assertEqual(
            rollup_overall_status(
                [component("configuration", "EXCELLENT"), component("pipeline", "CRITICAL")]
            )[0],
            "CRITICAL",
        )
        self.assertEqual(
            rollup_overall_status(
                [component("configuration", "EXCELLENT"), component("pipeline", "OFFLINE")]
            )[0],
            "OFFLINE",
        )

    def test_network_health_mapping(self):
        run = clean_run()
        for network_state, expected in (
            ("NETWORK_PARTIAL", "LIMITED"),
            ("NETWORK_DEGRADED", "DEGRADED"),
            ("NETWORK_CRITICAL", "CRITICAL"),
        ):
            run["source_intelligence"]["network_health"]["network_status"] = network_state
            summary = evaluate_component_status("evidence_network", run, registry_context())
            self.assertEqual(summary["status"], expected)

    def test_source_confidence_mapping(self):
        run = clean_run()
        for state, expected_status, expected_confidence in (
            ("HIGH", "EXCELLENT", "HIGH"),
            ("MODERATE", "LIMITED", "HIGH"),
            ("LOW", "DEGRADED", "HIGH"),
            ("UNKNOWN", "WARNING", "UNKNOWN"),
        ):
            run["source_intelligence"]["source_confidence"]["confidence_state"] = state
            summary = evaluate_component_status("source_confidence", run, registry_context())
            self.assertEqual(summary["status"], expected_status)
            self.assertEqual(summary["confidence"], expected_confidence)

    def test_network_confidence_mapping(self):
        for state, expected_status, expected_confidence in (
            ("HIGH", "EXCELLENT", "HIGH"),
            ("MODERATE", "LIMITED", "HIGH"),
            ("LOW", "DEGRADED", "HIGH"),
            ("VERY_LOW", "CRITICAL", "HIGH"),
            ("UNKNOWN", "WARNING", "UNKNOWN"),
        ):
            run = clean_run(network_confidence_state=state)
            summary = evaluate_component_status(
                "network_confidence", run, registry_context()
            )
            self.assertEqual(summary["status"], expected_status)
            self.assertEqual(summary["confidence"], expected_confidence)

    def test_network_confidence_missing_block_maps_to_offline(self):
        run = clean_run(network_confidence_state=None)

        summary = evaluate_component_status("network_confidence", run, registry_context())

        self.assertEqual(summary["status"], "OFFLINE")
        self.assertEqual(summary["confidence"], "UNKNOWN")
        self.assertEqual(
            summary["reason"],
            "No Network Confidence block was persisted for this run.",
        )
        self.assertEqual(
            summary["recommendation"],
            "Investigate missing Network Confidence inputs.",
        )

    def test_network_confidence_unknown_state_has_distinct_warning_copy(self):
        run = clean_run(network_confidence_state="UNKNOWN")

        summary = evaluate_component_status("network_confidence", run, registry_context())

        self.assertEqual(summary["status"], "WARNING")
        self.assertEqual(summary["confidence"], "UNKNOWN")
        self.assertEqual(
            summary["reason"],
            "Network Confidence could not be evaluated from the latest run data.",
        )
        self.assertEqual(
            summary["recommendation"],
            "Investigate missing Network Confidence inputs.",
        )

    def test_network_confidence_component_builds_with_expected_metadata(self):
        context = build_operations_center(clean_run(), registry_context())
        components = {component["key"]: component for component in context["components"]}

        self.assertIn("network_confidence", components)
        self.assertEqual(components["network_confidence"]["title"], "Network Confidence")
        self.assertEqual(
            components["network_confidence"]["detail_anchor"],
            "evidence-network",
        )

    def test_network_confidence_component_copy_does_not_forward_raw_diagnostics(self):
        run = clean_run(network_confidence_state="LOW")
        summary = evaluate_component_status("network_confidence", run, registry_context())

        rendered_copy = " ".join([summary["reason"], summary["recommendation"]])
        for raw_fragment in (
            "QUARANTINE",
            "WATCH",
            "NETWORK_CRITICAL",
            "NETWORK_DEGRADED",
            "persisted",
        ):
            self.assertNotIn(raw_fragment, rendered_copy)
        self.assertNotIn("supporting_factors", summary)
        self.assertNotIn("limiting_factors", summary)

    def test_watch_sources_downgrade_overall_rollup_via_network_confidence(self):
        run = clean_run(network_confidence_state="MODERATE")
        run["source_intelligence"]["source_reliability"]["summary"]["watch_count"] = 2
        run["source_intelligence"]["source_reliability"]["summary"]["stable_count"] = 0

        context = build_operations_center(run, registry_context())

        self.assertEqual(context["overall"]["status"], "LIMITED")
        self.assertIn("Network Confidence is LIMITED", context["overall"]["reason"])

    def test_minimal_coverage_downgrades_overall_rollup_via_network_confidence(self):
        run = clean_run(network_confidence_state="LOW")
        run["source_intelligence"]["coverage_intelligence"]["per_narrative"] = [
            {"narrative_id": "AI", "coverage_state": "MINIMAL"}
        ]

        context = build_operations_center(run, registry_context())

        self.assertEqual(context["overall"]["status"], "DEGRADED")
        self.assertIn("Network Confidence is DEGRADED", context["overall"]["reason"])

    def test_healthy_network_confidence_preserves_healthy_rollup(self):
        context = build_operations_center(
            clean_run(network_confidence_state="HIGH"), registry_context()
        )

        self.assertEqual(context["overall"]["status"], "EXCELLENT")

    def test_source_reliability_quarantine_recommended_maps_to_warning(self):
        run = clean_run()
        run["source_intelligence"]["source_reliability"]["summary"] = {
            "stable_count": 0,
            "watch_count": 0,
            "repeated_failure_count": 0,
            "quarantine_recommended_count": 1,
            "unknown_count": 0,
        }

        summary = evaluate_component_status("source_reliability", run, registry_context())

        self.assertEqual(summary["status"], "WARNING")
        self.assertEqual(
            summary["recommendation"],
            "Review sources recommended for quarantine in Source Reliability.",
        )

    def test_platform_observability_mapping(self):
        run = clean_run()
        self.assertEqual(
            evaluate_component_status("pipeline", run, registry_context())["status"],
            "EXCELLENT",
        )
        run["platform_observability"]["stages"][0]["status"] = "FAILED"
        self.assertEqual(
            evaluate_component_status("pipeline", run, registry_context())["status"],
            "CRITICAL",
        )
        missing = clean_run()
        missing.pop("platform_observability")
        summary = evaluate_component_status("pipeline", missing, registry_context())
        self.assertEqual(summary["status"], "OFFLINE")
        self.assertEqual(summary["confidence"], "UNKNOWN")

    def test_configuration_mapping(self):
        clean = evaluate_component_status("configuration", clean_run(), registry_context())
        failed = evaluate_component_status(
            "configuration",
            clean_run(),
            registry_context("registry missing source_reliability_thresholds"),
        )

        self.assertEqual(clean["status"], "EXCELLENT")
        self.assertEqual(failed["status"], "CRITICAL")
        self.assertIn("Fix registry/configuration errors", failed["recommendation"])

    def test_recommendations_are_deterministic_and_fixed(self):
        run = clean_run()
        run["source_intelligence"]["source_health"][0]["severity"] = "CRITICAL"
        run["source_intelligence"]["source_health"][0]["state"] = "BLOCKED"
        run["source_intelligence"]["source_freshness"][0]["status"] = "UNKNOWN"
        run["source_intelligence"]["source_reliability"]["summary"] = {
            "stable_count": 0,
            "watch_count": 1,
            "repeated_failure_count": 1,
            "quarantine_recommended_count": 0,
            "unknown_count": 0,
        }
        run["source_intelligence"]["network_health"]["network_status"] = "NETWORK_PARTIAL"
        run["source_intelligence"]["network_health"]["categories"].append(
            {
                "category": "ETFs",
                "category_state": "UNCOVERED",
                "single_provider_dependency": False,
            }
        )

        first = build_operations_center(run, registry_context())
        second = build_operations_center(copy.deepcopy(run), registry_context())

        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertIn("Review stale sources in Feed Health.", first["recommendations"])
        self.assertIn(
            "Review sources marked WATCH in Source Reliability.",
            first["recommendations"],
        )
        self.assertIn(
            "Review sources with repeated failures in Source Reliability.",
            first["recommendations"],
        )
        self.assertIn(
            "Review Evidence Network categories marked UNCOVERED.",
            first["recommendations"],
        )

    def test_missing_data_blocks_do_not_crash(self):
        for key in (
            "source_confidence",
            "network_confidence",
            "network_health",
            "source_reliability",
            "platform_observability",
        ):
            run = clean_run()
            if key == "platform_observability":
                run.pop("platform_observability")
            else:
                run["source_intelligence"].pop(key)
            context = build_operations_center(run, registry_context())

            self.assertIn("overall", context)
            self.assertEqual(len(context["components"]), 8)

    def test_coverage_status_reflects_measurement_not_breadth(self):
        run = clean_run()
        run["source_intelligence"]["coverage_intelligence"]["per_narrative"] = [
            {"narrative_id": "AI", "coverage_state": "MINIMAL"}
        ]

        summary = evaluate_component_status("coverage_intelligence", run, registry_context())

        self.assertEqual(summary["status"], "EXCELLENT")
        self.assertIn("broadest at MINIMAL", summary["reason"])

    def test_admin_renders_operations_center_above_existing_sections(self):
        run = clean_run()
        run_path = Path("/tmp/2026-07-09_120000.json")
        with (
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = (
                registry_context()["configuration_report"]
            )
            view = dashboard.build_view_model(run, run_path)

        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("admin.html").render(
                request=object(),
                results_dir="/tmp/results",
                recent_runs=[{"filename": run_path.name, "label": "07/09 12:00"}],
                selected_file=run_path.name,
                message=None,
                view=view,
            )
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn("Operations Center", html)
        self.assertIn("Platform Operations Summary", html)
        self.assertIn("Network Confidence", html)
        self.assertIn("The evidence network is strong enough to support today&#39;s read.", html)
        self.assertLess(html.index("Platform Operations Summary"), html.index("Active Data Directory"))
        self.assertLess(html.index("Platform Operations Summary"), html.index("Pipeline Telemetry"))
        self.assertIn("Source Confidence (data collection quality)", html)
        self.assertIn("Coverage Intelligence", html)
        self.assertIn(
            "2 source(s) were marked QUARANTINE_RECOMMENDED from persisted NETWORK_CRITICAL.",
            html,
        )
        self.assertIn("Watch Count Threshold", html)
        self.assertNotIn("alarm", html.lower())

    def test_dashboard_trust_summary_is_unchanged_by_operations_center_integration(self):
        run = clean_run(network_confidence_state="MODERATE")

        summary = build_dashboard_trust_summary(run)

        self.assertEqual(summary["state"], "Usable evidence base")
        self.assertEqual(summary["confidence"], "High")
        self.assertIn("Evidence network: Moderate", summary["facts"])

    def test_research_workspace_templates_do_not_reference_operations_center(self):
        selector = Path("templates/research_selector.html").read_text(encoding="utf-8")
        investigation = Path("templates/narrative_investigation.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("operations_center", selector)
        self.assertNotIn("operations_center", investigation)

    def test_research_workspace_module_does_not_reference_operations_center(self):
        import mne.research_workspace as research_workspace

        self.assertNotIn("operations_center", inspect.getsource(research_workspace))

    def test_user_dashboard_route_context_does_not_include_operations_center_markup(self):
        run = clean_run()
        with (
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = (
                registry_context()["configuration_report"]
            )
            view = dashboard.build_view_model(run, Path("/tmp/2026-07-09_120000.json"))

        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("dashboard.html").render(
                request=object(),
                message=None,
                notice=None,
                view=view,
                recent_runs=[],
                selected_file=None,
                regime_history={},
                narrative_leadership_history={},
            )
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertNotIn("Platform Operations Summary", html)
        self.assertNotIn("What needs attention", html)


if __name__ == "__main__":
    unittest.main()
