# Cross-Group Narrative Relationship Model — Implementation Handoff

## Purpose

The Narrative Constellation currently renders only confirmed group→theme membership edges
(`mne/narrative_constellation.py` module docstring, lines 1–16, states this explicitly as a V1
limitation). It has no cross-group relationship layer, so the constellation cannot show that,
say, "AI / Tech Growth" and "Energy / Commodities" are structurally connected. This sprint adds a
curated, versioned, auditable relationship layer between narrative groups — config-backed, not
inferred from score movement, word similarity, or an LLM — and a safe read path that the
constellation and Research Workspace can consume. It does not touch scoring, taxonomy matching,
source ingestion, Narrative Memory, or Historical Replay.

Every node in the constellation already carries an unused `related_keys: []` field
(`mne/narrative_constellation.py:135` area, `select_visible_nodes`) — placeholder scaffolding for
exactly this feature. This sprint gives that field (and a sibling relationships list) real
content.

**Status: brief only, not yet ratified.** Two grounding decisions below resolve implementation
ambiguity by matching existing codebase convention (§Grounding Decisions) and do not need
sign-off. A short list of genuine product judgment calls remains open (§Open Items for Daniel).

Do not implement code from this document directly. This is the Codex-ready brief.

---

## Grounding Decisions (resolved against existing convention, no sign-off needed)

1. **Group identity: use the existing `NARRATIVE_GROUPS` dict keys directly, not new slugs.**
   `mne/narrative_signals.py:1–6` defines the actual narrative-group taxonomy as a hardcoded
   Python dict, not a JSON config:
   ```python
   NARRATIVE_GROUPS = {
       "AI / Tech Growth": ["ai", "semiconductors", "big_tech"],
       "Macro Pressure": ["rates", "inflation", "recession"],
       "Energy / Commodities": ["energy", "oil", "commodities"],
       "Geopolitical Risk": ["war", "china", "tariffs"],
   }
   ```
   There is no canonical slug distinct from the display label anywhere in the codebase — the
   dict key itself (spaces, slash and all) is the identifier used everywhere: `accounts.py:40`
   (`valid_groups = set(NARRATIVE_GROUPS)`), URL routing via `narrative_key("group", "AI / Tech
   Growth")`, and the constellation's own node `key`/`taxonomy_key` fields. The original spec's
   instruction to "use stable group keys if the taxonomy already exposes them" is satisfied by
   this dict — `source_group`/`target_group` in `config/narrative_relationships.json` should be
   the exact `NARRATIVE_GROUPS` key strings (e.g. `"AI / Tech Growth"`), validated by importing
   and checking membership in `set(NARRATIVE_GROUPS)`. Do not invent a parallel slug system —
   that would create two identifier spaces for the same four groups.
   - **Known asymmetry worth documenting, not fixing:** the group taxonomy itself lives in Python
     source (`narrative_signals.py`), while the new relationship layer lives in JSON config
     (`config/narrative_relationships.json`) per the spec. This means relationship config
     validates against a Python-defined vocabulary, not another config file. That's fine — it
     mirrors how `mne/theme_analysis.py:96` validates theme config against its own taxonomy — but
     call it out in `docs/narrative_relationship_model.md` so a future reader doesn't assume both
     taxonomies are config-driven.

2. **Validation style: mirror `mne/source_registry.py`, not `mne/theme_analysis.py`.**
   `source_registry.py` (`load_source_registry` / `validate_source_registry`, lines ~166–260) is
   the codebase's fail-closed reference implementation: a dedicated `SourceRegistryError(ValueError)`
   subclass, `load_*` does I/O and delegates to `validate_*`, `validate_*` raises immediately and
   specifically on the first violation (missing keys, type checks, duplicate IDs, enum membership,
   semver checks), and the loader returns an immutable dataclass (tuples, not lists). By contrast
   `theme_analysis.py:96`'s `load_taxonomy_config` normalizes/defaults instead of raising — too
   lenient for a "fail closed, no silent repair" requirement. `mne/narrative_relationships.py`
   should follow `source_registry.py`'s shape: `NarrativeRelationshipError(ValueError)`,
   `load_narrative_relationships(path=...)`, `validate_relationship_config(data)`.

---

## Open Items for Daniel

