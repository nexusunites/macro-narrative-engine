# User-Facing Historical Research UX — Codex Implementation Handoff

## Objective

Expose existing historical replay intelligence through a clean, read-only user experience. A normal user can browse completed historical reconstructions and investigate one — dominant narrative at the cutoff, strongest themes/groups, supporting evidence, coverage breadth, and honest limitations — without ever seeing operational internals. This sprint surfaces existing capability; it builds no new replay, backfill, or scoring logic.

**Core principle:** the user sees historical market understanding. The user never sees: backfill IDs, workflow IDs, manifest or filesystem paths, connector diagnostics, replay-engine metadata, admin controls, raw JSON, telemetry, or source-registry internals.

Read `AGENTS.md` before starting. All standing rules apply.

## Alignment with the Dashboard Rework (binding)

The new pages are user-facing surfaces and therefore inherit the reworked user-dashboard conventions in full:

- **Plain language.** All labels and states route through `mne/presentation_language.py`. Extend the dictionary with historical vocabulary (coverage breadth states, evidence-origin explanations); never hardcode user copy in templates. Engine terminology appears only inside Why-expanders.
- **Color budget.** Neutral base + `--up`/`--down` only, `--brand-accent` scoped repoint pattern. Historical pages additionally apply the existing `--tier-historical` surface tint and set `active_tier = "historical"` in the app rail so users always know they've left live intelligence.
- **Explainability.** Every synthesized statement is deterministic template-fill from persisted replay fields, with a Why-expander exposing the underlying engine values.
- **Honest degradation.** Calm empty states everywhere; no technical error text.

## Scope

### 1. Historical selector — `GET /history`

