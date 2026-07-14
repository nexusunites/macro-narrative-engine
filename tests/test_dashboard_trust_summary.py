import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.dashboard_trust_summary import (
    LIMITED,
    STRONG,
    THIN,
    UNAVAILABLE,
    USABLE,
    build_dashboard_trust_summary,
    normalize_user_facing_network_state,
)


def trust_run(
    source_confidence="HIGH",
    network_status="NETWORK_HEALTHY",
    accepted_count=18,
    coverage_state="BROAD",
    matched_headlines=8,
    network_confidence_state=None,
):
    coverage_counts = {
        "extensive_count": 0,
        "broad_count": 0,
        "moderate_count": 0,
        "limited_count": 0,
        "minimal_count": 0,
    }
    coverage_counts[f"{coverage_state.lower()}_count"] = 1
    source_intelligence = {
        "accepted_count": accepted_count,
        "accepted_evidence": [
            {"source_id": "s1", "provider": "Provider One"},
            {"source_id": "s2", "provider": "Provider Two"},
            {"source_id": "s3", "provider": "Provider Three"},
        ],
        "evidence_funnel": {"accepted_fresh": accepted_count},
        "source_confidence": {
            "confidence_state": source_confidence,
            "thresholds_used": {"accepted_evidence_floor": 10},
        },
        "network_health": {
            "network_status": network_status,
            "providers": [
                {"provider": "Provider One"},
                {"provider": "Provider Two"},
                {"provider": "Provider Three"},
            ],
        },
        "coverage_intelligence": {
            "overall": {
                "provider_diversity": {"unique_provider_count": 3},
                "source_diversity": {"unique_source_count": 3},
                "coverage_summary": coverage_counts,
            },
            "per_narrative": [
                {
                    "narrative_level": "group",
                    "narrative_id": "AI / Tech Growth",
                    "coverage_state": coverage_state,
                }
            ],
        },
    }
    if network_confidence_state is not None:
        source_intelligence["network_confidence"] = {
            "network_confidence_state": network_confidence_state,
            "confidence_level": None,
            "reason": "Network Health persisted NETWORK_DEGRADED for this run.",
            "recommended_action": (
                "Review network health, source reliability, and coverage limits "
                "before relying on this run."
            ),
            "supporting_factors": ["Network Health: NETWORK_HEALTHY"],
            "limiting_factors": [
                "WATCH sources: 2",
                "QUARANTINE_RECOMMENDED sources: 1",
            ],
        }

    return {
        "timestamp": "2026-07-09_120000",
        "theme_scores": {"ai": 6},
        "group_scores": {"AI / Tech Growth": 6},
        "matched_headlines": matched_headlines,
        "source_intelligence": source_intelligence,
    }


