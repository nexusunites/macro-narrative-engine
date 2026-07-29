# User-Facing Historical Comparison UX — Codex Implementation Handoff

## Objective

Extend the user-facing historical experience with read-only comparison of two persisted historical reconstructions, answering: "What changed between these two historical market narratives?" — which narratives strengthened or weakened, whether dominance changed, what appeared or disappeared, how the evidence base differed, and what coverage limitations apply. This sprint safely exposes the existing deterministic comparison helper; it creates no new comparison engine.

**Core principle:** the user sees narrative change. The user never sees: replay IDs as primary labels, backfill IDs, workflow IDs, artifact filenames, filesystem paths, raw replay metadata, connector diagnostics, admin controls, raw JSON, or operational errors.

Read `AGENTS.md` before starting. All standing rules apply.

## Alignment (binding)

Inherits everything established by the Dashboard Rework and the User-Facing Historical Research UX (`docs/handoffs/user_historical_research_handoff.md`):

- All labels/states through `mne/presentation_language.py`; extend the dictionary with comparison vocabulary. Direction enums (`INCREASED`, `DROPPED`, etc.) translate to: **Increased · Decreased · Unchanged · New · No longer present**. Raw enums never render.
- Color budget: neutral base + `--up`/`--down`. Score-change rows are deltas, so directional arrows/colors are in-budget — reuse the Sprint D change-chip pattern (▲/▼ + `--up`/`--down`). Direction color signals magnitude direction only, never judgment ("Increased" is not "good").
- Historical tier styling and rail state (`active_tier = "historical"`), persistent banner: historical comparison · read-only · not current market intelligence · based on persisted historical reconstructions.
- **Whitelist rule:** the display helper (`mne/historical_comparison_view.py`) enumerates user-safe fields in; it does not filter unsafe fields out.
- Deterministic composition (skip unavailable parts; "unavailable" never appears in prose), calm empty states, no technical errors.

## Scope

### 1. Selector — `GET /history/compare`

Two period pickers (A and B) listing the same user-safe reconstructions as `/history`, with the same labels: date (primary), dominant narrative, evidence breadth, one-line context. Users never need to understand replay IDs. Periods are auto-ordered chronologically — A is always the earlier period regardless of pick order, so comparison prose always reads "from earlier to later" *(Judgment Call #2)*.

### 2. Comparison route

Validated replay identifiers internally (query params or path — implementer's choice, IDs never emphasized in copy). Reuse the existing historical comparison helper. Never: generate a replay, run a backfill, fetch sources, read live results as fallback, or modify artifacts. Refresh performs no work.

### 3. Page structure

Sections in order: **Comparison Snapshot** · **Dominance Changes** · **Theme Changes** · **Narrative Group Changes** · **Evidence Base Changes** · **Historical Coverage and Limitations** · **Explore Each Period**.

### 4. Comparison Snapshot

Date A and Date B, dominant theme/group for each (plain names), evidence and source counts, breadth states (translated), and a concise deterministic summary of the main changes — template-fill from persisted comparison fields, same composer discipline as the dashboard.

### 5. Narrative changes (themes and groups)

Per row: name, score A, score B, change with directional arrow/color, rank A → rank B, translated direction label. Rendered in the reworked visual language (list rows or compact cards, not raw admin tables). Pluralization helper applies to all counts.

### 6. Dominance changes

Calm deterministic sentences: "The dominant theme changed from AI to Energy." · "The dominant narrative group remained AI / Tech Growth." · "Rates moved from rank 4 to rank 2." No prediction or trade language anywhere.

### 7. Evidence-base comparison

Accepted evidence counts, contributing source/provider/category counts, breadth states, evidence-origin mix in user-safe origin language (reuse the origin→copy mapping from Historical Research) when useful. Copy must never imply more evidence = more true or predictive.

### 8. Coverage honesty (fixed copy, in the dictionary)

"Historical coverage reflects supported sources available for each reconstruction." · "This is not complete historical market-news coverage." · "Differences may partly reflect differences in available historical evidence."

### 9. Investigation links

"Explore earlier period →" / "Explore later period →" linking to the existing `/history/{replay_id}` investigation pages, accent-link styling.

### 10. Empty and unavailable states

Calm renders for: fewer than two reconstructions available (selector explains comparison needs two periods), invalid selection, malformed replay, missing comparison fields, missing coverage intelligence (omit the block), and same-replay-twice — which renders a calm no-change state ("These are the same reconstruction — nothing to compare") rather than an error.

### 11. Entry point

One restrained link on `/history`: "Compare historical narratives →". No dashboard redesign; the dashboard's existing single historical entry point is unchanged.

### 12. User/admin boundary

Admin Historical Comparison unchanged. No admin links, generation controls, workflow controls, diagnostics, paths, or IDs on user surfaces.

## Non-Goals

No user-run backfills/replays, no unified historical request workflow, no charts unless trivially supported by existing patterns, no AI interpretation, no changes to scoring, taxonomy, cutoff rules, comparison calculations, Coverage Intelligence, Narrative Memory, or Operations Center. No auth/billing/entitlements. No predictions or trade recommendations. Read-only comparison only.

## Likely files

`dashboard.py`, `mne/historical_comparison.py` (reuse), new `mne/historical_comparison_view.py` (display-only whitelist), `templates/historical_comparison_selector.html`, `templates/historical_comparison_user.html`, small edit to `templates/historical_selector.html`, `static/styles.css`, `mne/presentation_language.py` (comparison vocabulary), `tests/test_historical_comparison_user.py`. Reuse safe validation/comparison helpers; keep user-safe shaping separate from admin context.

## Ratified Decisions (Daniel, 2026-07-29)

1. **Directional color on narrative change rows** — ▲/▼ in `--up`/`--down`, reusing the dashboard change-chip pattern. Ratified.
2. **Chronological auto-ordering** — A is always the earlier period; reversed picks are silently swapped so comparison prose always reads forward in time. Ratified.
3. **Dedicated `/history/compare` page with two pickers.** Ratified; checkbox-compare on `/history` remains a possible future addition.

## Tests required

The 32 tests as specified: selector render/listing/malformed-exclusion/fewer-than-two (1–4); valid and same-replay comparison (5–6); all sections render (7–10, 16–17); all five direction labels render (11–15); missing-coverage calm state (18); both investigation links (19); no raw replay-ID emphasis, backfill IDs, workflow IDs, evidence/source IDs, filesystem paths, or admin controls (20–25); no writes, no replay, no backfill, no live fetching (26–29); admin comparison and user Historical Research unchanged (30–31); no scoring/taxonomy regression (32). Add: presentation-dictionary coverage for all comparison vocabulary (no untranslated-fallback markers).

## Verification

- `python -m unittest tests.test_historical_comparison_user -v`
- `python -m unittest tests.test_historical_comparison -v`
- `python -m unittest tests.test_historical_research_user -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`

Manual: open `/history` → comparison selector → compare two reconstructions; confirm the page clearly explains what changed; confirm both investigation links; grep rendered HTML for `backfill`, `manifest`, `evidence_id`, `MNE_DATA_DIR`; confirm admin comparison still works; confirm refresh performs no work; color budget + tier styling; 1280/1024/390 widths. No backfills, replays, or live fetching during verification.

## Output required

Report: objective summary; files changed; route/helper summary; selector behavior; comparison-page behavior; narrative-change behavior; evidence and coverage behavior; user/admin boundary verification; replay/backfill/live isolation verification; verification performed; known remaining gaps; whether User-Facing Historical Comparison UX can be marked implemented.

Implement to a verified local state and stop — do not stage, commit, or push.
