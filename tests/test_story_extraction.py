import json
import unittest

from mne.story_extraction import build_story_extraction, extract_stories
from mne.story_registry import validate_story_registry


def registry():
    base = {
        "group": "AI / Tech Growth",
        "themes": ["ai"],
        "driving_sectors": ["technology"],
        "catalyst_names": [],
        "connected": [],
    }
    return validate_story_registry({
        "version": "1.0.0",
        "stories": {
            "ai_chips": {**base, "display_name": "AI Chips", "keywords": {"strong": ["nvidia"], "medium": ["ai chips"], "weak": ["chip"]}},
            "cloud_spending": {**base, "display_name": "Cloud Spending", "keywords": {"strong": ["ai capex"], "medium": ["cloud"], "weak": []}},
            "zero_story": {**base, "display_name": "Zero Story", "keywords": {"strong": ["never appears"], "medium": [], "weak": []}},
        },
    })


class StoryExtractionTests(unittest.TestCase):
    def setUp(self):
        self.headlines = [
            "Nvidia unveils AI chips for servers",
            "Cloud providers lift AI capex",
            "Nvidia chip demand remains firm",
            "Nvidia expands production",
        ]
        self.attribution = [{"headline": title, "themes": ["ai"]} for title in self.headlines]
        self.evidence = [
            {"title": title, "provider": f"Source {index}", "published_at": f"2026-08-0{index}T12:00:00Z"}
            for index, title in enumerate(self.headlines, 1)
        ]

    def test_scores_counts_omission_and_examples_are_deterministic(self):
        result = extract_stories(self.headlines, self.attribution, registry(), self.evidence)
        self.assertEqual(list(result), ["ai_chips", "cloud_spending"])
        self.assertEqual(result["ai_chips"]["score"], 12)
        self.assertEqual(result["ai_chips"]["matched_count"], 3)
        self.assertEqual(len(result["ai_chips"]["examples"]), 3)
        self.assertEqual(result["ai_chips"]["examples"][0]["title"], self.headlines[0])
        self.assertEqual(result["cloud_spending"]["score"], 5)
        self.assertNotIn("zero_story", result)
        self.assertEqual(
            json.dumps(result, sort_keys=True),
            json.dumps(extract_stories(self.headlines, self.attribution, registry(), self.evidence), sort_keys=True),
        )

    def test_titles_without_evidence_still_score_but_have_no_example(self):
        result = extract_stories(self.headlines, self.attribution, registry(), self.evidence[1:])
        self.assertEqual(result["ai_chips"]["matched_count"], 3)
        self.assertNotEqual(result["ai_chips"]["examples"][0]["title"], self.headlines[0])

    def test_direction_share_delta_is_steady_without_prior_and_changes_with_prior(self):
        first = build_story_extraction(self.headlines, self.attribution, self.evidence, registry(), None)
        self.assertTrue(all(item["share_delta"] == 0 for item in first["stories"].values()))
        prior = {"story_extraction": {"stories": {"ai_chips": {"score": 1}, "cloud_spending": {"score": 9}}}}
        current = build_story_extraction(self.headlines, self.attribution, self.evidence, registry(), prior)
        self.assertGreater(current["stories"]["ai_chips"]["share_delta"], 0)
        self.assertLess(current["stories"]["cloud_spending"]["share_delta"], 0)
        self.assertEqual(json.dumps(current, sort_keys=True), json.dumps(build_story_extraction(self.headlines, self.attribution, self.evidence, registry(), prior), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
