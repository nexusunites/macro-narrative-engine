import re

import feedparser


def normalize_headline(headline):
    headline = headline.lower()
    headline = re.sub(r"[^a-z0-9\s]", "", headline)
    headline = re.sub(r"\s+", " ", headline).strip()
    return headline


def dedupe_headlines(headlines):
    deduped = []
    seen = set()

    for headline in headlines:
        normalized = normalize_headline(headline)
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        deduped.append(headline)

    return deduped


def fetch_headlines_from_rss(rss_urls, limit_per_feed=25):
    headlines = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if title:
                headlines.append(title)

    return dedupe_headlines(headlines)
