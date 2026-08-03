import json
import unittest
from pathlib import Path

import dashboard
from mne.narrative_constellation import (
    build_constellation_context,
    build_group_theme_relationships,
    compute_deterministic_positions,
    derive_direction,
    select_visible_nodes,
    validate_constellation_context,
)


def populated_run():
    return {
        "dominant_group": "AI / Tech Growth",
        "group_scores": {
            "Geopolitical Risk": 8,
            "Macro Pressure": 20,
            "AI / Tech Growth": 40,
            "Energy / Commodities": 12,
            "Zero": 0,
        },
        "theme_scores": {"ai": 25, "semiconductors": 15, "rates": 12, "inflation": 8, "oil": 12, "war": 8, "zero": 0},
        "narrative_memory": {"groups": [
            {"name": "AI / Tech Growth", "memory_state": "PERSISTENT", "plain_language_summary": "AI remains consistently visible."},
            {"name": "Macro Pressure", "memory_state": "FADING", "plain_language_summary": "Macro pressure is easing."},
        ], "themes": []},
        "narrative_dynamics": {"groups": {
            "AI / Tech Growth": {"acceleration": "Accelerating"},
            "Macro Pressure": {"acceleration": "Cooling"},
        }},
        "narrative_pulse": {"AI / Tech Growth": {"pulse_state": "Building"}},
    }


class NarrativeConstellationTests(unittest.TestCase):
    def test_context_builds_bounded_groups_and_themes_from_persisted_data(self):
        context = build_constellation_context(populated_run())
        groups = [n for n in context["nodes"] if n["level"] == "group"]
        themes = [n for n in context["nodes"] if n["level"] == "theme"]
        self.assertEqual(len(groups), 4)
        self.assertLessEqual(len(themes), 12)
        self.assertTrue(groups[0]["dominant"])
        self.assertTrue(all(52 <= n["radius"] <= 74 for n in groups))
        self.assertTrue(all(n["score"] > 0 for n in context["nodes"]))

    def test_direction_precedence_and_conflicts(self):
        self.assertEqual(derive_direction("Emerging", "Accelerating"), "Strengthening")
        self.assertEqual(derive_direction("Fading", "Cooling"), "Weakening")
        self.assertEqual(derive_direction("Persistent", "Stable"), "Stable")
        self.assertEqual(derive_direction(None, "Accelerating"), "Strengthening")
        self.assertEqual(derive_direction("Fading", "Accelerating"), "Stable")
        self.assertEqual(derive_direction(None, "Cooling", "Building"), "Stable")

    def test_relationships_are_confirmed_membership_only(self):
        nodes = select_visible_nodes(populated_run())
        relationships = build_group_theme_relationships(nodes)
        self.assertTrue(relationships)
        self.assertTrue(all(r["type"] == "group_theme" for r in relationships))
        fake = {**nodes[0], "key": "theme:fake", "taxonomy_key": "fake", "level": "theme", "parent_group": "AI / Tech Growth"}
        self.assertNotIn("theme:fake", {r["target"] for r in build_group_theme_relationships(nodes + [fake])})

    def test_cross_group_relationships_are_curated_visible_and_distinct(self):
        context = build_constellation_context(populated_run())
        relationships = [item for item in context["relationships"] if item["type"] == "cross_group"]
        self.assertEqual(len(relationships), 3)
        self.assertTrue(all(item["label"] and item["explanation"] for item in relationships))
        geopolitical = next(node for node in context["nodes"] if node["taxonomy_key"] == "Geopolitical Risk")
        self.assertEqual(geopolitical["related_keys"], [])
        ai = next(node for node in context["nodes"] if node["taxonomy_key"] == "AI / Tech Growth")
        self.assertEqual(ai["related_keys"], ["Energy / Commodities", "Macro Pressure"])

    def test_context_and_positions_are_byte_stable(self):
        first = build_constellation_context(populated_run())
        second = build_constellation_context(populated_run())
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(compute_deterministic_positions(first["nodes"]), compute_deterministic_positions(list(reversed(first["nodes"]))))

    def test_display_names_links_and_plain_language_are_safe(self):
        context = build_constellation_context(populated_run())
        theme = next(n for n in context["nodes"] if n["taxonomy_key"] == "semiconductors")
        self.assertEqual(theme["display_name"], "Semiconductors")
        self.assertEqual(theme["href"], "/research/theme:semiconductors")
        combined = " ".join(n["explanation"] for n in context["nodes"]).lower()
        for banned in ("force graph", "node weight", "edge weight", "normalization coefficient", "run count", "buy", "sell", "forecast"):
            self.assertNotIn(banned, combined)

    def test_empty_single_and_malformed_states(self):
        empty = build_constellation_context({"group_scores": {}})
        self.assertFalse(empty["has_data"])
        single = build_constellation_context({"group_scores": {"AI / Tech Growth": 3}})
        self.assertEqual(len(single["nodes"]), 1)
        self.assertEqual((single["nodes"][0]["x"], single["nodes"][0]["y"]), (400, 215))
        malformed = validate_constellation_context({"nodes": [{"key": "bad"}], "relationships": []})
        self.assertEqual(malformed["nodes"], [])

    def test_no_fetch_score_or_mutation_calls_exist(self):
        source = Path("mne/narrative_constellation.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("compute_group_scores", source)
        run = populated_run()
        before = json.dumps(run, sort_keys=True)
        build_constellation_context(run)
        self.assertEqual(json.dumps(run, sort_keys=True), before)

    def test_server_svg_xray_keyboard_mobile_and_reduced_motion_contract(self):
        template = Path("templates/_partials/narrative_constellation.html").read_text(encoding="utf-8")
        css = Path("static/styles.css").read_text(encoding="utf-8")
        self.assertIn("<svg", template)
        self.assertIn("<a href=", template)
        self.assertIn("tabindex=\"0\"", template)
        self.assertIn("data-constellation-xray", template)
        self.assertIn("relationship-{{ relation.type }}", template)
        self.assertIn("relationship-cross_group", css)
        self.assertIn("@media (max-width: 430px)", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_populated_single_empty_and_malformed_contexts_render(self):
        template = dashboard.templates.env.get_template("_partials/narrative_constellation.html")
        populated = template.render(view={"narrative_constellation": build_constellation_context(populated_run())})
        self.assertIn("<svg", populated)
        self.assertIn("AI / Tech Growth", populated)
        self.assertIn("X-Ray View", populated)
        self.assertIn("Infrastructure demand connection", populated)
        self.assertIn("AI infrastructure growth is connected to rising power demand.", populated)
        single = template.render(view={"narrative_constellation": build_constellation_context({"group_scores": {"Macro Pressure": 2}})})
        self.assertEqual(single.count("constellation-node-group"), 1)
        empty = template.render(view={"narrative_constellation": build_constellation_context({"group_scores": {"broken": "nope"}})})
        self.assertIn("No clear narrative cluster is available yet", empty)
        self.assertNotIn("<svg", empty)


if __name__ == "__main__":
    unittest.main()
