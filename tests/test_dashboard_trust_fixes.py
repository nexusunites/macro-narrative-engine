import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.operating_modes import generate_macro_context


class DashboardTrustFixTests(unittest.TestCase):
    def test_macro_context_fallback_does_not_repeat_market_context(self):
        context = generate_macro_context(
            dominant_theme=None,
            dominant_group="AI / Tech Growth",
            narrative_signals={},
            market_environment=None,
            narrative_market_relationship=None,
            breadth_confirmation=None,
            catalyst_environment=None,
            positioning_environment=None,
            regime_alignment=None,
            market_snapshot={},
        )

        self.assertEqual(
            context["read"],
            (
                "AI / Tech Growth is the dominant narrative group, while market "
                "context is unclear and breadth is unclear."
            ),
        )
        self.assertNotIn("market context is market confirmation", context["read"])

    def test_run_options_use_human_readable_labels_with_filename_values(self):
        paths = [
            Path("/tmp/2026-07-07_114250.json"),
            Path("/tmp/manual_run.json"),
        ]

        with patch.object(dashboard, "fmt_file_timestamp", return_value="2026-07-07 12:00"):
            options = dashboard.build_run_options(paths)

        self.assertEqual(
            options,
            [
                {"filename": "2026-07-07_114250.json", "label": "07/07 11:42"},
                {
                    "filename": "manual_run.json",
                    "label": "manual_run (modified 2026-07-07 12:00)",
                },
            ],
        )

    def test_regime_history_summary_names_latest_move_separately(self):
        paths = [
            Path("/tmp/2026-07-04_090000.json"),
            Path("/tmp/2026-07-05_090000.json"),
            Path("/tmp/2026-07-06_090000.json"),
            Path("/tmp/2026-07-07_090000.json"),
        ]
        scores_by_name = {
            "2026-07-04_090000.json": 50,
            "2026-07-05_090000.json": 60,
            "2026-07-06_090000.json": 70,
            "2026-07-07_090000.json": 62,
        }

        def load_result(path):
            return {
                "timestamp": path.stem,
                "regime_alignment": {"score": scores_by_name[path.name]},
            }

        with patch.object(dashboard, "list_regime_history_files", return_value=list(reversed(paths))):
            with patch.object(dashboard, "load_result", side_effect=load_result):
                history = dashboard.build_regime_history()

        self.assertEqual(
            history["summary"],
            "Alignment higher over the recent window; latest move down.",
        )

    def test_admin_renders_evidence_network_section_neutrally(self):
        run_path = Path("/tmp/2026-07-08_120000.json")
        run = {
            "timestamp": "2026-07-08_120000",
            "source_intelligence": {
                "source_confidence": {
                    "confidence_state": "LOW",
                    "confidence_level": None,
                    "reason": "Only 6 of 16 active sources contributed accepted evidence.",
                    "contributing_factors": [
                        "Contribution ratio: 6/16 = 0.38",
                        "cnbc-top-news: BLOCKED",
                    ],
                    "recommended_action": "Review active sources that did not contribute accepted evidence.",
                    "thresholds_used": {
                        "accepted_evidence_floor": 10,
                        "low_fetch_ratio": 0.50,
                        "low_contribution_ratio": 0.40,
                        "high_fetch_ratio": 0.85,
                        "high_freshness_ratio": 0.80,
                        "high_contribution_ratio": 0.70,
                    },
                },
                "source_reliability": {
                    "evaluation_window": {
                        "window_runs_configured": 5,
                        "runs_evaluated": 5,
                        "oldest_run_timestamp": "2026-07-04_120000",
                        "newest_run_timestamp": "2026-07-08_120000",
                    },
                    "thresholds_used": {
                        "source_reliability_window_runs": 5,
                        "minimum_required_runs": 3,
                        "repeated_failure_ratio": 0.50,
                        "quarantine_ratio": 0.80,
                    },
                    "summary": {
                        "stable_count": 1,
                        "watch_count": 1,
                        "repeated_failure_count": 0,
                        "quarantine_recommended_count": 1,
                        "unknown_count": 0,
                    },
                    "sources": [
                        {
                            "source_id": "wsj-markets",
                            "source_name": "WSJ Markets",
                            "provider": "Wall Street Journal",
                            "category": "Market Structure",
                            "registry_status": "DISABLED",
                            "runs_observed": 5,
                            "healthy_runs": 1,
                            "stale_runs": 4,
                            "blocked_runs": 0,
                            "empty_runs": 0,
                            "malformed_runs": 0,
                            "error_runs": 0,
                            "contributing_runs": 1,
                            "non_contributing_runs": 4,
                            "latest_state": "HEALTHY",
                            "reliability_state": "QUARANTINE_RECOMMENDED",
                            "reason": "Stale in 4 of 5 observed runs; 4 weak run(s) total.",
                            "recommended_action": "Review for disabling or replacement; source appears persistently stale.",
                        },
                        {
                            "source_id": "cnbc-top-news",
                            "source_name": "CNBC Top News",
                            "provider": "CNBC",
                            "category": "General Business",
                            "registry_status": "ACTIVE",
                            "runs_observed": 5,
                            "healthy_runs": 4,
                            "stale_runs": 0,
                            "blocked_runs": 1,
                            "empty_runs": 0,
                            "malformed_runs": 0,
                            "error_runs": 0,
                            "contributing_runs": 4,
                            "non_contributing_runs": 1,
                            "latest_state": "HEALTHY",
                            "reliability_state": "WATCH",
                            "reason": "Blocked in 1 of 5 observed runs; 1 weak run(s) total.",
                            "recommended_action": "Monitor access restrictions in upcoming runs.",
                        },
                    ],
                },
                "network_health": {
                    "network_status": "NETWORK_PARTIAL",
                    "providers": [
                        {
                            "provider": "Federal Reserve",
                            "sources_total": 2,
                            "sources_healthy": 2,
                            "sources_degraded": 0,
                            "evidence_contributed": 3,
                            "provider_state": "HEALTHY",
                        }
                    ],
                    "categories": [
                        {
                            "category": "Rates",
                            "providers_total": 1,
                            "providers_healthy": 1,
                            "sources_total": 2,
                            "sources_healthy": 2,
                            "evidence_contributed": 3,
                            "single_provider_dependency": True,
                            "category_state": "HEALTHY",
                        },
                        {
                            "category": "ETFs",
                            "providers_total": 0,
                            "providers_healthy": 0,
                            "sources_total": 0,
                            "sources_healthy": 0,
                            "evidence_contributed": 0,
                            "single_provider_dependency": False,
                            "category_state": "UNCOVERED",
                        },
                    ],
                    "concentration": {
                        "total_accepted_evidence": 3,
                        "provider_shares": [
                            {
                                "provider": "Federal Reserve",
                                "evidence_count": 3,
                                "share": 1.0,
                            }
                        ],
                        "top_provider": "Federal Reserve",
                        "top_provider_share": 1.0,
                        "concentration_flag": True,
                    },
                    "thresholds_used": {
                        "concentration_threshold": 0.40,
                        "evidence_floor": 5,
                    },
                }
            },
        }

        with (
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = {}
            view = dashboard.build_view_model(run, run_path)
            original_url_for = dashboard.templates.env.globals.get("url_for")
            dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
            try:
                html = dashboard.templates.env.get_template("admin.html").render(
                    request=object(),
                    results_dir="/tmp/results",
                    recent_runs=[
                        {
                            "filename": run_path.name,
                            "label": "07/08 12:00",
                        }
                    ],
                    selected_file=run_path.name,
                    message=None,
                    view=view,
                )
            finally:
                if original_url_for is None:
                    dashboard.templates.env.globals.pop("url_for", None)
                else:
                    dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn("Evidence Network", html)
        self.assertIn("Source Confidence (data collection quality)", html)
        self.assertIn("Source Reliability / Quarantine Tracking", html)
        self.assertIn("Quarantine Recommended", html)
        self.assertIn("Recommended Action", html)
        self.assertIn("Review for disabling or replacement; source appears persistently stale.", html)
        self.assertIn("Only 6 of 16 active sources contributed accepted evidence.", html)
        self.assertIn("Review active sources that did not contribute accepted evidence.", html)
        self.assertIn("NETWORK_PARTIAL", html)
        self.assertIn("Federal Reserve contributed", html)
        self.assertIn("UNCOVERED", html)
        self.assertNotIn("Quarantined", html)
        self.assertNotIn("klaxon", html.lower())
        self.assertNotIn("alarm", html.lower())

    def test_user_dashboard_does_not_render_source_confidence_admin_section(self):
        run = {
            "timestamp": "2026-07-08_120000",
            "source_intelligence": {
                "source_confidence": {
                    "confidence_state": "LOW",
                    "reason": "Admin-only diagnostic.",
                }
            },
        }
        with (
            patch.object(dashboard, "build_configuration_report"),
            patch.object(dashboard, "build_source_registry_diagnostics", return_value={}),
        ):
            dashboard.build_configuration_report.return_value.to_dict.return_value = {}
            view = dashboard.build_view_model(run, Path("/tmp/2026-07-08_120000.json"))

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

        self.assertNotIn("Source Confidence (data collection quality)", html)
        self.assertNotIn("Admin-only diagnostic.", html)


if __name__ == "__main__":
    unittest.main()
