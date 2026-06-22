import io
import json
import unittest
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

    def build_environment(self):
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
                catalysts_file=self.manual_path,
                enable_auto_company_catalysts=False,
                enable_auto_macro_catalysts=True,
            )

    def test_empty_calendar(self):
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "loaded_empty")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Quiet")
        self.assertEqual(result["density_score"], 0)

    def test_missing_calendar(self):
        self.calendar_path = self.root / "missing_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "missing_file")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Unavailable")
        self.assertEqual(result["density_score"], 0)

    def test_invalid_calendar(self):
        self.calendar_path = self.root / "invalid_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "invalid_json")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Calendar Error")
        self.assertEqual(result["density_score"], 0)

    def test_valid_future_event(self):
        self.calendar_path = self.root / "future_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "loaded_with_events")
        self.assertFalse(result["macro_calendar_warning"])
        self.assertEqual(result["macro_calendar_event_count"], 1)
        self.assertEqual(result["macro_calendar_latest_event_date"], "2099-01-01")
        self.assertEqual(result["density_score"], 0)

    def test_historical_calendar(self):
        self.calendar_path = self.root / "historical_calendar.json"
        result = self.build_environment()
        self.assertEqual(result["macro_calendar_status"], "stale_calendar")
        self.assertTrue(result["macro_calendar_warning"])
        self.assertEqual(result["state"], "Quiet")
        self.assertEqual(result["density_score"], 0)

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
