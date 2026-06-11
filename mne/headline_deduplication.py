import re
import unicodedata


def remove_punctuation(text):
    return "".join(
        character
        for character in text
        if not unicodedata.category(character).startswith("P")
    )


def normalize_headline_for_deduplication(headline):
    normalized = headline.lower()
    normalized = remove_punctuation(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def dedupe_headlines(headlines):
    deduped = []
    seen = set()

    for headline in headlines:
        normalized = normalize_headline_for_deduplication(headline)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        deduped.append(headline)

    return {
        "raw_headlines": headlines,
        "deduped_headlines": deduped,
        "raw_headline_count": len(headlines),
        "deduped_headline_count": len(deduped),
        "duplicate_count": len(headlines) - len(deduped),
    }
