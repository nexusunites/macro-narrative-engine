import unittest

from mne.evidence import (
    evidence_to_headlines,
    normalize_rss_entries_to_evidence,
    source_intelligence_counts,
)
from mne.freshness import (
    FRESH,
    QUIET,
    STALE,
    UNKNOWN,
    classify_source_freshness,
    evaluate_evidence_freshness,
)
from mne.source_registry import SourceRegistry
from mne.theme_analysis import analyze_themes


def source(source_id, url, threshold=60):
    return {
        "source_id": source_id,
        "display_name": source_id.replace("-", " ").title(),
        "provider": "Test",
        "category": "General Business",
        "priority": "TIER_1",
        "ingestion_type": "RSS",
        "supported_evidence_types": ["Headline"],
        "url": url,
        "status": "ACTIVE",
        "freshness_threshold_minutes": threshold,
        "expected_update_frequency_minutes": 60,
        "supported_narratives": ["Macro"],
        "supported_groups": ["Macro"],
        "notes": None,
    }


def registry_with_sources(*sources):
    return SourceRegistry(
        registry_version="1.0.0",
        sources=tuple(sources),
        evidence_types=({"evidence_type": "Headline", "status": "active"},),
        categories=({"category": "General Business", "description": "Business news."},),
        priority_tiers=({"tier": "TIER_1", "description": "Core sources."},),
    )


