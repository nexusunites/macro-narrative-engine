import json
import unittest

from mne.alert_engine import ALERT_HISTORY_MAX, build_default_alert_state, dedupe_alert_events, evaluate_alert_rules
from mne.personalization import build_default_preferences, follow_narrative


def run(run_id, state, *, dominant="energy", expression="MUTED", coverage="BROAD"):
    return {
        "run_id": run_id,
        "timestamp": f"2026-07-{run_id[-2:]}T12:00:00",
        "dominant_theme": dominant,
        "narrative_memory": {"themes": [{"name": "energy", "memory_state": state, "plain_language_summary": "Observed persisted history."}], "groups": []},
        "market_expression_context": {"state": expression},
        "source_intelligence": {"coverage_intelligence": {"breadth_state": coverage}},
    }


class AlertEngineTests(unittest.TestCase):
    def setUp(self):
        self.preferences = follow_narrative(build_default_preferences(), "theme", "energy")

    def evaluate(self, new_state, old_state="EMERGING", **kwargs):
        return evaluate_alert_rules(run("02", new_state, **kwargs), run("01", old_state), self.preferences, build_default_alert_state())

    def test_lifecycle_transitions_fire(self):
        expected = {
            "DOMINANT": "NARRATIVE_BECAME_DOMINANT",
            "BUILDING": "NARRATIVE_BUILDING_AGAIN",
            "RE_ACCELERATING": "NARRATIVE_BUILDING_AGAIN",
            "FADING": "NARRATIVE_FADING",
            "RECURRING": "NARRATIVE_RETURNED",
        }
        for state, alert_type in expected.items():
            with self.subTest(state=state):
                self.assertIn(alert_type, [event["event_type"] for event in self.evaluate(state)["events"]])

    def test_persistent_dominance_does_not_refire(self):
        self.assertEqual(self.evaluate("DOMINANT", old_state="DOMINANT")["events"], [])

    def test_dominant_narrative_change_fires(self):
        old = run("01", "EMERGING", dominant="ai")
        result = evaluate_alert_rules(run("02", "EMERGING", dominant="energy"), old, self.preferences, build_default_alert_state())
        self.assertIn("DOMINANT_NARRATIVE_CHANGED", [event["event_type"] for event in result["events"]])

    def test_expression_and_coverage_transitions_fire(self):
        old = run("01", "EMERGING", expression="MUTED", coverage="BROAD")
        new = run("02", "EMERGING", expression="STRONGLY_CONFIRMING", coverage="LIMITED")
        result = evaluate_alert_rules(new, old, self.preferences, build_default_alert_state())
        types = {event["event_type"] for event in result["events"]}
        self.assertIn("MARKET_EXPRESSION_CHANGED_MATERIALLY", types)
        self.assertIn("EVIDENCE_BREADTH_LIMITED_OR_UNAVAILABLE", types)

    def test_missing_data_does_not_trigger(self):
        self.assertEqual(evaluate_alert_rules({"run_id": "02"}, {"run_id": "01"}, self.preferences, build_default_alert_state())["events"], [])

    def test_already_evaluated_run_is_byte_identical_noop(self):
        first = self.evaluate("DOMINANT")
        second = evaluate_alert_rules(run("02", "DOMINANT"), run("01", "EMERGING"), self.preferences, first)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_cooldown_counts_meaningful_runs(self):
        first = self.evaluate("DOMINANT")
        second = evaluate_alert_rules(run("03", "EMERGING"), run("02", "DOMINANT"), self.preferences, first)
        third = evaluate_alert_rules(run("04", "DOMINANT"), run("03", "EMERGING"), self.preferences, second)
        self.assertEqual(sum(event["event_type"] == "NARRATIVE_BECAME_DOMINANT" for event in third["events"]), 1)

    def test_deduplication_and_history_bound(self):
        event = {"event_type": "X", "narrative_key": "a", "transition": "a->b", "triggered_at": "1"}
        self.assertEqual(len(dedupe_alert_events([event, event])), 1)
        state = build_default_alert_state()
        state["events"] = [{**event, "narrative_key": str(i)} for i in range(ALERT_HISTORY_MAX + 5)]
        result = evaluate_alert_rules(run("02", "EMERGING"), run("01", "EMERGING"), self.preferences, state)
        self.assertLessEqual(len(result["events"]), ALERT_HISTORY_MAX)

    def test_language_has_no_prediction_or_trade_language(self):
        text = json.dumps(self.evaluate("DOMINANT")).lower()
        for term in ("predict", "price target", "buy ", "sell ", "trade recommendation"):
            self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
