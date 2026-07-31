import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader

from mne.historical_connection import (
    COVERAGE_CAVEAT,
    MAX_CONNECTIONS,
    build_current_narrative_profile,
    build_replay_narrative_profile,
    compare_current_to_recent_peak,
    compute_profile_similarity,
    load_completed_replay_artifacts,
    load_current_and_historical_context,
    rank_historical_connections,
)
from mne.research_workspace import select_latest_meaningful_run


def live_run(**overrides):
    value = {
        "timestamp": "2026-07-30T12:00:00Z",
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "theme_scores": {"ai": 70, "energy": 20, "inflation": 10},
        "group_scores": {
            "AI / Tech Growth": 70,
            "Energy / Commodities": 20,
            "Macro Pressure": 10,
        },
        "source_intelligence": {
            "coverage_intelligence": {"breadth_state": "BROAD"}
        },
    }
    value.update(overrides)
    return value


def replay(replay_date="2024-03-15", **overrides):
    value = {
        "replay_id": f"replay_{replay_date}_macro",
        "replay_date": replay_date,
        "evidence_cutoff": f"{replay_date}T23:59:59Z",
        "status": "completed",
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "theme_scores": {"ai": 65, "energy": 25, "inflation": 10},
        "group_scores": {
            "AI / Tech Growth": 65,
            "Energy / Commodities": 25,
            "Macro Pressure": 10,
        },
        "source_intelligence": {
            "coverage_intelligence": {"breadth_state": "BROAD"}
        },
    }
    value.update(overrides)
    return value


def history_points():
    return {
        "points": [
            {"date": "2026-07-25", "score": 40, "share": 0.40, "rank": 1, "pulse_state": "Active"},
            {"date": "2026-07-26", "score": 70, "share": 0.70, "rank": 1, "pulse_state": "Active"},
            {"date": "2026-07-27", "score": 60, "share": 0.60, "rank": 1, "pulse_state": "Active"},
            {"date": "2026-07-28", "score": 50, "share": 0.50, "rank": 1, "pulse_state": "Active"},
        ]
    }


