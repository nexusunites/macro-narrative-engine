from urllib.parse import urlparse


LIMITATION_TEXT = (
    "This interpretation is based on the persisted headline and evidence metadata. "
    "Full article text is not available in MNE."
)

FULL_ARTICLE_LIMITATION = "This is not a complete article summary."

THEME_RELEVANCE_TERMS = {
    "ai": {
        "product activity": ("model", "product", "release", "launch", "platform"),
        "capital spending": ("capex", "capital spending", "data center", "gpu", "chip"),
        "competition": ("compete", "competition", "rival"),
        "regulation": ("regulation", "regulator", "policy"),
        "infrastructure": ("infrastructure", "compute", "cloud"),
        "adoption": ("adoption", "customer", "enterprise"),
    },
    "rates": {
        "central-bank expectations": ("fed", "central bank", "rate cut", "rate hike"),
        "yields": ("yield", "treasury"),
        "financing conditions": ("credit", "loan", "financing"),
        "policy": ("policy",),
    },
    "energy": {
        "supply": ("supply", "output", "production"),
        "demand": ("demand",),
        "pricing": ("price", "oil", "gas"),
        "geopolitical sensitivity": ("geopolitical", "sanction", "conflict"),
    },
    "inflation": {
        "price pressure": ("inflation", "prices", "price pressure"),
        "consumer costs": ("consumer", "cost"),
        "wages": ("wage", "pay"),
        "policy sensitivity": ("policy", "fed", "central bank"),
    },
    "growth": {
        "economic activity": ("growth", "gdp", "activity"),
        "employment": ("jobs", "employment", "labor"),
        "demand": ("demand",),
        "slowdown risk": ("slowdown", "recession", "contraction"),
    },
    "recession": {
        "economic activity": ("growth", "gdp", "activity"),
        "employment": ("jobs", "employment", "labor"),
        "demand": ("demand",),
        "slowdown risk": ("slowdown", "recession", "contraction"),
    },
}


def build_evidence_reader_summary(evidence, selected_narrative):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    metadata = normalize_evidence_reader_metadata(evidence, selected_narrative)
    headline = metadata["title"] if metadata["has_headline"] else None
    matched_terms = _matched_terms(evidence, selected_narrative)
    known_information = build_evidence_known_fields(evidence, selected_narrative)
    limitations = build_evidence_limitations(evidence, selected_narrative)

    return {
        "evidence_type": metadata["evidence_type"],
        "main_point": summarize_evidence_main_point(evidence),
        "why_it_matters": summarize_evidence_relevance(evidence, selected_narrative),
        "narrative_connection": summarize_evidence_narrative_connection(
            evidence,
            selected_narrative,
        ),
        "matched_terms": matched_terms,
        "known_information": known_information,
        "what_mne_knows": " ".join(known_information),
        "what_mne_does_not_know": (
            "Full article text is not stored in MNE, so this is not a complete article summary."
        ),
        "limitations": " ".join(limitations),
        "limitation_items": limitations,
        "limited_detail": not bool(headline),
    }


def summarize_evidence_main_point(evidence):
    evidence = evidence if isinstance(evidence, dict) else {}
    evidence_text = _available_evidence_text(evidence)
    if not evidence_text:
        return "MNE has limited headline-level detail for this evidence item."
    if evidence_text["field"] in {"summary", "snippet", "text", "normalized_text"}:
        return f'The persisted evidence text references "{evidence_text["value"]}".'
    return f'This headline references "{evidence_text["value"]}".'


def summarize_evidence_relevance(evidence, selected_narrative):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    narrative_name = _clean_text(selected_narrative.get("display_name")) or "the selected narrative"
    theme = _primary_theme(evidence, selected_narrative)
    subtype = _supported_relevance_subtype(theme, _available_text_value(evidence))

    if subtype:
        return (
            f"This supports {narrative_name} by adding accepted headline-level evidence "
            f"related to {subtype}."
        )
    if theme:
        return (
            f"This supports {narrative_name} because the persisted evidence is attributed "
            f"to the {theme} theme."
        )
    return (
        f"This supports {narrative_name} because MNE accepted this item as "
        "headline-level evidence for the selected investigation."
    )


def summarize_evidence_narrative_connection(evidence, selected_narrative):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    narrative_name = _clean_text(selected_narrative.get("display_name"))
    if not narrative_name:
        return (
            "This item contributes supporting evidence to the selected investigation. "
            "One evidence item should be interpreted as one part of the broader evidence set."
        )

    matched_terms = _matched_terms(evidence, selected_narrative)
    if matched_terms:
        terms = ", ".join(matched_terms)
        return (
            f"This item contributes supporting evidence to {narrative_name} because it "
            f"matched persisted narrative terms: {terms}. One evidence item does not "
            "independently validate the entire narrative."
        )
    return (
        f"This item contributes supporting evidence to {narrative_name} through persisted "
        "narrative attribution. One evidence item does not independently validate the "
        "entire narrative."
    )


