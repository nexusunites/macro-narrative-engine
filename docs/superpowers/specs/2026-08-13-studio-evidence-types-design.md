# Studio — Evidence Types (Design Spec)

**Date:** 2026-08-13 · **Author:** Claude (orchestrator) · **Status:** approved design, pre-handoff
**Builds on (shipped):** Q1 board (`4856dba`), Q2 thesis library (`fbc607b`).
**North star:** `docs/product_blueprint_v3.md` — Studio owns *conviction*. Guard: [[mne-studio-thesis-frame]] — Studio is thesis-building, not a graph.
**Naming:** the generative "Collaborator" remains the separate, later sprint. This sprint adds non-story *evidence* only.

## What this sprint is

Let the user attach the **actual evidence behind a story** — supporting headlines and the next catalyst — to their thesis board as first-class objects. These are exactly what the node intelligence panel already surfaces from real run data, so this reuses existing data and stays fully deterministic. Scope this sprint: **headlines + catalysts, promoted from the story intelligence panel.** Assets and sectors are deferred; there is no freeform evidence picker.

**Identity-test rationale:** evidence types earn their place because they let the user attach the real evidence behind a story to a claim — serving "form/defend a view," not merely enriching the graph.

## Section 1 — payload model for evidence

Extend the node `kind` with two **leaf** evidence nodes (self-contained content, no further intelligence behind them — they *are* the evidence):
```
headline: { id, kind:"headline", title, source, x, y, source_story:<story-node-id> }
catalyst: { id, kind:"catalyst", name,  timing, x, y, source_story:<story-node-id> }
```
- `title / source / name / timing`: plain text, markup-stripped, length-capped (same treatment as `thesis`). No slug — content is a **snapshot captured at promote-time**, so a revisited thesis keeps the evidence it was built on even if the run moves on.
- `source_story`: the story node id this was promoted from.

**Auto-linking (ratified).** Promoting creates the evidence node **plus** a connection to its source story, using a new evidence label **`supports`** (evidence→claim). The existing labels (`moves_with / moves_against / drives / depends_on`) are inter-narrative; `supports` is the evidence relationship. Rejected alternative: place evidence unconnected and make the user draw the link — loses the "this backs that" value.

**Unchanged:** ≤40-node / ≤80-connection caps cover evidence nodes; `validate_board` still drops malformed items honestly (now per-kind); story nodes and their direction/intelligence are untouched.

## Section 2 — the promote interaction

Evidence is added by **promoting from a story node's intelligence panel** — no new picker, no search.

- In the panel, each **supporting headline** row and the **next catalyst** get a **"+ Add as evidence"** control.
- Clicking it: (1) creates the evidence node near its source story, (2) auto-creates the `supports` connection, (3) triggers the existing **debounced autosave**.
- **Dedup:** promoting the same headline/catalyst again is a no-op (dedupe by source-story + title/name); the panel control shows an **"Added"** state.
- **No new server endpoint.** Evidence content comes from data already fetched via `GET /studio/node/{slug}`; promote appends nodes/connections and saves through the existing `POST /studio/board/{id}`. The leak-safety/whitelist already verified for that endpoint still fully applies — nothing new is exposed.

## Section 3 — rendering & behavior

- **Headline node:** quote/newspaper glyph, headline text, source in muted slate; visually lighter/smaller than a story card.
- **Catalyst node:** calendar/clock glyph, event name, timing in muted slate.
- Neither is directional → **no up/down/steady color**; render neutral (bright slate), reserving teal/amber for story state. The `supports` connector renders like other connectors but with a subtly quieter style so it doesn't compete with narrative-relationship links.
- **Leaf behavior:** clicking a headline/catalyst node does **not** open an intelligence panel (nothing behind it). It is draggable/movable/removable like any node; removing it also removes its `supports` connection (existing dangling-drop).
- **JS-off:** evidence nodes and connectors **server-render** from the payload exactly like story nodes.
- **Copy discipline:** "evidence / supports / add as evidence" — thesis language; still no node/edge/graph/canvas in rendered text.

## Section 4 — verification & scope

**Verification (per AGENTS.md):**
- Full suite green (**baseline 890, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + new tests:
  - `validate_board` per-kind: valid headline/catalyst normalize + sanitize (fields capped, markup stripped); malformed evidence dropped; unknown `kind` dropped; `supports` accepted, out-of-vocab still rejected; caps enforced across mixed kinds.
  - `supports` integrity: dropped when its source-story node is gone (dangling-drop now covers evidence).
  - round-trip: story + headline + catalyst + `supports` saves and reloads intact.
- Logged-in browser audit (temp DB): open a story panel; "+ Add as evidence" a headline and a catalyst → appear near the story, auto-linked with `supports`, **persist across reload**; dedup shows "Added"; remove an evidence node → its link goes too; JS-off render shows evidence + connectors; color census (evidence neutral, story state teal/amber, **zero red**); no leak; 1280 / 1024 / 390.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

**Out of scope:** assets & sectors as evidence (later); a freeform evidence picker/search; generative AI / the Collaborator (that sprint); any engine/token/threshold changes.

## New / changed surface (summary for the handoff)

- **Changed:** `mne/studio_board.py` (`validate_board`: per-kind node handling for `story|headline|catalyst`, `supports` in the connection-label vocab, evidence field sanitization); `static/artboard.js` (panel "+ Add as evidence" controls + dedup/"Added" state; create evidence node + `supports` link + autosave; render headline/catalyst nodes; leaf click behavior); `static/styles.css` (headline/catalyst node styles + quieter `supports` connector); `templates/studio.html` (server-render evidence nodes/connectors for JS-off); `mne/presentation_language.py` (evidence copy); studio tests.
- **No new routes, no schema/migration** — evidence lives inside the existing board payload.
