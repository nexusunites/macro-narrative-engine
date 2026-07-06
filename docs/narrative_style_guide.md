# Narrative Style Guide

The Narrative Brief is the public voice of the Macro Narrative Engine. It is a deterministic composition layer, not an AI-generated summary.

## Product Role

The Narrative Brief communicates what MNE currently observes from existing module outputs. It does not predict, recommend trades, speculate, or introduce new scoring logic.

Every sentence must be generated from a reviewed template and must resolve to one or more evidence objects in the persisted `narrative_brief.evidence_registry`.

## Tone

Narrative Brief language must remain:

- Calm
- Concise
- Analytical
- Objective
- Evidence-based
- Neutral
- High signal
- Low noise

It must not read like financial media, social media, marketing copy, opinion writing, clickbait, or AI-generated commentary.

## Writing Principles

Brief sentences should describe, explain, connect existing evidence, state conflicts plainly, and acknowledge unavailable data when required.

Templates must not:

- Predict future market direction
- Recommend trades
- Speculate
- Assume causality beyond explicit MNE evidence
- Invent relationships
- Overstate certainty

## Preferred Language

Preferred terms include:

- remains
- continues
- strengthened
- weakened
- accelerated
- moderated
- challenged
- confirmed
- diverged
- stabilized
- suggests
- indicates
- reflects
- appears
- transitioned

Avoid terms such as:

- exploded
- collapsed
- massive
- incredible
- shocking
- obvious
- guaranteed
- certain
- proves
- definitely
- must
- will
- likely
- expect

## Confidence Language

Brief-level `confidence` and section-level `section_confidence` describe data completeness and template specificity. They never describe predictive certainty.

User-facing UI must label this as "Data Completeness" or equivalent wording, not "Confidence in Outcome."

## Template Authoring Contract

Every Narrative Brief template must:

- Be registered in the source-controlled template library.
- Declare `style_guide = narrative_style_guide.v1`.
- Use calm, institutional language.
- Declare non-empty required evidence.
- Render deterministically from fixed bindings.
- Avoid forward-looking or recommendation language.
- Avoid the banned terms enforced by `mne.narrative_brief.validate_template_library`.

If a claim cannot be fully supported by explicit MNE evidence, no template should generate that claim.
