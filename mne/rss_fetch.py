import feedparser
from calendar import timegm
from datetime import datetime, timezone


def _entry_timestamp(entry):
    parsed_timestamp = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed_timestamp:
        return datetime.fromtimestamp(timegm(parsed_timestamp), timezone.utc).isoformat()

    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if published:
        return str(published)

    return datetime.now(timezone.utc).isoformat()


def _entry_metadata(entry):
    metadata = {}
    guid = getattr(entry, "id", None)
    if guid:
        metadata["guid"] = str(guid)

    tags = getattr(entry, "tags", None)
    if tags:
        terms = [getattr(tag, "term", None) for tag in tags]
        terms = [term for term in terms if term]
        if terms:
            metadata["tags"] = terms

    return metadata


def fetch_headline_entries_from_rss(rss_urls, limit_per_feed=25):
    entries = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if title:
                entries.append(
                    {
                        "title": title,
                        "summary": getattr(entry, "summary", None),
                        "url": getattr(entry, "link", None),
                        "timestamp": _entry_timestamp(entry),
                        "feed_url": url,
                        "metadata": _entry_metadata(entry),
                    }
                )

    return entries


def fetch_headlines_from_rss(rss_urls, limit_per_feed=25, as_entries=False):
    entries = fetch_headline_entries_from_rss(rss_urls, limit_per_feed=limit_per_feed)
    if as_entries:
        return entries
    headlines = []
    for entry in entries:
        title = entry["title"].strip()
        if title:
            headlines.append(title)
    return headlines
