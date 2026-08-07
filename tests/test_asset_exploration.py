import json
import unittest
from pathlib import Path

from mne.asset_exploration import (AssetRegistryError, build_asset_execution_context, build_asset_exploration_context,
    compute_asset_breadth, load_asset_registry, load_narrative_asset_map,
    validate_asset_registry, validate_narrative_asset_map)
from mne.asset_price_history import AssetPriceHistory, Candle
from mne.sector_isolation import build_sector_isolation_context, load_sector_map


ROOT = Path(__file__).resolve().parents[1]
class AssetExplorationTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_asset_registry()
        self.asset_map = load_narrative_asset_map(registry=self.registry)

    def sector_row(self, narrative, sector, state="UNAVAILABLE"):
        participation = {"sectors": {sector: {"participation_state": state, "data_freshness": "FRESH" if state != "UNAVAILABLE" else "UNAVAILABLE", "instrument": {"technology": "XLK", "energy": "XLE", "financials": "XLF"}.get(sector), "pct_change": .4}}}
        return next(row for row in build_sector_isolation_context(narrative, load_sector_map(), participation)["sectors"] if row["sector_key"] == sector)

    def test_mapping_scope_is_exact_and_sparse(self):
        mappings = {name: {item.ticker: item.role for item in rows} for name, rows in self.asset_map.narratives}
        self.assertEqual({"NVDA": "PRIMARY", "MSFT": "SECONDARY", "QQQ": "SECONDARY", "VIX": "OFFSET"}, mappings["AI / Tech Growth"])
        self.assertEqual({"XOM": "PRIMARY", "CVX": "PRIMARY", "SLB": "SECONDARY"}, mappings["Energy / Commodities"])
        self.assertEqual({"VIX": "PRIMARY", "DXY": "PRIMARY", "TLT": "PRIMARY", "HYG": "SECONDARY", "QQQ": "OFFSET", "NVDA": "OFFSET"}, mappings["Macro Pressure"])
        self.assertNotIn("Geopolitical Risk", mappings)
        self.assertNotIn("DXY", mappings["AI / Tech Growth"])
        self.assertNotIn("XLE", mappings["Energy / Commodities"])

    def test_unknown_narrative_ticker_duplicate_role_and_direction_fail_closed(self):
        def fixture(name="AI / Tech Growth", assets=None): return {"version": "1.0.0", "narratives": {name: {"assets": assets or []}}}
        valid = {"ticker": "NVDA", "role": "PRIMARY", "expected_expression": "UP", "rationale": "Direct.", "display_enabled": True}
        cases = (fixture("Unknown"), fixture(assets=[{**valid, "ticker": "UNKNOWN"}]), fixture(assets=[{**valid, "ticker": "SMH"}]), fixture(assets=[valid, valid]), fixture(assets=[{**valid, "role": "BUY"}]), fixture(assets=[{key: value for key, value in valid.items() if key != "expected_expression"}]))
        for case in cases:
            with self.subTest(case=case), self.assertRaises(AssetRegistryError): validate_narrative_asset_map(case, self.registry)

    def test_sector_filtering_context_assets_and_sector_etf_reuse(self):
        sector_row = self.sector_row("AI / Tech Growth", "technology", "PARTICIPATING")
        participation = {"assets": {"NVDA": {"participation_state": "STRONG", "data_freshness": "FRESH", "pct_change": 1.2}, "QQQ": {"participation_state": "PARTICIPATING", "data_freshness": "FRESH", "pct_change": .5}, "VIX": {"participation_state": "MUTED", "data_freshness": "FRESH", "pct_change": 0}}}
        context = build_asset_exploration_context("AI / Tech Growth", "technology", registry=self.registry, asset_map=self.asset_map, participation=participation, sector_row=sector_row)
        self.assertEqual({"NVDA", "MSFT", "XLK"}, {row["ticker"] for row in context["sector_assets"]})
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

    def test_energy_company_coverage_and_unmapped_asset_movement_are_honest(self):
        row = self.sector_row("Energy / Commodities", "energy")
        context = build_asset_exploration_context("Energy / Commodities", "energy", registry=self.registry, asset_map=self.asset_map, participation={"assets": {"SPY": {"participation_state": "STRONG"}}}, sector_row=row)
        self.assertEqual(("CVX", "XOM", "SLB", "XLE"), tuple(item["ticker"] for item in context["sector_assets"]))
        self.assertEqual((), context["context_assets"])

    def test_new_company_and_macro_assets_render_but_smh_and_synthetics_do_not(self):
        ai = build_asset_exploration_context("AI / Tech Growth", "technology", registry=self.registry, asset_map=self.asset_map)
        macro = build_asset_exploration_context("Macro Pressure", "technology", registry=self.registry, asset_map=self.asset_map)
        self.assertIn("MSFT", {row["ticker"] for row in ai["assets"]})
        self.assertTrue({"TLT", "HYG"}.issubset({row["ticker"] for row in macro["assets"]}))
        rendered = {row["ticker"] for row in (*ai["assets"], *macro["assets"])}
        self.assertNotIn("SMH", rendered)
        self.assertTrue(rendered.isdisjoint({"RATES", "CLOUD", "DATA_CENTER", "CRUDE_OIL", "COMMODITY_FX", "GROWTH_CONCERNS"}))

    def test_hidden_asset_is_excluded_and_context_is_byte_stable(self):
        registry = json.loads(json.dumps(self.registry)); registry["assets"]["NVDA"]["display_enabled"] = False
        first = build_asset_exploration_context("AI / Tech Growth", "technology", registry=registry, asset_map=self.asset_map)
        second = build_asset_exploration_context("AI / Tech Growth", "technology", registry=registry, asset_map=self.asset_map)
        self.assertNotIn("NVDA", {row["ticker"] for row in first["assets"]})
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_execution_context_uses_yfinance_symbol_and_persisted_candles(self):
        requested = []
        def load_prices(symbol):
            requested.append(symbol)
            return AssetPriceHistory(symbol, "1.0.0", (
                Candle("2026-08-05", 20.0, 22.0, 19.0, 21.0),
                Candle("2026-08-06", 21.0, 24.0, 20.0, 23.1),
            ))
        context = build_asset_execution_context(
            "AI / Tech Growth", "technology", "VIX",
            registry=self.registry, asset_map=self.asset_map,
            ticker_symbols={"VIX": "^VIX", "NVDA": "NVDA", "technology": "XLK"},
            price_loader=load_prices,
        )
        self.assertEqual(["^VIX"], requested)
        self.assertEqual("^VIX", context["yfinance_symbol"])
        self.assertEqual(2, len(context["candles"]))
        self.assertEqual(10.0, context["launch_delta_pct"])

    def test_execution_context_missing_symbol_and_history_are_honest(self):
        unloaded = build_asset_execution_context(
            "AI / Tech Growth", "technology", "SMH",
            registry=self.registry, asset_map=self.asset_map, ticker_symbols={},
            price_loader=lambda symbol: self.fail("missing symbol must not load prices"),
        )
        self.assertIsNone(unloaded["yfinance_symbol"])
        self.assertFalse(unloaded["has_candles"])
        empty = build_asset_execution_context(
            "AI / Tech Growth", "technology", "NVDA",
            registry=self.registry, asset_map=self.asset_map,
            ticker_symbols={"NVDA": "NVDA"},
            price_loader=lambda symbol: AssetPriceHistory(symbol, "1.0.0", ()),
        )
        self.assertEqual([], empty["candles"])
        self.assertIsNone(empty["latest_candle"])

    def test_breadth_precedence(self):
        def rows(*states): return [{"participation_state": state} for state in states]
        cases = ((rows("STRONG", "PARTICIPATING", "STRONG"), "BROAD"), (rows("STRONG", "PARTICIPATING"), "MODERATE"), (rows("STRONG"), "CONCENTRATED"), (rows("EMERGING"), "LIMITED"), (rows("STRONG", "CONTRADICTING"), "CONTRADICTED"), (rows("MUTED"), "UNAVAILABLE"))
        for fixture, expected in cases: self.assertEqual(expected, compute_asset_breadth(fixture)["state"])

    def test_structural_live_boundary_and_safety_language(self):
        source = (ROOT / "mne" / "asset_exploration.py").read_text()
        for prohibited in ("asset_participation", "market_context", "import yfinance", "fetch_"): self.assertNotIn(prohibited, source)
        copy = (ROOT / "mne" / "presentation_language.py").read_text().lower()
        template = (ROOT / "templates" / "asset_exploration.html").read_text().lower() + (ROOT / "templates" / "_partials" / "asset_grid.html").read_text().lower()
        for prohibited in ("best asset", "top pick", "strongest opportunity", "likely winner", "expected return", "optimal entry", "conviction score"): self.assertNotIn(prohibited, copy + template)

    def test_route_order_template_and_design_contracts(self):
        dashboard = (ROOT / "dashboard.py").read_text(); assets = dashboard.index('@app.get("/research/{key:path}/sectors/{sector}/assets"'); execution = dashboard.index('@app.get("/research/{key:path}/sectors/{sector}/assets/{ticker}"'); catch = dashboard.index('@app.get("/research/{key:path}"')
        self.assertLess(assets, catch)
        self.assertLess(execution, catch)
        sector_template = (ROOT / "templates" / "sector_isolation.html").read_text(); asset_template = (ROOT / "templates" / "_partials" / "asset_grid.html").read_text(); css = (ROOT / "static" / "styles.css").read_text()
        self.assertIn("Explore assets", sector_template); self.assertIn("asset-rationale", asset_template); self.assertLess(asset_template.index("asset-rationale"), asset_template.index("asset-ticker")); self.assertIn("data-asset-xray", asset_template); self.assertIn("asset.execution_href", asset_template)
        self.assertIn(".asset-card:focus-visible", css); self.assertIn(".asset-grid { grid-template-columns:1fr; }", css); self.assertIn(".asset-card { transition:none !important; }", css)


if __name__ == "__main__": unittest.main()
