import copy
import hashlib
import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import dashboard
from mne.narrative_memory import (
    DEFAULT_MEMORY_RUNS,
    STATE_ABSENT,
    STATE_BUILDING,
    STATE_DOMINANT,
    STATE_DORMANT,
    STATE_EMERGING,
    STATE_FADING,
    STATE_PERSISTENT,
    STATE_RE_ACCELERATING,
    STATE_RECURRING,
    build_narrative_memory,
    classify_memory_state,
    compute_narrative_streak,
    compute_rank_changes,
    load_recent_memory_runs,
)
from mne.storage import save_run_json


def temp_data_root():
    root = Path(".tmp_mne_data") / f"narrative_memory_{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def write_run(results_dir, name, theme_scores=None, group_scores=None, **extra):
    results_dir.mkdir(parents=True, exist_ok=True)
    run = {
        "timestamp": name,
        "theme_scores": theme_scores if theme_scores is not None else {},
        "group_scores": group_scores if group_scores is not None else {},
    }
    if theme_scores:
        run["dominant_theme"] = max(theme_scores.items(), key=lambda item: item[1])[0]
    if group_scores:
        run["dominant_group"] = max(group_scores.items(), key=lambda item: item[1])[0]
    run.update(extra)
    path = results_dir / f"{name}.json"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return path, run


def directory_digest(path):
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


