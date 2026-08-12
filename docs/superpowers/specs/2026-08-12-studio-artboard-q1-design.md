# Studio Sprint Q1 — The Working Board (Design Spec)

**Date:** 2026-08-12 · **Author:** Claude (orchestrator) · **Status:** approved design, pre-handoff
**North star:** [`docs/product_blueprint_v3.md`](../../product_blueprint_v3.md) — Studio owns *conviction* ("what do I think?"); the value is the intelligence attached to objects, not the canvas.

## Sprint decomposition (context)

The blueprint's Studio vision is multi-sprint. It is cut into three:

- **Q1 — The working board** *(this spec).* Real canvas: drag saved stories onto a persistent per-user board, position them, draw labeled connections, and click a node to see the intelligence MNE already computes for it — plus a deterministic relationship hint. Ships the mockup **and** proves the intelligence payoff via reuse, not new AI.
- **Q2 — More to build with.** Additional draggable object types (catalysts, sectors, assets, individual headlines); multiple named boards; save-as-investigation / revisit.
- **Q3 — The Collaborator (Studio AI role).** Generative suggestions that require new inference: suggested connections, missing-evidence flags, contradictions, opposing explanations, challenge-a-thesis. Belongs with the surface-differentiated-AI work.

**Why Q1 is cut here:** it leans entirely on things that already exist (the rail's saved-story data, the investigation intelligence builder, the curated narrative-relationship config), so it is mostly one persistence path, two read endpoints, and hand-written canvas JS — while still answering the blueprint's own warning that a bare canvas is low-value.

## Current state (what exists today)

- `/studio` route → `build_studio_context` / `build_studio_compare_context` (`dashboard.py:2318`, `:2368`).
- `templates/studio.html`: working left rail (saved stories + watchlist with live direction), a **static `studio-artboard-placeholder`** (copy only — no canvas, no JS, no interaction), and a fully-working Compare tool (`_partials/studio_compare.html`).
- No artboard JS, no board persistence.
- Preferences persist as **relational tables** (`SavedStory`, `FollowedNarrative`, …) behind `validate_preferences` — **not** a JSON blob. Migrations are Alembic under `alembic/versions/` (latest `0003_saved_stories.py`).
- `Story` (`mne/story_registry.py`) carries `slug`, `display_name`, `group`, `themes`. A story maps to its narrative investigation deterministically: `story.group → narrative_key("group", group) → build_narrative_investigation(run, "group", key)`.
- Curated narrative relationships (`mne/narrative_relationships.py`) are keyed by **group pair** with `public_label` + `explanation`; helpers `get_relationships_for_group()`, `build_relationship_adjacency()`.

## Section 1 — Board data model & persistence

**Storage.** New Alembic migration `0004_studio_board.py` → table `studio_boards`, **one row per user** (Q1 = one board each): `user_id` (PK), `payload` (JSON), `updated_at`. A board is a document, not a relational graph, so a single validated JSON payload is preferred over a node/edge table model.

**Payload schema** — validated by a new `mne/studio_board.py` normalizer (same spirit as `validate_preferences`):

```
schema_version: 1
nodes:       [ { id, kind: "story", slug, x, y } ]
connections: [ { id, from, to, label } ]
```

- `label` ∈ fixed vocabulary `{ moves_with, moves_against, drives, depends_on }`; any other value is rejected.
- `kind` is `"story"` in Q1 (the enum exists so Q2 can add `catalyst`/`sector`/`asset`/`headline` without a schema break).

**Server-side integrity + honest degradation** (AGENTS.md rule 8):
- `slug` must exist in the story registry; a node whose story later leaves the registry is **dropped on load**, never fabricated.
- `from`/`to` must reference node ids present in the same payload; dangling connections are **dropped on load**.
- `x`/`y` clamped to canvas bounds.
- Node and connection counts capped (e.g. ≤ 40 nodes, ≤ 80 connections) so a board cannot be inflated into an abuse vector.

**Access.**
- `GET /studio` — loads the board via `load_board(user_id)` and renders it **server-side** (works JS-off).
- `POST /studio/board` — auth-required, **CSRF-protected** (reuse the `_csrf` pattern), **full-replace** of the payload (mirrors how `saved_stories` saves). Repo functions `load_board(user_id)` / `save_board(user_id, payload)` (co-located with the other account/board persistence).
- **Entitlement:** reuse the existing `SAVED_STORIES_FEATURE` gate — you need saved stories to have anything to place, so no new entitlement is minted.

## Section 2 — Canvas interaction (frontend)

New `static/artboard.js`, following the existing `static/chart.js` pattern — **no framework, no build step**, progressive enhancement over the server-rendered board.

- **Input model: pointer events only** (not HTML5 drag-and-drop) — reliable, touch-friendly, and one model for both add and move.
- **Add a node:** pointer-drag a saved story from the left rail onto the canvas → a node appears at the drop point.
- **Move a node:** pointer-drag on the canvas; connectors re-route live.
- **Draw a connection:** each node has a small **link handle** → press it, drag/click to a target node → a compact popover offers the four labels → connection created. Rendered like the mockup: dashed teal SVG path + arrowhead + a labeled pill at the midpoint.
- **Remove:** node has a remove control (on hover/focus); connection pill removes on click. Keyboard-reachable with visible focus states.
- **Persist: debounced autosave** — 800 ms after the last change, one `POST /studio/board` full-replace, with a subtle "Saved" indicator. The debounce collapses a drag into a single write (no per-drag spamming).
- **Look:** dot-grid background, 190 px node cards (direction glyph + name + one-liner), teal glow on the selected node, teal/amber connectors — straight from `docs/mockups/research_studio_concept_v1.html` (`#view-studio`), consistent with the color-leading re-saturation standard.

## Section 3 — Intelligence panel (the payoff)

**Click a node** (a click, distinct from a drag) → a side panel surfaces what MNE already knows about that story. No new inference — pure reuse.

**Data path (deterministic, cheap):**
`node.slug → registry story.group → narrative_key("group", group) → build_narrative_investigation(current run)` → project a **compact, whitelisted subset**:
- top related narratives
- a few supporting headlines
- the next catalyst
- current direction / state (already on the node)

**Deterministic relationship hint** *(the one "engine helps you think" element in Q1)*: when two nodes on the board sit in **related groups**, surface the curated relationship — its `public_label` (e.g. "tends to move with") — and offer to draw the link. Reuse of `narrative_relationships.py` (`get_relationships_for_group` / `build_relationship_adjacency`); fully hand-derivable, no inference. **Group granularity** is honest and explicit: the hint does **not** fire for two same-group siblings, and it is phrased at group level. Generative suggestions (contradictions, opposing explanations, missing-evidence, challenge-a-thesis) are **out of scope → Q3**.

**Endpoint:** `GET /studio/node/{slug}` (auth-required) returns the compact intelligence as JSON, computed on demand from the current run; `artboard.js` renders it into the panel. On-demand per click (not precomputed for every saved story at page load) — you only pay for nodes actually inspected.

**Projection module:** new `build_studio_node_intelligence(run, slug)` that **calls the existing investigation builder** and selects whitelisted fields. Same discipline as `build_user_historical_comparison`: **translation layer respected** (copy via `presentation_language`), and **no engine terms, file paths, or internal ids leak** — guarded by a no-leak test.

**Honest empty state:** a story with no related narratives / headlines / catalyst in the current run shows a truthful "nothing attached right now," never fabricated filler. A panel footer links to the full Research investigation for the deep dive.

## Section 4 — States, JS-off fallback, verification

**Honest states:**
- No saved stories → canvas shows the drop-hint + CTA to Research to star stories. Rail keeps its own empty case.
- Empty board (stories saved, none placed) → drop-hint only.
- Node with no attached intelligence → truthful "nothing attached right now."

**JS-disabled fallback (progressive enhancement):** `GET /studio` renders the saved board **server-side, read-only** — nodes positioned via inline coords, connections as static SVG, panel degraded to a link to the full Research investigation. No drag, but nothing is blank or broken. (This is why the board must load from storage on the server, not only via JS.)

**Color budget:** teal = strengthening node/connector, amber = fading, **red stays price-only and must NOT appear here**, bright slate = steady. Node glyphs reuse the existing `direction-{up,down,steady}` hooks. Studio must measurably gain color vs. today's near-colorless landing.

**Verification (per AGENTS.md):**
- Full suite green (**baseline 874, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) plus **new tests**:
  - board-payload normalizer: slug-drop degradation, dangling-connection drop, label-vocab rejection, position clamp, node/connection caps.
  - `POST /studio/board`: CSRF required, auth required, full-replace semantics.
  - `build_studio_node_intelligence`: whitelist + **no-leak** (mirror the `build_user_historical_comparison` no-leak test — embed secret path/workflow/id, assert none serialize).
  - relationship hint: fires only for related-group pairs, never same-group.
- Alembic migration tested **up and down**.
- Browser audit: 1280 / 1024 / 390; JS-disabled render intact; color census (Studio gains teal/amber, **zero red**); no filename/id leak; no horizontal scroll.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

## Out of scope (Q1)

Multiple/named boards, save-as-investigation, revisit (Q2). Additional object types beyond `story` (Q2). Generative/AI suggestions of any kind (Q3). Token redefinitions, engine logic, thresholds, persistence formats for anything but the new `studio_boards` table.

## New / changed surface (summary for the handoff)

- **New:** `alembic/versions/0004_studio_board.py`; `mne/studio_board.py` (normalizer + repo `load_board`/`save_board`, or repo in `account_repository.py`); `build_studio_node_intelligence` (in `dashboard.py` or a small module); `static/artboard.js`; tests for each.
- **Changed:** `templates/studio.html` (placeholder → real canvas + panel + JS-off render); `dashboard.py` (`GET /studio` loads board; new `POST /studio/board`; new `GET /studio/node/{slug}`; `build_studio_context` provides board payload); `static/styles.css` (artboard/node/connector/panel styles from the mockup); `mne/presentation_language.py` (any new user-facing copy).
