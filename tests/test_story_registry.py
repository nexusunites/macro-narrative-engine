import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from mne.story_registry import (
    StoryRegistryError,
    load_story_registry,
    validate_story_registry,
)


def story(**overrides):
    record = {
        "display_name": "AI Chips",
        "group": "AI / Tech Growth",
        "themes": ["ai"],
        "keywords": {"strong": ["nvidia"], "medium": [], "weak": []},
        "driving_sectors": ["technology"],
        "catalyst_names": [],
        "connected": [],
    }
    record.update(overrides)
    return record


class StoryRegistryTests(unittest.TestCase):
    def test_checked_in_registry_loads_as_frozen_records(self):
        registry = load_story_registry()
        self.assertEqual(registry.version, "1.0.0")
        self.assertEqual(len(registry.stories), 15)
        with self.assertRaises(FrozenInstanceError):
            registry.stories[0].slug = "changed"
        with self.assertRaises(FrozenInstanceError):
            registry.stories[0].keywords.strong = ()

    def test_schema_failures_are_closed(self):
        cases = [
            ({"version": "v1", "stories": {}}, "version"),
            ({"version": "1.0.0", "stories": []}, "stories"),
            ({"version": "1.0.0", "stories": {"x": story(group="Unknown")}}, ".group"),
            ({"version": "1.0.0", "stories": {"x": story(themes=["rates"])}}, ".themes"),
            ({"version": "1.0.0", "stories": {"x": story(driving_sectors=["moon"])}}, ".driving_sectors"),
            ({"version": "1.0.0", "stories": {"x": story(connected=["x"])}}, ".connected"),
            ({"version": "1.0.0", "stories": {"x": story(connected=["missing"])}}, ".connected"),
            ({"version": "1.0.0", "stories": {"x": story(keywords={"strong": [], "medium": [], "weak": []})}}, ".keywords"),
        ]
        for data, location in cases:
            with self.subTest(location=location), self.assertRaisesRegex(StoryRegistryError, location):
                validate_story_registry(data)

    def test_loader_wraps_io_and_json_errors(self):
        with self.assertRaises(StoryRegistryError):
            load_story_registry("/definitely/missing/story-registry.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(StoryRegistryError):
                load_story_registry(path)

    def test_deterministic_sort_is_stable(self):
        first = story(display_name="Zulu")
        second = story(display_name="Alpha")
        a = validate_story_registry({"version": "1.0.0", "stories": {"z_story": first, "a_story": second}})
        b = validate_story_registry({"stories": {"a_story": second, "z_story": first}, "version": "1.0.0"})
        self.assertEqual(a, b)
        self.assertEqual([item.slug for item in a.stories], ["a_story", "z_story"])


if __name__ == "__main__":
    unittest.main()
