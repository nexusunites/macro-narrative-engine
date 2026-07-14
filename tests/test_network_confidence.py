import ast
import copy
import inspect
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dashboard
import main
from mne import historical_replay, research_workspace
from mne.network_confidence import (
    ACTION_BY_STATE,
    HIGH,
    LOW,
    MODERATE,
    UNKNOWN,
    VERY_LOW,
    build_network_confidence,
)


def source_intelligence(
    network_status="NETWORK_HEALTHY",
    source_confidence_state="HIGH",
    stable_count=5,
    watch_count=0,
    repeated_failure_count=0,
    quarantine_recommended_count=0,
    unknown_count=0,
    minimal_count=0,
    limited_count=0,
    moderate_count=0,
    broad_count=1,
    extensive_count=0,
):
    return {
        "network_health": {
            "network_status": network_status,
            "categories": [],
            "concentration": {"concentration_flag": False},
        },
        "source_confidence": {
            "confidence_state": source_confidence_state,
            "reason": f"{source_confidence_state} source confidence",
            "recommended_action": "No action needed.",
        },
        "source_reliability": {
            "summary": {
                "stable_count": stable_count,
                "watch_count": watch_count,
                "repeated_failure_count": repeated_failure_count,
                "quarantine_recommended_count": quarantine_recommended_count,
                "unknown_count": unknown_count,
            },
            "sources": [],
        },
        "coverage_intelligence": {
            "overall": {
                "coverage_summary": {
                    "minimal_count": minimal_count,
                    "limited_count": limited_count,
                    "moderate_count": moderate_count,
                    "broad_count": broad_count,
                    "extensive_count": extensive_count,
                }
            },
            "per_narrative": [],
        },
    }


def run_with_network_confidence():
    si = source_intelligence()
    si["network_confidence"] = build_network_confidence(si)
    return {
        "timestamp": "2026-07-14_120000",
        "raw_headline_count": 3,
        "deduped_headline_count": 3,
        "headline_count": 3,
        "matched_headlines": 2,
        "coverage_pct": 66.7,
        "theme_scores": {"AI": 2},
        "group_scores": {"AI / Tech Growth": 2},
        "source_intelligence": si,
        "platform_observability": {"stages": []},
    }


