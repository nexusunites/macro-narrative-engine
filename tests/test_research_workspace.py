import unittest

from mne.research_workspace import (
    build_narrative_investigation,
    build_narrative_selector,
    select_latest_meaningful_run,
    split_narrative_key,
)


def sample_run():
    return {
        "dominant_group": "AI / Tech Growth",
        "dominant_theme": "ai",
        "theme_scores": {"ai": 12, "rates": 3},
        "group_scores": {"AI / Tech Growth": 14, "Macro Pressure": 3},
        "narrative_pulse": {
            "AI / Tech Growth": {
                "pulse_state": "Strong",
                "confidence": "High",
            }
        },
        "regime_alignment": {
            "score": 72,
            "state": "Aligned",
        },
        "source_intelligence": {
            "evidence_objects": [
                {
                    "evidence_id": "accepted-ai",
                    "source_id": "s1",
                    "source_name": "Source One",
                    "title": "AI capex expands",
                    "url": "https://example.com/ai",
                    "accepted": True,
                    "themes": ["ai"],
                },
                {
                    "evidence_id": "rejected-ai",
                    "source_id": "s1",
                    "source_name": "Source One",
                    "title": "Duplicate AI capex expands",
                    "accepted": False,
                    "themes": ["ai"],
                },
                {
                    "evidence_id": "accepted-rates",
                    "source_id": "s2",
                    "source_name": "Source Two",
                    "title": "Rates move higher",
                    "accepted": True,
                    "themes": ["rates"],
                },
            ],
            "source_health": [
                {"source_id": "s1", "source_name": "Source One", "state": "HEALTHY"},
                {"source_id": "s2", "source_name": "Source Two", "state": "HEALTHY"},
            ],
            "source_freshness": [
                {"source_id": "s1", "freshness_state": "FRESH"},
                {"source_id": "s2", "freshness_state": "FRESH"},
            ],
            "coverage_intelligence": {
                "per_narrative": [
                    {
                        "narrative_level": "group",
                        "narrative_id": "AI / Tech Growth",
                        "evidence_count": 1,
                        "unique_source_count": 1,
                        "unique_provider_count": 1,
                        "concentration_ratio": 1.0,
                        "coverage_state": "MINIMAL",
                        "source_contribution_breakdown": [
                            {
                                "source_id": "s1",
                                "source_name": "Source One",
                                "evidence_count": 1,
                            }
                        ],
                    }
                ]
            },
        },
        "event_lifecycle": {
            "events": [
                {
                    "event_id": "ai-event",
                    "event_name": "AI Developer Conference",
                    "lifecycle_state": "Upcoming",
                    "narrative_groups": ["AI / Tech Growth"],
                },
                {
                    "event_id": "macro-event",
                    "event_name": "CPI",
                    "lifecycle_state": "Upcoming",
                },
                {
                    "event_id": "theme-only-event",
                    "event_name": "AI Product Event",
                    "lifecycle_state": "Upcoming",
                    "themes": ["ai"],
                },
            ]
        },
        "narrative_brief": {
            "headline": "AI remains the dominant story",
            "confidence": "HIGH",
            "summary": "AI leadership persisted.",
            "sections": [
                {
                    "section": "dominant_story",
                    "text": "AI / Tech Growth remains dominant.",
                    "evidence": ["brief-1"],
                }
            ],
            "evidence_registry": [{"evidence_id": "brief-1"}],
        },
        "platform_observability": {
            "run_metadata": {
                "run_id": "run-123",
                "run_duration_ms": 456,
            }
        },
    }


