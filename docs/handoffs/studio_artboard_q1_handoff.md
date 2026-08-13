# Studio Sprint Q1 — The Working Board (Implementation Handoff)

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser (logged-in), before commit.
**Design spec (read first):** `docs/superpowers/specs/2026-08-12-studio-artboard-q1-design.md`
**North star:** `docs/product_blueprint_v3.md` — Studio owns *conviction*.

## Why this exists

`/studio` today has a working left rail and Compare tool but only a **static placeholder** where the artboard should be (`templates/studio.html`, `.studio-artboard-placeholder`). Sprint Q1 makes it a real, persistent **thesis board**: an editable thesis line anchors the surface; the user drags saved stories on as evidence, positions them, draws labeled connections, and clicks one to see the intelligence MNE already computes — plus a deterministic relationship hint. No new AI: everything is reuse of existing builders + curated config.

## Non-negotiable framing (do not drift)

**Studio is thesis-building, not a story graph.** The graph is the mechanism, not the point. Two hard guards:
1. **Language discipline** — user-facing copy NEVER says "node," "edge," "graph," or "canvas." That vocabulary is code-only. Users see thesis language: *what you think / the case you're building / what supports this / what argues against it*. All copy in `mne/presentation_language.py`.
2. **Identity test** — every element must help the user form or defend a view, not merely enrich a graph.

## Ratified decisions (do not re-litigate)

- **One board per user** in Q1 (multiple/named boards = Q2). **Story-only** node kind in Q1 (other object types = Q2). **No generative AI** (suggested connections, contradictions, opposing evidence = Q3).
- Connection labels are a **fixed vocabulary**: `moves_with`, `moves_against`, `drives`, `depends_on`. Reject anything else.
- **Debounced autosave** (no explicit Save button). **Pointer events** for all drag (no HTML5 DnD). **Reuse `SAVED_STORIES_FEATURE`** entitlement (no new one).
- Red is **price-only** and must not appear on this surface.

## Existing anchors (use these, don't reinvent)

- Models: `mne/models.py` (SQLAlchemy `Base` from `mne/database.py`). Migrations: `alembic/versions/` (latest `0003_saved_stories.py`).
- Story → intelligence hop: `story.group → narrative_key("group", group) → build_narrative_investigation(run, "group", key)`. `Story` fields (`mne/story_registry.py`): `slug, display_name, group, themes`.
- Relationships: `mne/narrative_relationships.py` — `get_relationships_for_group(group_key)`, `build_relationship_adjacency()`; each relationship carries `public_label` + `explanation`, keyed by **group pair**.
- Entitlement: `from mne.entitlements import SAVED_STORIES_FEATURE, check_entitlement, require_entitlement` (already imported in `dashboard.py`).
- POST pattern: `form = _form(await request.body()); _csrf(request, form)` then persist. Studio context builders: `build_studio_context` (`dashboard.py:2318`), `build_studio_compare_context` (`:2368`).

---

## Workstream A — Persistence (model, migration, normalizer, repo)

1. **Model** — add `StudioBoard(Base)` to `mne/models.py`: `__tablename__ = "studio_boards"`, `user_id` (PK, str), `payload` (JSON), `updated_at` (datetime, server-updated on write).
2. **Migration** — `alembic/versions/0004_studio_board.py` creating that table; `down_revision = "0003_saved_stories"`. Must run **up and down** cleanly.
3. **Normalizer** — new `mne/studio_board.py`, `validate_board(payload) -> dict` (spirit of `validate_preferences` in `mne/personalization.py`). Payload contract:
   ```
   schema_version: 1
   thesis:      str            # ≤240 chars, markup-stripped, may be ""
   nodes:       [ { id, kind: "story", slug, x, y } ]
   connections: [ { id, from, to, label } ]
   ```
   Rules — **honest degradation, applied on load and on save**:
   - `thesis`: coerce to str, strip markup/control chars, cap length.
   - node `slug` must exist in the story registry → else the node is **dropped** (never fabricated).
   - node `kind` must be `"story"` (enum reserved for Q2 growth); `x`/`y` clamped to canvas bounds; ids unique.
   - connection `from`/`to` must reference node ids present after node-drop → else the connection is **dropped**.
   - `label` must be in the fixed vocab → else the connection is **dropped** (or the whole payload rejected on save; dropped-on-load).
   - Caps: **≤ 40 nodes, ≤ 80 connections** (reject-on-save if exceeded).
4. **Repo** — `load_board(user_id) -> dict` (returns a normalized empty board `{schema_version:1, thesis:"", nodes:[], connections:[]}` when none exists) and `save_board(user_id, payload) -> dict` (validates then upserts). Co-locate with `mne/account_repository.py` or in `mne/studio_board.py` — your call; keep session handling consistent with `account_repository`.

**Tests:** normalizer (slug-drop, dangling-connection drop, label rejection, position clamp, node/connection caps, thesis cap + sanitization); repo round-trip + empty default; migration up/down.

