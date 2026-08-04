import json
import unittest

from mne.asset_exploration import (
    AssetRegistryError,
    load_asset_registry,
    load_synthetic_concepts,
    validate_asset_registry,
    validate_synthetic_concepts,
)
from mne.breadth import BREADTH_TICKERS
from mne.sector_market_context import build_sector_ticker_map
from main import ASSET_EXPANSION_TICKERS, NASDAQ_TICKERS


EXISTING = {"QQQ", "NVDA", "VIX", "DXY", "SPY", "RSP", "QQQE", "IWM", "XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLU", "XLRE", "XLP", "XLV"}
APPROVED = {"MSFT", "XOM", "CVX", "SLB", "TLT", "HYG"}
SYNTHETIC = {"RATES", "CLOUD", "DATA_CENTER", "CRUDE_OIL", "COMMODITY_FX", "GROWTH_CONCERNS"}


class AssetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_asset_registry()
        self.concepts = load_synthetic_concepts()

    def test_registry_is_deterministic_and_has_exact_live_universe(self):
        self.assertEqual(self.registry, load_asset_registry())
        fetched = {ticker for ticker, asset in self.registry["assets"].items() if asset["fetched"]}
        self.assertEqual(EXISTING | APPROVED, fetched)
        self.assertEqual(25, len(fetched))
        self.assertEqual(APPROVED, set(ASSET_EXPANSION_TICKERS))
        self.assertEqual({"SMH"}, set(self.registry["assets"]) - fetched)

    def test_fetched_registry_reconciles_with_actual_fetch_dict(self):
        sector_tickers = build_sector_ticker_map()
        actual = {**NASDAQ_TICKERS, **BREADTH_TICKERS, **sector_tickers, **ASSET_EXPANSION_TICKERS}
        fetched = {ticker for ticker, asset in self.registry["assets"].items() if asset["fetched"]}
        resolved = (set(actual) - set(sector_tickers)) | set(sector_tickers.values())
        self.assertEqual(fetched, resolved)

    def test_metadata_display_and_fetched_are_validated_separately(self):
        for ticker, asset in self.registry["assets"].items():
            if asset["display_enabled"]:
                self.assertTrue(asset["fetched"], ticker)
                self.assertTrue(asset["display_name"])
        base = {"version": "1.0.0", "assets": {"QQQ": {"display_name": "QQQ", "asset_type": "ETF", "sector_key": None, "broad_market_role": "GROWTH_INDEX", "fetched": False, "display_enabled": True}}}
        with self.assertRaises(AssetRegistryError): validate_asset_registry(base)
        del base["assets"]["QQQ"]["fetched"]
        with self.assertRaises(AssetRegistryError): validate_asset_registry(base)

    def test_duplicates_invalid_metadata_and_identity_collisions_fail_closed(self):
        base = json.loads(json.dumps(self.registry))
        duplicate = json.loads(json.dumps(base)); duplicate["assets"]["qqq"] = duplicate["assets"]["QQQ"]
        invalid_sector = json.loads(json.dumps(base)); invalid_sector["assets"]["QQQ"].update(sector_key="unknown", broad_market_role=None)
        collision = {"version": "1.0.0", "concepts": {"QQQ": {"description": "Not real.", "tradable": False}}}
        for data, concepts in ((duplicate, None), (invalid_sector, None), (base, collision)):
            with self.subTest(data=data, concepts=concepts), self.assertRaises(AssetRegistryError):
                validate_asset_registry(data, concepts)

    def test_synthetic_registry_is_typed_non_tradable_and_disjoint(self):
        self.assertEqual(SYNTHETIC, set(self.concepts["concepts"]))
        self.assertTrue(set(self.registry["assets"]).isdisjoint(SYNTHETIC))
        invalid = json.loads(json.dumps(self.concepts)); invalid["concepts"]["RATES"]["tradable"] = True
        with self.assertRaises(AssetRegistryError): validate_synthetic_concepts(invalid)


if __name__ == "__main__": unittest.main()
