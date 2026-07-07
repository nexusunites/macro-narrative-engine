import unittest

from mne.feed_health import (
    BLOCKED,
    CRITICAL,
    EMPTY,
    HEALTHY,
    INFO,
    OFFLINE,
    PARSE_ERROR,
    PARTIAL,
    RATE_LIMITED,
    REDIRECTED,
    UNKNOWN,
    WARNING,
    FetchMetadata,
    build_source_health_output,
    evaluate_feed_health,
)


class FeedHealthTests(unittest.TestCase):
    def metadata(self, **overrides):
        values = {
            "http_status": 200,
            "entries_seen": 1,
            "entries_parsed": 1,
            "fetch_error": None,
            "checked_at": "2026-07-06T12:00:00+00:00",
        }
        values.update(overrides)
        return FetchMetadata(**values)

    def test_evaluates_all_health_states(self):
        cases = [
            (self.metadata(http_status=None, entries_seen=0, entries_parsed=0, no_response=True), OFFLINE),
            (self.metadata(http_status=429, entries_seen=0, entries_parsed=0), RATE_LIMITED),
            (self.metadata(http_status=403, entries_seen=0, entries_parsed=0), BLOCKED),
            (
                self.metadata(redirected=True, final_url="https://example.com/new.xml"),
                REDIRECTED,
            ),
            (
                self.metadata(entries_seen=0, entries_parsed=0, parse_error=True),
                PARSE_ERROR,
            ),
            (self.metadata(entries_seen=0, entries_parsed=0), EMPTY),
            (self.metadata(entries_seen=2, entries_parsed=2), HEALTHY),
            (self.metadata(entries_seen=3, entries_parsed=1), PARTIAL),
            (self.metadata(entries_seen=1, entries_parsed=0), UNKNOWN),
        ]

        for metadata, expected_state in cases:
            with self.subTest(expected_state=expected_state):
                state, reason = evaluate_feed_health(metadata)
                self.assertEqual(state, expected_state)
                self.assertTrue(reason)

    def test_builds_source_health_output_with_fixed_severity_and_action(self):
        source = {
            "source_id": "test-source",
            "display_name": "Test Source",
            "url": "https://example.com/rss.xml",
        }

        output = build_source_health_output(
            source,
            self.metadata(entries_seen=2, entries_parsed=1),
        ).to_dict()

        self.assertEqual(output["source_id"], "test-source")
        self.assertEqual(output["source_name"], "Test Source")
        self.assertEqual(output["state"], PARTIAL)
        self.assertEqual(output["severity"], WARNING)
        self.assertEqual(output["recommended_action"], "Review feed structure if persistent; parsed entries remain usable.")

    def test_fixed_severity_mapping_for_required_classes(self):
        expectations = {
            HEALTHY: INFO,
            PARTIAL: WARNING,
            EMPTY: WARNING,
            REDIRECTED: WARNING,
            OFFLINE: CRITICAL,
            PARSE_ERROR: CRITICAL,
            RATE_LIMITED: CRITICAL,
            BLOCKED: CRITICAL,
            UNKNOWN: CRITICAL,
        }
        source = {
            "source_id": "test-source",
            "display_name": "Test Source",
            "url": "https://example.com/rss.xml",
        }

        for state, severity in expectations.items():
            metadata = self.metadata()
            if state == OFFLINE:
                metadata = self.metadata(http_status=None, entries_seen=0, entries_parsed=0, no_response=True)
            elif state == RATE_LIMITED:
                metadata = self.metadata(http_status=429, entries_seen=0, entries_parsed=0)
            elif state == BLOCKED:
                metadata = self.metadata(http_status=403, entries_seen=0, entries_parsed=0)
            elif state == REDIRECTED:
                metadata = self.metadata(redirected=True, final_url="https://example.com/new.xml")
            elif state == PARSE_ERROR:
                metadata = self.metadata(entries_seen=0, entries_parsed=0, parse_error=True)
            elif state == EMPTY:
                metadata = self.metadata(entries_seen=0, entries_parsed=0)
            elif state == PARTIAL:
                metadata = self.metadata(entries_seen=2, entries_parsed=1)
            elif state == UNKNOWN:
                metadata = self.metadata(entries_seen=1, entries_parsed=0)

            with self.subTest(state=state):
                output = build_source_health_output(source, metadata)
                self.assertEqual(output.state, state)
                self.assertEqual(output.severity, severity)


if __name__ == "__main__":
    unittest.main()
