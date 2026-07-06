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
                "feed_url": "https://feeds.reuters.com/reuters/businessNews",
                "metadata": {"guid": "item-1"},
            },
            {
                "title": " Fed holds rates ",
                "summary": "Summary",
                "url": "https://example.com/fed",
                "timestamp": "2026-07-06T12:00:00+00:00",
                "feed_url": "https://feeds.reuters.com/reuters/businessNews",
                "metadata": {"guid": "item-1"},
            },
        ]

        evidence = normalize_rss_entries_to_evidence(entries)

        self.assertEqual(len(evidence), 2)
        self.assertTrue(evidence[0].accepted)
        self.assertIsNone(evidence[0].rejection_reason)
        self.assertFalse(evidence[1].accepted)
        self.assertEqual(evidence[1].rejection_reason, "duplicate")
        self.assertEqual(evidence_to_headlines(evidence), ["Fed holds rates"])
        self.assertEqual(
            source_intelligence_counts(evidence),
            {
                "evidence_count": 2,
                "accepted_count": 1,
                "rejected_count": 1,
            },
        )

    def test_adapter_preserves_accepted_headline_order_and_text(self):
        entries = [
            "  First headline  ",
            "Second headline",
            "first headline",
        ]

        evidence = normalize_rss_entries_to_evidence(
            entries,
            run_timestamp="2026-07-06T12:00:00+00:00",
        )

        self.assertEqual(evidence_to_headlines(evidence), ["First headline", "Second headline"])


if __name__ == "__main__":
    unittest.main()