def build_evidence_known_fields(evidence, selected_narrative=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    metadata = normalize_evidence_reader_metadata(evidence, selected_narrative)
    known = []

    if metadata["has_headline"]:
        known.append("Headline-level evidence is available.")
    else:
        known.append("Headline-level detail is limited.")
    if metadata["source"] != "Unknown source" or metadata["provider"]:
        known.append("Source metadata is available.")
    if metadata["published_at"]:
        known.append("Publication timestamp is available.")
    if metadata["narrative"]:
        known.append("Narrative attribution is available.")
    if metadata["evidence_type"]:
        known.append("Evidence type is available.")
    if metadata["article_link_available"]:
        known.append("Original article link is available.")
    else:
        known.append("Original article link is unavailable.")
    return known


def build_evidence_limitations(evidence, selected_narrative=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    metadata = normalize_evidence_reader_metadata(evidence, selected_narrative)
    limitations = [LIMITATION_TEXT, FULL_ARTICLE_LIMITATION]
    if not metadata["has_headline"]:
        limitations.append("MNE has limited headline-level detail for this evidence item.")
    if not metadata["published_at"]:
        limitations.append("Publication time is unavailable.")
    if not metadata["provider"]:
        limitations.append("Provider metadata is unavailable.")
    if not metadata["article_link_available"]:
        limitations.append("Original article link is unavailable.")
    return limitations


def normalize_evidence_reader_metadata(evidence, selected_narrative=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    headline = _clean_text(evidence.get("title") or evidence.get("headline"))
    article_url = _valid_url(evidence.get("url") or evidence.get("link"))
    theme = _primary_theme(evidence, selected_narrative)
    group = _primary_group(evidence, selected_narrative)

    return {
        "title": headline or "Untitled evidence",
        "has_headline": bool(headline),
        "source": _clean_text(evidence.get("source_name")) or "Unknown source",
        "provider": _clean_text(evidence.get("provider")),
        "published_at": _clean_text(evidence.get("timestamp") or evidence.get("published_at")),
        "evidence_type": _clean_text(evidence.get("evidence_type")) or "Headline",
        "narrative": _clean_text(selected_narrative.get("display_name")),
        "theme": theme,
        "group": group,
        "matched_terms": _matched_terms(evidence, selected_narrative),
        "article_url": article_url,
        "article_link_available": bool(article_url),
    }


def _matched_terms(evidence, selected_narrative):
    terms = []
    narrative_level = selected_narrative.get("narrative_level")
    narrative_id = selected_narrative.get("narrative_id")

    if narrative_level == "theme":
        terms.extend(_matching_values(evidence.get("themes"), narrative_id))
        metadata = evidence.get("metadata")
        if isinstance(metadata, dict):
            terms.extend(_matching_values(metadata.get("themes"), narrative_id))
    elif narrative_level == "group":
        groups = evidence.get("groups") or evidence.get("narrative_groups")
        terms.extend(_matching_values(groups, narrative_id))
        metadata = evidence.get("metadata")
        if isinstance(metadata, dict):
            terms.extend(_matching_values(metadata.get("groups"), narrative_id))
        terms.extend(_theme_values(evidence))

    return sorted(dict.fromkeys(terms))


def _primary_theme(evidence, selected_narrative):
    if selected_narrative.get("narrative_level") == "theme":
        return _clean_text(selected_narrative.get("narrative_id"))
    themes = _theme_values(evidence)
    return themes[0] if themes else None


def _primary_group(evidence, selected_narrative):
    if selected_narrative.get("narrative_level") == "group":
        return _clean_text(selected_narrative.get("narrative_id"))
    groups = evidence.get("groups") or evidence.get("narrative_groups")
    if isinstance(groups, list):
        for group in groups:
            cleaned = _clean_text(group)
            if cleaned:
                return cleaned
    metadata = evidence.get("metadata")
    metadata_groups = metadata.get("groups") if isinstance(metadata, dict) else None
    if isinstance(metadata_groups, list):
        for group in metadata_groups:
            cleaned = _clean_text(group)
            if cleaned:
                return cleaned
    return None


def _theme_values(evidence):
    themes = []
    if isinstance(evidence.get("themes"), list):
        themes.extend(_clean_text(theme) for theme in evidence.get("themes"))
    metadata = evidence.get("metadata")
    metadata_themes = metadata.get("themes") if isinstance(metadata, dict) else None
    if isinstance(metadata_themes, list):
        themes.extend(_clean_text(theme) for theme in metadata_themes)
    return [theme for theme in dict.fromkeys(themes) if theme]


def _supported_relevance_subtype(theme, text):
    if not theme or not text:
        return None
    normalized_theme = str(theme).lower()
    text = text.lower()
    for theme_key, subtype_terms in THEME_RELEVANCE_TERMS.items():
        if theme_key not in normalized_theme:
            continue
        for subtype, terms in subtype_terms.items():
            if any(term in text for term in terms):
                return subtype
    return None


def _available_evidence_text(evidence):
    for field in ("summary", "snippet", "text", "normalized_text", "title", "headline"):
        value = _clean_text(evidence.get(field))
        if value:
            return {"field": field, "value": value}
    return None


def _available_text_value(evidence):
    text = _available_evidence_text(evidence)
    return text["value"] if text else None


def _valid_url(value):
    text = _clean_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text
    return None


def _matching_values(values, expected):
    if not isinstance(values, list) or expected is None:
        return []
    expected = str(expected)
    return [str(value) for value in values if str(value) == expected]


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None