class HistoricalConnectionTests(unittest.TestCase):
    def test_latest_meaningful_live_result_excludes_no_signal_and_failed_files(self):
        paths = [Path("latest.json"), Path("failed.json"), Path("meaningful.json")]
        records = {
            "latest.json": {"theme_scores": {}, "group_scores": {}},
            "meaningful.json": live_run(),
        }

        def loader(path):
            if path.name == "failed.json":
                raise ValueError("bad")
            return records[path.name]

        selected = select_latest_meaningful_run(paths, loader)
        self.assertEqual(selected.path.name, "meaningful.json")
        self.assertEqual(selected.run["dominant_theme"], "ai")

    def test_completed_artifacts_are_loaded_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            replay_dir = Path(directory)
            artifact = replay()
            path = replay_dir / f"{artifact['replay_id']}.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            before = path.read_bytes()
            loaded = load_completed_replay_artifacts(replay_dir)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(path.read_bytes(), before)

    def test_incomplete_artifacts_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            replay_dir = Path(directory)
            artifact = replay(status="running")
            path = replay_dir / f"{artifact['replay_id']}.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            self.assertEqual(load_completed_replay_artifacts(replay_dir), [])

    def test_matching_dominance_and_distributions_raise_resemblance(self):
        current = build_current_narrative_profile(live_run())
        matching = compute_profile_similarity(
            current, build_replay_narrative_profile(replay())
        )
        different = compute_profile_similarity(
            current,
            build_replay_narrative_profile(
                replay(
                    dominant_theme="oil",
                    dominant_group="Energy / Commodities",
                    theme_scores={"oil": 100},
                    group_scores={"Energy / Commodities": 100},
                )
            ),
        )
        self.assertGreater(matching["score"], different["score"])
        self.assertEqual(matching["components"]["dominant_theme"], 1)
        self.assertEqual(matching["components"]["dominant_group"], 1)
        self.assertGreater(matching["components"]["theme_distribution"], 0.8)
        self.assertGreater(matching["components"]["group_distribution"], 0.8)

    def test_label_fixtures_cover_strong_moderate_shared_and_limited(self):
        current = build_current_narrative_profile(live_run())
        fixtures = [
            (replay(), "Strong resemblance"),
            (
                replay(
                    dominant_theme="energy",
                    theme_scores={"ai": 50, "energy": 40, "inflation": 10},
                    group_scores={
                        "AI / Tech Growth": 50,
                        "Energy / Commodities": 40,
                        "Macro Pressure": 10,
                    },
                ),
                "Moderate resemblance",
            ),
            (
                replay(
                    dominant_theme="energy",
                    dominant_group="AI / Tech Growth",
                    theme_scores={"ai": 35, "energy": 50, "rates": 15},
                    group_scores={
                        "AI / Tech Growth": 35,
                        "Energy / Commodities": 50,
                        "Macro Pressure": 15,
                    },
                ),
                "Some shared features",
            ),
            (
                replay(
                    dominant_theme="energy",
                    dominant_group="Energy / Commodities",
                    theme_scores={"ai": 35, "energy": 50, "rates": 15},
                    group_scores={
                        "AI / Tech Growth": 35,
                        "Energy / Commodities": 50,
                        "Macro Pressure": 15,
                    },
                ),
                "Limited resemblance",
            ),
        ]
        for artifact, label in fixtures:
            with self.subTest(label=label):
                result = compute_profile_similarity(
                    current, build_replay_narrative_profile(artifact)
                )
                self.assertEqual(result["label"], label)

    def test_unrelated_profile_is_omitted(self):
        ranked = rank_historical_connections(
            live_run(),
            [
                (
                    "replay_2020-01-01_macro",
                    replay(
                        "2020-01-01",
                        dominant_theme="rates",
                        dominant_group="Policy / Rates",
                        theme_scores={"rates": 100},
                        group_scores={"Policy / Rates": 100},
                    ),
                )
            ],
        )
        self.assertEqual(ranked, [])

    def test_meaningful_differences_and_safe_links_are_preserved(self):
        connections = rank_historical_connections(
            live_run(),
            [
                (
                    "replay_2024-03-15_macro",
                    replay(
                        group_scores={
                            "AI / Tech Growth": 55,
                            "Energy / Commodities": 5,
                            "Macro Pressure": 40,
                        }
                    ),
                )
            ],
        )
        self.assertTrue(connections[0]["differences"])
        self.assertEqual(
            connections[0]["historical_url"],
            "/history/replay_2024-03-15_macro",
        )

    def test_coverage_difference_caveat_and_material_caps(self):
        current = build_current_narrative_profile(live_run())
        one_level = compute_profile_similarity(
            current,
            build_replay_narrative_profile(
                replay(
                    source_intelligence={
                        "coverage_intelligence": {"breadth_state": "MODERATE"}
                    }
                )
            ),
        )
        self.assertEqual(one_level["label"], "Strong resemblance")
        self.assertTrue(one_level["coverage"]["differs"])

        material = compute_profile_similarity(
            current,
            build_replay_narrative_profile(
                replay(
                    source_intelligence={
                        "coverage_intelligence": {"breadth_state": "MINIMAL"}
                    }
                )
            ),
        )
        self.assertEqual(material["raw_label"], "Strong resemblance")
        self.assertEqual(material["label"], "Moderate resemblance")
        connection = rank_historical_connections(
            live_run(),
            [("replay_2024-03-15_macro", replay(source_intelligence={
                "coverage_intelligence": {"breadth_state": "MINIMAL"}
            }))],
        )[0]
        self.assertEqual(connection["coverage_caveat"], COVERAGE_CAVEAT)

    def test_material_cap_demotes_moderate_only_one_step_and_not_weak(self):
        current = build_current_narrative_profile(live_run())
        moderate_artifact = replay(
            dominant_theme="energy",
            theme_scores={"ai": 50, "energy": 40, "inflation": 10},
            group_scores={
                "AI / Tech Growth": 50,
                "Energy / Commodities": 40,
                "Macro Pressure": 10,
            },
            source_intelligence={"coverage_intelligence": {"breadth_state": "MINIMAL"}},
        )
        moderate = compute_profile_similarity(
            current, build_replay_narrative_profile(moderate_artifact)
        )
        self.assertEqual(moderate["raw_label"], "Moderate resemblance")
        self.assertEqual(moderate["label"], "Some shared features")

        weak_artifact = replay(
            dominant_theme="oil",
            dominant_group="Energy / Commodities",
            theme_scores={"oil": 70, "ai": 30},
            group_scores={"Energy / Commodities": 70, "AI / Tech Growth": 30},
            source_intelligence={"coverage_intelligence": {"breadth_state": "MINIMAL"}},
        )
        weak = compute_profile_similarity(
            current, build_replay_narrative_profile(weak_artifact)
        )
        self.assertEqual(weak["raw_label"], weak["label"])

    def test_results_are_bounded_and_tie_broken_by_descending_date(self):
        artifacts = [
            (f"replay_{year}-01-01_macro", replay(f"{year}-01-01"))
            for year in range(2020, 2026)
        ]
        results = rank_historical_connections(live_run(), artifacts)
        self.assertEqual(len(results), MAX_CONNECTIONS)
        self.assertEqual(
            [item["date"] for item in results],
            ["2025-01-01", "2024-01-01", "2023-01-01"],
        )

    def test_peak_and_natural_below_peak_context(self):
        context = compare_current_to_recent_peak(
            "AI / Tech Growth", history_points()
        )
        self.assertEqual(context["peak_score"], {"value": 70.0, "date": "2026-07-26"})
        self.assertEqual(context["peak_share"], {"value": 0.7, "date": "2026-07-26"})
        self.assertEqual(context["share_delta_from_peak"], -0.2)
        self.assertIn("less concentrated", context["headline"])
        self.assertTrue(context["prior_similar_periods"])

    def test_returning_and_limited_history_are_calm(self):
        returning = {
            "points": [
                {"date": "2026-07-25", "score": 20, "share": 0.2, "rank": 2, "pulse_state": "Active"},
                {"date": "2026-07-26", "score": None, "share": None, "rank": None, "pulse_state": "Absent"},
                {"date": "2026-07-27", "score": 25, "share": 0.25, "rank": 2, "pulse_state": "Active"},
                {"date": "2026-07-28", "score": 35, "share": 0.35, "rank": 1, "pulse_state": "Active"},
            ]
        }
        self.assertEqual(
            compare_current_to_recent_peak("AI / Tech Growth", returning)["trajectory"],
            "returning",
        )
        limited = compare_current_to_recent_peak("AI / Tech Growth", None)
        self.assertFalse(limited["available"])
        self.assertEqual(limited["trajectory"], "limited")

    def test_missing_scores_and_coverage_degrade_without_error(self):
        result = load_current_and_historical_context(
            live_run(source_intelligence={}),
            replay_artifacts=[
                (
                    "replay_2024-03-15_macro",
                    replay(theme_scores={}, group_scores={}, source_intelligence={}),
                )
            ],
        )
        self.assertEqual(result["connections"], [])
        self.assertIn("No prior reconstruction", result["empty_message"])

    def test_same_inputs_are_byte_identical(self):
        kwargs = {
            "narrative_name": "AI / Tech Growth",
            "history": history_points(),
            "replay_artifacts": [("replay_2024-03-15_macro", replay())],
        }
        first = load_current_and_historical_context(live_run(), **kwargs)
        second = load_current_and_historical_context(live_run(), **kwargs)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_copy_has_no_operational_predictive_or_trade_language(self):
        context = load_current_and_historical_context(
            live_run(),
            history=history_points(),
            replay_artifacts=[("replay_2024-03-15_macro", replay())],
        )
        rendered = json.dumps(context).lower()
        for forbidden in (
            "history will repeat",
            "this predicts",
            "same outcome will follow",
            " buy ",
            " sell ",
            " opportunity",
            "backfill",
            "workflow",
        ):
            self.assertNotIn(forbidden, rendered)
        product_copy = json.dumps(
            {
                "explanation": context["explanation"],
                "connection_explanations": [
                    item["explanation"] for item in context["connections"]
                ],
            }
        ).lower()
        self.assertNotIn("run", product_copy)

    def test_no_fetch_replay_backfill_or_scoring_dependency(self):
        source = Path("mne/historical_connection.py").read_text(encoding="utf-8")
        for forbidden_import in (
            "rss_fetch",
            "historical_backfill",
            "run_historical_replay",
            "analyze_themes",
            "compute_group_scores",
        ):
            self.assertNotIn(forbidden_import, source)

    def test_research_template_renders_connection_before_evidence(self):
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("narrative_investigation.html")
        source = Path("templates/narrative_investigation.html").read_text(encoding="utf-8")
        self.assertLess(
            source.index("historical_connection_copy.heading"),
            source.index('id="supporting-evidence"'),
        )
        self.assertIn("historical_connection.connections", source)

    def test_dashboard_template_has_only_one_concise_connection_binding(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("historical_context_sentence"), 2)
        self.assertNotIn("historical_connection_list", source)


if __name__ == "__main__":
    unittest.main()