## Workstream B — Endpoints & context (dashboard.py)

1. `build_studio_context` — add `board = load_board(user.user_id)` (or empty board for anon/no-entitlement) to the context so `GET /studio` renders server-side.
2. `POST /studio/board` — auth-required, `_csrf`-validated. Body is form-encoded (so `artboard.js` reuses the CSRF field): `csrf_token` + `payload` (JSON string). Validate via `validate_board`, `save_board`, return **`204 No Content`** (or `{"saved": true}` JSON) — this is a fetch endpoint, NOT a redirect. Entitlement: `require_entitlement(user, SAVED_STORIES_FEATURE)`; on `EntitlementDenied`/`ValueError`, return a 4xx without persisting (do not silently 303 like the form handlers).
3. `GET /studio/node/{slug}` — auth-required. Returns compact intelligence JSON via a new `build_studio_node_intelligence(run, slug)`:
   - resolve `slug → registry story → group → narrative_key → build_narrative_investigation(current run)`; project a **whitelisted** subset: top related narratives, a few supporting headlines, next catalyst, current direction/state.
   - **relationship hint:** include, for this story's group, curated related groups via `get_relationships_for_group` with `public_label`; the client uses it to hint links between two on-board nodes in related groups. Group-granularity is intentional; do NOT fabricate story-level relationships.
   - **No-leak discipline** (mirror `build_user_historical_comparison`): no engine terms, file paths, workflow ids, or raw internal ids in the output; copy via `presentation_language`.
   - Honest empty: story with nothing attached → truthful empty payload, not filler.

**Tests:** `POST /studio/board` requires auth + CSRF, full-replace semantics, rejects over-cap/bad-label; `build_studio_node_intelligence` whitelist + **no-leak** (embed secret path/workflow/id, assert none serialize); relationship hint fires only for related-group pairs, never same-group.

## Workstream C — Frontend (template, JS, CSS)

1. **`templates/studio.html`** — replace `.studio-artboard-placeholder` with:
   - the **thesis line** at the top (editable; placeholder copy from `presentation_language`), rendered with `payload.thesis`.
   - the board rendered **server-side from `board`**: nodes at their coords (inline positioning), connections as static SVG, so it works **JS-disabled** (read-only). Node click in the no-JS case degrades to a link to the full Research investigation.
2. **`static/artboard.js`** (new, `static/chart.js` pattern — no framework, progressive enhancement over the server render):
   - pointer-drag a rail story onto the board → new story node at drop point.
   - pointer-drag nodes to move; connectors re-route live.
   - link handle on each node → press → target node → label popover (fixed vocab) → connection created. Dashed teal SVG path + arrowhead + labeled pill (match mockup).
   - remove controls for nodes + connections; keyboard-reachable, visible focus.
   - editing the thesis line updates `payload.thesis`.
   - **debounced autosave** (800 ms after last change) → `POST /studio/board` form-encoded (`csrf_token` + `payload`), subtle "Saved" indicator.
   - node click (distinct from drag) → `GET /studio/node/{slug}` → render the intelligence panel; surface the relationship hint when two on-board nodes are in related groups.
3. **`static/styles.css`** — artboard/node/connector/panel/thesis-line styles ported from `docs/mockups/research_studio_concept_v1.html` (`#view-studio`): dot-grid bg, 190px node cards (direction glyph + name + one-liner), teal glow on selected, teal/amber connectors. **Color budget:** teal = strengthening, amber = fading, bright slate = steady, **zero red**. Reuse existing `direction-{up,down,steady}` hooks. Studio must measurably gain color vs. today.
4. **Copy** — all new user-facing strings in `mne/presentation_language.py`; thesis language only.

**Tests:** copy-discipline structure test (rendered studio template contains no "node/edge/graph/canvas"); template renders board + thesis line server-side; existing studio structure tests still pass.

---

## Verification (per AGENTS.md — audit before Daniel commits)

- Full suite green (**baseline 874, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + all new tests above.
- Alembic migration up **and** down clean.
- Logged-in browser audit (Studio is auth-gated for the board): create a QA session, cache-bust CSS. Verify drag/move/connect/remove, autosave persists across reload, thesis line persists, node panel loads with real intelligence + relationship hint, honest empty states.
- **JS-disabled** render intact (board read-only, thesis shown, no blank/broken).
- Color census: Studio gains teal/amber, **zero red**; no filename/id leak; no horizontal scroll at 1280 / 1024 / 390.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; **nothing staged/committed/pushed** (Daniel commits).

**Recurring gotchas:** cache-bust CSS (`link.href = link.href.split('?')[0] + '?bust=' + Date.now()`) before reading computed styles; `pkill -f uvicorn` before starting the audit server.

## Out of scope (Q1)

Multiple/named boards, save-as-investigation, revisit (Q2). Object types beyond `story` (Q2). Any generative/AI suggestion (Q3). Token redefinitions, engine logic/thresholds, persistence formats other than the new `studio_boards` table.
