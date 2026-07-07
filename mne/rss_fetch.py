import feedparser
import requests
from calendar import timegm
from datetime import datetime, timezone

from mne.feed_health import FetchMetadata, build_source_health_output, checked_at_now


def _entry_timestamp(entry):
    parsed_timestamp = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed_timestamp:
        return datetime.fromtimestamp(timegm(parsed_timestamp), timezone.utc).isoformat()

    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if published:
        return str(published)

    return None


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


def _parse_feed_entry(entry, feed_url):
    title = getattr(entry, "title", "").strip()
    if not title:
        return None
    return {
        "title": title,
        "summary": getattr(entry, "summary", None),
        "url": getattr(entry, "link", None),
        "timestamp": _entry_timestamp(entry),
        "feed_url": feed_url,
        "metadata": _entry_metadata(entry),
    }


def _is_redirected(registered_url, final_url):
    if not final_url:
        return False
    return final_url.rstrip("/") != registered_url.rstrip("/")


def _source_for_url(registry, url):
    if registry is None:
        return None
    return registry.source_by_url(url)


def fetch_headline_entries_with_health_from_rss(
    rss_urls,
    limit_per_feed=25,
    registry=None,
    timeout=10,
):
    entries = []
    source_health = []

    for url in rss_urls:
        checked_at = checked_at_now()
        source = _source_for_url(registry, url)
        response = None
        feed = None
        feed_entries = []
        parsed_entries = []
        metadata = None

        try:
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            http_status = response.status_code
            final_url = response.url
            redirected = _is_redirected(url, final_url)

            if http_status in (403, 429):
                metadata = FetchMetadata(
                    http_status=http_status,
                    entries_seen=0,
                    entries_parsed=0,
                    fetch_error=f"HTTP {http_status} received",
                    checked_at=checked_at,
                    redirected=redirected,
                    final_url=final_url,
                )
            else:
                feed = feedparser.parse(response.content)
                feed_entries = list(getattr(feed, "entries", []) or [])[:limit_per_feed]
                for entry in feed_entries:
                    try:
                        parsed_entry = _parse_feed_entry(entry, url)
                    except Exception:
                        parsed_entry = None
                    if parsed_entry:
                        parsed_entries.append(parsed_entry)

                bozo_exception = getattr(feed, "bozo_exception", None)
                parse_error = bool(getattr(feed, "bozo", False)) and not feed_entries
                fetch_error = str(bozo_exception) if parse_error and bozo_exception else None
                if redirected:
                    fetch_error = f"Redirected to {final_url} (registered URL: {url})"

                metadata = FetchMetadata(
                    http_status=http_status,
                    entries_seen=len(feed_entries),
                    entries_parsed=len(parsed_entries),
                    fetch_error=fetch_error,
                    checked_at=checked_at,
                    redirected=redirected,
                    final_url=final_url,
                    parse_error=parse_error,
                )
                entries.extend(parsed_entries)
        except (requests.Timeout, requests.ConnectionError) as error:
            metadata = FetchMetadata(
                http_status=None,
                entries_seen=0,
                entries_parsed=0,
                fetch_error=str(error),
                checked_at=checked_at,
                no_response=True,
            )
        except Exception as error:
            metadata = FetchMetadata(
                http_status=getattr(response, "status_code", None),
                entries_seen=len(feed_entries),
                entries_parsed=len(parsed_entries),
                fetch_error=f"{type(error).__name__}: {error}",
                checked_at=checked_at,
            )

        if source is not None:
            source_health.append(build_source_health_output(source, metadata).to_dict())

    return {
        "entries": entries,
        "source_health": source_health,
    }


def fetch_headline_entries_from_rss(rss_urls, limit_per_feed=25):
    entries = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            parsed_entry = _parse_feed_entry(entry, url)
            if parsed_entry:
                entries.append(parsed_entry)

    return entries


def fetch_headlines_from_rss(
    rss_urls,
    limit_per_feed=25,
    as_entries=False,
    include_health=False,
    registry=None,
):
    if include_health:
        result = fetch_headline_entries_with_health_from_rss(
            rss_urls,
            limit_per_feed=limit_per_feed,
            registry=registry,
        )
        if as_entries:
            return result
        entries = result["entries"]
        result["headlines"] = [entry["title"].strip() for entry in entries if entry["title"].strip()]
        return result

    entries = fetch_headline_entries_from_rss(rss_urls, limit_per_feed=limit_per_feed)
    if as_entries:
        return entries
    headlines = []
    for entry in entries:
        title = entry["title"].strip()
        if title:
            headlines.append(title)
    return headlines
