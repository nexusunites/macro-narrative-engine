# mne/rss_fetch.py
import feedparser

def fetch_headlines_from_rss(rss_urls, limit_per_feed=25):
    headlines = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if title:
                headlines.append(title)

    # De-dupe while preserving order
    deduped = list(dict.fromkeys(headlines))
    return deduped