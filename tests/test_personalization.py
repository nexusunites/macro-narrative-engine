import json
import tempfile
import unittest
from pathlib import Path

from mne.personalization import (
    build_default_preferences,
    follow_narrative,
    load_preferences,
    remove_historical_view,
    save_historical_view,
    save_preferences,
    unfollow_narrative,
)


class PersonalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_preferences_build_deterministically(self):
        self.assertEqual(build_default_preferences(), build_default_preferences())

    def test_followed_theme_and_group_persist_and_unfollow(self):
        profile = follow_narrative(build_default_preferences(), "theme", "energy")
        profile = follow_narrative(profile, "group", "Macro Pressure")
        save_preferences(profile, self.data_dir)
        loaded = load_preferences(self.data_dir)
        self.assertEqual(len(loaded["followed_narratives"]), 2)
        loaded = unfollow_narrative(loaded, "theme", "energy")
        self.assertEqual(loaded["followed_narratives"], [{"narrative_level": "group", "narrative_key": "Macro Pressure"}])

    def test_saved_investigation_and_comparison_persist(self):
        profile = save_historical_view(build_default_preferences(), "investigation", ["replay_2024-03-15_macro"])
        profile = save_historical_view(profile, "comparison", ["replay_2024-03-15_macro", "replay_2025-04-10_macro"])
        save_preferences(profile, self.data_dir)
        self.assertEqual(len(load_preferences(self.data_dir)["saved_historical_views"]), 2)
        profile = remove_historical_view(profile, "investigation", ["replay_2024-03-15_macro"])
        self.assertEqual(len(profile["saved_historical_views"]), 1)

    def test_invalid_or_raw_ids_are_rejected(self):
        for value in ("../result.json", "/tmp/replay.json", "raw_id"):
            with self.assertRaises(ValueError):
                save_historical_view(build_default_preferences(), "investigation", [value])

    def test_malformed_profile_falls_back_calmly(self):
        path = self.data_dir / "preferences" / "profile.json"
        path.parent.mkdir(parents=True)
        path.write_text("{bad", encoding="utf-8")
        loaded = load_preferences(self.data_dir)
        self.assertTrue(loaded["limitation_note"])
        self.assertEqual(loaded["followed_narratives"], [])

    def test_storage_does_not_expose_paths_or_internals(self):
        save_preferences(build_default_preferences(), self.data_dir)
        text = (self.data_dir / "preferences" / "profile.json").read_text()
        self.assertNotIn(str(self.data_dir), text)
        self.assertNotIn("source_id", text)


if __name__ == "__main__":
    unittest.main()
