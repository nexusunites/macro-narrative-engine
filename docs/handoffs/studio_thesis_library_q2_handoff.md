# Studio Sprint Q2 — The Thesis Library (Implementation Handoff)

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser (logged-in), before commit.
**Design spec (read first):** `docs/superpowers/specs/2026-08-13-studio-thesis-library-q2-design.md`
**Builds on (shipped):** Q1 board — `docs/handoffs/studio_artboard_q1_handoff.md`, commit `4856dba`.
**North star:** `docs/product_blueprint_v3.md`. Guard: Studio is thesis-building, not a graph.

## What Q2 is

Turn Studio from one per-user board into a **library of named theses** the user saves and revisits. Two views:
- **Library** (`GET /studio`) — a grid of thesis cards (the collection).
- **Editor** (`GET /studio/board/{id}`) — the **unchanged Q1 artboard** for one thesis, behind a card.

A board's title is its thesis line (`payload.thesis`); no separate name field.

## Non-negotiable framing (do not drift)

- **Studio is thesis-building.** User-facing copy NEVER says "node / edge / graph / canvas" — code-only. All copy in `mne/presentation_language.py`, thesis language.
- **The Q1 board payload and `validate_board` normalizer are unchanged** (`thesis / nodes / connections`, caps, honest degradation, fixed label vocab). Q2 only adds the envelope (id, user, timestamps) and the multi-board plumbing.
- Red is price-only; must not appear on this surface.

## Existing anchors (from Q1 — reuse, don't reinvent)

- Model: `StudioBoard` in `mne/models.py` (currently `user_id` PK, `payload` JSON, `updated_at`). Migrations: `alembic/versions/`, latest `0004_studio_board.py`.
- Persistence: `mne/studio_board.py` — `validate_board`, `empty_board`, `load_board(user_id)`, `save_board(user_id, payload)`.
- Routes/context: `dashboard.py` — `build_studio_context(request)` (loads the single board, builds `board_nodes`), `studio_page` (`GET /studio`), `studio_board_save` (`POST /studio/board`), `studio_node_intelligence` (`GET /studio/node/{slug}`). Template `templates/studio.html`, JS `static/artboard.js`.
- Entitlement: `SAVED_STORIES_FEATURE`, `require_entitlement`. POST pattern: `form = _form(await request.body()); _csrf(request, form)`.

---

## Workstream A — multi-board schema, migration, repo

1. **Model** (`mne/models.py`): change `StudioBoard` to `board_id` (PK, str — generated id), `user_id` (str, indexed), `payload` (JSON), `created_at`, `updated_at`.
2. **Migration** `alembic/versions/0005_studio_boards_multi.py`, `down_revision = "0004_studio_board"`:
   - **Up (lossless):** restructure to the new shape; for each existing row, generate a `board_id` and write it as that user's first thesis, preserving `payload` and `updated_at` (set `created_at = updated_at`).
   - **Down (documented lossy):** collapse back to one-per-user, keeping each user's **most-recently-updated** board and dropping the rest. Must run cleanly; document the loss in the migration docstring.
   - Verify **up and down** and the **data migration** (existing single board survives as a named thesis).
3. **Repo** (`mne/studio_board.py`) — board-id aware, every mutating/reading call **ownership-checked**:
   - `list_boards(user_id) -> [ {board_id, thesis, node_count, connection_count, updated_at} ]` (sorted most-recent first; cheap projection for cards, no full payload needed).
   - `create_board(user_id) -> board_id` — enforces cap **≤ 25** (raise on exceed); seeds an `empty_board()` payload.
   - `load_board(user_id, board_id) -> dict | None` — returns normalized payload **only if the board belongs to `user_id`**, else `None`.
   - `save_board(user_id, board_id, payload) -> dict` — validates via `validate_board`, writes **only if owned**, bumps `updated_at`; raise/return-None on non-ownership.
   - `delete_board(user_id, board_id) -> bool` — deletes **only if owned**.
   - Keep `validate_board` / `empty_board` as-is.

