import json
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import dashboard
from mne.explanation_layer import explain_market_expression
from mne.market_expression import (
    DEFAULT_EXPRESSION_MAP_PATH,
    build_market_expression_for_run,
    build_market_expression_summary,
    build_narrative_expression_profile,
    classify_instrument_expression,
    classify_market_expression_state,
    compute_expression_breadth,
    load_market_expression_map,
)
from mne.research_workspace import build_narrative_investigation


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
FORBIDDEN = (
    "buy",
    "sell",
    "entry",
    "target",
    "stop",
    "trade",
    "bullish setup",
    "bearish setup",
    "guaranteed",
    "prediction",
)


def market_record(pct_change, timestamp=None):
    record = {"pct_change": pct_change}
    if timestamp:
        record["timestamp"] = timestamp
    return record


def ai_snapshot(**overrides):
    snapshot = {
        "QQQ": market_record(0.7),
        "NVDA": market_record(1.2),
        "SMH": market_record(0.6),
        "CLOUD": market_record(0.4),
        "DATA_CENTER": market_record(0.5),
        "VIX": market_record(-0.4),
        "DXY": market_record(-0.3),
        "RATES": market_record(-0.3),
    }
    snapshot.update(overrides)
    return snapshot


def run_for(narrative="AI / Tech Growth", snapshot=None):
    return {
        "timestamp": "2026-07-30T12:00:00Z",
        "dominant_group": narrative,
        "dominant_theme": "ai",
        "group_scores": {narrative: 10},
        "theme_scores": {"ai": 10},
        "market_snapshot": ai_snapshot() if snapshot is None else snapshot,
    }


def render_investigation(investigation):
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["url_for"] = lambda endpoint, **values: (
        f"/research/{values.get('key', '')}"
        if endpoint in {"narrative_investigation", "narrative_history"}
        else f"/static/{values.get('path', '')}"
    )
    return env.get_template("narrative_investigation.html").render(
        request=object(),
        results_dir="/tmp/results",
        selected_file="result.json",
        message=None,
        notice=None,
        is_admin=False,
        investigation=investigation,
        history=None,
        historical_connection=None,
        narrative_key="group:AI / Tech Growth",
    )


