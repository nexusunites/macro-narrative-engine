# Studio Documentation Synchronization — Implementation Handoff

**Status: ready to hand to Codex. Do not implement in this authoring session; do not stage, commit, or push.**
**Author:** Claude (orchestrator) · **Implements:** Codex, from this document only · **Verify:** per the checklist at the end, before Daniel commits.

## What this is (and is NOT)

This is a **documentation-only synchronization**. MNE's canonical current-state documents predate the entire Studio arc and do not mention it, so a reader searching one old architecture paragraph can wrongly conclude Studio does not exist. This handoff brings the canonical docs into agreement with the **verified implemented** Studio feature set — **without** rewriting history and **without** over-claiming that every generic "saved investigation / annotation / collaborative / custom workspace" concept is now built.

**No application code, tests, schemas, templates, static assets, migrations, config, or runtime behavior may change.** This is prose only, in the files named in the Scope section. If you find yourself editing anything under `mne/`, `dashboard.py`, `templates/`, `static/`, `alembic/`, `config/`, or `tests/`, stop — that is out of scope.

## Why this is needed (the problem, precisely)

- `docs/project_status.md`, `docs/product_backlog.md`, `ARCHITECTURE.md`, and `docs/research_workspace_architecture.md` contain **zero** occurrences of "Studio" or "thesis" (verified 2026-08-15).
- The Research Workspace Architecture (RWA) §16 says Saved investigations, Watchlists, Annotations, Custom workspaces, Shared workspaces, etc. are *"reserved for architectural compatibility, **not implemented by this document**."* That was a **scoped statement about that document's own scope at authoring time** — it is being misread as a repository-wide, still-current fact.
- Since then, a **bounded Studio thesis workspace** shipped across Sprints N → O → P → Q1 → Q2 → evidence types. A constrained realization of *some* of those reserved concepts now exists; several others genuinely do not.

The fix is to record what is true today, mark the historical statements as historical (dated cross-references, not rewrites), and make documentation precedence explicit.

---

## Verified implementation ground truth (do not re-derive; cite as needed)

All of the following were verified against the codebase on 2026-08-15. Use them as the authoritative feature list.

**Model & persistence**
- `mne/models.py:85` — `class StudioBoard` (`board_id`, `user_id` FK with `CASCADE`, `payload` JSON, `created_at`, `updated_at`). Per-user, ownership-scoped.
- Migrations `alembic/versions/0004_studio_board.py` and `alembic/versions/0005_studio_boards_multi.py` (multi-board).
- `mne/studio_board.py` — board validation/normalization: fixed connection-label vocabulary (`moves_with`, `moves_against`, `drives`, `depends_on`, `supports`), caps (≤40 nodes, ≤80 connections, ≤25 boards/user), per-kind node sanitization, honest drop of dead references.

**Routes (`dashboard.py`)**
- `GET /studio` — thesis **library** landing (grid of thesis cards).
- `POST /studio/board/new`, `GET /studio/board/{board_id}`, `POST /studio/board/{board_id}` (autosave), `POST /studio/board/{board_id}/delete` — named boards, ownership-guarded (cross-user access returns 404).
- `GET /studio/node/{slug}` — current-run node intelligence (whitelisted, no-leak).
- `GET /studio/board/{board_id}/compare`, `GET /studio/compare` — **Compare-over-time** (reuses the existing historical-comparison builder; Sprint P).

