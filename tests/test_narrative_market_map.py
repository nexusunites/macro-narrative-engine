import json
import tempfile
import unittest
from pathlib import Path

import dashboard
from mne.reporting import build_daily_report


ROOT = Path(__file__).resolve().parents[1]


def minimal_run(**extra):
    run = {
        "timestamp": "2026-08-04T12:00:00+00:00",
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "theme_scores": {"ai": 4},
        "group_scores": {"AI / Tech Growth": 4},
        "market_snapshot": {},
    }
    run.update(extra)
    return run


class LegacyNarrativeMarketMapRetirementTests(unittest.TestCase):
    def test_active_source_has_no_legacy_import_call_or_run_key_dependency(self):
        active_paths = [ROOT / "main.py", ROOT / "dashboard.py"]
        active_paths.extend((ROOT / "mne").glob("*.py"))
        for path in active_paths:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("narrative_market_map", source, path)
            self.assertNotIn("get_market_expression", source, path)
            self.assertNotIn('run["market_expression"]', source, path)
            self.assertNotIn("run['market_expression']", source, path)

    def test_templates_and_static_assets_do_not_require_legacy_run_key(self):
        paths = list((ROOT / "templates").rglob("*.html"))
        paths.extend((ROOT / "static").rglob("*.js"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("run.market_expression", source, path)
            self.assertNotIn("view.market_expression ", source, path)
            self.assertNotIn("view.market_expression\n", source, path)

    def test_old_artifacts_with_or_without_legacy_field_still_load(self):
        old_with_field = minimal_run(
            market_expression={"mapped": True, "primary": ["NVDA"]},
            unknown_legacy_field={"harmless": True},
        )
        old_without_field = minimal_run()
        with tempfile.TemporaryDirectory() as directory:
            for index, expected in enumerate((old_with_field, old_without_field)):
                path = Path(directory) / f"old-{index}.json"
                path.write_text(json.dumps(expected), encoding="utf-8")
                self.assertEqual(expected, dashboard.load_result(path))

    def test_dashboard_view_ignores_legacy_field_and_renders_canonical_expression(self):
        canonical = {
            "state": "BROAD_CONFIRMATION",
            "instruments": [],
            "limitations": [],
        }
        old_view = dashboard.build_view_model(
            minimal_run(
                market_expression={"mapped": True, "primary": ["NVDA"]},
                market_expression_context=canonical,
            ),
            Path("old.json"),
        )
        new_view = dashboard.build_view_model(
            minimal_run(market_expression_context=canonical),
            Path("new.json"),
        )
        self.assertNotIn("market_expression", old_view)
        self.assertNotIn("market_expression", new_view)
        self.assertEqual(canonical, old_view["market_expression_context"])
        self.assertEqual(canonical, new_view["market_expression_context"])

    def test_daily_report_omits_legacy_narrative_market_block(self):
        report = build_daily_report(
            readable_time="2026-08-04 12:00 UTC",
            headline_count=1,
            feed_count=1,
            coverage_pct=100.0,
            signals={},
            nonzero_results=[("ai", 1)],
            concentration={
                "dominant_theme": "ai",
                "dominant_count": 1,
                "total_mentions": 1,
                "dominant_share": 1.0,
                "concentration_gap": 1,
            },
        )
        self.assertNotIn("=== Market Expression Map ===", report)
        self.assertNotIn("Primary Expressions:", report)
        self.assertNotIn("Potential Offsets:", report)


if __name__ == "__main__":
    unittest.main()