- **Initial relationship set vs. the fourth group.** `NARRATIVE_GROUPS` has four entries, not
  three: AI / Tech Growth, Macro Pressure, Energy / Commodities, **and Geopolitical Risk**. The
  spec's candidate list (§Initial Relationship Set below) only covers the first three. Confirm
  it's acceptable to ship v1 with Geopolitical Risk unconnected (sparse network, consistent with
  "don't force every group to connect") rather than inventing a relationship for it under
  deadline pressure.
- **Constellation edge styling.** The SVG `<line>` loop in
  `templates/_partials/narrative_constellation.html` (lines 14–20) currently renders all edges
  identically. Making cross-group edges "visually distinct from group-to-theme membership lines"
  (spec §10) requires a small template change — a CSS class keyed off `relationship.type` — not
  just a data change. Confirm this counts as in-scope "constellation integration," not a deferred
  follow-up.

---

## 1. Objective Summary

Add a versioned, curated config (`config/narrative_relationships.json`) describing explicit
directional relationships between the four `NARRATIVE_GROUPS` keys; a fail-closed loader/validator
and read API (`mne/narrative_relationships.py`); a public-safe presentation model
(`mne/presentation_language.py` additions); cross-group edges rendered in the Narrative
Constellation, visually distinct from existing group→theme membership edges; and an optional
compact "Related narratives" section in the Research Workspace investigation page. No scoring,
taxonomy, ingestion, or layout-engine changes.

## 2. Files Changed

**Create:**
- `config/narrative_relationships.json` — the versioned relationship config (§3).
- `mne/narrative_relationships.py` — loader, validator, read API (§7). Follows the
  `source_registry.py` fail-closed pattern (Grounding Decision 2).
- `tests/test_narrative_relationships.py` — unittest-style, mirroring
  `tests/test_narrative_constellation.py`'s conventions (module-level fixture factories, direct
  import of the module under test, plus a partial-render test via
  `dashboard.templates.env.get_template(...)`).
- `docs/narrative_relationship_model.md` — schema reference, relationship-type definitions, the
  group-identity note from Grounding Decision 1.

**Modify:**
- `mne/narrative_constellation.py` — add `build_cross_group_relationships(nodes)` as a sibling to
  the existing `build_group_theme_relationships` (line 177), producing
  `{"source": key, "target": key, "type": "cross_group", "relationship_type": ..., "strength": ...}`
  dicts sorted per §7's deterministic order. Call it from `build_constellation_context` (line 247)
  and append its output to the same unified `relationships` list the group/theme edges already
  populate — the template's edge loop already iterates this list generically, so no new template
  data-plumbing is needed, only the type-discriminated styling from Open Item 2. Also populate the
  previously-unused `related_keys` field on each group node (`select_visible_nodes`, line 135) with
  the group's connected group keys, sorted, for X-Ray consumption.
- `templates/_partials/narrative_constellation.html` — add a `relationship-{{ type }}` (or
  equivalent) CSS class to the `<line>` loop (lines 14–20) so `cross_group` edges render distinctly
  from `group_theme` edges (e.g. dashed vs. solid, different stroke color drawn from the existing
  token set — no new hues). Extend the plain-text X-Ray details block (lines 41–43) to include
  relationship label/explanation text so the JS-disabled fallback still carries the meaning, not
  just the SVG line.
- `static/narrative_constellation.js` — only if the hover/focus card (`aside[data-constellation-card]`)
  needs a new field for relationship explanation text; the existing `pointerenter`/`focus` handler
  already populates the card from a JSON payload, so this is additive, not structural.
- `mne/presentation_language.py` — add a `NARRATIVE_RELATIONSHIP_COPY` dict + accessor function
  following the exact `NARRATIVE_CONSTELLATION_COPY` / `constellation_copy()` pattern (lines
  80–96): flat dict, function raises `KeyError` on unknown keys rather than defaulting silently.
  Do not touch `narrative_display_name` — note for whoever picks this up that it is defined twice
  in this file (lines 325 and 772) and the second definition wins; don't add relationship-label
  logic to the dead first copy by mistake.
- `templates/narrative_investigation.html` — if Related Narratives is included (§11), add it as
  its own small `content-section`, **not** by repurposing the two `future-entry` placeholder rows
  already reserved for "Historical replay" and "Narrative memory" inside Zone 4 / Research Entry
  Points (lines 339–352) — those are spoken for. Either a new section near Zone 4
  (`#investigation-next`, line 309) or a `_partials/` include following the
  `_partials/narrative_history_summary.html` inclusion pattern (imported at template line 2).