Lists completed replay artifacts that are safe for user display. Each card shows: historical date (primary label), dominant group and theme (plain names), evidence count ("N pieces of evidence"), coverage breadth in translated language, and a one-line deterministic context sentence. Replay IDs are never the primary visible label. Selection rule: an artifact is listed iff it loads cleanly through the existing safe replay loader and contains the minimum snapshot fields; malformed artifacts are silently excluded (logged server-side only). Replays with zero accepted evidence are listed but badged "Limited reconstruction" *(Judgment Call #3)*.

### 2. Historical investigation — `GET /history/{replay_id}`

Internally validated replay ID via the existing safe validation/loading helpers; invalid or missing IDs render a calm "This historical reconstruction isn't available" state (HTTP 404 semantics, friendly page). No live-results fallback, ever. *(Judgment Call #1 on the URL identifier.)*

### 3. Page structure — Research Workspace investigation style

Zones, in order: **Historical Snapshot** · **Narrative Explanation** · **Supporting Historical Evidence** · **Coverage and Limitations** · **Where to Look Next**. A persistent banner strip at the top states, in plain language: historical reconstruction · evidence cutoff date · read-only · "This is not current market intelligence." The banner uses the historical tier styling, not warning color.

### 4. Historical Snapshot

Replay date, evidence cutoff, dominant theme and group (plain names), theme/group scores rendered with the reworked card conventions (counts pluralized, "stories"/"pieces of evidence" language), evidence count, source count, breadth state (translated), and a deterministic historical summary sentence composed from those fields — same composer discipline as the dashboard (skip unavailable parts; the word "unavailable" never appears in composed prose). No technical replay metadata on the surface; engine values live in the Why-expander.

### 5. Supporting evidence

Reuse the existing safe evidence display and Evidence Reader panel behavior. Per item: headline, source/provider display name, publication date, narrative attribution (plain group name), original link when available ("Read original →"; calm "Original article unavailable" otherwise), and a user-safe origin explanation (e.g., "From the official Federal Reserve statement archive" / "From live news collection at the time") via a deterministic origin→copy mapping in the presentation dictionary. Never render: `evidence_id`, `source_id`, `backfill_id`, `connector_source_id`, or internal provenance dictionaries.

### 6. Coverage honesty

Neutral, fixed copy (in the presentation dictionary, not templates): "Historical coverage reflects the supported sources available for this reconstruction." · "This is not complete historical market-news coverage." · "Evidence published after the historical cutoff is excluded." Breadth describes evidence availability, never narrative truth or quality.

### 7. Empty and unavailable states

Calm renders for: no replays available (selector explains what historical reconstructions are and that none exist yet), malformed/unavailable replay, zero accepted evidence, missing optional coverage fields (omit the block, don't placeholder it), missing article links. No stack traces, no raw error strings.

### 8. User/admin boundary

The user pages are strictly read-only. All backfill/replay generation, comparison, workflow status, and diagnostics remain in `/admin`, unchanged. No admin-only warnings leak to `/history`. The existing admin Historical Research Workspace is not modified; shared safe context helpers may be reused, admin-only fields must stay admin-side (prefer a display-only view helper, e.g., `mne/historical_research_view.py`, that whitelists user-safe fields rather than blacklisting unsafe ones — whitelist is the required approach).

### 9. Dashboard entry point

One restrained link on the user dashboard: "Explore historical narratives →", accent-link styling, placed in the Where to Look Next position at the page bottom (or beneath the hero chart if a natural slot exists — implementer's choice between these two only). No dashboard redesign.

## Non-Goals

No user-run backfills or replays, no user-facing comparison view (future sprint), no background jobs, no accounts/entitlements, no changes to scoring, taxonomy, replay cutoff logic, backfill connectors, Coverage Intelligence, Narrative Memory, or Operations Center. No LLMs, no predictions, no trade recommendations.

## Likely files

`dashboard.py`, `mne/historical_research.py` (reuse), new `mne/historical_research_view.py` (display-only whitelist helper), `templates/historical_selector.html`, `templates/historical_investigation.html`, small edit to `templates/dashboard.html`, `static/styles.css`, `mne/presentation_language.py` (historical vocabulary), `tests/test_historical_research_user.py`. Reuse safe replay validation/loading; duplicate no replay or backfill logic.

## Ratified Decisions (Daniel, 2026-07-29)

1. **URL identifier: internal replay ID in the path** (`/history/{replay_id}`, validated, never emphasized in visible copy; the date is the visible label everywhere). Ratified.
2. **Historical tier styling applied to user pages** (tier tint + rail state) so reconstructions are never mistaken for live intelligence. Ratified — presentation-only and reversible if it doesn't land visually.
3. **Zero-evidence replays are listed with a "Limited reconstruction" badge**, not hidden. Ratified.

## Tests required

The 28 tests as specified: selector rendering/listing/malformed-exclusion/empty state (1–4); investigation route and all five zones rendering (5–9); future-evidence exclusion copy and historical/not-current labeling (10–11); no raw replay-ID emphasis, no backfill IDs, workflow IDs, evidence/source IDs, or filesystem paths in rendered HTML (12–16); no admin controls (17); source links present and missing-link calm state (18–19); missing coverage fields and zero-evidence calm states (20–21); dashboard entry point (22); admin Historical Research unchanged (23); user route performs no writes, triggers no replay, no backfill, no live fetching (24–27); no scoring/taxonomy regression (28). Add: presentation-dictionary coverage for all new historical vocabulary (no untranslated-fallback markers on rendered pages).

## Verification

- `python -m unittest tests.test_historical_research_user -v`
- `python -m unittest tests.test_historical_research -v`
- `python -m unittest tests.test_historical_replay -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`

Manual: open `/history`, select a replay, confirm the page reads as a historical investigation with readable evidence and clear limitations; confirm no admin/backfill/replay internals in page source (grep rendered HTML for `backfill`, `manifest`, `evidence_id`, `MNE_DATA_DIR`); confirm dashboard entry point; confirm `/admin` historical tools unchanged; confirm color budget and tier styling; check 1280/1024/390 widths. Do not run new backfills or live fetches during verification.

## Output required

Report: objective summary; files changed; route/helper summary; selector behavior; investigation behavior; evidence display behavior; coverage/limitations behavior; user/admin boundary verification; replay/backfill/live isolation verification; verification performed; known remaining gaps; whether User-Facing Historical Research UX can be marked implemented.

Implement to a verified local state and stop — do not stage, commit, or push.