class NetworkConfidenceTests(unittest.TestCase):
    def test_high_when_all_inputs_are_strong(self):
        block = build_network_confidence(source_intelligence())

        self.assertEqual(block["network_confidence_state"], HIGH)
        self.assertEqual(block["recommended_action"], ACTION_BY_STATE[HIGH])
        self.assertIn("Network Health: NETWORK_HEALTHY", block["supporting_factors"])
        self.assertIn("BROAD/EXTENSIVE coverage records: 1", block["supporting_factors"])

    def test_unknown_when_coverage_intelligence_missing(self):
        diagnostics = source_intelligence()
        diagnostics.pop("coverage_intelligence")

        block = build_network_confidence(diagnostics)

        self.assertEqual(block["network_confidence_state"], UNKNOWN)
        self.assertIn("Missing required diagnostic: coverage_intelligence", block["limiting_factors"])
        self.assertEqual(block["recommended_action"], ACTION_BY_STATE[UNKNOWN])

    def test_unknown_when_source_confidence_state_is_unknown(self):
        block = build_network_confidence(
            source_intelligence(source_confidence_state="UNKNOWN")
        )

        self.assertEqual(block["network_confidence_state"], UNKNOWN)
        self.assertIn("input diagnostic state was UNKNOWN", block["reason"])

    def test_network_critical_first_match_forces_very_low(self):
        block = build_network_confidence(
            source_intelligence(
                network_status="NETWORK_CRITICAL",
                source_confidence_state="LOW",
                quarantine_recommended_count=3,
            )
        )

        self.assertEqual(block["network_confidence_state"], VERY_LOW)
        self.assertEqual(block["reason"], "Network Health persisted NETWORK_CRITICAL for this run.")

    def test_low_source_confidence_forces_very_low(self):
        block = build_network_confidence(
            source_intelligence(source_confidence_state="LOW")
        )

        self.assertEqual(block["network_confidence_state"], VERY_LOW)
        self.assertIn("Source Confidence persisted LOW", block["reason"])

    def test_quarantine_recommended_maps_to_low(self):
        block = build_network_confidence(
            source_intelligence(quarantine_recommended_count=1)
        )

        self.assertEqual(block["network_confidence_state"], LOW)
        self.assertIn("QUARANTINE_RECOMMENDED sources: 1", block["limiting_factors"])

    def test_degraded_network_maps_to_low(self):
        block = build_network_confidence(
            source_intelligence(network_status="NETWORK_DEGRADED")
        )

        self.assertEqual(block["network_confidence_state"], LOW)
        self.assertEqual(block["reason"], "Network Health persisted NETWORK_DEGRADED for this run.")

    def test_repeated_failure_maps_to_low(self):
        block = build_network_confidence(
            source_intelligence(repeated_failure_count=1)
        )

        self.assertEqual(block["network_confidence_state"], LOW)
        self.assertIn("REPEATED_FAILURE sources: 1", block["limiting_factors"])

    def test_minimal_coverage_maps_to_low(self):
        block = build_network_confidence(
            source_intelligence(minimal_count=1, broad_count=1)
        )

        self.assertEqual(block["network_confidence_state"], LOW)
        self.assertIn("MINIMAL coverage records: 1", block["limiting_factors"])

    def test_partial_network_maps_to_moderate(self):
        block = build_network_confidence(
            source_intelligence(network_status="NETWORK_PARTIAL")
        )

        self.assertEqual(block["network_confidence_state"], MODERATE)

    def test_moderate_source_confidence_maps_to_moderate(self):
        block = build_network_confidence(
            source_intelligence(source_confidence_state="MODERATE")
        )

        self.assertEqual(block["network_confidence_state"], MODERATE)

    def test_watch_threshold_maps_to_moderate(self):
        block = build_network_confidence(source_intelligence(watch_count=2))

        self.assertEqual(block["network_confidence_state"], MODERATE)
        self.assertIn("WATCH sources: 2", block["limiting_factors"])

    def test_no_broad_or_extensive_coverage_maps_to_moderate(self):
        block = build_network_confidence(
            source_intelligence(broad_count=0, moderate_count=2)
        )

        self.assertEqual(block["network_confidence_state"], MODERATE)
        self.assertIn("No BROAD or EXTENSIVE coverage records.", block["limiting_factors"])

    def test_first_match_precedence_is_deterministic(self):
        diagnostics = source_intelligence(
            network_status="NETWORK_DEGRADED",
            repeated_failure_count=1,
            minimal_count=1,
        )

        first = build_network_confidence(diagnostics)
        second = build_network_confidence(copy.deepcopy(diagnostics))

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first["reason"], "Network Health persisted NETWORK_DEGRADED for this run.")

    def test_fixed_action_mapping_for_all_states(self):
        cases = [
            (source_intelligence(), HIGH),
            (source_intelligence(network_status="NETWORK_PARTIAL"), MODERATE),
            (source_intelligence(repeated_failure_count=1), LOW),
            (source_intelligence(network_status="NETWORK_CRITICAL"), VERY_LOW),
            ({}, UNKNOWN),
        ]

        for diagnostics, expected_state in cases:
            block = build_network_confidence(diagnostics)
            self.assertEqual(block["network_confidence_state"], expected_state)
            self.assertEqual(block["recommended_action"], ACTION_BY_STATE[expected_state])

    def test_reuses_reliability_summary_without_walking_sources(self):
        diagnostics = source_intelligence()
        diagnostics["source_reliability"]["sources"] = [
            {"reliability_state": "QUARANTINE_RECOMMENDED"}
        ]

        block = build_network_confidence(diagnostics)

        self.assertEqual(block["network_confidence_state"], HIGH)
        self.assertNotIn("QUARANTINE_RECOMMENDED sources: 1", block["limiting_factors"])

    def test_build_does_not_mutate_source_intelligence(self):
        diagnostics = source_intelligence()
        before = copy.deepcopy(diagnostics)

        build_network_confidence(diagnostics)

        self.assertEqual(diagnostics, before)

    def test_schema_persists_expected_fields(self):
        block = build_network_confidence(source_intelligence())

        self.assertEqual(
            set(block),
            {
                "network_confidence_state",
                "confidence_level",
                "reason",
                "recommended_action",
                "supporting_factors",
                "limiting_factors",
                "thresholds_used",
                "inputs",
            },
        )
        self.assertIsNone(block["confidence_level"])
        self.assertIn("network_status", block["inputs"])

    def test_main_integrates_network_confidence_after_source_reliability(self):
        source = inspect.getsource(main)
        tree = ast.parse(source)
        call_names = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]

        self.assertIn("build_network_confidence", call_names)
        self.assertEqual(call_names.count("build_network_confidence"), 2)
        first_reliability = call_names.index("build_source_reliability")
        first_confidence = call_names.index("build_network_confidence")
        self.assertLess(first_reliability, first_confidence)

    def test_admin_renders_network_confidence_card(self):
        run = run_with_network_confidence()
        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("admin.html").render(
                request=object(),
                results_dir="/tmp/results",
                recent_runs=[],
                selected_file="2026-07-14_120000.json",
                message=None,
                view=SimpleNamespace(
                    run=run,
                    current_file="2026-07-14_120000.json",
                    file_timestamp=None,
                    last_updated="2026-07-14 12:00",
                    raw_json="{}",
                    summary={},
                    regime={},
                    mode_context={},
                    market_environment_card={},
                    market_expression=None,
                    catalyst_environment_card={},
                    event_lifecycle={},
                    positioning_environment_card={},
                    environment={
                        "Market Environment": None,
                        "Narrative / Market Relationship": None,
                        "Breadth Confirmation": None,
                        "Catalyst Environment": {},
                        "Positioning Environment": None,
                        "Narrative Crowding Risk": None,
                    },
                    theme_scores=[],
                    group_scores=[],
                    narrative_leadership=[],
                    dominant_share=None,
                    concentration_gap=None,
                    market_context={},
                    narrative_brief=None,
                    narrative_memory={},
                    narrative_brief_evidence_rows=[],
                    narrative_brief_error=None,
                    catalyst={},
                    red_events=[],
                    orange_events=[],
                    examples={},
                    all_examples={},
                    headline_stats={},
                    source_intelligence=run["source_intelligence"],
                    evidence_quality={"coverage": {}, "per_narrative": []},
                    platform_observability={
                        "run_metadata": {},
                        "stages": [],
                        "stages_by_duration": [],
                        "engine_versions": {},
                        "evidence_flow": {},
                    },
                    configuration_report={},
                    source_registry={},
                    operations_center={
                        "overall": {
                            "status": "GOOD",
                            "confidence": "HIGH",
                            "reason": "ok",
                            "recommendation": "No action needed.",
                        },
                        "recommendations": [],
                        "working": [],
                        "needs_attention": [],
                        "components": [],
                    },
                    theme_match_audit=None,
                    diagnostics={},
                ),
                historical_replay_console={
                    "form": {},
                    "recent_replays": {"files": [], "error": None},
                    "result": None,
                    "error": None,
                    "message": None,
                },
            )
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn("Network Confidence", html)
        self.assertIn("Evidence network inputs are healthy", html)
        self.assertIn("Watch Count Threshold", html)

    def test_dashboard_template_does_not_add_network_confidence_card(self):
        template = Path("templates/dashboard.html").read_text(encoding="utf-8")

        self.assertNotIn("Network Confidence", template)
        self.assertNotIn("network_confidence", template)

    def test_research_workspace_does_not_read_network_confidence(self):
        selector = research_workspace.build_narrative_selector(
            {
                "theme_scores": {"AI": 1},
                "group_scores": {"AI / Tech Growth": 2},
                "source_intelligence": {"network_confidence": {"network_confidence_state": HIGH}},
            }
        )

        self.assertEqual([item["key"] for item in selector], ["group:AI / Tech Growth", "theme:AI"])
        self.assertNotIn("network_confidence", inspect.getsource(research_workspace))

    def test_historical_replay_does_not_build_network_confidence(self):
        replay_source = inspect.getsource(historical_replay)

        self.assertNotIn("network_confidence", replay_source)
        self.assertNotIn("build_network_confidence", replay_source)

    def test_module_does_not_import_fetching_or_llm_paths(self):
        import mne.network_confidence as network_confidence

        module_source = inspect.getsource(network_confidence)

        self.assertNotIn("fetch_headlines_from_rss", module_source)
        self.assertNotIn("openai", module_source.lower())
        self.assertNotIn("llm", module_source.lower())


if __name__ == "__main__":
    unittest.main()