- `dashboard.py` — wire `build_narrative_relationships(run, narrative_level, narrative_id)` into
  `build_investigation_context` (lines 1996–2041), assigning to `context["related_narratives"]`,
  the same shape as the existing `context["historical_connection"]` injection. No change needed to
  the dashboard-level `build_view_model` wiring (line 1640) — cross-group edges flow through
  `build_constellation_context` already.

**Tests (new or extended):**
- `tests/test_narrative_relationships.py` — new, covers config load/validate/read-API cases (§15
  items 1–15 from the original spec).
- `tests/test_narrative_constellation.py` — extend for cross-group edge presence, distinct styling
  hook, byte-stability with relationships present/absent, `related_keys` population.
- Focused Research Workspace test file (extend whichever currently covers
  `narrative_investigation.html` rendering) — Related Narratives section renders only when data
  exists, degrades cleanly when absent.

## 3. Relationship-Schema Summary

`config/narrative_relationships.json`, versioned (`"version": "1.0.0"`), a list of relationship
objects:

```json
{
  "version": "1.0.0",
  "relationships": [
    {
      "source_group": "AI / Tech Growth",
      "target_group": "Energy / Commodities",
      "relationship_type": "DEPENDENCY",
      "directionality": "BIDIRECTIONAL",
      "strength": "MODERATE",
      "public_label": "Infrastructure demand connection",
      "explanation": "AI infrastructure growth can increase power and data-center demand.",
      "display_enabled": true,
      "evidence_basis": "CURATED_DOMAIN_LOGIC"
    }
  ]
}
```

`source_group` / `target_group` values must be exact `NARRATIVE_GROUPS` keys (Grounding Decision
1) — not display-formatted variants, not new slugs.

## 4. Allowed Relationship-Type Summary

Seven types, narrow and explicit, each requiring precise documentation in
`docs/narrative_relationship_model.md` (no vague "RELATED" catch-all):

| Type | Meaning |
|---|---|
| `SUPPORTIVE` | One narrative can reinforce another. |
| `DEPENDENCY` | One narrative's development relies partly on another condition or resource. |
| `OVERLAP` | Narratives share meaningful underlying evidence or sectors. |
| `TRANSMISSION` | A development in one narrative commonly propagates into another area. |
| `OFFSETTING` | Narratives can create counter-pressure or opposing market expression. |
| `CONDITIONAL` | The relationship matters only under a stated condition. |
| `SHARED_DRIVER` | Both narratives respond to the same underlying factor. |

**Directionality:** `SOURCE_TO_TARGET`, `TARGET_TO_SOURCE`, `BIDIRECTIONAL`. One-way relationships
are never auto-mirrored — `get_relationships_for_group()` must respect direction when deciding
whether a group sees itself as source or target of a given edge.

**Strength:** `STRONG`, `MODERATE`, `LIMITED` — a curated structural-importance rating, not a
computed correlation, probability, or confidence score. No market-data calculation of strength
this sprint.

## 5. Validation Behavior

Fail closed (raise `NarrativeRelationshipError`, never silently repair) on:
- unknown `source_group` / `target_group` (not in `set(NARRATIVE_GROUPS)`)
- self-links (`source_group == target_group`)
- duplicate relationships (same source/target/directionality combination appearing twice)
- invalid `relationship_type`, `directionality`, or `strength` (not in the enumerated sets above)
- missing `explanation` or missing `public_label`
- malformed `version` (not semver-shaped)
- `display_enabled: true` without a non-empty, safe `public_label` and `explanation`

Malformed config must fail the loader, not the dashboard render — `build_constellation_context`
and `build_investigation_context` should treat a relationship-config load failure the same way
`build_group_theme_relationships` already treats bad input: degrade to an empty relationships
list for that layer rather than crashing the page (mirroring the constellation's existing
"filter invalid nodes/edges rather than raise" behavior at the read-path boundary, while the
config loader itself still raises hard at load time — the failure surfaces in logs/tests, not to
end users).

## 6. Initial Curated Relationship Set

Candidates to validate against `NARRATIVE_GROUPS`' actual four entries (AI / Tech Growth, Macro
Pressure, Energy / Commodities, Geopolitical Risk):

- **AI / Tech Growth ↔ Energy / Commodities** — `DEPENDENCY`, `BIDIRECTIONAL`, infrastructure and
  power-demand connection.
