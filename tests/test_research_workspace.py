import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from mne.evidence_summary import (
    FULL_ARTICLE_LIMITATION,
    LIMITATION_TEXT,
    build_evidence_reader_summary,
    normalize_evidence_reader_metadata,
    summarize_evidence_main_point,
    summarize_evidence_relevance,
)
from mne.research_workspace import (
    build_narrative_investigation,
    build_narrative_selector,
    select_latest_meaningful_run,
    split_narrative_key,
)


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def render_template(name, **context):
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["url_for"] = lambda endpoint, **values: (
        f"/research/{values['key']}"
        if endpoint == "narrative_investigation"
        else f"/static/{values.get('path', '')}"
    )
    defaults = {
        "request": object(),
        "results_dir": "/tmp/results",
        "selected_file": "2026-07-09_120000.json",
        "message": None,
        "notice": None,
        "is_admin": False,
    }
    defaults.update(context)
    return env.get_template(name).render(**defaults)


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
                    "provider": "Provider One",
                    "title": "AI capex expands",
                    "url": "https://example.com/ai",
                    "timestamp": "2026-07-09T10:00:00Z",
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
                                "provider": "Provider One",
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
        self.assertIn("type_label", selector[0])

    def test_selector_filters_zero_signal_narratives(self):
        selector = build_narrative_selector(
            {
                "theme_scores": {"ai": 0, "rates": 3},
                "group_scores": {"AI / Tech Growth": 0, "Macro Pressure": 3},
            }
        )

        keys = [item["key"] for item in selector]

        self.assertEqual(keys, ["group:Macro Pressure", "theme:rates"])

    def test_research_selector_template_renders_investigable_narratives(self):
        html = render_template(
            "research_selector.html",
            selector=build_narrative_selector(sample_run()),
        )

        self.assertIn("Choose a narrative to investigate", html)
        self.assertIn("AI / Tech Growth", html)
        self.assertIn("Investigate narrative", html)

    def test_research_selector_template_renders_calm_empty_state(self):
        html = render_template("research_selector.html", selector=[])

        self.assertIn("No narratives with supporting evidence in this run", html)
        self.assertNotIn("error", html.lower())

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
        self.assertEqual(
            investigation["supporting_evidence_display"],
            [
                {
                    "title": "AI capex expands",
                    "source_name": "Source One",
                    "provider": "Provider One",
                    "timestamp": "2026-07-09T10:00:00Z",
                    "url": "https://example.com/ai",
                    "article_link_available": True,
                    "matched_narrative": "AI / Tech Growth",
                    "matched_theme": "ai",
                    "matched_group": "AI / Tech Growth",
                    "evidence_type": "Headline",
                    "reader_summary": {
                        "evidence_type": "Headline",
                        "main_point": 'This headline references "AI capex expands".',
                        "why_it_matters": (
                            "This supports AI / Tech Growth by adding accepted "
                            "headline-level evidence related to capital spending."
                        ),
                        "narrative_connection": (
                            "This item contributes supporting evidence to AI / Tech Growth "
                            "because it matched persisted narrative terms: ai. One evidence "
                            "item does not independently validate the entire narrative."
                        ),
                        "matched_terms": ["ai"],
                        "known_information": [
                            "Headline-level evidence is available.",
                            "Source metadata is available.",
                            "Publication timestamp is available.",
                            "Narrative attribution is available.",
                            "Evidence type is available.",
                            "Original article link is available.",
                        ],
                        "what_mne_knows": "Headline-level evidence is available. Source metadata is available. Publication timestamp is available. Narrative attribution is available. Evidence type is available. Original article link is available.",
                        "what_mne_does_not_know": (
                            "Full article text is not stored in MNE, so this is not a "
                            "complete article summary."
                        ),
                        "limitations": f"{LIMITATION_TEXT} {FULL_ARTICLE_LIMITATION}",
                        "limitation_items": [
                            LIMITATION_TEXT,
                            FULL_ARTICLE_LIMITATION,
                        ],
                        "limited_detail": False,
                    },
                }
            ],
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

    def test_investigation_template_renders_zones_and_readable_evidence(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
        )

        self.assertIn("Zone 1 / Snapshot", html)
        self.assertIn("Zone 2 / Explanation", html)
        self.assertIn("Zone 3 / Evidence", html)
        self.assertIn("Zone 4 / Research Entry Points", html)
        self.assertIn("AI capex expands", html)
        self.assertIn("Source One", html)
        self.assertIn("Provider One", html)
        self.assertIn("2026-07-09T10:00:00Z", html)
        self.assertIn("evidence-card-button", html)
        self.assertIn("data-evidence-reader-target", html)
        self.assertIn("Evidence Reader", html)
        self.assertIn("Select an evidence item to read a quick summary.", html)
        self.assertIn("Headline-level summary", html)
        self.assertIn('This headline references &#34;AI capex expands&#34;.', html)
        self.assertIn("Matched narrative: AI / Tech Growth", html)
        self.assertIn("Matched theme: ai", html)
        self.assertIn("Matched narrative group: AI / Tech Growth", html)
        self.assertIn("Evidence type: Headline", html)
        self.assertIn("Open full article", html)
        self.assertIn('target="_blank" rel="noopener noreferrer"', html)
        self.assertIn(LIMITATION_TEXT, html)
        self.assertIn(FULL_ARTICLE_LIMITATION, html)
        self.assertNotIn("accepted-ai", html)
        self.assertNotIn("evidence_id", html)
        self.assertNotIn("source_id", html)
        self.assertNotIn("rejected-ai", html)
        self.assertNotIn("POL", html)
        self.assertNotIn("rejection_reason", html)
        self.assertNotIn("{&#", html)

    def test_evidence_reader_panel_shows_missing_url_state(self):
        run = sample_run()
        run["source_intelligence"]["evidence_objects"][0].pop("url")
        investigation = build_narrative_investigation(
            run,
            "group",
            "AI / Tech Growth",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
        )

        self.assertIn("Original article link unavailable.", html)
        self.assertNotIn("Open full article", html)

    def test_evidence_reader_ignores_invalid_url(self):
        run = sample_run()
        run["source_intelligence"]["evidence_objects"][0]["url"] = "javascript:alert(1)"
        investigation = build_narrative_investigation(
            run,
            "group",
            "AI / Tech Growth",
        )

        display = investigation["supporting_evidence_display"][0]

        self.assertIsNone(display["url"])
        self.assertFalse(display["article_link_available"])

    def test_evidence_summary_uses_headline_level_fields_without_article_body(self):
        evidence = {
            "title": "AI capex expands",
            "source_name": "Source One",
            "provider": "Provider One",
            "timestamp": "2026-07-09T10:00:00Z",
            "article_body": "This text must not appear in the reader summary.",
            "themes": ["ai"],
        }
        narrative = {
            "narrative_level": "theme",
            "narrative_id": "ai",
            "display_name": "Ai",
        }

        summary = build_evidence_reader_summary(evidence, narrative)

        rendered = " ".join(str(value) for value in summary.values())
        self.assertIn('This headline references "AI capex expands".', rendered)
        self.assertIn("matched persisted narrative terms: ai", rendered)
        self.assertNotIn("This text must not appear", rendered)

    def test_evidence_summary_can_use_persisted_snippet_without_article_body(self):
        evidence = {
            "snippet": "Company reported a model launch",
            "article_body": "This body must not appear.",
            "themes": ["ai"],
        }

        summary = build_evidence_reader_summary(
            evidence,
            {
                "narrative_level": "theme",
                "narrative_id": "ai",
                "display_name": "Ai",
            },
        )

        self.assertIn("Company reported a model launch", summary["main_point"])
        self.assertNotIn("This body must not appear", " ".join(str(value) for value in summary.values()))

    def test_evidence_summary_is_deterministic(self):
        evidence = {
            "title": "AI capex expands",
            "source_name": "Source One",
            "provider": "Provider One",
            "timestamp": "2026-07-09T10:00:00Z",
            "themes": ["ai"],
        }
        narrative = {
            "narrative_level": "theme",
            "narrative_id": "ai",
            "display_name": "Ai",
        }

        self.assertEqual(
            build_evidence_reader_summary(evidence, narrative),
            build_evidence_reader_summary(evidence, narrative),
        )

    def test_minimal_evidence_reader_state_renders_calmly(self):
        run = sample_run()
        run["source_intelligence"]["evidence_objects"][0] = {
            "accepted": True,
            "themes": ["ai"],
        }
        investigation = build_narrative_investigation(
            run,
            "group",
            "AI / Tech Growth",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
        )

        self.assertIn("Untitled evidence", html)
        self.assertIn("Unknown source", html)
        self.assertIn("MNE has limited headline-level detail for this evidence item.", html)
        self.assertIn(LIMITATION_TEXT, html)

    def test_main_point_minimal_state_is_honest(self):
        self.assertEqual(
            summarize_evidence_main_point({}),
            "MNE has limited headline-level detail for this evidence item.",
        )

    def test_why_it_matters_is_deterministic_and_conservative(self):
        evidence = {
            "title": "Rates move higher",
            "themes": ["rates"],
        }
        narrative = {
            "narrative_level": "theme",
            "narrative_id": "rates",
            "display_name": "Rates",
        }

        self.assertEqual(
            summarize_evidence_relevance(evidence, narrative),
            "This supports Rates because the persisted evidence is attributed to the rates theme.",
        )
        self.assertEqual(
            summarize_evidence_relevance(evidence, narrative),
            summarize_evidence_relevance(evidence, narrative),
        )

    def test_evidence_reader_metadata_is_user_safe_and_url_validated(self):
        metadata = normalize_evidence_reader_metadata(
            {
                "evidence_id": "internal-id",
                "source_id": "internal-source",
                "title": "AI model launch",
                "source_name": "Source One",
                "url": "https://example.com/story",
                "themes": ["ai"],
                "groups": ["AI / Tech Growth"],
            },
            {
                "narrative_level": "group",
                "narrative_id": "AI / Tech Growth",
                "display_name": "AI / Tech Growth",
            },
        )

        self.assertNotIn("evidence_id", metadata)
        self.assertNotIn("source_id", metadata)
        self.assertEqual(metadata["article_url"], "https://example.com/story")
        self.assertTrue(metadata["article_link_available"])

    def test_evidence_summary_has_no_external_or_ai_dependencies(self):
        source = Path(__file__).resolve().parents[1] / "mne" / "evidence_summary.py"
        text = source.read_text()

        self.assertNotIn("requests", text)
        self.assertNotIn("httpx", text)
        self.assertNotIn("urllib.request", text)
        self.assertNotIn("openai", text.lower())
        self.assertNotIn("anthropic", text.lower())

    def test_research_workspace_logic_regression_surface_stays_unchanged(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )

        self.assertEqual(investigation["overview"]["score"], 14)
        self.assertEqual(investigation["brief"]["headline"], "AI remains the dominant story")
        self.assertEqual(investigation["coverage"]["coverage_state"], "MINIMAL")
        self.assertEqual(
            [row["source_id"] for row in investigation["source_summary"]],
            ["s1"],
        )

    def test_coverage_explanation_is_neutral_for_minimal_state(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
        )

        self.assertIn("how broad the supporting evidence is", html)
        self.assertIn("not a judgment of narrative quality", html)
        self.assertNotIn("failure", html.lower())
        self.assertNotIn("warning", html.lower())

    def test_event_lifecycle_empty_state_renders_calmly(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "Macro Pressure",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
        )

        self.assertIn(
            "No relevant catalyst lifecycle context is available for this narrative in the selected run.",
            html,
        )
        self.assertNotIn("failed", html.lower())

    def test_standard_investigation_template_does_not_show_admin_content(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
            is_admin=False,
        )

        self.assertNotIn("Open admin diagnostics", html)
        self.assertNotIn("Platform Observability", html)
        self.assertNotIn("POL", html)

    def test_admin_investigation_template_shows_admin_reference(self):
        investigation = build_narrative_investigation(
            sample_run(),
            "group",
            "AI / Tech Growth",
            admin=True,
        )
        html = render_template(
            "narrative_investigation.html",
            investigation=investigation,
            is_admin=True,
        )

        self.assertIn("Open admin diagnostics", html)
        self.assertIn("run-123", html)

    def test_dashboard_investigate_link_wording_and_route_remain(self):
        dashboard_template = (TEMPLATE_DIR / "dashboard.html").read_text()

        self.assertIn("Investigate narrative", dashboard_template)
        self.assertIn("url_for('narrative_investigation'", dashboard_template)

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
