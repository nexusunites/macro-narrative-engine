# Narrative History Charts and Lifecycle Visualization — Codex Implementation Handoff

## Objective

Let users see how a narrative evolved: when it emerged, strengthened, became dominant, peaked, faded, went dormant, or recurred. Deterministic visualization of persisted history only — no prediction, no interpolation-as-fact, no rescoring of old evidence, no LLM judgments, no causation claims, no trade language.

Read `AGENTS.md` before starting. All standing rules apply — rule 5 (data philosophy) and rule 6 (color budget) especially.

## Architecture corrections to the original draft (decided — do not re-derive)

1. **Data source is daily snapshots, not "latest 30 meaningful runs."** Standing rule 5: trends read one representative point per day; per-run series inflate busy days. Verified basis: `mne/storage.py::_run_narratives` already persists per-day narrative rows in snapshots — `group`, `share`, `score`, `rank`, `pulse_state` — exactly the series the charts need. Default window: **latest 90 snapshot days** (configurable constant), fewer handled calmly.
2. **No Chart.js.** It is not in the repo and no new dependencies are permitted. Charts follow the existing vanilla pattern (`static/chart.js` hero chart): inline SVG, hover scrub where useful, gradient fill, min/max labels only, graceful static/JS-disabled fallback.

## Scope

### 1. History helper — new `mne/narrative_history.py` (read-only)

`build_narrative_history(group_key, window_days=90)` reads daily snapshots via existing storage helpers (through `mne/render_cache.py`) and returns a deterministic context: per-day points `{date, score, share, rank, dominant (rank == 1), pulse_state}`; absent-on-that-day is an explicit gap, never interpolated. Same input history → byte-identical output.