class MarketExpressionTests(unittest.TestCase):
    def test_mapping_loads_deterministically(self):
        first = load_market_expression_map()
        second = load_market_expression_map()
        self.assertTrue(first["valid"])
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=False),
            json.dumps(second, sort_keys=False),
        )

    def test_ai_tech_growth_mapping_fixture(self):
        profile = build_narrative_expression_profile("AI / Tech Growth")
        self.assertEqual([item["asset"] for item in profile["primary"]], ["QQQ", "NVDA", "SMH"])
        self.assertEqual([item["asset"] for item in profile["offsets"]], ["VIX", "DXY", "RATES"])

    def test_energy_commodities_mapping_fixture(self):
        profile = build_narrative_expression_profile("energy")
        self.assertEqual(profile["narrative_key"], "Energy / Commodities")
        self.assertEqual(profile["primary"][0]["asset"], "CRUDE_OIL")

    def test_macro_pressure_mapping_fixture(self):
        profile = build_narrative_expression_profile("rates")
        self.assertEqual(profile["narrative_key"], "Macro Pressure")
        self.assertEqual(profile["primary"][0]["asset"], "VIX")

    def test_malformed_map_fails_closed(self):
        path = Path("/tmp/mne-malformed-market-expression.json")
        path.write_text('{"mapping_version":"x","narratives":{"AI":{"primary":[]}}}', encoding="utf-8")
        loaded = load_market_expression_map(path)
        self.assertFalse(loaded["valid"])
        self.assertEqual(loaded["narratives"], {})

    def test_unknown_instrument_fails_closed(self):
        payload = json.loads(DEFAULT_EXPRESSION_MAP_PATH.read_text(encoding="utf-8"))
        payload["narratives"]["AI / Tech Growth"]["primary"][0]["asset"] = "TYPO"
        path = Path("/tmp/mne-unknown-market-expression.json")
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_market_expression_map(path)
        self.assertFalse(loaded["valid"])
        self.assertIn("unknown instrument", loaded["errors"][0])

    def test_primary_asset_confirmation_detected(self):
        result = classify_instrument_expression(
            {"asset": "QQQ", "label": "growth", "confirming_direction": "UP"},
            market_record(0.5),
            role="primary",
        )
        self.assertEqual(result["status"], "CONFIRMING")

    def test_secondary_confirmation_detected(self):
        result = classify_instrument_expression(
            {"asset": "CLOUD", "label": "cloud", "confirming_direction": "UP"},
            market_record(0.5),
            role="secondary",
        )
        self.assertEqual(result["status"], "CONFIRMING")

    def test_offset_pressure_detected(self):
        result = classify_instrument_expression(
            {"asset": "VIX", "label": "volatility", "pressure_direction": "UP"},
            market_record(1.1),
            role="offsets",
        )
        self.assertEqual(result["status"], "PRESSURE")

    def test_broad_confirmation_fixture(self):
        result = build_market_expression_summary("AI / Tech Growth", ai_snapshot())
        self.assertEqual(result["state"], "STRONGLY_CONFIRMING")
        self.assertEqual(result["expression_breadth"], "broad")

    def test_narrow_confirmation_fixture(self):
        instruments = [
            {"asset": "QQQ", "role": "primary", "status": "CONFIRMING"},
            {"asset": "NVDA", "role": "primary", "status": "MUTED"},
            {"asset": "VIX", "role": "offset", "status": "MUTED"},
        ]
        breadth = compute_expression_breadth(instruments)
        self.assertEqual(breadth["expression_breadth"], "concentrated")
        self.assertEqual(classify_market_expression_state(instruments, breadth), "CONFIRMING")

    def test_mixed_fixture(self):
        result = build_market_expression_summary(
            "AI / Tech Growth",
            ai_snapshot(NVDA=market_record(-0.8)),
        )
        self.assertEqual(result["state"], "MIXED")
        self.assertEqual(result["expression_breadth"], "mixed")

    def test_diverging_fixture(self):
        snapshot = ai_snapshot(
            QQQ=market_record(-0.7),
            NVDA=market_record(-1.2),
            SMH=market_record(-0.6),
            CLOUD=market_record(0),
            DATA_CENTER=market_record(0),
        )
        result = build_market_expression_summary("AI / Tech Growth", snapshot)
        self.assertEqual(result["state"], "DIVERGING")

    def test_muted_fixture(self):
        result = build_market_expression_summary(
            "AI / Tech Growth",
            {key: market_record(0) for key in ai_snapshot()},
        )
        self.assertEqual(result["state"], "MUTED")

    def test_unavailable_fixture(self):
        result = build_market_expression_summary("AI / Tech Growth", {})
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertEqual(result["expression_breadth"], "unavailable")

    def test_missing_instrument_is_retained_and_calm(self):
        snapshot = ai_snapshot()
        del snapshot["SMH"]
        result = build_market_expression_summary("AI / Tech Growth", snapshot)
        smh = next(item for item in result["instruments"] if item["asset"] == "SMH")
        self.assertEqual(smh["status"], "UNAVAILABLE")
        self.assertIn("SMH", result["unavailable_assets"])
        self.assertEqual(result["state"], "PARTIALLY_CONFIRMING")

    def test_stale_data_is_excluded(self):
        snapshot = ai_snapshot(
            QQQ=market_record(1, "2026-07-28T00:00:00Z"),
            NVDA=market_record(1, "2026-07-28T00:00:00Z"),
            SMH=market_record(1, "2026-07-28T00:00:00Z"),
        )
        result = build_market_expression_summary(
            "AI / Tech Growth",
            snapshot,
            as_of="2026-07-30T12:00:00Z",
        )
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertTrue(any(item["stale"] for item in result["instruments"]))
        self.assertIn("Stale market data", result["limitations"][0])

    def test_breadth_and_lists_reconcile_exactly(self):
        result = build_market_expression_summary("AI / Tech Growth", ai_snapshot())
        statuses = {item["asset"]: item["status"] for item in result["instruments"]}
        self.assertEqual(
            result["confirming_assets"],
            [asset for asset, status in statuses.items() if status in {"CONFIRMING", "ALIGNED"}],
        )
        self.assertEqual(result["confirming_asset_count"], len(result["confirming_assets"]))
        self.assertEqual(result["diverging_asset_count"], len(result["diverging_assets"]))
        self.assertEqual(result["unavailable_asset_count"], len(result["unavailable_assets"]))
        self.assertEqual(result["primary_expression_count"], 3)
        self.assertEqual(result["secondary_expression_count"], 2)

    def test_primary_confirmation_with_offset_pressure_is_partial(self):
        result = build_market_expression_summary(
            "AI / Tech Growth",
            ai_snapshot(VIX=market_record(1.2)),
        )
        self.assertEqual(result["state"], "PARTIALLY_CONFIRMING")
        self.assertEqual(result["expression_breadth"], "contradicted")

    def test_primary_copy_has_no_prohibited_or_predictive_language(self):
        for state_snapshot in (
            ai_snapshot(),
            ai_snapshot(NVDA=market_record(-1)),
            {},
        ):
            explanation = explain_market_expression(
                build_market_expression_summary("AI / Tech Growth", state_snapshot)
            )
            primary = " ".join(
                [
                    explanation["headline"],
                    explanation["what_changed"],
                    explanation["why_it_matters"],
                    *explanation["supporting_points"],
                    *explanation["limitations"],
                ]
            ).lower()
            for term in FORBIDDEN:
                self.assertNotIn(term, primary)

    def test_raw_ticker_states_remain_secondary(self):
        explanation = explain_market_expression(
            build_market_expression_summary("AI / Tech Growth", ai_snapshot())
        )
        self.assertNotIn("QQQ", explanation["headline"])
        self.assertTrue(explanation["technical_details"])

    def test_research_workspace_renders_between_connections_and_evidence(self):
        investigation = build_narrative_investigation(run_for(), "group", "AI / Tech Growth")
        html = render_investigation(investigation)
        self.assertIn("Market Expression", html)
        self.assertIn("Market expression details", html)
        self.assertLess(html.index("Market Expression"), html.index("Supporting Evidence"))
        source = (TEMPLATE_DIR / "narrative_investigation.html").read_text(encoding="utf-8")
        self.assertGreater(
            source.index("investigation.market_expression"),
            source.index("historical_connection"),
        )

    def test_unmapped_research_narrative_omits_section(self):
        investigation = build_narrative_investigation(run_for(), "group", "Unknown Group")
        self.assertIsNone(investigation["market_expression"])
        self.assertNotIn("Market Expression", render_investigation(investigation))

    def test_dashboard_has_one_concise_context_sentence(self):
        view = dashboard.build_view_model(
            run_for(),
            Path("/tmp/2026-07-30_120000.json"),
        )
        sentence = view["market_expression_sentence"]
        self.assertEqual(sentence.count("."), 1)
        self.assertNotIn("QQQ", sentence)
        self.assertIn("confirming", sentence)

    def test_dashboard_omits_unavailable_context(self):
        view = dashboard.build_view_model(
            run_for(snapshot={}),
            Path("/tmp/2026-07-30_120000.json"),
        )
        self.assertIsNone(view["market_expression_sentence"])

    def test_existing_evidence_history_and_connections_markup_remain(self):
        source = (TEMPLATE_DIR / "narrative_investigation.html").read_text(encoding="utf-8")
        self.assertIn("evidence_reader(", source)
        self.assertIn("investigation-history-preview", source)
        self.assertIn("historical_connection", source)

    def test_expression_helper_has_no_fetch_dependency(self):
        source = Path("mne/market_expression.py").read_text(encoding="utf-8")
        self.assertNotIn("yfinance", source)
        self.assertNotIn("get_market_snapshot", source)
        self.assertNotIn("requests", source)

    def test_no_scoring_or_taxonomy_mutation(self):
        source = Path("mne/market_expression.py").read_text(encoding="utf-8")
        self.assertNotIn("theme_analysis", source)
        self.assertNotIn("compute_group_scores", source)
        self.assertEqual(DEFAULT_EXPRESSION_MAP_PATH.name, "market_expression_map.json")

    def test_same_input_is_byte_identical(self):
        run = run_for()
        first = build_market_expression_for_run(run)
        second = build_market_expression_for_run(run)
        self.assertEqual(
            json.dumps(first, separators=(",", ":"), ensure_ascii=False),
            json.dumps(second, separators=(",", ":"), ensure_ascii=False),
        )


if __name__ == "__main__":
    unittest.main()
