# Studio Sprint Q2 — The Thesis Library (Design Spec)

**Date:** 2026-08-13 · **Author:** Claude (orchestrator) · **Status:** approved design, pre-handoff
**Builds on:** `docs/superpowers/specs/2026-08-12-studio-artboard-q1-design.md` (shipped, commit `4856dba`)
**North star:** `docs/product_blueprint_v3.md` — Studio owns *conviction*. Guard: [[mne-studio-thesis-frame]] — Studio is thesis-building, not a graph.

## What Q2 is

Q1 shipped a single per-user thesis board. Q2 turns Studio into a **library of named theses** the user saves and revisits: multiple boards, browsable as a collection, each opening into the unchanged Q1 artboard. This is the blueprint's "save investigations, revisit previous thinking," and it passes the identity test cleanly — each board *is* a position the user returns to and defends.

**IA chosen: library landing (two views).**
- **Library** (`/studio`) — a grid of thesis cards (the collection).
- **Editor** (`/studio/board/{id}`) — the full Q1 artboard for one thesis, behind a card.

Rejected alternatives: rail-list (leaner but cramped) and header-switcher (hides the collection). The library landing is the most intuitive "these are my theses" read and makes revisiting a first-class action. (Mockup comparison produced during design.)

## Section 1 — data model & migration

**Schema.** `studio_boards` moves from one-row-per-user to a real board identity:
```
studio_boards: board_id (PK)  ·  user_id (indexed)  ·  payload (JSON)  ·  created_at  ·  updated_at
```
**Migration `0005`** restructures the table and **migrates each existing single board into that user's first thesis** — generated `board_id`, timestamps preserved, payload untouched. No user loses the board they built in Q1. Reversible (down-migration collapses back to one-per-user, keeping the most-recently-updated board).

**Board identity = the thesis line, not a separate name.** The library card's title is `payload.thesis`; empty thesis → "Untitled thesis." This keeps the thesis as the single anchor (per [[mne-studio-thesis-frame]]) — a thesis is named by making it, not by a separate title box that can drift from the claim.

**The Q1 payload is unchanged** — `thesis / nodes / connections`, same `validate_board` normalizer (caps, honest degradation, fixed label vocab). Q2 only adds the *envelope* (id, user, timestamps) around it.

**Defaults:**
- Cap: **≤ 25 theses per user**, enforced server-side on create.
- Sort: library shows **most-recently-updated first**.
- Delete is destructive (a whole board) → requires confirm + CSRF + ownership.

## Section 2 — the library landing (`/studio`)

A responsive **grid of thesis cards**, most-recently-updated first, plus a "+ New thesis" card. Each card, **server-rendered from the payload**:
- thesis line as title (fallback "Untitled thesis"),
- evidence count + connection count ("3 evidence · 2 links"),
- last-updated (relative),
- a small **static board preview** (dot-grid with a few placed evidence dots) — no heavy JS.

**Actions:**
- **Open** — card → `/studio/board/{id}`.
- **New** — `POST /studio/board/new` (auth + CSRF + `SAVED_STORIES_FEATURE`, cap-checked) → creates a blank board, redirects into its editor.
- **Delete** — per-card control → confirm → `POST /studio/board/{id}/delete`; server verifies ownership.

**Rail:** the saved-stories/watchlist rail is *editor context*, so it is **dropped on the library view** (grid uses full width) and **returns in the editor**, where dragging happens.

**Empty state:** no theses → a single honest "Start your first thesis" prompt → New.

## Section 3 — the editor per board (`/studio/board/{id}`)

**The Q1 Studio, reused wholesale behind a board id** — thesis line, artboard, evidence, connections, intelligence panel, debounced autosave all identical. Deltas only:
- **Route + ownership:** loads that board; server verifies it belongs to the requester → **404 on mismatch** (no cross-user id peeking). `build_studio_context` takes a board id, not just the user.
- **Autosave board-scoped:** `POST /studio/board/{id}` saves that board's payload (id in the path); same 204 + 800 ms debounce.
- **"← All theses" back-link** in the editor header → library grid. Saved-stories rail present here.

**Fold in the Q1 direction-reconciliation fix** (same file, one spot): evidence-card direction is resolved from the **current run**, not from `saved_stories`, so the card glyph matches the intelligence panel's direction (Q1 follow-up — a boarded-but-unsaved story previously showed "steady" while the panel read the true direction). Default to steady only when the run genuinely has nothing.

## Section 4 — states, JS-off, verification

**Honest states:** empty library → prompt; empty-thesis board → "Untitled thesis" card, still usable; deleting the last thesis → back to empty-library prompt.

**JS-disabled:** library grid is server-rendered (cards, previews, counts from payload) and read-only-usable; Open is a plain link; New/Delete are real form POSTs (work JS-off); editor keeps its Q1 read-only fallback.

**Ownership & safety:** every board route (`/studio/board/{id}`, save, delete) checks ownership → 404 on mismatch. New/delete/save are auth + CSRF + `SAVED_STORIES_FEATURE`. Cap enforced server-side on New. Copy discipline holds (no node/edge/graph/canvas in rendered text); red stays price-only.

**Verification (per AGENTS.md):**
- Full suite green (**baseline 883, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) plus new tests:
  - migration `0005` up **and** down; **data migration** (existing single board → named thesis, nothing lost).
  - multi-board repo: create / list / load / save / delete, cap enforcement, **ownership isolation** (user A cannot load/save/delete user B's board id).
  - library route renders cards from payload; New redirects into a fresh editor; Delete requires ownership + CSRF.
  - **direction fix:** a boarded story reflects the current run's direction, matching the intelligence panel.
- Logged-in browser audit (temp DB): create 2–3 theses; grid + counts + previews; open/switch; autosave scoped to the correct board; delete with confirm; direction glyph matches panel; JS-off render; color census (zero red); no id leak; 1280 / 1024 / 390.
- `/`, `/admin`, `/research`, `/studio` return 200; `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

## Out of scope (Q2)

Additional evidence types — catalysts / sectors / assets / headlines (later). Generative Collaborator AI (Q3). Any token/engine/threshold changes. Optional future nicety noted but **not** in Q2: opening Studio to the last-open board instead of the library (library-first is the chosen default).

## New / changed surface (summary for the handoff)

- **New:** `alembic/versions/0005_studio_boards_multi.py`; library landing template (e.g. `templates/studio_library.html`); repo functions for multi-board (`list_boards`, `create_board`, `load_board(board_id)`, `save_board(board_id, payload)`, `delete_board`, ownership guard) in `mne/studio_board.py`; tests.
- **Changed:** `mne/models.py` (StudioBoard: board_id PK + user_id + timestamps); `dashboard.py` (`GET /studio` → library; `GET /studio/board/{id}` → editor; `POST /studio/board/new`; `POST /studio/board/{id}`; `POST /studio/board/{id}/delete`; `build_studio_context(board_id)`; direction from current run); `templates/studio.html` (editor: back-link, board-scoped save URL); `static/artboard.js` (post to board-scoped URL); `static/styles.css` (library grid + cards + preview); `mne/presentation_language.py` (library copy); studio tests.