**Tests:** migration up/down + data migration; create/list/load/save/delete; cap enforcement; **ownership isolation** (user A cannot load/save/delete user B's `board_id`).

## Workstream B — library landing (`GET /studio`)

1. **Route:** `GET /studio` renders the **library** (not a board). Anonymous → the existing signed-out studio state (sign-in CTA); signed-in without entitlement → same. Signed-in + entitled → `list_boards(user_id)`.
2. **Template** `templates/studio_library.html` (new; `app-topbar-page studio-page`, v2 palette): a responsive grid of **thesis cards** + a "+ New thesis" card. Each card, **server-rendered from the projection**:
   - thesis line as title, fallback copy "Untitled thesis";
   - "N evidence · M links";
   - relative last-updated;
   - a small **static board preview** (dot-grid with a few placed dots from node coords — pure CSS/inline SVG, no heavy JS).
   - **Open** = a plain link to `/studio/board/{id}` (works JS-off).
   - **Delete** = a small form → confirm → `POST /studio/board/{id}/delete`.
3. **New:** `POST /studio/board/new` — auth + CSRF + `SAVED_STORIES_FEATURE`, cap-checked → `create_board`, **redirect (303) into `/studio/board/{id}`**.
4. **Delete:** `POST /studio/board/{id}/delete` — auth + CSRF + **ownership** → `delete_board`, redirect (303) back to `/studio`.
5. **Rail:** the saved-stories/watchlist rail is **not** on the library (it's editor context); grid uses full width.
6. **Empty state:** no theses → a single honest "Start your first thesis" prompt → New.
7. **Styles** (`static/styles.css`): library grid + cards + preview, matching the approved mockup and v2 palette. Copy in `presentation_language`.

**Tests:** library renders cards from projection; New requires auth+CSRF+entitlement, enforces cap, redirects into the new editor; Delete requires ownership+CSRF; empty state renders.

## Workstream C — editor per board (`GET /studio/board/{id}`) + direction fix

1. **Route + ownership:** `GET /studio/board/{id}` → `build_studio_context(request, board_id)`; if `load_board(user_id, board_id)` is `None` (missing or not owned) → **404**. This route renders the **existing `templates/studio.html`** (thesis line + artboard + intelligence panel), unchanged except:
   - **"← All theses"** back-link in the editor header → `/studio`.
   - The board container's `data-save-url` becomes **`/studio/board/{id}`** (board-scoped).
   - **Compare tool:** the existing `studio_compare` partial stays in the editor (reuse-wholesale per the approved spec). *(Noted future refinement, not in Q2: Compare is not thesis-specific and could relocate to the library later.)*
2. **Autosave scoped:** `POST /studio/board/{id}` replaces `POST /studio/board` — auth + CSRF + `SAVED_STORIES_FEATURE` + **ownership**; validates + `save_board(user_id, board_id, payload)`; returns **204**. `static/artboard.js` posts to the board-scoped URL from `data-save-url` (it already reads that attribute — confirm it uses it rather than a hardcoded path).
3. **Node intelligence** (`GET /studio/node/{slug}`): unchanged (not board-scoped; it's about a story in the current run).
4. **Direction-reconciliation fix** (folds the Q1 follow-up): in `build_studio_context`, enrich `board_nodes` direction from the **current run** (`current_by_slug`, already computed in that function from `build_narrative_selector`) instead of from `saved_by_slug`. Result: a boarded story's card glyph matches the intelligence panel's direction; default to "steady" only when the run genuinely has nothing for that slug.

**Tests:** editor 404s on missing/non-owned board id; board-scoped autosave requires ownership + CSRF, full-replace of that board only; **direction fix** — a boarded story reflects the current run's direction (add/extend a test that boards a story with a known non-steady current direction and asserts the node direction matches).

---

## Verification (per AGENTS.md — audit before Daniel commits)

- Full suite green (**baseline 883, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + all new tests above.
- Migration `0005` up **and** down; data migration preserves an existing Q1 board as a named thesis.
- Logged-in browser audit (temp DB, cache-bust CSS): create 2–3 theses; library grid shows correct titles / counts / previews / order; Open a card → editor; autosave writes to the **correct** board (edit board A, confirm board B unchanged); Delete with confirm; "← All theses" navigates back; direction glyph matches the intelligence panel; New from empty state.
- **JS-disabled**: library grid renders read-only, Open links work, New/Delete form POSTs work, editor keeps Q1 fallback.
- Color census (zero red), copy discipline (no node/edge/graph/canvas in rendered text), no board-id/path leak, no horizontal scroll at 1280 / 1024 / 390.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; **nothing staged/committed/pushed** (Daniel commits).

**Recurring gotchas:** cache-bust CSS (`link.href = link.href.split('?')[0] + '?bust=' + Date.now()`) before reading computed styles; `pkill -f uvicorn` before starting the audit server. Auth-gated pages need a logged-in QA session.

## Out of scope (Q2)

Additional evidence types (catalysts / sectors / assets / headlines). Generative Collaborator AI (Q3). Relocating Compare off the editor. Opening Studio to the last-open board instead of the library. Any token / engine / threshold changes.
