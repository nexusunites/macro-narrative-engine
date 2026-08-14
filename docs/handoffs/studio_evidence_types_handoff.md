# Studio — Evidence Types (Implementation Handoff)

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser (logged-in), before commit.
**Design spec (read first):** `docs/superpowers/specs/2026-08-13-studio-evidence-types-design.md`
**Builds on (shipped):** Q1 board `4856dba`, Q2 library `fbc607b`.
**North star:** `docs/product_blueprint_v3.md`. Guard: Studio is thesis-building, not a graph.

## What this is

Let the user attach **headline** and **catalyst** evidence to a thesis board by **promoting them from a story node's intelligence panel**. Reuses the data `GET /studio/node/{slug}` already returns; no new routes, no schema/migration. Evidence lives inside the existing board payload.

## Non-negotiable framing

- Studio is thesis-building. User-facing copy never says "node / edge / graph / canvas"; all copy in `mne/presentation_language.py`, thesis language ("evidence / supports / add as evidence").
- Story nodes, their direction/intelligence, and the Q1/Q2 caps are untouched. Red stays price-only. Evidence is neutral (no direction color).

## Data model (extend `validate_board` in `mne/studio_board.py`)

Node `kind` gains two **leaf** evidence kinds (self-contained content, no deeper intelligence):
```
headline: { id, kind:"headline", title, source, x, y, source_story:<story-node-id> }
catalyst: { id, kind:"catalyst", name,  timing, x, y, source_story:<story-node-id> }
```
- Per-kind normalization in the node loop (currently it requires `kind == "story"` and `slug` in registry):
  - `story` — unchanged (slug must be in the registry, else drop).
  - `headline` — require non-empty `title`; `title`/`source` are `_plain_text`-sanitized + length-capped (reuse the thesis treatment; a ~200-char cap on title, ~120 on source is fine). Drop if `title` empty.
  - `catalyst` — require non-empty `name`; `name`/`timing` sanitized + capped. Drop if `name` empty.
  - `source_story` — sanitize; keep only if it matches a **story** node id present in the payload, else drop the field (the node survives, just unlinked).
  - unknown `kind` → drop the node.
  - `x`/`y` clamped as today; ids via `_SAFE_ID`; unique.
- **Connection label vocab:** add `"supports"` to `CONNECTION_LABELS` (evidence→claim). Connections still require `from`/`to` to reference present node ids and a valid label; `supports` links point **from the evidence node to its source story node**.
- Caps unchanged (≤40 nodes, ≤80 connections) across all kinds.

**Server-side test additions** (`tests/test_studio_board.py`): valid headline/catalyst normalize + sanitize (markup stripped, capped); empty-title/empty-name dropped; unknown kind dropped; `source_story` dropped when it references a missing/non-story node; `supports` accepted, out-of-vocab still rejected; a `supports` connection dropped when its source-story node is absent (existing dangling-drop, now covering evidence); round-trip of story + headline + catalyst + `supports`.

## Context / server render

1. **`build_studio_context` (`dashboard.py`)** currently builds `board_nodes` by looking up `registry_by_slug[node["slug"]]` and **skips non-story nodes**. Change it to handle per-kind:
   - `story` — unchanged (display_name + direction from `current_by_slug`, research_url).
   - `headline` — pass through `title`, `source`, plus `kind` and coords.
   - `catalyst` — pass through `name`, `timing`, plus `kind` and coords.
   So evidence nodes are present in `board["nodes"]` for the template.
2. **`templates/studio.html`** — server-render evidence nodes per kind (distinct markup from story cards) and include `supports` connectors in the static SVG, so the board is correct **JS-disabled**.

## Client (`static/artboard.js`) — the important gotchas

1. **Line ~17 strips fields:** `board.nodes = board.nodes.map(({id, kind, slug, x, y}) => ({id, kind, slug, x, y}))` — this **discards evidence fields**. Change the normalization to **preserve per-kind fields** (keep `title/source/name/timing/source_story` for evidence kinds) so autosave round-trips them. This is the single easiest thing to get wrong.
2. **`renderNode`** assumes story (`storyData(node.slug)`, direction glyph). Branch by `node.kind`:
   - `headline` — quote/newspaper glyph, `title`, `source` in muted slate; no direction class; leaf.
   - `catalyst` — calendar/clock glyph, `name`, `timing` in muted slate; no direction class; leaf.
   - keep story rendering as-is.
3. **Leaf click:** headline/catalyst nodes must **not** call `openPanel` (only story nodes have `[data-board-open]` → panel). Keep drag/move/remove.
4. **Promote from the panel (`openPanel`):** on each headline `<li>` and the catalyst `<p>`, add a **"+ Add as evidence"** control carrying the item's fields (title/source or name/timing) and the current panel's story slug. On click:
   - resolve the source story node id from that slug (`board.nodes.find(n => n.kind==="story" && n.slug===slug)`);
   - **dedup:** no-op if an evidence node with the same kind + source_story + title/name already exists; mark the control **"Added"** (use `copy.evidence_added`);
   - create the evidence node (id via `uid("headline"|"catalyst")`) placed near the source story (offset so it doesn't overlap), respecting the 40-node cap;
   - push a `supports` connection `{id: uid("link"), from: evidenceId, to: storyNodeId, label:"supports"}` (respect the 80-connection cap);
   - `renderNode`, `renderLinks`, `scheduleSave`.
5. **`renderLinks`** already sets `connection-${label}` → `connection-supports` gets a **quieter** connector style (see CSS). `center()` assumes a 190×96 box; if evidence cards are smaller, either keep the same box footprint or compute center from the element's size — pick one and keep connector geometry correct.

## Styles (`static/styles.css`)

Headline/catalyst node styles (lighter/smaller than story cards, neutral bright-slate, distinct glyphs) and a **quieter `supports` connector** (`.connection-supports`) so evidence links don't compete with narrative-relationship links. No red. Studio color budget preserved (teal/amber for story state only).

## Copy (`mne/presentation_language.py`)

Add: `evidence_add` ("Add as evidence"), `evidence_added` ("Added"), plus any headline/catalyst labels. `connection_supports` ("Supports") for the new label (the client reads `labels[connection.label]`). Thesis language only.

## Verification (per AGENTS.md — audit before Daniel commits)

- Full suite green (**baseline 890, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + the new tests above.
- Logged-in browser audit (temp DB, cache-bust CSS): open a story panel → "+ Add as evidence" a headline and a catalyst → they appear near the story, auto-linked with a `supports` connector, and **persist across reload**; dedup shows "Added" and doesn't duplicate; remove an evidence node → its `supports` link goes too; JS-off render shows evidence nodes + connectors; color census (evidence neutral, story state teal/amber, **zero red**); no filename/id leak; no horizontal scroll at 1280 / 1024 / 390.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; **nothing staged/committed/pushed** (Daniel commits).

**Recurring gotchas:** cache-bust CSS (`link.href = link.href.split('?')[0] + '?bust=' + Date.now()`) before reading computed styles; `pkill -f uvicorn` before starting the audit server. Auth-gated — use a logged-in QA session.

## Out of scope

Assets & sectors as evidence (later). A freeform evidence picker/search. Generative AI / the Collaborator (that sprint). Any route/schema/migration/engine/token changes — evidence lives in the existing payload and saves through the existing `POST /studio/board/{id}`.
