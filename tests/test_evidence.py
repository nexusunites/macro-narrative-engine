import unittest

from mne.evidence import (
    EVIDENCE_TYPE_HEADLINE,
    accepted_attributed_evidence_records,
    finalize_source_intelligence_diagnostics,
    evidence_to_headlines,
    generate_evidence_id,
    normalize_rss_entries_to_evidence,
    source_intelligence_counts,
)


class RegistryStub:
    def source_by_id(self, source_id):
        return {
            "source_id": source_id,
            "display_name": "Wall Street Journal",
            "provider": "Dow Jones",
        }


class EvidenceObjectTests(unittest.TestCase):
    def test_evidence_id_is_deterministic_and_normalizes_title(self):
        first = generate_evidence_id(
            source_id="reuters-business-news",
            evidence_type=EVIDENCE_TYPE_HEADLINE,
            timestamp="2026-07-06T12:00:00+00:00",
            title="  Fed Holds Rates  ",
            url="https://example.com/fed",
        )
        second = generate_evidence_id(
            source_id="reuters-business-news",
            evidence_type=EVIDENCE_TYPE_HEADLINE,
            timestamp="2026-07-06T12:00:00+00:00",
            title="fed holds rates",
            url="https://example.com/fed",
        )

        self.assertEqual(first, second)

    def test_normalizer_marks_exact_evidence_id_duplicate_rejected(self):
        entries = [
            {
                "title": "Fed holds rates",
                "summary": "Summary",
                "url": "https://example.com/fed",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
                "metadata": {"guid": "item-1"},
            },
            {
                "title": " Fed holds rates ",
                "summary": "Summary",
                "url": "https://example.com/fed",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
                "metadata": {"guid": "item-1"},
            },
        ]

        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:30:00+00:00",
        )

        self.assertEqual(len(evidence), 2)
        self.assertTrue(evidence[0].accepted)
        self.assertIsNone(evidence[0].rejection_reason)
        self.assertEqual(evidence[0].freshness_state, "FRESH")
        self.assertFalse(evidence[1].accepted)
        self.assertEqual(evidence[1].rejection_reason, "duplicate")
        self.assertEqual(evidence[1].freshness_state, "FRESH")
        self.assertEqual(evidence_to_headlines(evidence), ["Fed holds rates"])
        counts = source_intelligence_counts(evidence)
        self.assertEqual(counts["evidence_count"], 2)
        self.assertEqual(counts["accepted_count"], 1)
        self.assertEqual(counts["rejected_count"], 1)
        self.assertEqual(counts["evidence_freshness"]["fresh_count"], 2)
        self.assertEqual(counts["accepted_evidence"][0]["title"], "Fed holds rates")
        self.assertFalse(counts["accepted_evidence_truncated"])
        self.assertEqual(counts["evidence_funnel"]["fetched"], 2)
        self.assertEqual(counts["evidence_funnel"]["accepted_fresh"], 1)
        self.assertEqual(counts["evidence_funnel"]["rejected_duplicate"], 1)
        self.assertEqual(counts["evidence_funnel"]["analyzer_input_count"], 1)
        self.assertEqual(counts["rejected_evidence_preview"][0]["rejection_reason"], "duplicate")

    def test_adapter_preserves_accepted_headline_order_and_text(self):
        entries = [
            {
                "title": "  First headline  ",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
            {
                "title": "Second headline",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
            {
                "title": "first headline",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
        ]

        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
        )

        self.assertEqual(evidence_to_headlines(evidence), ["First headline", "Second headline"])

    def test_finalizer_records_analyzer_input_and_zero_match_warning(self):
        entries = [
            {
                "title": "First unrelated headline",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
            {
                "title": "Second unrelated headline",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
        ]
        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
        )
        source_intelligence = source_intelligence_counts(evidence)

        finalize_source_intelligence_diagnostics(
            source_intelligence,
            evidence,
            matched_headlines=0,
        )

        self.assertEqual(
            [item["title"] for item in source_intelligence["accepted_evidence"]],
            ["First unrelated headline", "Second unrelated headline"],
        )
        self.assertEqual(
            source_intelligence["evidence_funnel"]["analyzer_input_count"],
            2,
        )
        self.assertEqual(
            source_intelligence["zero_match_warning"]["sample_accepted_titles"],
            ["First unrelated headline", "Second unrelated headline"],
        )

    def test_accepted_attributed_records_persist_research_workspace_fields(self):
        entries = [
            {
                "title": "AI demand lifts shares",
                "summary": "Summary",
                "url": "https://example.com/ai",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
            {
                "title": "Duplicate stale headline",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            },
        ]
        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
        )
        evidence[1].accepted = False
        evidence[1].rejection_reason = "stale"

        records, truncated = accepted_attributed_evidence_records(
            evidence,
            [{"themes": ["ai"]}, {"themes": ["ai"]}],
            RegistryStub(),
        )

        self.assertFalse(truncated)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "AI demand lifts shares")
        self.assertEqual(records[0]["source_name"], evidence[0].source_name)
        self.assertEqual(records[0]["provider"], "Dow Jones")
        self.assertEqual(records[0]["evidence_type"], EVIDENCE_TYPE_HEADLINE)
        self.assertEqual(records[0]["published_at"], "2026-07-06T12:00:00+00:00")
        self.assertEqual(records[0]["url"], "https://example.com/ai")
        self.assertEqual(records[0]["freshness_state"], "FRESH")
        self.assertTrue(records[0]["accepted"])
        self.assertIn("theme:ai", records[0]["narrative_keys"])
        self.assertIn("group:AI / Tech Growth", records[0]["narrative_keys"])

    def test_zero_match_warning_is_omitted_when_matches_exist(self):
        entries = [
            {
                "title": "AI demand lifts shares",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            }
        ]
        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
        )
        source_intelligence = source_intelligence_counts(evidence)

        finalize_source_intelligence_diagnostics(
            source_intelligence,
            evidence,
            matched_headlines=1,
        )

        self.assertIsNone(source_intelligence["zero_match_warning"])


if __name__ == "__main__":
    unittest.main()
