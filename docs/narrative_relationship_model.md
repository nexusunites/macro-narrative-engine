# Narrative Relationship Model

The relationship model is a sparse, curated, deterministic presentation layer between existing narrative groups. It does not infer relationships from scores, text similarity, market data, or model output.

## Identity and schema

`config/narrative_relationships.json` uses semantic versioning and a `relationships` list. Each record requires `source_group`, `target_group`, `relationship_type`, `directionality`, `strength`, `public_label`, `explanation`, `display_enabled`, and `evidence_basis`.

Group identity is intentionally asymmetric: group keys are defined in Python by `NARRATIVE_GROUPS`, while relationships live in JSON. The exact `NARRATIVE_GROUPS` dictionary keys are the identifiers; no parallel slug vocabulary exists. The validator recognizes all current groups, including Geopolitical Risk, even when a group has no configured edge.

## Relationship types

- `SUPPORTIVE`: one narrative can reinforce another.
- `DEPENDENCY`: one narrative's development relies partly on another condition or resource.
- `OVERLAP`: narratives share meaningful underlying evidence or sectors.
- `TRANSMISSION`: a development in one narrative commonly propagates into another area.
- `OFFSETTING`: narratives can create counter-pressure or opposing market expression.
- `CONDITIONAL`: the relationship matters only under a stated condition.
- `SHARED_DRIVER`: both narratives respond to the same underlying factor.

Directionality is `SOURCE_TO_TARGET`, `TARGET_TO_SOURCE`, or `BIDIRECTIONAL`. One-way records are not mirrored. Strength is `STRONG`, `MODERATE`, or `LIMITED` and describes curated structural importance—not correlation, probability, confidence, or a forecast.

## Validation and display boundary

Loading fails closed on malformed versions, fields, enums, group keys, self-links, and duplicates. No value is repaired or defaulted. UI consumers catch loader failures and omit only the relationship layer, preserving the rest of the dashboard or Research page. Public output includes approved labels and explanations, but excludes evidence-basis and config metadata.
