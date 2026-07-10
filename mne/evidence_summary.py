LIMITATION_TEXT = "This is based on headline-level evidence. Full article text is not stored in MNE."


def build_evidence_reader_summary(evidence, selected_narrative):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    headline = _clean_text(evidence.get("title") or evidence.get("headline"))
    narrative_name = _clean_text(selected_narrative.get("display_name"))
    matched_terms = _matched_terms(evidence, selected_narrative)

    return {
        "evidence_type": _clean_text(evidence.get("evidence_type")) or "Headline",
        "main_point": summarize_evidence_main_point(evidence),
        "why_it_matters": _why_it_matters(narrative_name),
        "narrative_connection": summarize_evidence_narrative_connection(
            evidence,
            selected_narrative,
        ),
        "matched_terms": matched_terms,
        "what_mne_knows": _what_mne_knows(evidence),
        "what_mne_does_not_know": (
            "MNE does not have the full article body, so this is not a full article summary."
        ),
        "limitations": build_evidence_limitations(evidence),
        "limited_detail": not bool(headline),
    }


def summarize_evidence_main_point(evidence):
    evidence = evidence if isinstance(evidence, dict) else {}
    headline = _clean_text(evidence.get("title") or evidence.get("headline"))
    if not headline:
        return "MNE has limited headline-level detail for this evidence item."
    return f'This evidence references the headline "{headline}".'


def summarize_evidence_narrative_connection(evidence, selected_narrative):
    evidence = evidence if isinstance(evidence, dict) else {}
    selected_narrative = selected_narrative if isinstance(selected_narrative, dict) else {}
    narrative_name = _clean_text(selected_narrative.get("display_name"))
    if not narrative_name:
        return "This evidence has a persisted narrative attribution in MNE."

    matched_terms = _matched_terms(evidence, selected_narrative)
    if matched_terms:
        terms = ", ".join(matched_terms)
        return (
            f"This evidence was attributed to {narrative_name} through persisted "
            f"matched terms: {terms}."
        )
    return f"This evidence was attributed to {narrative_name} in the persisted evidence record."


def build_evidence_limitations(evidence):
    return LIMITATION_TEXT


def _why_it_matters(narrative_name):
    if not narrative_name:
        return "It matters because MNE accepted this item as supporting evidence for the selected narrative."
    return (
        f"It supports the {narrative_name} narrative by adding accepted headline-level "
        "evidence to the investigation."
    )


def _what_mne_knows(evidence):
    fields = []
    if _clean_text(evidence.get("title") or evidence.get("headline")):
        fields.append("headline")
    if _clean_text(evidence.get("source_name")):
        fields.append("source")
    if _clean_text(evidence.get("provider")):
        fields.append("provider")
    if _clean_text(evidence.get("timestamp") or evidence.get("published_at")):
        fields.append("timestamp")
    fields.append("narrative attribution")

    if len(fields) == 1:
        field_text = fields[0]
    else:
        field_text = ", ".join(fields[:-1]) + f", and {fields[-1]}"
    return f"MNE has the {field_text}."


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

    return sorted(dict.fromkeys(terms))


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