class ResearchWorkspaceTests(unittest.TestCase):
    def test_select_latest_meaningful_run_skips_empty_latest_with_notice(self):
        files = [
            type("PathStub", (), {"name": "2026-07-07_114250.json"})(),
            type("PathStub", (), {"name": "2026-07-06_114048.json"})(),
        ]
        runs = {
            "2026-07-07_114250.json": {
                "theme_scores": {"ai": 0},
                "group_scores": {"AI / Tech Growth": 0},
            },
            "2026-07-06_114048.json": {
                "theme_scores": {"ai": 4},
                "group_scores": {"AI / Tech Growth": 4},
            },
        }

        selection = select_latest_meaningful_run(
            files,
            lambda path: runs[path.name],
        )

        self.assertEqual(selection.path.name, "2026-07-06_114048.json")
        self.assertEqual(
            selection.notice,
            (
                "Latest run had no narrative signal; showing latest meaningful run: "
                "2026-07-06_114048.json."
            ),
        )

    def test_select_latest_meaningful_run_has_no_notice_when_latest_has_signal(self):
        files = [type("PathStub", (), {"name": "2026-07-07_114250.json"})()]
        selection = select_latest_meaningful_run(
            files,
            lambda path: {"theme_scores": {"ai": 4}},
        )

        self.assertEqual(selection.path.name, "2026-07-07_114250.json")
        self.assertIsNone(selection.notice)

    def test_selector_lists_groups_and_themes_from_existing_scores(self):
        selector = build_narrative_selector(sample_run())

        keys = [item["key"] for item in selector]

        self.assertIn("group:AI / Tech Growth", keys)
        self.assertIn("theme:ai", keys)

    def test_selector_filters_zero_signal_narratives(self):
        selector = build_narrative_selector(
            {
                "theme_scores": {"ai": 0, "rates": 3},
                "group_scores": {"AI / Tech Growth": 0, "Macro Pressure": 3},
            }
        )

        keys = [item["key"] for item in selector]

        self.assertEqual(keys, ["group:Macro Pressure", "theme:rates"])

    def test_investigation_reads_coverage_values_and_filters_sources_exactly(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )

        self.assertEqual(investigation["coverage"]["evidence_count"], 1)
        self.assertEqual(investigation["coverage"]["unique_source_count"], 1)
        self.assertEqual(investigation["coverage"]["unique_provider_count"], 1)
        self.assertEqual(investigation["coverage"]["concentration_ratio"], 1.0)
        self.assertEqual(investigation["coverage"]["coverage_state"], "MINIMAL")
        self.assertEqual(
            [row["source_id"] for row in investigation["source_summary"]],
            ["s1"],
        )

    def test_supporting_evidence_uses_only_accepted_persisted_narrative_links(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )

        self.assertEqual(
            [row["evidence_id"] for row in investigation["supporting_evidence"]],
            ["accepted-ai"],
        )

    def test_supporting_evidence_reads_persisted_accepted_attributed_records(self):
        run = sample_run()
        run["source_intelligence"].pop("evidence_objects")
        run["source_intelligence"]["accepted_evidence"] = [
            {
                "evidence_id": "accepted-ai",
                "source_id": "s1",
                "source_name": "Source One",
                "title": "AI capex expands",
                "url": "https://example.com/ai",
                "accepted": True,
                "themes": ["ai"],
                "groups": ["AI / Tech Growth"],
                "narrative_keys": ["theme:ai", "group:AI / Tech Growth"],
            },
            {
                "evidence_id": "rejected-ai",
                "source_id": "s1",
                "source_name": "Source One",
                "title": "Rejected AI capex expands",
                "accepted": False,
                "themes": ["ai"],
                "groups": ["AI / Tech Growth"],
                "narrative_keys": ["theme:ai", "group:AI / Tech Growth"],
            },
            {
                "evidence_id": "accepted-rates",
                "source_id": "s2",
                "source_name": "Source Two",
                "title": "Rates move higher",
                "accepted": True,
                "themes": ["rates"],
                "groups": ["Macro Pressure"],
                "narrative_keys": ["theme:rates", "group:Macro Pressure"],
            },
        ]

        investigation = build_narrative_investigation(
            run,
            "group",
            "AI / Tech Growth",
        )

        self.assertEqual(
            [row["evidence_id"] for row in investigation["supporting_evidence"]],
            ["accepted-ai"],
        )

    def test_events_require_existing_narrative_link_and_empty_without_one(self):
        ai = build_narrative_investigation(sample_run(), "group", "AI / Tech Growth")
        ai_theme = build_narrative_investigation(sample_run(), "theme", "ai")
        macro = build_narrative_investigation(sample_run(), "group", "Macro Pressure")

        self.assertEqual([event["event_id"] for event in ai["events"]], ["ai-event"])
        self.assertEqual(
            [event["event_id"] for event in ai_theme["events"]],
            ["theme-only-event"],
        )
        self.assertEqual(macro["events"], [])

    def test_events_can_use_existing_definition_lookup_by_event_id(self):
        run = sample_run()
        run["event_lifecycle"]["events"] = [
            {
                "event_id": "ai-definition-event",
                "event_name": "AI Supplier Earnings",
                "lifecycle_state": "Upcoming",
            }
        ]

        investigation = build_narrative_investigation(
            run,
            "group",
            "AI / Tech Growth",
            event_definitions=[
                {
                    "event_id": "ai-definition-event",
                    "narrative_groups": ["AI / Tech Growth"],
                }
            ],
        )

        self.assertEqual(
            [event["event_id"] for event in investigation["events"]],
            ["ai-definition-event"],
        )

    def test_platform_observability_is_admin_only(self):
        user_view = build_narrative_investigation(sample_run(), "group", "AI / Tech Growth")
        admin_view = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
            admin=True,
        )

        self.assertIsNone(user_view["platform_observability"])
        self.assertEqual(
            admin_view["platform_observability"],
            {
                "run_id": "run-123",
                "run_duration_ms": 456,
            },
        )

    def test_split_narrative_key_rejects_invalid_values(self):
        self.assertEqual(
            split_narrative_key("group:AI / Tech Growth"),
            ("group", "AI / Tech Growth"),
        )
        self.assertEqual(split_narrative_key("bad:AI"), (None, None))


if __name__ == "__main__":
    unittest.main()