class FreshnessTests(unittest.TestCase):
    def test_evaluates_fresh_stale_unknown_and_timezone_offsets(self):
        checked_at = "2026-07-06T12:00:00+00:00"

        fresh = evaluate_evidence_freshness("2026-07-06T07:30:00-04:00", 60, checked_at)
        stale = evaluate_evidence_freshness("2026-07-06T10:59:00+00:00", 60, checked_at)
        malformed = evaluate_evidence_freshness("not-a-date", 60, checked_at)
        future = evaluate_evidence_freshness("2026-07-06T12:01:00+00:00", 60, checked_at)

        self.assertEqual(fresh.freshness_state, FRESH)
        self.assertEqual(fresh.age_minutes, 30)
        self.assertEqual(stale.freshness_state, STALE)
        self.assertEqual(stale.age_minutes, 61)
        self.assertEqual(malformed.freshness_state, UNKNOWN)
        self.assertEqual(future.freshness_state, UNKNOWN)

    def test_fresh_evidence_enters_adapter_output(self):
        registry = registry_with_sources(source("fresh-source", "https://example.com/fresh.xml"))
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Fresh AI spending accelerates",
                    "timestamp": "2026-07-06T11:45:00+00:00",
                    "feed_url": "https://example.com/fresh.xml",
                }
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
        )

        self.assertTrue(evidence[0].accepted)
        self.assertEqual(evidence[0].freshness_state, FRESH)
        self.assertEqual(evidence_to_headlines(evidence), ["Fresh AI spending accelerates"])

    def test_stale_evidence_is_excluded_from_adapter_output(self):
        registry = registry_with_sources(source("stale-source", "https://example.com/stale.xml"))
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Stale AI spending accelerates",
                    "timestamp": "2026-07-06T10:00:00+00:00",
                    "feed_url": "https://example.com/stale.xml",
                }
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
        )

        self.assertFalse(evidence[0].accepted)
        self.assertEqual(evidence[0].freshness_state, STALE)
        self.assertEqual(evidence[0].rejection_reason, "stale")
        self.assertEqual(evidence_to_headlines(evidence), [])

    def test_unknown_timestamp_evidence_is_excluded_from_adapter_output(self):
        registry = registry_with_sources(source("unknown-source", "https://example.com/unknown.xml"))
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Unknown timestamp headline",
                    "timestamp": "not-a-date",
                    "feed_url": "https://example.com/unknown.xml",
                }
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
        )

        self.assertFalse(evidence[0].accepted)
        self.assertEqual(evidence[0].freshness_state, UNKNOWN)
        self.assertEqual(evidence[0].rejection_reason, "unknown_timestamp")
        self.assertEqual(evidence_to_headlines(evidence), [])

    def test_classifies_source_freshness_statuses(self):
        self.assertEqual(classify_source_freshness("HEALTHY", [FRESH, STALE]), FRESH)
        self.assertEqual(classify_source_freshness("HEALTHY", [STALE]), STALE)
        self.assertEqual(classify_source_freshness("EMPTY", []), QUIET)
        self.assertEqual(classify_source_freshness("OFFLINE", []), UNKNOWN)
        self.assertEqual(classify_source_freshness("HEALTHY", [UNKNOWN]), UNKNOWN)

    def test_source_freshness_and_run_diagnostics_are_persisted(self):
        fresh_source = source("fresh-source", "https://example.com/fresh.xml")
        stale_source = source("stale-source", "https://example.com/stale.xml")
        quiet_source = source("quiet-source", "https://example.com/quiet.xml")
        failed_source = source("failed-source", "https://example.com/failed.xml")
        registry = registry_with_sources(fresh_source, stale_source, quiet_source, failed_source)
        source_health = [
            {"source_id": "fresh-source", "state": "HEALTHY", "checked_at": "2026-07-06T12:00:00+00:00"},
            {"source_id": "stale-source", "state": "HEALTHY", "checked_at": "2026-07-06T12:00:00+00:00"},
            {"source_id": "quiet-source", "state": "EMPTY", "checked_at": "2026-07-06T12:00:00+00:00"},
            {"source_id": "failed-source", "state": "OFFLINE", "checked_at": "2026-07-06T12:00:00+00:00"},
        ]
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Fresh macro headline",
                    "timestamp": "2026-07-06T11:45:00+00:00",
                    "feed_url": "https://example.com/fresh.xml",
                },
                {
                    "title": "Stale macro headline",
                    "timestamp": "2026-07-06T10:00:00+00:00",
                    "feed_url": "https://example.com/stale.xml",
                },
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
            source_health=source_health,
        )

        counts = source_intelligence_counts(
            evidence,
            registry_version="1.0.0",
            source_health=source_health,
            registry=registry,
        )
        statuses = {
            item["source_id"]: item["status"]
            for item in counts["source_freshness"]
        }

        self.assertEqual(counts["evidence_freshness"], {
            "fresh_count": 1,
            "stale_count": 1,
            "unknown_count": 0,
        })
        self.assertEqual(statuses["fresh-source"], FRESH)
        self.assertEqual(statuses["stale-source"], STALE)
        self.assertEqual(statuses["quiet-source"], QUIET)
        self.assertEqual(statuses["failed-source"], UNKNOWN)
        self.assertEqual(counts["rejected_evidence_preview"][0]["rejection_reason"], "stale")

    def test_healthy_but_severely_stale_source_is_annotated(self):
        stale_source = source("stale-source", "https://example.com/stale.xml", threshold=60)
        registry = registry_with_sources(stale_source)
        source_health = [
            {
                "source_id": "stale-source",
                "source_name": "Stale Source",
                "state": "HEALTHY",
                "severity": "INFO",
                "checked_at": "2026-07-06T12:00:00+00:00",
            }
        ]
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Very old headline",
                    "timestamp": "2026-06-29T12:00:00+00:00",
                    "feed_url": "https://example.com/stale.xml",
                }
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
            source_health=source_health,
        )

        counts = source_intelligence_counts(
            evidence,
            registry_version="1.0.0",
            source_health=source_health,
            registry=registry,
        )

        self.assertTrue(counts["source_health"][0]["healthy_but_severely_stale"])
        self.assertEqual(counts["source_health"][0]["staleness_ratio"], 168.0)

    def test_mildly_stale_source_is_not_annotated_as_severe(self):
        stale_source = source("stale-source", "https://example.com/stale.xml", threshold=60)
        registry = registry_with_sources(stale_source)
        source_health = [
            {
                "source_id": "stale-source",
                "source_name": "Stale Source",
                "state": "HEALTHY",
                "severity": "INFO",
                "checked_at": "2026-07-06T12:00:00+00:00",
            }
        ]
        evidence = normalize_rss_entries_to_evidence(
            [
                {
                    "title": "Mildly old headline",
                    "timestamp": "2026-07-06T10:00:00+00:00",
                    "feed_url": "https://example.com/stale.xml",
                }
            ],
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
            source_health=source_health,
        )

        counts = source_intelligence_counts(
            evidence,
            registry_version="1.0.0",
            source_health=source_health,
            registry=registry,
        )

        self.assertFalse(counts["source_health"][0]["healthy_but_severely_stale"])
        self.assertEqual(counts["source_health"][0]["staleness_ratio"], 2.0)

    def test_stale_exclusion_changes_narrative_scores_attributably(self):
        registry = registry_with_sources(source("score-source", "https://example.com/score.xml"))
        entries = [
            {
                "title": "AI demand lifts technology shares",
                "timestamp": "2026-07-06T11:45:00+00:00",
                "feed_url": "https://example.com/score.xml",
            },
            {
                "title": "AI spending boom expands",
                "timestamp": "2026-07-06T10:00:00+00:00",
                "feed_url": "https://example.com/score.xml",
            },
        ]
        themes = {"ai": {"strong": ["ai"], "medium": [], "weak": []}}
        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
            registry=registry,
        )

        accepted_headlines = evidence_to_headlines(evidence)
        _, _, _, accepted_scores, _ = analyze_themes(accepted_headlines, themes)
        _, _, _, hypothetical_scores, _ = analyze_themes([entry["title"] for entry in entries], themes)

        self.assertEqual(accepted_headlines, ["AI demand lifts technology shares"])
        self.assertEqual(accepted_scores["ai"], 3)
        self.assertEqual(hypothetical_scores["ai"], 6)


if __name__ == "__main__":
    unittest.main()