**Narrative groups only in this MVP** — snapshots do not persist per-theme daily rows *(Judgment Call #2)*. No replay-artifact reads, no live fetching, no writes.

### 2. Charts (vanilla, hero-chart pattern)

- **Primary: Score over time** — line + gradient, accent color, scrub readout (date, score, translated pulse state).
- **Secondary: Share of narrative attention** — same pattern, percent axis.
- **Compact: Rank over time** — small step-line (1 at top); rendered only when ≥3 ranked points exist.
- Gaps render as gaps. Days-absent shown as breaks with a quiet legend note. All charts JS-optional (static SVG baseline rendered server-side; scrub added progressively). Color budget: accent line only; no red/green judgment coloring — score movement is not "good/bad."

### 3. Lifecycle timeline

Horizontal strip of per-day lifecycle states across the window, using **persisted vocabulary only**: `pulse_state` from snapshots (Dormant/Emerging/Building/Strong/Dominant) plus explicit `Absent` for gap days. Memory-derived states (Recurring, Re-accelerating, Persistent, Fading) appear **only** where persisted `narrative_memory`/`narrative_dynamics` values exist for that period — never derived fresh in this module. If a state is not persisted, the timeline shows the pulse state alone; the derivation source is documented in the module docstring. No invented or contradictory states.

### 4. Current lifecycle summary (fixed deterministic templates)

Compact card: current stage, previous stage, current streak, appearances in window ("Present on 34 of 90 days"), dominance count ("Led on 12 days"), peak score + date, highest share + date, most recent recurrence/re-acceleration if persisted. All labels through `mne/presentation_language.py` — extend the dictionary as needed; engine terms only in the Why-expander, which also carries the integrity copy (below).

### 5. Placement — dedicated history route

Daniel expects this section to grow, so it gets its own page from the start: `GET /research/{narrative}/history`, using the same validated narrative-key handling as the existing investigation route and the Research Workspace investigation style. The full experience (charts, lifecycle timeline, lifecycle summary, integrity copy) lives there.

The live Narrative Investigation page gets a **compact preview** in the after-Recent-Memory / before-Supporting-Evidence slot: the current lifecycle summary card plus a small static score sparkline, with "View full history →" linking to the history page. No sticky-nav complexity; Evidence Reader untouched. Invalid narrative keys on the history route render the same calm not-found treatment as the investigation route.

### 6. Integrity copy (fixed, in the presentation dictionary)

"History reflects persisted MNE runs." · "Missing run dates are not interpolated." · "Lifecycle labels describe observed narrative behavior, not future outcomes."

### 7. Empty/thin states

Calm renders for: no snapshot history; one day; fewer than three days (summary renders, charts replaced by "Not enough history to chart yet — history builds as daily runs accrue"); narrative absent most of the window; missing share/rank fields (omit that chart, keep the rest); missing memory states (pulse-only timeline). Never a broken or misleading chart.

### 8. Display language

Plain labels only: Score, Share of narrative attention, Rank, Dominant, Building, Fading, Recurring, Re-accelerating. Forbidden anywhere: bullish, bearish, forecast, prediction, buy, sell, winner, loser.

## Non-Goals

No changes to Narrative Memory classification, scoring, taxonomy, evidence acceptance, Historical Replay/Comparison, or snapshot persistence format. No market-price outcome analysis, AI analyst, alerts, personalization, prediction models, or databases. No theme-level series (future item; requires a persistence decision first).

## Likely files

New `mne/narrative_history.py`; `mne/research_workspace.py` (context wiring); `templates/narrative_investigation.html`; `static/styles.css`; small JS following the `static/chart.js` pattern (extend or sibling file — implementer's choice, no duplication of scrub logic if extraction is clean); `mne/presentation_language.py`; `tests/test_narrative_history.py`; `tests/test_research_workspace.py` additions. Reuse: snapshot loading helpers, `render_cache`, presentation language, persisted `narrative_memory`/`narrative_dynamics`.

## Ratified Decisions (Daniel, 2026-07-29)

1. **Daily snapshots as the sole series source** (corrects the draft's 30-meaningful-runs window; enforces standing rule 5). Ratified.
2. **Groups-only MVP**; theme-level daily history deferred pending its own snapshot-persistence handoff. Ratified.
3. **Dedicated `GET /research/{narrative}/history` route** with a compact preview + link on the investigation page — Daniel expects this section to grow, so it gets its own page from the start. Ratified (supersedes the draft's inline preference).

## Tests required

Adapting the draft's list to the corrected architecture: snapshot-only loading with replay artifacts and malformed snapshots excluded (1–3); group series builds correctly with persisted score/share/rank preserved exactly (4–8, groups); dominant flags from rank (9); persisted lifecycle states reused, missing states degrade to pulse-only (10–11); peak score/date and peak share/date correct (12–13); appearances and dominance counts reconcile (14); thin-history and no-history states (15–16); gaps never interpolated (17); investigation page renders the compact preview with Recent Memory and Evidence Reader intact, and the history route renders the full experience with calm invalid-key handling (18–20); no raw JSON/paths/telemetry/admin diagnostics (21); dashboard, Historical Research, and Comparison unchanged (22–23); no replay-directory reads, no source fetching (24–25); no scoring/taxonomy regression (26); byte-identical context for identical input (27). Add: window bound respected; forbidden-language absence in rendered HTML; presentation-dictionary coverage (no untranslated markers).

## Verification

- `python -m unittest tests.test_narrative_history -v`
- `python -m unittest tests.test_research_workspace -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`

Manual: open a dominant narrative's investigation; confirm score/share charts and lifecycle timeline render and scrub; thin-history state calm; Evidence Reader intact; grep rendered HTML for forbidden terms (`bullish`, `forecast`, `prediction`, `buy`, `sell`); dashboard and historical pages unchanged; JS-disabled render; 1280/1024/390 widths. No live fetching.

## Output required

Report: objective summary; files changed; history module summary; history schema example; chart behavior; lifecycle timeline behavior; lifecycle summary example; thin/missing-history behavior; Research Workspace integration; safety/boundary verification; verification performed; known remaining gaps; whether Narrative History Charts and Lifecycle Visualization can be marked implemented.

Implement to a verified local state and stop — do not stage, commit, or push.