class DashboardTrustSummaryTests(unittest.TestCase):
    def test_strong_evidence_base(self):
        summary = build_dashboard_trust_summary(trust_run())

        self.assertEqual(summary["state"], STRONG)
        self.assertEqual(summary["confidence"], "High")
        self.assertIn("Accepted evidence: 18", summary["facts"])
        self.assertIn("Network status: Healthy", summary["facts"])
        self.assertIn("Source confidence: High", summary["facts"])
        self.assertIn("Coverage: Broad", summary["facts"])

    def test_network_confidence_high_drives_strong_summary(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="LOW",
                network_status="NETWORK_DEGRADED",
                coverage_state="LIMITED",
                network_confidence_state="HIGH",
            )
        )

        self.assertEqual(summary["state"], STRONG)
        self.assertEqual(summary["confidence"], "High")
        self.assertEqual(
            summary["reason"],
            "Today's read is supported by a strong evidence network.",
        )
        self.assertIn("Evidence network: Strong", summary["facts"])
        self.assertNotIn("Network status: Limited", summary["facts"])

    def test_network_confidence_moderate_drives_usable_summary(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="LOW",
                network_status="NETWORK_DEGRADED",
                coverage_state="LIMITED",
                network_confidence_state="MODERATE",
            )
        )

        self.assertEqual(summary["state"], USABLE)
        self.assertEqual(summary["confidence"], "High")
        self.assertIn("Evidence network: Moderate", summary["facts"])

    def test_network_confidence_low_drives_limited_summary(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="HIGH",
                network_status="NETWORK_HEALTHY",
                coverage_state="BROAD",
                network_confidence_state="LOW",
            )
        )

        self.assertEqual(summary["state"], LIMITED)
        self.assertEqual(summary["confidence"], "High")
        self.assertIn("Evidence network: Limited", summary["facts"])

    def test_network_confidence_very_low_drives_thin_summary(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="HIGH",
                network_status="NETWORK_HEALTHY",
                coverage_state="BROAD",
                network_confidence_state="VERY_LOW",
            )
        )

        self.assertEqual(summary["state"], THIN)
        self.assertEqual(summary["confidence"], "High")
        self.assertIn("Evidence network: Thin", summary["facts"])

    def test_network_confidence_unknown_falls_back_to_existing_heuristic(self):
        with_unknown = build_dashboard_trust_summary(
            trust_run(network_confidence_state="UNKNOWN")
        )
        without_network_confidence = build_dashboard_trust_summary(trust_run())

        self.assertEqual(with_unknown, without_network_confidence)
        self.assertEqual(with_unknown["state"], STRONG)
        self.assertIn("Network status: Healthy", with_unknown["facts"])
        self.assertNotIn("Evidence network: Unknown", with_unknown["facts"])

    def test_missing_network_confidence_falls_back_to_existing_heuristic(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="MODERATE",
                network_status="NETWORK_PARTIAL",
                coverage_state="MODERATE",
            )
        )

        self.assertEqual(summary["state"], USABLE)
        self.assertEqual(summary["confidence"], "Moderate")
        self.assertIn("Network status: Partial", summary["facts"])
        self.assertNotIn("Evidence network: Moderate", summary["facts"])

    def test_usable_evidence_base_with_moderate_source_confidence(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="MODERATE",
                network_status="NETWORK_PARTIAL",
                coverage_state="MODERATE",
            )
        )

        self.assertEqual(summary["state"], USABLE)
        self.assertEqual(summary["confidence"], "Moderate")
        self.assertIn("Network status: Partial", summary["facts"])
        self.assertIn("Source confidence: Moderate", summary["facts"])

    def test_limited_evidence_base_when_moderate_confidence_has_weak_coverage(self):
        summary = build_dashboard_trust_summary(
            trust_run(
                source_confidence="MODERATE",
                network_status="NETWORK_PARTIAL",
                accepted_count=7,
                coverage_state="LIMITED",
            )
        )

        self.assertEqual(summary["state"], LIMITED)
        self.assertEqual(summary["confidence"], "Moderate")

    def test_limited_evidence_base_for_degraded_network(self):
        summary = build_dashboard_trust_summary(
            trust_run(network_status="NETWORK_DEGRADED", coverage_state="MODERATE")
        )

        self.assertEqual(summary["state"], LIMITED)
        self.assertIn("Network status: Limited", summary["facts"])

    def test_thin_evidence_base_for_low_evidence(self):
        summary = build_dashboard_trust_summary(
            trust_run(source_confidence="LOW", accepted_count=1, coverage_state="MINIMAL")
        )

        self.assertEqual(summary["state"], THIN)
        self.assertEqual(summary["confidence"], "Moderate")

    def test_data_unavailable_without_supported_facts(self):
        summary = build_dashboard_trust_summary({"timestamp": "2026-07-09_120000"})

        self.assertEqual(summary["state"], UNAVAILABLE)
        self.assertEqual(summary["confidence"], "Low")
        self.assertEqual(summary["facts"], [])

    def test_missing_optional_blocks_do_not_crash(self):
        run = trust_run()
        run["source_intelligence"].pop("evidence_funnel")
        run["source_intelligence"].pop("coverage_intelligence")

        summary = build_dashboard_trust_summary(run)

        self.assertIn(summary["state"], {USABLE, LIMITED, STRONG})
        self.assertIn("Accepted evidence: 18", summary["facts"])

    def test_latest_meaningful_fallback_maps_to_thin_with_notice_copy(self):
        summary = build_dashboard_trust_summary(
            trust_run(network_confidence_state="HIGH"),
            latest_meaningful_fallback_active=True,
        )

        self.assertEqual(summary["state"], THIN)
        self.assertEqual(summary["confidence"], "Low")
        self.assertIn("latest meaningful run", summary["reason"])
        self.assertIn(
            "Today's read is thin because accepted fresh evidence or matched narrative coverage was low.",
            summary["reason"],
        )

    def test_user_facing_copy_avoids_alarmist_and_admin_only_words(self):
        summary = build_dashboard_trust_summary(
            trust_run(source_confidence="LOW", network_status="NETWORK_DEGRADED")
        )
        rendered = " ".join([summary["state"], summary["confidence"], summary["reason"]] + summary["facts"])

        for word in (
            "bad",
            "broken",
            "danger",
            "critical",
            "unreliable",
            "failure",
            "panic",
            "unsafe",
            "threshold",
            "registry",
            "quarantine",
        ):
            self.assertNotIn(word, rendered.lower())

    def test_network_confidence_user_facing_copy_avoids_raw_enums_and_market_language(self):
        forbidden_raw_tokens = (
            "HIGH",
            "MODERATE",
            "LOW",
            "VERY_LOW",
            "NETWORK_HEALTHY",
            "NETWORK_DEGRADED",
            "QUARANTINE_RECOMMENDED",
        )
        forbidden_language = (
            "predict",
            "forecast",
            "bullish",
            "bearish",
            "trade",
            "panic",
            "danger",
            "critical",
        )

        for state in ("HIGH", "MODERATE", "LOW", "VERY_LOW"):
            summary = build_dashboard_trust_summary(
                trust_run(network_confidence_state=state)
            )
            rendered = " ".join(
                [summary["state"], summary["confidence"], summary["reason"]]
                + summary["facts"]
            )
            for text in forbidden_raw_tokens:
                self.assertNotIn(text, rendered)
            for text in forbidden_language:
                self.assertNotIn(text.lower(), rendered.lower())

    def test_network_confidence_admin_fields_never_leak_to_dashboard_output(self):
        summary = build_dashboard_trust_summary(
            trust_run(network_confidence_state="LOW")
        )
        rendered = " ".join(
            [summary["state"], summary["confidence"], summary["reason"]]
            + summary["facts"]
        )

        for text in (
            "Network Health persisted",
            "Review network health",
            "WATCH sources:",
            "QUARANTINE_RECOMMENDED",
            "NETWORK_DEGRADED",
            "Network Health: NETWORK_HEALTHY",
        ):
            self.assertNotIn(text, rendered)

    def test_dashboard_template_renders_network_confidence_summary_end_to_end(self):
        latest_path = Path("/tmp/2026-07-09_120000.json")
        run = trust_run(network_confidence_state="MODERATE")

        with (
            patch.object(dashboard, "list_result_files", return_value=[latest_path]),
            patch.object(dashboard, "list_all_result_files", return_value=[latest_path]),
            patch.object(dashboard, "list_regime_history_files", return_value=[]),
            patch.object(dashboard, "load_result", return_value=run),
            patch.object(dashboard, "build_narrative_leadership_history", return_value={}),
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = {}
            context = dashboard.build_template_context(object(), run=None)

        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("dashboard.html").render(
                **context
            )
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn("Usable evidence base", html)
        self.assertIn("Evidence network: Moderate", html)
        self.assertNotIn("Network status:", html)
        self.assertNotIn("NETWORK_DEGRADED", html)

    def test_network_partial_normalizes_calmly(self):
        self.assertEqual(
            normalize_user_facing_network_state("NETWORK_PARTIAL"),
            "Partial",
        )

    def test_dashboard_context_renders_banner_with_latest_run_notice(self):
        latest_path = Path("/tmp/2026-07-09_120000.json")
        meaningful_path = Path("/tmp/2026-07-08_120000.json")
        runs = {
            latest_path.name: {
                "timestamp": "2026-07-09_120000",
                "theme_scores": {"ai": 0},
                "group_scores": {"AI / Tech Growth": 0},
            },
            meaningful_path.name: trust_run(),
        }

        with (
            patch.object(dashboard, "list_result_files", return_value=[latest_path, meaningful_path]),
            patch.object(dashboard, "list_all_result_files", return_value=[latest_path, meaningful_path]),
            patch.object(dashboard, "list_regime_history_files", return_value=[]),
            patch.object(dashboard, "load_result", side_effect=lambda path: runs[path.name]),
            patch.object(dashboard, "build_narrative_leadership_history", return_value={}),
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = {}
            context = dashboard.build_template_context(object(), run=None)

        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("dashboard.html").render(**context)
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn("Data Quality", html)
        self.assertIn("Thin evidence base", html)
        self.assertIn("latest meaningful run", html)
        self.assertIn("View operational details in Admin", html)
        self.assertNotIn("Platform Operations Summary", html)


if __name__ == "__main__":
    unittest.main()
