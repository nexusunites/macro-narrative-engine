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
):
    coverage_counts = {
        "extensive_count": 0,
        "broad_count": 0,
        "moderate_count": 0,
        "limited_count": 0,
        "minimal_count": 0,
    }
    coverage_counts[f"{coverage_state.lower()}_count"] = 1
    return {
        "timestamp": "2026-07-09_120000",
        "theme_scores": {"ai": 6},
        "group_scores": {"AI / Tech Growth": 6},
        "matched_headlines": matched_headlines,
        "source_intelligence": {
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
        },
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
            trust_run(),
            latest_meaningful_fallback_active=True,
        )

        self.assertEqual(summary["state"], THIN)
        self.assertEqual(summary["confidence"], "Low")
        self.assertIn("latest meaningful run", summary["reason"])

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
