import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mne.sector_isolation import build_sector_isolation_context, load_sector_map, validate_sector_map
from mne.sector_market_context import (
    DETACHED_MOVE_EPSILON,
    MEANINGFUL_MOVE_PCT,
    NarrativeSectorInstrumentError,
    STRONG_MOVE_PCT,
    build_sector_ticker_map,
    classify_sectors_for_run,
    load_sector_instruments,
    validate_sector_instruments,
)


NOW = datetime(2026, 8, 4, 16, tzinfo=timezone.utc)


def record(change, age=timedelta(hours=1)):
    return {"ticker": "TEST", "pct_change": change, "observed_at": (NOW - age).isoformat()}


class SectorMarketContextTests(unittest.TestCase):
    def test_registry_loads_and_builds_all_sector_tickers_deterministically(self):
        first, second = load_sector_instruments(), load_sector_instruments()
        self.assertEqual(first, second)
        self.assertEqual("XLK", build_sector_ticker_map(first)["technology"])
        self.assertEqual(11, len(build_sector_ticker_map(first)))

    def test_registry_rejects_unknown_sector_duplicate_instrument_and_bad_fields(self):
        base = {"version": "1.0.0", "sectors": {"technology": {"display_name": "Technology", "instrument": "XLK", "instrument_type": "sector_etf", "display_enabled": True}}}
        cases = []
        unknown = json.loads(json.dumps(base)); unknown["sectors"]["unknown"] = unknown["sectors"].pop("technology"); cases.append(unknown)
        duplicate = json.loads(json.dumps(base)); duplicate["sectors"]["energy"] = {**duplicate["sectors"]["technology"]}; cases.append(duplicate)
        bad = json.loads(json.dumps(base)); bad["sectors"]["technology"]["display_enabled"] = "yes"; cases.append(bad)
        for item in cases:
            with self.subTest(item=item), self.assertRaises(NarrativeSectorInstrumentError):
                validate_sector_instruments(item)

    def test_real_states_and_breadth_are_hand_derivable(self):
        snapshot = {"technology": record(1.2), "communication_services": record(.5), "utilities": record(.1), "industrials": record(0)}
        result = classify_sectors_for_run({"market_snapshot": snapshot}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("STRONG", result["sectors"]["technology"]["participation_state"])
        self.assertEqual("PARTICIPATING", result["sectors"]["communication_services"]["participation_state"])
        self.assertEqual("EMERGING", result["sectors"]["utilities"]["participation_state"])
        self.assertEqual("DETACHED", result["sectors"]["industrials"]["participation_state"])
        self.assertEqual("MODERATE", result["participation_breadth"]["state"])

    def test_emerging_structural_role_can_show_strong_participation_without_mutation(self):
        result = classify_sectors_for_run({"market_snapshot": {"utilities": record(4)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("STRONG", result["sectors"]["utilities"]["participation_state"])
        context = build_sector_isolation_context("AI / Tech Growth", participation=result)
        utilities = next(item for item in context["sectors"] if item["sector_key"] == "utilities")
        self.assertEqual("EMERGING", utilities["structural_role"])
        self.assertEqual("STRONG", utilities["participation_state"])
        self.assertNotIn("MIXED", {row["participation_state"] for row in result["sectors"].values()})

    def test_emerging_structural_role_can_still_show_emerging_participation(self):
        result = classify_sectors_for_run({"market_snapshot": {"utilities": record(.1)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("EMERGING", result["sectors"]["utilities"]["participation_state"])

    def test_emerging_structural_role_can_contradict_only_with_expected_direction_and_threshold(self):
        result = classify_sectors_for_run({"market_snapshot": {"utilities": record(-.5)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("CONTRADICTING", result["sectors"]["utilities"]["participation_state"])
        muted = classify_sectors_for_run({"market_snapshot": {"utilities": record(-.1)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("DETACHED", muted["sectors"]["utilities"]["participation_state"])
        fixture = {"version": "1.0.0", "narratives": {"AI / Tech Growth": {"sectors": [{"sector": "utilities", "role": "EMERGING", "rationale": "Developing.", "display_enabled": True}]}}}
        unavailable = classify_sectors_for_run({"market_snapshot": {"utilities": record(-2)}}, validate_sector_map(fixture), "AI / Tech Growth", now=NOW)
        self.assertEqual("UNAVAILABLE", unavailable["sectors"]["utilities"]["participation_state"])

    def test_opposing_expected_direction_contradicts_primary_or_secondary(self):
        result = classify_sectors_for_run({"market_snapshot": {"technology": record(-.5)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertEqual("CONTRADICTING", result["sectors"]["technology"]["participation_state"])
        self.assertEqual("CONTRADICTED", result["participation_breadth"]["state"])

    def test_down_expected_direction_can_confirm_narrative_specific_expression(self):
        result = classify_sectors_for_run({"market_snapshot": {"real_estate": record(-1.2)}}, load_sector_map(), "Macro Pressure", now=NOW)
        self.assertEqual("STRONG", result["sectors"]["real_estate"]["participation_state"])

    def test_missing_stale_and_legacy_records_fail_closed(self):
        stale = {"ticker": "TEST", "pct_change": 2, "observed_at": "2026-07-31T20:00:00+00:00"}
        malformed = {"ticker": "TEST", "pct_change": 2, "observed_at": "not-a-time"}
        future = {"ticker": "TEST", "pct_change": 2, "observed_at": "2026-08-05T20:00:00+00:00"}
        cases = ({}, {"technology": None}, {"technology": {"pct_change": 2}}, {"technology": stale}, {"technology": malformed}, {"technology": future})
        expected_freshness = ("UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "STALE", "UNAVAILABLE", "UNAVAILABLE")
        for snapshot, freshness in zip(cases, expected_freshness):
            result = classify_sectors_for_run({"market_snapshot": snapshot}, load_sector_map(), "AI / Tech Growth", now=NOW)
            row = result["sectors"]["technology"]
            self.assertEqual("UNAVAILABLE", row["participation_state"])
            self.assertEqual(freshness, row["data_freshness"])

    def test_missing_stale_or_malformed_data_is_unavailable_for_emerging_role(self):
        records = (None, {"pct_change": 2}, {"pct_change": 2, "observed_at": "bad"}, {"pct_change": "bad", "observed_at": NOW.isoformat()}, {"pct_change": float("nan"), "observed_at": NOW.isoformat()})
        for value in records:
            with self.subTest(value=value):
                row = classify_sectors_for_run({"market_snapshot": {"utilities": value}}, load_sector_map(), "AI / Tech Growth", now=NOW)["sectors"]["utilities"]
                self.assertEqual("UNAVAILABLE", row["participation_state"])

    def test_named_threshold_boundaries_remain_unchanged(self):
        self.assertEqual((1.0, .25, .01), (STRONG_MOVE_PCT, MEANINGFUL_MOVE_PCT, DETACHED_MOVE_EPSILON))
        cases = ((1.0, "STRONG"), (.25, "PARTICIPATING"), (.1, "EMERGING"), (0.0, "DETACHED"), (-.25, "CONTRADICTING"))
        for change, expected in cases:
            with self.subTest(change=change):
                result = classify_sectors_for_run({"market_snapshot": {"technology": record(change)}}, load_sector_map(), "AI / Tech Growth", now=NOW)
                self.assertEqual(expected, result["sectors"]["technology"]["participation_state"])

    def test_detached_structural_role_without_expected_expression_cannot_contradict(self):
        fixture = {"version": "1.0.0", "narratives": {"AI / Tech Growth": {"sectors": [{"sector": "health_care", "role": "DETACHED", "rationale": "No directional claim.", "display_enabled": True}]}}}
        result = classify_sectors_for_run({"market_snapshot": {"health_care": record(-5)}}, validate_sector_map(fixture), "AI / Tech Growth", now=NOW)
        self.assertEqual("UNAVAILABLE", result["sectors"]["health_care"]["participation_state"])

    def test_breadth_states_and_partial_coverage_use_only_fresh_classifiable_rows(self):
        cases = (
            ({"technology": record(1), "communication_services": record(1), "utilities": record(1)}, "BROAD"),
            ({"technology": record(1), "communication_services": record(1)}, "MODERATE"),
            ({"technology": record(1)}, "CONCENTRATED"),
            ({"utilities": record(.1)}, "LIMITED"),
            ({"technology": record(-.25)}, "CONTRADICTED"),
            ({"technology": {"pct_change": 1}}, "UNAVAILABLE"),
        )
        for snapshot, expected in cases:
            with self.subTest(expected=expected):
                result = classify_sectors_for_run({"market_snapshot": snapshot}, load_sector_map(), "AI / Tech Growth", now=NOW)
                self.assertEqual(expected, result["participation_breadth"]["state"])

    def test_missing_expected_expression_fails_closed(self):
        fixture = {"version": "1.0.0", "narratives": {"AI / Tech Growth": {"sectors": [{"sector": "technology", "role": "PRIMARY", "rationale": "Direct.", "display_enabled": True}]}}}
        result = classify_sectors_for_run({"market_snapshot": {"technology": record(2)}}, validate_sector_map(fixture), "AI / Tech Growth", now=NOW)
        self.assertEqual("UNAVAILABLE", result["sectors"]["technology"]["participation_state"])

    def test_broad_market_inputs_are_not_sector_proxies_and_output_is_stable(self):
        run = {"market_snapshot": {key: record(5) for key in ("QQQ", "NVDA", "VIX", "DXY")}}
        first = classify_sectors_for_run(run, load_sector_map(), "AI / Tech Growth", now=NOW)
        second = classify_sectors_for_run(run, load_sector_map(), "AI / Tech Growth", now=NOW)
        self.assertTrue(all(row["participation_state"] == "UNAVAILABLE" for row in first["sectors"].values()))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_classification_does_not_rewrite_persisted_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "old-run.json")
            original = json.dumps({"market_snapshot": {"QQQ": {"pct_change": 1}}}).encode()
            path.write_bytes(original)
            run = json.loads(path.read_text())
            classify_sectors_for_run(run, load_sector_map(), "AI / Tech Growth", now=NOW)
            self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