- **Macro Pressure → AI / Tech Growth** — `TRANSMISSION`, `SOURCE_TO_TARGET`, rates/financial-
  conditions transmission into growth-sensitive narratives.
- **Energy / Commodities → Macro Pressure** — `TRANSMISSION`, `SOURCE_TO_TARGET`, inflation-
  pressure transmission.
- **Macro Pressure ↔ Energy / Commodities** — `SHARED_DRIVER` or `OFFSETTING`, only if the
  rationale is precise; do not add if it can't be stated without hedging.

Geopolitical Risk is left unconnected in v1 pending Daniel's confirmation (Open Items). Sparse and
credible beats dense and decorative — do not force a fourth group into a relationship to make the
network look complete.

## 7. Read API Summary

`mne/narrative_relationships.py`, deterministic ordering throughout (sort by strength, then
relationship type, then target group key):

- `load_narrative_relationships(path=...)` — I/O + delegates to validation, raises
  `NarrativeRelationshipError` on any failure, returns an immutable structure (tuple of frozen
  relationship records, matching `source_registry.py`'s dataclass convention).
- `validate_relationship_config(data)` — the fail-closed checks in §5.
- `get_relationships_for_group(group_key)` — respects directionality; a group only sees inbound
  edges where it is the resolved target, and outbound where it is the resolved source, with
  `BIDIRECTIONAL` resolving both ways.
- `get_display_relationships(...)` — filters to `display_enabled: true` only.
- `build_relationship_adjacency(...)` — group-key → sorted list of related group keys, feeds the
  constellation's `related_keys` node field.
- `build_relationship_summary(...)` — aggregate counts/labels for a compact UI surface.
- `relationship_exists(source, target)` — directionality-aware existence check.
- `normalize_relationship(...)` — internal helper turning a raw config dict into the public
  presentation shape (§8), used by both the constellation and Research Workspace consumers.

## 8. Constellation Integration

- `build_cross_group_relationships(nodes)` in `narrative_constellation.py` (new, sibling to
  `build_group_theme_relationships`) converts loaded relationships into the same
  `{"source", "target", "type"}` edge shape already used for membership edges, adding
  `relationship_type` and `strength` for styling/X-Ray use, appended into the single
  `constellation.relationships` array `build_constellation_context` already returns.
- Only `display_enabled: true` relationships render.
- Cross-group edges get a distinct SVG class from membership edges (Open Item 2) — different
  stroke style, same token-derived color set, no new hues introduced.
- Node positions are untouched — `compute_deterministic_positions` (line 188) is explicitly out of
  scope; relationship strength must never feed into layout.
- No continuous animation on edges (matches the existing static/hover-reveal interaction model).
- X-Ray disclosure: extend the existing plain-text details block (template lines 41–43) and the
  hover/focus card (JS) to surface relationship label + explanation, so both the JS-disabled
  fallback and the interactive card carry the same meaning.
- Default (non-X-Ray) view stays exactly as simple as today — cross-group edges only appear inside
  the existing `data-constellation-xray` reveal, consistent with how theme nodes/membership edges
  already behave.

## 9. Research Workspace Integration

Optional, low-risk, secondary section on `narrative_investigation.html` only (not the selector
grid, not a network view): for each related group (via `get_relationships_for_group`), show
relationship label, related group's display name, explanation, and a link to that group's
investigation page (`/research/{key}`). Placed as its own section, not inside the two reserved
`future-entry` placeholder rows (Grounding Decision territory — see §2). No large network
visualization in Research this sprint.

## 10. Public-Language Behavior

Plain, hedged language only, following the existing `presentation_language.py` convention of
returning fixed, pre-approved copy strings rather than composing dynamic causal claims:

- "AI infrastructure growth is connected to rising power demand."
- "Interest-rate pressure can weigh on growth-sensitive narratives."
- "Energy developments can feed into the broader inflation narrative."

Never: causal certainty ("causes," "will lead to"), predictive phrasing, trade implications, or
numeric precision the model doesn't actually carry (no fabricated percentages/probabilities per
relationship). The public presentation shape exposes only `label`, `type_label`, `strength_label`,
`explanation`, `directionality` — never raw enum values, config file paths, `evidence_basis`, or
relationships where `display_enabled: false`.

## 11. Safety / Boundary Verification