**Templates / client**
- `templates/studio.html`, `templates/studio_library.html`, `templates/_partials/studio_compare.html`.
- `static/artboard.js` — pointer-driven board editor (placement, labeled connections, evidence promotion + dedup, debounced autosave to the board's save URL).

**Shipped commits (for provenance in prose, if referenced):** Sprint N `9c881e9` (story-level Saved backend), Sprint O `f78945d` (Studio shell + nav + Saved/Watchlist rail), Sprint P `a1566dc` (Compare-over-time), Q1 `4856dba` (thesis board), Q2 `fbc607b` (thesis library / multiple named theses), evidence types `5700c2c`.

**Reference specs/handoffs (already in repo):** `docs/handoffs/studio_foundation_handoff.md`, `docs/handoffs/studio_artboard_q1_handoff.md`, `docs/handoffs/studio_thesis_library_q2_handoff.md`, `docs/handoffs/studio_evidence_types_handoff.md`; specs `docs/superpowers/specs/2026-08-12-studio-artboard-q1-design.md`, `docs/superpowers/specs/2026-08-13-studio-thesis-library-q2-design.md`, `docs/superpowers/specs/2026-08-13-studio-evidence-types-design.md`.

---

## The three required semantic buckets (this is the heart of the task)

Every wording choice below must preserve these distinctions. **Do not collapse them.**

### A. Implemented — the bounded Studio thesis workspace
Studio is a **fixed-schema, single-user thesis-building workspace**, not a general workspace system. Implemented and verified:
1. **Studio surface + top-nav entry.**
2. **Thesis library** — multiple **named thesis boards** at `/studio`, newest-first grid, create/open/delete.
3. **Editable thesis line** — one editable claim per board (`payload.thesis`), autosaved.
4. **Pointer-driven evidence placement** — stories, headlines, and catalysts placed as nodes on a board at chosen coordinates.
5. **Labeled connections** — a **fixed** relationship vocabulary between nodes.
6. **Per-user persistence + autosave** with **verified ownership isolation** (cross-user access 404s).
7. **Saved (story-level) store + Watchlist rail** as **inputs** to a board.
8. **Current-run node intelligence** panel (whitelisted, no-leak).
9. **Headline/catalyst evidence promotion** from a story's intelligence panel onto the board (auto-linked with a `supports` connection; dedup).
10. **Compare-over-time** — compare a board against historical reconstructions, reusing the existing historical-comparison builder.

### B. Partially implemented — bounded now, general concept still open
State these as *partial*, never as fully done:
- **"Saved investigations."** Only a **story-level Saved store** exists (feeds the Studio rail). The general RWA concept of a *saved/persisted full Research Session/investigation* is **not** implemented.
- **"Custom workspaces."** Studio is a **bounded, fixed-schema thesis workspace**. **Unrestricted, user-defined custom workspaces** are **not** implemented.
- **Research Session persistence (RWA §10).** A Studio board persists a **thesis artifact**; the general Research Session-continuity concept remains unbuilt.

### C. Genuinely deferred — NOT implemented (must not be claimed as done)
- Collaborative research / **shared** (multi-user) workspaces
- **Annotations** / Research Notes / research journals
- **Portfolio overlays**
- **Trade journals**
- **Unrestricted custom workspaces**

**Rule:** The existence of Studio must never be used to assert that any item in bucket C is implemented, nor that the *general* form of any bucket-B item is complete.

---

## Scope — the ONLY files Codex may edit

1. `docs/project_status.md`
2. `docs/product_backlog.md`
3. `docs/research_workspace_architecture.md`
4. `AGENTS.md` (one small standing-rule addition — see Change 4)

`ARCHITECTURE.md` is **out of scope** for this pass (no required edit). Do not touch any other file.

---

## Change 1 — `docs/project_status.md`: Studio as an implemented surface

Additive, minimal. Preserve existing sections and their meaning.

1. **Add a Studio capability block.** Under "## Current Capabilities", add a new subsection (e.g. `### Studio (Thesis Workspace)`) that records the bucket-A feature list in canonical MNE terminology: the thesis **library** of multiple **named thesis boards**; the **editable thesis line**; **pointer-driven evidence placement** of stories, headlines, and catalysts; **labeled connections** (fixed vocabulary); **per-user persistence with autosave and verified ownership isolation**; the **Saved (story-level) + Watchlist rail** as inputs; **current-run node intelligence**; **headline/catalyst evidence promotion**; and **Compare-over-time**. Explicitly frame Studio as a **bounded, single-user, fixed-schema thesis workspace** — not a general/custom/collaborative workspace system. Add one sentence naming bucket-C as not implemented and bucket-B as partial (one clause each).
2. **Add a "Recent Major Additions" entry** for Studio (one paragraph), consistent in tone with the existing entries, citing the reference handoffs.
3. **Make documentation precedence explicit.** Near the top of the file (e.g. just under "## Project Overview"), add a short standing note stating the precedence order for resolving current-state questions: **current status (`docs/project_status.md`) → backlog (`docs/product_backlog.md`) → implemented handoffs (`docs/handoffs/`, `docs/superpowers/specs/`) → historical architecture/design documents (e.g. RWA).** Note that a phrase like *"not implemented by this document"* in an architecture document describes **that document's scope at its authoring time**, not the current repository state.
4. **Do not** delete or rewrite the Auth "Latest Product Milestone", "Current Focus", or "Known Limitations" sections. If a Known-Limitation line is now misleading because of Studio, you may add a brief parenthetical/cross-reference — **do not** silently claim broad completion. (In particular, do not claim collaboration, annotations, shared/custom workspaces, portfolio overlays, or trade journals exist.)

## Change 2 — `docs/product_backlog.md`: mark Studio foundations complete; keep bucket-C future

1. **Add a "Completed Foundations" bullet** for the **Studio Thesis Workspace**, phrased to bucket A only, explicitly noting it is a **bounded, fixed-schema, single-user** workspace, and explicitly stating that collaborative/shared workspaces, annotations/research journals, portfolio overlays, trade journals, and unrestricted custom workspaces **remain future** (bucket C), and that general saved-investigation/Research-Session persistence and general custom workspaces remain **partial/future** (bucket B). Cite the four Studio handoffs.
2. **Epic 1 item table.** Add a row (or rows) marking the Studio thesis-workspace foundation **Complete** (Studio library, named boards, thesis line, evidence placement, labeled connections, persistence/autosave, Saved/Watchlist inputs, node intelligence, headline/catalyst evidence, Compare-over-time). **Leave existing Future rows Future**, and tighten them so Studio is not misread as fulfilling them:
   - `Research Session persistence` — remains **Future**; add a clause that Studio persists a bounded thesis artifact but not general Research Session continuity.
   - `Annotations, shared workspaces, and research journals` — remains **Future** (bucket C), unchanged in status.
   - Any `Custom workspaces` / `Saved investigations` phrasing — clarify Studio is a bounded realization; the general form remains Future.
3. Do not alter unrelated Epics or the Historical Replay epic.

## Change 3 — `docs/research_workspace_architecture.md`: dated status note, NOT a rewrite

**Preserve every existing sentence, including the original §16 wording.** Add clearly-marked, dated status notes that reconcile the historical text with current state:

1. **§16 (Future Workspace Extensions):** immediately after the existing "reserved for architectural compatibility, not implemented by this document" list, add a block such as:
   > **Status note (2026-08-15):** The phrase "not implemented by this document" above describes this architecture document's scope at its authoring time — it is not a current repository-state claim. Since then, a **bounded, single-user Studio thesis workspace** (Sprints N–Q plus evidence types) has implemented a constrained realization of *some* concepts named here — a persisted thesis artifact, a story-level Saved store, a Watchlist rail, and a Compare-over-time tool. **Collaborative/shared workspaces, annotations/research journals, portfolio overlays, trade journals, and unrestricted custom workspaces remain unimplemented.** For current state, see `docs/project_status.md` and `docs/product_backlog.md` (precedence: current status → backlog → implemented handoffs → this document).
2. **§10 (Research Session Model):** add a one-line dated cross-reference noting that a bounded persisted **thesis artifact** now exists in Studio, while the general Research Session-persistence concept described here remains future; point to project_status/backlog.
3. **§18 step 8 ("Stop."):** add a one-line dated note that a bounded Studio thesis workspace has since been built within these boundaries, and that the reserved collaborative/annotation/portfolio/journal/shared/unrestricted-custom items remain deferred.

Do **not** edit §1–§15 substantive architecture prose beyond the two one-line cross-references named above. Do not make it read as though Studio existed when the document was written.

## Change 4 — `AGENTS.md`: standing "verify before negative claims" rule

Add one concise standing rule (fits the existing "Standing rules (all agents)" list or "Where current state lives") instructing agents that **before asserting a feature does not exist**, they must check all of: (1) `docs/project_status.md`; (2) `docs/product_backlog.md`; (3) `docs/handoffs/` and `docs/superpowers/specs/`; (4) application routes; (5) templates and static assets; (6) models and migrations; (7) tests; (8) recent git history. Include the note that phrases like *"not implemented by this document"* are **scoped historical statements, not repository-wide current-state facts**; when sources conflict, report the conflict and prefer verified code plus newer approved handoffs; never conclude "not implemented" from an architecture document alone. Keep it short and in the file's existing voice.

---

## Required wording / semantic guardrails (checklist for the writer)

- Studio is described as **bounded, single-user, fixed-schema thesis workspace** — never as "custom workspaces," "collaborative," or "shared."
- Bucket C terms (collaboration, shared workspaces, annotations, research journals, portfolio overlays, trade journals, unrestricted custom workspaces) appear **only** as *not implemented / future*.
- Bucket B terms (general saved investigations / Research Session persistence, general custom workspaces) appear **only** as *partial / bounded now, general form future*.
- Canonical engine terminology preserved; user-facing plain language stays in `mne/presentation_language.py` (do not invent new user-facing copy in docs). The engine/experience/architecture boundary language in RWA §3, §11 is preserved.
- No historical spec/architecture document is rewritten to pretend the later implementation already existed. Status notes are additive and dated.
- Documentation precedence is stated explicitly at least once (project_status.md), and cross-referenced from the RWA status note.

---

## Verification (before Daniel commits — nothing staged/committed/pushed)

Run and record results for each:

1. **No-code-change proof:** `git status --porcelain` shows only the four in-scope docs modified; **no** files under `mne/`, `dashboard.py`, `templates/`, `static/`, `alembic/`, `config/`, `tests/`. (Optionally `git diff --stat` to confirm.)
2. **Studio is now discoverable in canonical current-state docs:**
   - `rg -i 'studio' docs/project_status.md docs/product_backlog.md` → non-empty (Studio present in both).
   - `rg -i 'compare-over-time|compare over time' docs/project_status.md` → present (feature recorded).
3. **No contradictory current-state claims survive:**
   - `rg -n 'not implemented by this document' docs/research_workspace_architecture.md` → original line still present **and** immediately followed by the dated Status note (manual read to confirm adjacency).
   - `rg -ni 'studio' docs/research_workspace_architecture.md` → appears only inside dated status notes, never in the original §1–§15 body claims.
   - Manual read: no doc asserts collaboration / shared workspaces / annotations / portfolio overlays / trade journals / unrestricted custom workspaces are implemented.
4. **Precedence statement present:** `rg -ni 'precedence|current status' docs/project_status.md` → the precedence note exists.
5. **AGENTS.md rule present:** `rg -ni 'before asserting|does not exist|recent git history' AGENTS.md` → the new standing rule exists.
6. **Link/path integrity:** every doc path referenced by the new prose resolves — check each cited handoff/spec/file path exists (`ls` or `test -f`). No broken relative links introduced.
7. **`git diff --check`** clean (no whitespace/conflict-marker errors).
8. **Final full-diff review:** read the complete `git diff` end to end; confirm every change is additive prose in the four files, buckets A/B/C are respected, and nothing was rewritten to falsify history.
9. **Nothing staged, committed, or pushed.**

## Out of scope (explicit)

- Any application code, template, static asset, schema, migration, config, or test change.
- `ARCHITECTURE.md` edits.
- New user-facing copy (belongs in `mne/presentation_language.py`, not docs).
- Rewriting or deleting any historical spec/architecture prose.
- Reconciling the broader Research-tier v2 rework (Sprints H–R) in the docs — **this pass is Studio-scoped only.** (A separate broader sync may be worthwhile later; note it to Daniel, do not do it here.)
