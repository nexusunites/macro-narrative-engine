import unittest
from pathlib import Path

from mne.narrative_market_map import MARKET_EXPRESSION_MAP_VERSION, get_market_expression


ROOT = Path(__file__).resolve().parents[1]


class LegacyNarrativeMarketMapTests(unittest.TestCase):
    def test_legacy_behavior_remains_compatible(self):
        result = get_market_expression("ai")
        self.assertTrue(result["mapped"])
        self.assertEqual(MARKET_EXPRESSION_MAP_VERSION, result["mapping_version"])
        self.assertEqual(["NVDA", "MSFT", "AVGO"], result["primary"])

    def test_legacy_run_key_is_not_read_by_live_templates(self):
        for path in (ROOT / "templates").rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("run.market_expression", source, path)
            self.assertNotIn("run['market_expression']", source, path)
            self.assertNotIn('run["market_expression"]', source, path)


if __name__ == "__main__": unittest.main()
