import json
import unittest
from pathlib import Path

from mne.asset_exploration import (AssetRegistryError, build_asset_exploration_context,
    compute_asset_breadth, load_asset_registry, load_narrative_asset_map,
    validate_asset_registry, validate_narrative_asset_map)
from mne.sector_isolation import build_sector_isolation_context, load_sector_map


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {"QQQ", "NVDA", "VIX", "DXY", "SPY", "RSP", "QQQE", "IWM", "XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLU", "XLRE", "XLP", "XLV"}


class AssetExplorationTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_asset_registry()
        self.asset_map = load_narrative_asset_map(registry=self.registry)

    def sector_row(self, narrative, sector, state="UNAVAILABLE"):
        participation = {"sectors": {sector: {"participation_state": state, "data_freshness": "FRESH" if state != "UNAVAILABLE" else "UNAVAILABLE", "instrument": {"technology": "XLK", "energy": "XLE", "financials": "XLF"}.get(sector), "pct_change": .4}}}
        return next(row for row in build_sector_isolation_context(narrative, load_sector_map(), participation)["sectors"] if row["sector_key"] == sector)

    def test_registry_contains_exactly_the_19_persisted_symbols(self):
        self.assertEqual(CANONICAL, set(self.registry["assets"]))
        self.assertEqual(19, len(self.registry["assets"]))

    def test_registry_loads_deterministically_and_fails_closed(self):
        self.assertEqual(self.registry, load_asset_registry())
        base = {"version": "1.0.0", "assets": {"QQQ": {"display_name": "QQQ", "asset_type": "ETF", "sector_key": None, "broad_market_role": "GROWTH_INDEX", "display_enabled": True}}}
        cases = []
        duplicate = json.loads(json.dumps(base)); duplicate["assets"]["qqq"] = duplicate["assets"]["QQQ"]; cases.append(duplicate)
        invalid_sector = json.loads(json.dumps(base)); invalid_sector["assets"]["QQQ"].update(sector_key="unknown", broad_market_role=None); cases.append(invalid_sector)
        both = json.loads(json.dumps(base)); both["assets"]["QQQ"]["sector_key"] = "technology"; cases.append(both)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(AssetRegistryError): validate_asset_registry(case)

    def test_mapping_scope_is_exact_and_sparse(self):
        mappings = {name: {item.ticker: item.role for item in rows} for name, rows in self.asset_map.narratives}
        self.assertEqual({"NVDA": "PRIMARY", "QQQ": "SECONDARY", "VIX": "OFFSET"}, mappings["AI / Tech Growth"])
        self.assertEqual({}, mappings["Energy / Commodities"])
        self.assertEqual({"VIX": "PRIMARY", "DXY": "PRIMARY", "QQQ": "OFFSET", "NVDA": "OFFSET"}, mappings["Macro Pressure"])
        self.assertNotIn("Geopolitical Risk", mappings)
        self.assertNotIn("DXY", mappings["AI / Tech Growth"])
        self.assertNotIn("XLE", mappings["Energy / Commodities"])

    def test_unknown_narrative_ticker_duplicate_role_and_direction_fail_closed(self):
        def fixture(name="AI / Tech Growth", assets=None): return {"version": "1.0.0", "narratives": {name: {"assets": assets or []}}}
        valid = {"ticker": "NVDA", "role": "PRIMARY", "expected_expression": "UP", "rationale": "Direct.", "display_enabled": True}
        cases = (fixture("Unknown"), fixture(assets=[{**valid, "ticker": "MSFT"}]), fixture(assets=[valid, valid]), fixture(assets=[{**valid, "role": "BUY"}]), fixture(assets=[{key: value for key, value in valid.items() if key != "expected_expression"}]))
        for case in cases:
            with self.subTest(case=case), self.assertRaises(AssetRegistryError): validate_narrative_asset_map(case, self.registry)

    def test_sector_filtering_context_assets_and_sector_etf_reuse(self):
        sector_row = self.sector_row("AI / Tech Growth", "technology", "PARTICIPATING")
        participation = {"assets": {"NVDA": {"participation_state": "STRONG", "data_freshness": "FRESH", "pct_change": 1.2}, "QQQ": {"participation_state": "PARTICIPATING", "data_freshness": "FRESH", "pct_change": .5}, "VIX": {"participation_state": "MUTED", "data_freshness": "FRESH", "pct_change": 0}}}
        context = build_asset_exploration_context("AI / Tech Growth", "technology", registry=self.registry, asset_map=self.asset_map, participation=participation, sector_row=sector_row)
        self.assertEqual({"NVDA", "XLK"}, {row["ticker"] for row in context["sector_assets"]})
        self.assertEqual({"QQQ", "VIX"}, {row["ticker"] for row in context["context_assets"]})
        xlk = next(row for row in context["sector_assets"] if row["ticker"] == "XLK")
        self.assertTrue(xlk["sector_participation_reused"])
        self.assertEqual(sector_row["participation_state"], xlk["participation_state"])

    def test_xray_cross_references_only_genuine_market_expression_roles(self):
        expression = {"instruments": [{"asset": "NVDA", "role": "primary"}, {"asset": "SMH", "role": "primary"}]}
        context = build_asset_exploration_context("AI / Tech Growth", "technology", registry=self.registry, asset_map=self.asset_map, market_expression=expression)
        roles = {row["ticker"]: row["market_expression_role"] for row in context["assets"]}
        self.assertEqual("primary", roles["NVDA"])
        self.assertIsNone(roles["QQQ"])

    def test_sparse_energy_and_unmapped_asset_movement_are_honest(self):
        row = self.sector_row("Energy / Commodities", "energy")
        context = build_asset_exploration_context("Energy / Commodities", "energy", registry=self.registry, asset_map=self.asset_map, participation={"assets": {"SPY": {"participation_state": "STRONG"}}}, sector_row=row)
        self.assertEqual(("XLE",), tuple(item["ticker"] for item in context["sector_assets"]))
        self.assertEqual((), context["context_assets"])

    def test_hidden_asset_is_excluded_and_context_is_byte_stable(self):
        registry = json.loads(json.dumps(self.registry)); registry["assets"]["NVDA"]["display_enabled"] = False
        first = build_asset_exploration_context("AI / Tech Growth", "technology", registry=registry, asset_map=self.asset_map)
        second = build_asset_exploration_context("AI / Tech Growth", "technology", registry=registry, asset_map=self.asset_map)
        self.assertNotIn("NVDA", {row["ticker"] for row in first["assets"]})
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_breadth_precedence(self):
        def rows(*states): return [{"participation_state": state} for state in states]
        cases = ((rows("STRONG", "PARTICIPATING", "STRONG"), "BROAD"), (rows("STRONG", "PARTICIPATING"), "MODERATE"), (rows("STRONG"), "CONCENTRATED"), (rows("EMERGING"), "LIMITED"), (rows("STRONG", "CONTRADICTING"), "CONTRADICTED"), (rows("MUTED"), "UNAVAILABLE"))
        for fixture, expected in cases: self.assertEqual(expected, compute_asset_breadth(fixture)["state"])

    def test_structural_live_boundary_and_safety_language(self):
        source = (ROOT / "mne" / "asset_exploration.py").read_text()
        for prohibited in ("asset_participation", "market_context", "yfinance", "fetch_"): self.assertNotIn(prohibited, source)
        copy = (ROOT / "mne" / "presentation_language.py").read_text().lower()
        template = (ROOT / "templates" / "asset_exploration.html").read_text().lower() + (ROOT / "templates" / "_partials" / "asset_grid.html").read_text().lower()
        for prohibited in ("best asset", "top pick", "strongest opportunity", "likely winner", "expected return", "optimal entry", "conviction score"): self.assertNotIn(prohibited, copy + template)

    def test_route_order_template_and_design_contracts(self):
        dashboard = (ROOT / "dashboard.py").read_text(); assets = dashboard.index('@app.get("/research/{key:path}/sectors/{sector}/assets"'); catch = dashboard.index('@app.get("/research/{key:path}"')
        self.assertLess(assets, catch)
        sector_template = (ROOT / "templates" / "sector_isolation.html").read_text(); asset_template = (ROOT / "templates" / "_partials" / "asset_grid.html").read_text(); css = (ROOT / "static" / "styles.css").read_text()
        self.assertIn("Explore assets", sector_template); self.assertIn("asset-rationale", asset_template); self.assertLess(asset_template.index("asset-rationale"), asset_template.index("asset-ticker")); self.assertIn("data-asset-xray", asset_template)
        self.assertIn(".asset-card:focus-visible", css); self.assertIn(".asset-grid { grid-template-columns:1fr; }", css); self.assertIn(".asset-card { transition:none !important; }", css)


if __name__ == "__main__": unittest.main()
