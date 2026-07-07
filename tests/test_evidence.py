import unittest

from mne.evidence import (
    EVIDENCE_TYPE_HEADLINE,
    evidence_to_headlines,
    generate_evidence_id,
    normalize_rss_entries_to_evidence,
    source_intelligence_counts,
)


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


if __name__ == "__main__":
    unittest.main()