- No changes to `mne/theme_analysis.py`, theme/group scoring, taxonomy matching, source ingestion,
  Narrative Memory, or Historical Replay — grep confirms zero references to those modules planned
  in this sprint's file list.
- `compute_deterministic_positions` untouched — relationship data never feeds layout.
- No LLM, embedding, or correlation computation anywhere in `narrative_relationships.py` — purely
  a config loader + deterministic transforms, matching the constellation module's own "no
  `requests`/`compute_group_scores` calls" test guarantee (`tests/test_narrative_constellation.py`).
- Fail-closed config loading verified by dedicated malformed-config tests (§5), not just a
  self-report.

## 12. Verification Performed

Read-only research pass, no code written: `mne/narrative_signals.py` (`NARRATIVE_GROUPS` source of
truth), `mne/narrative_constellation.py` (full module — node/edge construction, positioning,
context assembly, existing `related_keys` placeholder), `templates/_partials/narrative_constellation.html`
and `static/narrative_constellation.js` (edge rendering, X-Ray toggle, JS-disabled fallback),
`mne/presentation_language.py` (copy-block/accessor pattern, the duplicate `narrative_display_name`
definition), `templates/narrative_investigation.html` (full section inventory, the reserved
`future-entry` placeholder rows), `mne/research_workspace.py` (`build_narrative_investigation`),
`mne/source_registry.py` (fail-closed loader/validator pattern to mirror) vs. `mne/theme_analysis.py`
(the looser pattern to avoid), `tests/test_narrative_constellation.py` (test conventions to mirror),
`dashboard.py` (constellation and investigation-context wiring points, lines 45, 1640, 1776,
1996–2041). Codex must run the commands in §Verification Commands below after implementing —
nothing here substitutes for that.

## 13. Known Remaining Gaps

- Geopolitical Risk group has no candidate relationship in the initial set (Open Items).
- No existing per-edge CSS styling hook in the constellation template today — this sprint adds the
  first one; confirm the visual treatment (dashed line, distinct token color) doesn't drift toward
  a third hue.
- `narrative_display_name`'s duplicate definition in `presentation_language.py` (lines 325, 772)
  is unrelated dead code discovered during this research pass — not this sprint's job to fix, but
  worth a future cleanup ticket so nobody edits the dead copy by mistake.
- No Playwright/browser test suite exists for visual verification of edge styling distinction —
  manual visual pass required (see Verification Commands).
- `docs/narrative_relationship_model.md` does not yet exist — this sprint creates it from scratch.

## 14. Recommended Next Sprint

In priority order once this lands: (1) confirm and add a Geopolitical Risk relationship if a
precise, non-speculative rationale emerges, (2) sector-level heatmap using the same curated-config
pattern (explicit non-goal this sprint per §13 of the original spec), (3) surface relationship
context inside the AI Analyst's "what changed" explanations where a display-enabled relationship
is directly relevant, (4) revisit whether Research Workspace's Related Narratives section deserves
promotion to a primary (not secondary) placement once usage data exists.

## 15. Implementation Status

**Not implemented — brief only, pending ratification of the two Open Items above.** Once Daniel
confirms the Geopolitical Risk scope decision and the constellation-styling scope call, this
document is ready to hand to Codex as-is. Mark "Cross-Group Narrative Relationship Model"
implemented only after Codex completes the scoped work and every command below passes.

---

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_narrative_relationships -v`
- `python -m unittest tests.test_narrative_constellation -v`
- Focused Research Workspace tests (whichever file covers `narrative_investigation.html`)
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `node --check static/narrative_constellation.js` (only if that file is modified)
- `git diff --check`

Manual verification:
- Open the dashboard constellation; confirm only configured, `display_enabled: true` cross-group
  edges appear, and only inside the X-Ray reveal.
- Confirm membership edges and cross-group edges are visually distinct (not just data-distinct).
- Confirm relationship explanations are reachable by keyboard and via X-Ray, and present in the
  JS-disabled plain-text fallback.
- Confirm no relationship with `display_enabled: false` ever reaches the template context.
- Confirm malformed `config/narrative_relationships.json` fails the loader without breaking the
  dashboard route.
- Confirm the dashboard renders correctly with zero cross-group relationships configured (empty
  network case).
- Check 1280px, 1024px, 390px, `prefers-reduced-motion: reduce`, and JavaScript-disabled states.

Implement to a verified local state and stop — do not stage, commit, or push.
