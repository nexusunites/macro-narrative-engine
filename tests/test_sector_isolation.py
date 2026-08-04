import json
import tempfile
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from mne.sector_isolation import (
    PARTICIPATION_STATES,
    STRUCTURAL_ROLES,
    SectorIsolationError,
    build_sector_isolation_context,
    build_sector_isolation_preview,
    classify_sector_participation,
    load_sector_map,
    validate_sector_map,
)


ROOT = Path(__file__).resolve().parents[1]


class SectorIsolationTests(unittest.TestCase):
    def fixture(self):
        return {"version": "1.0.0", "narratives": {"AI / Tech Growth": {"sectors": [{"sector": "technology", "role": "PRIMARY", "rationale": "Direct connection.", "display_enabled": True}]}}}

    def test_checked_in_map_loads_deterministically(self):
        first = load_sector_map()
        second = load_sector_map()
        self.assertEqual(first, second)
        self.assertEqual("1.0.0", first.version)

    def test_unknown_narrative_sector_duplicate_and_role_fail_closed(self):
        cases = []
        unknown_narrative = self.fixture(); unknown_narrative["narratives"]["Unknown"] = unknown_narrative["narratives"].pop("AI / Tech Growth"); cases.append(unknown_narrative)
        unknown_sector = self.fixture(); unknown_sector["narratives"]["AI / Tech Growth"]["sectors"][0]["sector"] = "unknown"; cases.append(unknown_sector)
        duplicate = self.fixture(); duplicate["narratives"]["AI / Tech Growth"]["sectors"] *= 2; cases.append(duplicate)
        invalid_role = self.fixture(); invalid_role["narratives"]["AI / Tech Growth"]["sectors"][0]["role"] = "LIVE"; cases.append(invalid_role)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(SectorIsolationError): validate_sector_map(case)

    def test_hidden_mapping_is_excluded(self):
        fixture = self.fixture(); fixture["narratives"]["AI / Tech Growth"]["sectors"][0]["display_enabled"] = False
        context = build_sector_isolation_context("AI / Tech Growth", validate_sector_map(fixture))
        self.assertEqual((), context["sectors"])

    def test_participation_is_unconditionally_unavailable(self):
        self.assertIn("UNAVAILABLE", PARTICIPATION_STATES)
        for args in [(), ("AI / Tech Growth", "technology"), ({"price": 999},)]:
            self.assertEqual("UNAVAILABLE", classify_sector_participation(*args))

    def test_structural_role_and_participation_are_separate_and_honest(self):
        context = build_sector_isolation_context("AI / Tech Growth")
        self.assertEqual(4, context["breadth"]["count"])
        self.assertEqual("Broad", context["breadth"]["category"])
        self.assertEqual(1, context["breadth"]["role_counts"]["PRIMARY"])
        for sector in context["sectors"]:
            self.assertIn(sector["connection_role"], STRUCTURAL_ROLES)
            self.assertEqual("UNAVAILABLE", sector["participation_state"])
            self.assertEqual(0, sector["evidence_count"])
            self.assertEqual((), sector["instruments"])
            self.assertFalse(sector["available"])

    def test_preview_is_bounded_and_empty_mapping_is_calm(self):
        preview = build_sector_isolation_preview({"dominant_group": "AI / Tech Growth"}, limit=3)
        self.assertEqual(3, len(preview["sectors"]))
        self.assertEqual(4, preview["total_sector_count"])
        empty = build_sector_isolation_context("Geopolitical Risk")
        self.assertFalse(empty["has_mapping"])
        self.assertEqual("Unavailable", empty["breadth"]["category"])

    def test_context_is_byte_stable(self):
        first = json.dumps(build_sector_isolation_context("Macro Pressure"), sort_keys=True)
        second = json.dumps(build_sector_isolation_context("Macro Pressure"), sort_keys=True)
        self.assertEqual(first.encode(), second.encode())

    def test_templates_keep_role_participation_xray_and_fallback_visible(self):
        source = (ROOT / "templates" / "sector_isolation.html").read_text()
        partial = (ROOT / "templates" / "_partials" / "sector_heatmap.html").read_text()
        self.assertIn("data-sector-xray", source)
        self.assertIn("participation_explanation", source)
        self.assertIn("Supporting sector instruments: none available", source)
        self.assertIn("aria-label", partial)
        self.assertIn("sector.role_label", partial)
        self.assertIn("sector.participation_label", partial)

    def test_route_registered_before_catch_all_and_dashboard_ordered(self):
        source = (ROOT / "dashboard.py").read_text()
        self.assertLess(source.index('@app.get("/research/{key:path}/sectors"'), source.index('@app.get("/research/{key:path}",'))
        dashboard = (ROOT / "templates" / "dashboard.html").read_text()
        self.assertLess(dashboard.index('id="markets"'), dashboard.index('id="sector-isolation"'))
        self.assertLess(dashboard.index('id="sector-isolation"'), dashboard.index('id="events"'))

    def test_no_fetch_scoring_taxonomy_or_unsafe_copy(self):
        source = (ROOT / "mne" / "sector_isolation.py").read_text().lower()
        for prohibited in ("yfinance", "requests", "compute_group_scores", "market_context"):
            self.assertNotIn(prohibited, source)
        copy_source = (ROOT / "mne" / "presentation_language.py").read_text().lower().split("sector_isolation_copy =", 1)[1].split("historical_copy =", 1)[0]
        for word in ("overweight", "underweight", "buy", "sell", "sector call", "alpha signal", "expected return", "bullish setup", "bearish setup"):
            self.assertNotIn(word, copy_source)

    def test_css_has_keyboard_mobile_and_reduced_motion_contract(self):
        css = (ROOT / "static" / "styles.css").read_text()
        self.assertIn(".sector-tile:focus-visible", css)
        self.assertIn(".sector-heatmap { grid-template-columns:1fr; }", css)
        self.assertIn(".sector-tile { transition:none !important; }", css)


if __name__ == "__main__":
    unittest.main()
