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
        self.assertIn("NETWORK_PARTIAL", html)
        self.assertIn("Federal Reserve contributed", html)
        self.assertIn("UNCOVERED", html)
        self.assertNotIn("klaxon", html.lower())
        self.assertNotIn("alarm", html.lower())


if __name__ == "__main__":
    unittest.main()