class NarrativeMemoryTests(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(".tmp_mne_data", ignore_errors=True)

    def test_window_selects_recent_meaningful_live_runs_only(self):
        root = temp_data_root()
        results_dir = root / "results"
        for index in range(12):
            write_run(
                results_dir,
                f"2026-07-{index + 1:02d}_120000",
                {"ai": index + 1},
                {"AI": index + 1},
            )

        runs = load_recent_memory_runs(results_dir, lookback=10)

        self.assertEqual(len(runs), 10)
        self.assertEqual(runs[0]["timestamp"], "2026-07-03_120000")
        self.assertEqual(runs[-1]["timestamp"], "2026-07-12_120000")

    def test_replay_artifacts_excluded(self):
        root = temp_data_root()
        results_dir = root / "results"
        replays_dir = root / "replays"
        write_run(results_dir, "2026-07-01_120000", {"ai": 1}, {"AI": 1})
        write_run(results_dir, "2026-07-02_120000", {"rates": 2}, {"Macro": 2})
        write_run(replays_dir, "2026-07-03_replay", {"replay_only": 99}, {"Replay": 99})

        memory = build_narrative_memory(results_dir=results_dir, lookback=10)
        names = {record["name"] for record in memory["themes"]}

        self.assertNotIn("replay_only", names)
        self.assertEqual(memory["memory_window"]["runs_used"], 2)

    def test_failed_or_no_signal_runs_excluded(self):
        root = temp_data_root()
        results_dir = root / "results"
        write_run(results_dir, "2026-07-01_120000", {"ai": 1}, {"AI": 1})
        write_run(results_dir, "2026-07-02_120000", {"ai": 99}, {"AI": 99}, status="failed")
        write_run(results_dir, "2026-07-03_120000", {"rates": 2}, {"Macro": 2})

        runs = load_recent_memory_runs(results_dir, lookback=10)

        self.assertEqual([run["timestamp"] for run in runs], ["2026-07-01_120000", "2026-07-03_120000"])

    def test_classifies_dominant(self):
        state = classify_memory_state(
            is_dominant=True,
            appearances_in_window=3,
            runs_used=3,
            streak_length=3,
            current_score=10,
            score_history=[4, 7, 10],
        )
        self.assertEqual(state, STATE_DOMINANT)

    def test_classifies_persistent(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=4,
            runs_used=5,
            streak_length=3,
            current_score=7,
            score_history=[1, 0, 7, 7, 7],
        )
        self.assertEqual(state, STATE_PERSISTENT)

    def test_classifies_building(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=3,
            runs_used=5,
            streak_length=3,
            current_score=5,
            score_history=[0, 0, 1, 3, 5],
        )
        self.assertEqual(state, STATE_BUILDING)

    def test_classifies_fading(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=3,
            runs_used=5,
            streak_length=3,
            current_score=2,
            score_history=[0, 0, 8, 5, 2],
        )
        self.assertEqual(state, STATE_FADING)

    def test_classifies_recurring(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=2,
            runs_used=5,
            streak_length=1,
            current_score=4,
            score_history=[3, 0, 0, 0, 4],
        )
        self.assertEqual(state, STATE_RECURRING)

    def test_classifies_re_accelerating(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=3,
            runs_used=5,
            streak_length=3,
            current_score=6,
            score_history=[0, 0, 5, 4, 6],
        )
        self.assertEqual(state, STATE_RE_ACCELERATING)

    def test_classifies_dormant(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=2,
            runs_used=5,
            streak_length=0,
            current_score=0,
            score_history=[2, 3, 0, 0, 0],
        )
        self.assertEqual(state, STATE_DORMANT)

    def test_classifies_emerging(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=1,
            runs_used=2,
            streak_length=1,
            current_score=3,
            score_history=[0, 3],
        )
        self.assertEqual(state, STATE_EMERGING)

    def test_classifies_absent(self):
        state = classify_memory_state(
            is_dominant=False,
            appearances_in_window=0,
            runs_used=5,
            streak_length=0,
            current_score=0,
            score_history=[0, 0, 0, 0, 0],
        )
        self.assertEqual(state, STATE_ABSENT)

    def test_streak_length(self):
        self.assertEqual(compute_narrative_streak([1, 0, 2, 3, 4]), 3)
        self.assertEqual(compute_narrative_streak([1, 2, 0]), 0)

    def test_rank_change_computation(self):
        ranks = compute_rank_changes({"ai": 1, "rates": 2}, {"rates": 1, "ai": 2}, "ai")
        self.assertEqual(ranks["latest_rank"], 1)
        self.assertEqual(ranks["previous_rank"], 2)
        self.assertEqual(ranks["rank_delta"], 1)

    def test_summary_lists_reconcile_with_records(self):
        runs = [
            {"timestamp": "r1", "theme_scores": {"ai": 1, "rates": 5}, "group_scores": {"AI": 1, "Macro": 5}, "dominant_theme": "rates", "dominant_group": "Macro"},
            {"timestamp": "r2", "theme_scores": {"ai": 3, "rates": 4}, "group_scores": {"AI": 3, "Macro": 4}, "dominant_theme": "rates", "dominant_group": "Macro"},
            {"timestamp": "r3", "theme_scores": {"ai": 6, "rates": 3}, "group_scores": {"AI": 6, "Macro": 3}, "dominant_theme": "ai", "dominant_group": "AI"},
        ]
        root = temp_data_root()
        memory = build_narrative_memory(current_run=runs[-1], results_dir=root / "results", lookback=3)
        records = memory["themes"] + memory["groups"]
        persistent = [record["name"] for record in records if record["memory_state"] == STATE_PERSISTENT]

        self.assertEqual(memory["summary"]["persistent_narratives"], persistent)
        self.assertEqual(memory["summary"]["dominant_memory"]["memory_state"], STATE_DOMINANT)

    def test_thin_history_warning(self):
        root = temp_data_root()
        write_run(root / "results", "2026-07-01_120000", {"ai": 1}, {"AI": 1})

        memory = build_narrative_memory(results_dir=root / "results", lookback=DEFAULT_MEMORY_RUNS)

        self.assertTrue(any("thin history" in warning for warning in memory["warnings"]))

    def test_persistence_under_latest_live_run(self):
        root = temp_data_root()
        results_dir = root / "results"
        current = {
            "timestamp": "2026-07-02_120000",
            "theme_scores": {"ai": 3},
            "group_scores": {"AI": 3},
            "dominant_theme": "ai",
            "dominant_group": "AI",
        }
        write_run(results_dir, "2026-07-01_120000", {"rates": 2}, {"Macro": 2})
        current["narrative_memory"] = build_narrative_memory(
            current_run=current,
            results_dir=results_dir,
        )

        _, path = save_run_json(current, "2026-07-02_120000", results_dir=results_dir)
        persisted = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("narrative_memory", persisted)
        self.assertEqual(persisted["narrative_memory"]["memory_window"]["runs_used"], 2)

    def test_admin_section_renders(self):
        run = {
            "timestamp": "2026-07-02_120000",
            "theme_scores": {"ai": 3},
            "group_scores": {"AI": 3},
            "dominant_theme": "ai",
            "dominant_group": "AI",
            "narrative_memory": build_narrative_memory(
                current_run={
                    "timestamp": "2026-07-02_120000",
                    "theme_scores": {"ai": 3},
                    "group_scores": {"AI": 3},
                    "dominant_theme": "ai",
                    "dominant_group": "AI",
                },
                results_dir=temp_data_root() / "results",
            ),
        }
        view = dashboard.build_view_model(run, Path("2026-07-02_120000.json"))
        original_url_for = dashboard.templates.env.globals.get("url_for")
        dashboard.templates.env.globals["url_for"] = lambda *args, **kwargs: "/static/styles.css"
        try:
            html = dashboard.templates.env.get_template("admin.html").render(
                request=object(),
                results_dir="/tmp/results",
                recent_runs=[],
                selected_file="2026-07-02_120000.json",
                message=None,
                notice=None,
                view=view,
                historical_replay_console=dashboard.build_historical_replay_console(),
            )
        finally:
            if original_url_for is None:
                dashboard.templates.env.globals.pop("url_for", None)
            else:
                dashboard.templates.env.globals["url_for"] = original_url_for

        self.assertIn('id="narrative-memory"', html)
        self.assertIn("Narrative Memory", html)
        self.assertIn("DOMINANT", html)

    def test_summaries_are_template_based(self):
        memory = build_narrative_memory(
            current_run={
                "timestamp": "2026-07-02_120000",
                "theme_scores": {"ai": 3},
                "group_scores": {"AI": 3},
                "dominant_theme": "ai",
                "dominant_group": "AI",
            },
            results_dir=temp_data_root() / "results",
        )
        summary = memory["themes"][0]["plain_language_summary"]

        self.assertEqual(
            summary,
            "ai has appeared in 1 of the last 1 meaningful runs and is dominant in the latest run.",
        )

    def test_no_replay_files_modified(self):
        root = temp_data_root()
        results_dir = root / "results"
        replays_dir = root / "replays"
        write_run(results_dir, "2026-07-01_120000", {"ai": 1}, {"AI": 1})
        write_run(replays_dir, "replay_2026-07-01_macro", {"rates": 9}, {"Macro": 9})
        before = directory_digest(replays_dir)

        build_narrative_memory(results_dir=results_dir)

        self.assertEqual(directory_digest(replays_dir), before)

    def test_no_historical_result_files_modified(self):
        root = temp_data_root()
        results_dir = root / "results"
        write_run(results_dir, "2026-07-01_120000", {"ai": 1}, {"AI": 1})
        before = directory_digest(results_dir)

        build_narrative_memory(
            current_run={
                "timestamp": "2026-07-02_120000",
                "theme_scores": {"rates": 2},
                "group_scores": {"Macro": 2},
            },
            results_dir=results_dir,
        )

        self.assertEqual(directory_digest(results_dir), before)

    def test_no_scoring_or_taxonomy_regression(self):
        current = {
            "timestamp": "2026-07-02_120000",
            "theme_scores": {"ai": 3},
            "group_scores": {"AI": 3},
            "dominant_theme": "ai",
            "dominant_group": "AI",
        }
        original = copy.deepcopy(current)

        build_narrative_memory(current_run=current, results_dir=temp_data_root() / "results")

        self.assertEqual(current, original)

    def test_no_source_fetching_occurs(self):
        with patch("mne.rss_fetch.fetch_headlines_from_rss") as fetch:
            build_narrative_memory(
                current_run={
                    "timestamp": "2026-07-02_120000",
                    "theme_scores": {"ai": 3},
                    "group_scores": {"AI": 3},
                },
                results_dir=temp_data_root() / "results",
            )

        fetch.assert_not_called()

    def test_deterministic_output(self):
        root = temp_data_root()
        results_dir = root / "results"
        write_run(results_dir, "2026-07-01_120000", {"ai": 1}, {"AI": 1})
        current = {
            "timestamp": "2026-07-02_120000",
            "theme_scores": {"ai": 3},
            "group_scores": {"AI": 3},
            "dominant_theme": "ai",
            "dominant_group": "AI",
        }

        first = build_narrative_memory(current_run=current, results_dir=results_dir)
        second = build_narrative_memory(current_run=current, results_dir=results_dir)

        self.assertEqual(first, second)
