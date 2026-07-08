import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from mne.rss_fetch import fetch_headline_entries_with_health_from_rss


TEST_URL = "https://example.com/rss.xml"


class TestRegistry:
    def source_by_url(self, url):
        return {
            "source_id": "test-source",
            "display_name": "Test Source",
            "url": url,
        }


def response(status_code=200, content=b"", url=TEST_URL):
    return SimpleNamespace(status_code=status_code, content=content, url=url)


def feed_with_items(*titles):
    items = []
    for title in titles:
        title_xml = f"<title>{title}</title>" if title is not None else ""
        items.append(f"<item>{title_xml}<link>https://example.com/{title or 'missing'}</link></item>")
    return (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<title>Test Feed</title>"
        f"{''.join(items)}"
        "</channel></rss>"
    ).encode("utf-8")


class RssFetchHealthTests(unittest.TestCase):
    def fetch(self):
        return fetch_headline_entries_with_health_from_rss(
            [TEST_URL],
            registry=TestRegistry(),
            timeout=1,
        )

    def test_healthy_feed_returns_entries_and_health(self):
        with patch("mne.rss_fetch.requests.get", return_value=response(content=feed_with_items("First", "Second"))) as get:
            result = self.fetch()

        self.assertEqual([entry["title"] for entry in result["entries"]], ["First", "Second"])
        self.assertEqual(result["source_health"][0]["state"], "HEALTHY")
        self.assertEqual(result["source_health"][0]["entries_seen"], 2)
        self.assertEqual(result["source_health"][0]["entries_parsed"], 2)
        self.assertIn("User-Agent", get.call_args.kwargs["headers"])

    def test_offline_fetch_persists_health_record(self):
        with patch(
            "mne.rss_fetch.requests.get",
            side_effect=requests.Timeout("Connection timed out after 10s"),
        ):
            result = self.fetch()

        self.assertEqual(result["entries"], [])
        self.assertEqual(result["source_health"][0]["state"], "OFFLINE")
        self.assertIsNone(result["source_health"][0]["http_status"])
        self.assertIn("Connection timed out", result["source_health"][0]["fetch_error"])

    def test_empty_feed_produces_empty_state(self):
        with patch("mne.rss_fetch.requests.get", return_value=response(content=feed_with_items())):
            result = self.fetch()

        self.assertEqual(result["entries"], [])
        self.assertEqual(result["source_health"][0]["state"], "EMPTY")
        self.assertEqual(result["source_health"][0]["entries_seen"], 0)

    def test_blocked_feed_produces_blocked_state(self):
        with patch("mne.rss_fetch.requests.get", return_value=response(status_code=403)):
            result = self.fetch()

        self.assertEqual(result["entries"], [])
        self.assertEqual(result["source_health"][0]["state"], "BLOCKED")
        self.assertEqual(result["source_health"][0]["http_status"], 403)

    def test_malformed_feed_produces_parse_error(self):
        with patch("mne.rss_fetch.requests.get", return_value=response(content=b"not a feed")):
            result = self.fetch()

        self.assertEqual(result["entries"], [])
        self.assertEqual(result["source_health"][0]["state"], "PARSE_ERROR")
        self.assertEqual(result["source_health"][0]["entries_seen"], 0)
        self.assertEqual(result["source_health"][0]["entries_parsed"], 0)

    def test_partial_feed_keeps_parseable_entries(self):
        with patch("mne.rss_fetch.requests.get", return_value=response(content=feed_with_items("First", None))):
            result = self.fetch()

        self.assertEqual([entry["title"] for entry in result["entries"]], ["First"])
        self.assertEqual(result["source_health"][0]["state"], "PARTIAL")
        self.assertEqual(result["source_health"][0]["entries_seen"], 2)
        self.assertEqual(result["source_health"][0]["entries_parsed"], 1)

    def test_redirected_feed_records_redirect_but_keeps_entries(self):
        with patch(
            "mne.rss_fetch.requests.get",
            return_value=response(content=feed_with_items("First"), url="https://example.com/new.xml"),
        ):
            result = self.fetch()

        self.assertEqual([entry["title"] for entry in result["entries"]], ["First"])
        self.assertEqual(result["source_health"][0]["state"], "REDIRECTED")
        self.assertEqual(result["source_health"][0]["entries_seen"], 1)
        self.assertEqual(result["source_health"][0]["entries_parsed"], 1)
        self.assertIn("registered URL", result["source_health"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
