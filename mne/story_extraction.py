"""Deterministic story extraction from accepted, theme-attributed headlines."""

from __future__ import annotations

from typing import Any

from mne.story_registry import StoryRegistry
from mne.theme_analysis import find_theme_keyword_candidates, select_non_overlapping_matches


def _accepted_headlines(headlines, theme_attribution):
    allowed = {
        item.get("headline")
        for item in theme_attribution
        if isinstance(item, dict) and isinstance(item.get("headline"), str)
    }
    seen = set()
    output = []
    for headline in headlines:
        if not isinstance(headline, str) or headline not in allowed or headline in seen:
            continue
        seen.add(headline)
        output.append(headline)
    return output


def extract_stories(
    headlines,
    theme_attribution,
    registry: StoryRegistry,
    accepted_evidence=None,
) -> dict:
    accepted_evidence = accepted_evidence if isinstance(accepted_evidence, list) else []
    accepted = _accepted_headlines(headlines, theme_attribution)
    evidence_by_title = {
        item.get("title"): item
        for item in accepted_evidence
        if isinstance(item, dict) and isinstance(item.get("title"), str)
    }
    extracted = []
    for story in registry.stories:
        score = 0
        matched_titles = []
        keywords = story.keywords.as_dict()
        for headline in accepted:
            matches = select_non_overlapping_matches(
                find_theme_keyword_candidates(headline, keywords)
            )
            if not matches:
                continue
            score += sum(match["weight"] for match in matches)
            matched_titles.append(headline)
        if score <= 0:
            continue
        examples = []
        for title in matched_titles:
            record = evidence_by_title.get(title)
            if not isinstance(record, dict):
                continue
            examples.append({
                "title": title,
                "source": record.get("provider") or record.get("source_name") or "",
                "timestamp": record.get("published_at") or record.get("timestamp") or "",
            })
            if len(examples) == 3:
                break
        extracted.append((story.slug, {
            "slug": story.slug,
            "score": score,
            "matched_count": len(matched_titles),
            "examples": examples,
        }))
    extracted.sort(key=lambda item: (-item[1]["score"], item[0]))
    return dict(extracted)


def build_story_extraction(
    headlines,
    theme_attribution,
    accepted_evidence,
    registry: StoryRegistry,
    prior_run: Any = None,
) -> dict:
    stories = extract_stories(headlines, theme_attribution, registry, accepted_evidence)
    total = sum(item["score"] for item in stories.values())
    prior_extraction = prior_run.get("story_extraction") if isinstance(prior_run, dict) else None
    prior_stories = prior_extraction.get("stories") if isinstance(prior_extraction, dict) else None
    has_prior = isinstance(prior_stories, dict)
    prior_total = (
        sum(item.get("score", 0) for item in prior_stories.values() if isinstance(item, dict))
        if has_prior else 0
    )
    for slug, item in stories.items():
        share = item["score"] / total if total else 0
        if has_prior:
            prior_item = prior_stories.get(slug)
            prior_score = prior_item.get("score", 0) if isinstance(prior_item, dict) else 0
            prior_share = prior_score / prior_total if prior_total else 0
            item["share_delta"] = share - prior_share
        else:
            item["share_delta"] = 0
    return {"registry_version": registry.version, "stories": stories}
