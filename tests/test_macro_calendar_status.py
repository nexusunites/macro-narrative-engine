import io
import json
import tempfile
import unittest
from datetime import date
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

import mne.catalysts as catalysts_module
from mne.macro_catalysts import get_auto_macro_calendar_catalysts
from mne.reporting import append_macro_calendar_status, print_macro_calendar_status


STATUS_FIELDS = {
    "macro_calendar_status",
    "macro_calendar_message",
    "macro_calendar_path",
    "macro_calendar_event_count",
    "macro_calendar_latest_event_date",
    "macro_calendar_warning",
}


class MacroCalendarStatusTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / "fixtures"
        self.calendar_path = self.root / "empty_calendar.json"
        self.manual_path = self.root / "manual_catalysts.json"

    def build_environment(self, *, as_of=None, manual_path=None, enable_auto_company=False):
        original_loader = get_auto_macro_calendar_catalysts

        def load_test_calendar(as_of=None, metadata=None):
            return original_loader(
                as_of=as_of,
                calendar_file=self.calendar_path,
                metadata=metadata,
            )

        with patch.object(
            catalysts_module,
            "get_auto_macro_calendar_catalysts",
            side_effect=load_test_calendar,
        ):
            return catalysts_module.calculate_catalyst_density(
                as_of=as_of,
                catalysts_file=manual_path or self.manual_path,
                enable_auto_company_catalysts=enable_auto_company,
                enable_auto_macro_catalysts=True,
            )

    def test_empty_calendar(self):
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "loaded_empty")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Unavailable")
        self.assertEqual(result["confidence"], "Low")
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["density_score"], 0)
        self.assertIn("not populated", result["reason"])

    def test_missing_calendar(self):
        self.calendar_path = self.root / "missing_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "missing_file")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Unavailable")
        self.assertEqual(result["confidence"], "Low")
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["density_score"], 0)
        self.assertIn("unavailable", result["reason"])

    def test_invalid_calendar(self):
        self.calendar_path = self.root / "invalid_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "invalid_json")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Unavailable")
        self.assertEqual(result["confidence"], "Low")
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["density_score"], 0)
        self.assertIn("could not be loaded", result["reason"])

    def test_valid_future_event(self):
        self.calendar_path = self.root / "future_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "loaded_with_events")
        self.assertFalse(result["macro_calendar_warning"])
        self.assertTrue(result["calendar_found"])
        self.assertEqual(result["macro_calendar_event_count"], 1)
        self.assertEqual(result["macro_calendar_latest_event_date"], "2099-01-01")
        self.assertEqual(result["state"], "Quiet")
        self.assertEqual(result["density_score"], 0)
        self.assertEqual(
            result["reason"],
            "No high-impact or medium-impact catalysts are approaching.",
        )

    def test_partial_calendar_cannot_claim_verified_quiet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.calendar_path = root / "macro_calendar.json"
            self.calendar_path.write_text(
                json.dumps(
                    [
                        {
                            "date": "2099-01-01",
                            "name": "Consumer Price Index",
                            "importance": "red",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "macro_calendar_metadata.json").write_text(
                json.dumps(
                    {
                        "status": "partial",
                        "generated_at": "2026-07-14T08:00:00-04:00",
                        "coverage_start": "2026-07-14",
                        "coverage_end": "2099-01-01",
                        "failed_sources": ["bea"],
                        "partial": True,
                    }
                ),
                encoding="utf-8",
            )
            result = self.build_environment(as_of=date(2026, 7, 14))

        self.assertEqual(result["macro_calendar_status"], "partial_calendar")
        self.assertNotEqual(result["state"], "Quiet")
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["confidence"], "Low")
        self.assertIn("partial", result["reason"])

    def test_historical_calendar(self):
        self.calendar_path = self.root / "historical_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "stale_calendar")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Stale")
        self.assertEqual(result["confidence"], "Low")
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["density_score"], 0)
        self.assertEqual(
            result["reason"],
            "Scheduled macro calendar data does not cover the current catalyst window.",
        )

    def test_cpi_empty_calendar_regression_does_not_return_quiet(self):
        result = self.build_environment(as_of=date(2026, 7, 14))
        self.assertEqual(result["macro_calendar_status"], "loaded_empty")
        self.assertNotEqual(result["state"], "Quiet")
        self.assertNotEqual(
            result["reason"],
            "No high-impact or medium-impact catalysts are approaching.",
        )
        self.assertFalse(result["calendar_found"])

    def test_upcoming_manual_catalyst_is_preserved_with_macro_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manual_path = Path(tmpdir) / "manual_catalysts.json"
            manual_path.write_text(
                json.dumps(
                    [
                        {
                            "date": "2026-07-14",
                            "name": "Manual Market Structure Event",
                            "importance": "red",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = self.build_environment(
                as_of=date(2026, 7, 14),
                manual_path=manual_path,
            )

        self.assertEqual(result["macro_calendar_status"], "loaded_empty")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["density_score"], 2)
        self.assertEqual(result["state"], "Moderate")
        self.assertEqual(len(result["red_events"]), 1)
        self.assertEqual(result["red_events"][0]["name"], "Manual Market Structure Event")
        self.assertIn("not populated", result["reason"])

    def test_company_catalyst_is_preserved_with_macro_warning(self):
        company_event = {
            "date": "2026-07-14",
            "name": "NVDA Earnings",
            "importance": "red",
            "source": "auto_company_earnings",
            "ticker": "NVDA",
        }
        with patch.object(
            catalysts_module,
            "get_auto_company_earnings_catalysts",
            return_value=[company_event],
        ):
            result = self.build_environment(
                as_of=date(2026, 7, 14),
                enable_auto_company=True,
            )

        self.assertEqual(result["macro_calendar_status"], "loaded_empty")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertFalse(result["calendar_found"])
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["density_score"], 2)
        self.assertEqual(result["state"], "Moderate")
        self.assertEqual(result["red_events"][0]["source"], "auto_company_earnings")
        self.assertIn("not populated", result["reason"])

    def test_status_serialization_and_output(self):
        result = self.build_environment()
        self.assertTrue(STATUS_FIELDS.issubset(result))
        restored = json.loads(json.dumps({"catalyst_environment": result}))
        self.assertTrue(STATUS_FIELDS.issubset(restored["catalyst_environment"]))

        terminal = io.StringIO()
        with redirect_stdout(terminal):
            print_macro_calendar_status(result)
        self.assertIn("Status: loaded_empty", terminal.getvalue())

        report_lines = []
        append_macro_calendar_status(report_lines, result)
        self.assertIn("  Status: loaded_empty", report_lines)

    def test_dashboard_warning_and_admin_fields(self):
        repo_root = Path(__file__).resolve().parents[1]
        environment = Environment(
            loader=FileSystemLoader(repo_root / "templates"),
            undefined=ChainableUndefined,
            autoescape=True,
        )
        environment.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"

        catalyst = {
            "macro_calendar_status": "loaded_empty",
            "macro_calendar_message": "Macro calendar loaded but contains no events.",
            "macro_calendar_path": "test/macro_calendar.json",
            "macro_calendar_event_count": 0,
            "macro_calendar_latest_event_date": None,
            "macro_calendar_warning": True,
        }
        view = {
            "catalyst_environment_card": {
                "macro_calendar_warning": True,
                "macro_calendar_message": catalyst["macro_calendar_message"],
            },
            "catalyst": catalyst,
            "headline_stats": {},
            "red_events": [],
            "orange_events": [],
            "theme_scores": [],
            "group_scores": [],
            "all_examples": {},
            "environment": {
                "Market Environment": {},
                "Positioning Environment": {},
            },
            "regime": {},
            "mode_context": {},
            "diagnostics": {},
            "run": {},
        }

        dashboard_html = environment.get_template("dashboard.html").render(view=view)
        self.assertIn("Calendar Notice", dashboard_html)
        self.assertIn(catalyst["macro_calendar_message"], dashboard_html)

        view["catalyst_environment_card"]["macro_calendar_warning"] = False
        dashboard_html = environment.get_template("dashboard.html").render(view=view)
        self.assertNotIn("Calendar Notice", dashboard_html)

        admin_html = environment.get_template("admin.html").render(view=view)
        for label in (
            "Status",
            "Message",
            "Path",
            "Events Loaded",
            "Latest Event Date",
            "Warning",
        ):
            self.assertIn(label, admin_html)


if __name__ == "__main__":
    unittest.main()
