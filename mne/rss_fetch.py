import feedparser


def fetch_headlines_from_rss(rss_urls, limit_per_feed=25):
    headlines = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if title:
                headlines.append(title)

    return headlines
