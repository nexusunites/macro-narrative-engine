# Cross-Sector Heatmap and Sector Isolation — Implementation Handoff

## Purpose

MNE can surface leading narratives (Narrative Constellation), curated cross-narrative structure
(Cross-Group Relationship Model, implemented `7190972`), and broad market-expression context
("Markets Right Now"), but nothing today shows *where a narrative is spreading across sectors*.
This sprint adds a curated, deterministic Sector Isolation layer — a sector model, a
narrative-to-sector structural map, a dashboard preview, and a dedicated `/research/{narrative}/sectors`
view — completing step 2 of the Macro Discovery → Sector Isolation → Asset Exploration → Evidence
workflow.

**Status: scope ratified by Daniel, 2026-08-03**, after a data-availability audit changed what
this sprint can honestly ship (see §Ratified Decision below). Do not implement code from this
document directly — this is the Codex-ready brief.

---

## Ratified Decision (Daniel, 2026-08-03): Structural-only this sprint

The data audit (§3) found **no real per-sector market data anywhere in this codebase.** The live
market fetch is hardcoded to four tickers, none of them sector instruments; sector ETF tickers
referenced in existing config files are never actually fetched or persisted. Per the original
spec's own core principle ("do not invent sector metrics," "if data is insufficient, use
UNAVAILABLE rather than guessing"), the ratified scope is:

**Build:**
- A versioned, curated narrative-to-sector map (`config/narrative_sector_map.json`).
- A deterministic sector model with real structural connection roles: `PRIMARY`, `SECONDARY`,
  `EMERGING`, `OFFSET`, `DETACHED`.
- Deterministic heatmap layout, sector rationale, and plain-English explanations.
- Dashboard preview and dedicated `/research/{narrative}/sectors` route.
- `participation_state` present in the schema and rendered honestly as `UNAVAILABLE` everywhere,
  since no sector-level market data exists to classify it as anything else.

**Do not:**
- Infer sector participation from the four tickers the app does fetch (QQQ, NVDA, VIX, DXY) —
  none are sector-specific, and presenting them as sector confirmation would misrepresent
  broad-market signal as sector-level evidence.
- Expand live market-data fetching this sprint.
- Modify snapshot persistence (`mne/storage.py`).
- Fabricate participation states to make the heatmap look more populated than the data supports.

**User-facing copy must distinguish the two concepts explicitly:**
- Structural connection: *"This sector is meaningfully connected to the narrative."*
- Current participation: *"Current sector-level market participation is not yet available."*

A named follow-up sprint, **Sector Market Data Plumbing and Participation States**, is deferred
work (§17) covering real sector ETF coverage, snapshot persistence, freshness/staleness rules, and
genuine participation classification — while preserving the structural map this sprint delivers as
a separate, permanent concept.

---

## 1. Objective Summary

Ship a curated sector model and narrative-to-sector structural map (mirroring the pattern
`mne/narrative_relationships.py` already established for cross-group relationships), a compact
dashboard preview, and a dedicated Sector Isolation route showing structural connection role per
sector for the current/selected narrative. Participation state is schema-present but uniformly
`UNAVAILABLE` this sprint, honestly explained rather than guessed. No scoring, taxonomy, live
market-data fetch, or snapshot-persistence changes.

## 2. Files Changed

**Create:**
- `config/narrative_sector_map.json` — versioned, curated narrative→sector structural map (§5).
- `mne/sector_isolation.py` — sector model, loader/validator, read API, heatmap context builder
  (§6, §11). Follows the `source_registry.py` / `narrative_relationships.py` fail-closed pattern
  already established in this codebase — same shape, same conventions, no new pattern invented.
- `templates/sector_isolation.html` — dedicated `/research/{narrative}/sectors` page.
- `templates/_partials/sector_heatmap.html` — the tile-grid partial, reused by both the dashboard
  preview (bounded) and the dedicated route (full).
- `tests/test_sector_isolation.py` — unittest-style, mirroring `tests/test_narrative_constellation.py`
  and (once merged) `tests/test_narrative_relationships.py` conventions.
- `docs/narrative_sector_model.md` — schema reference, role/participation definitions, and an
  explicit statement of the data-availability boundary from §Ratified Decision.

**Modify:**
- `dashboard.py` —
  - Add `build_sector_isolation_preview(run, dominant_narrative)` call inside `build_view_model`
    (alongside the existing `build_constellation_context` call, line 1640), assigned into the view
    dict as `"sector_isolation_preview"` for `templates/dashboard.html`.
  - Add the dedicated route. **Must be registered before** the existing catch-all
    `@app.get("/research/{key:path}")` (line 2480), exactly mirroring how the existing `/history`
    suffix route is registered first at line 2474 — otherwise `{key:path}`'s greedy match consumes
    `/sectors` as part of the narrative key and the new route never fires:
    ```python
    @app.get("/research/{key:path}/sectors", response_class=HTMLResponse)
    ```
- `templates/dashboard.html` — insert the Sector Isolation preview section **between `id="markets"`
  (lines 266–289, "Markets Right Now") and `id="events"` (line 291)** — a natural drill-down of the
  Market Reaction section, and the ordering the prior design-system handoff already anticipated
  (`docs/handoffs/design_system_dashboard_foundation_handoff.md:285`: "...Sector Isolation view +
  sector heatmap...").
- `mne/presentation_language.py` — add `SECTOR_ISOLATION_COPY` dict + `sector_isolation_copy(key)`
  accessor, following the exact `NARRATIVE_RELATIONSHIP_COPY`/`narrative_relationship_copy()`
  pattern (`presentation_language.py:116` area) — flat dict, `KeyError` on unknown keys, no
  defensive fallback.
- `static/styles.css` — add `.sector-heatmap`, `.sector-tile`, tile border/accent classes for the
  five structural roles, reusing the existing two-hue token budget (`--teal`/`--amber`, no new
  hues) plus the existing neutral/`--muted` slate treatment for the (this sprint, universal)
  unavailable-participation state.
- Research Workspace route/context tests, design-system structure tests — extend for the new route
  and preview section per existing suite conventions.

**Do not touch:** `mne/market_expression.py`, `config/market_expression_map.json`,
`mne/narrative_market_map.py`, `main.py`'s ticker fetch, `mne/storage.py`, `mne/theme_analysis.py`,
scoring, or taxonomy matching.

## 3. Sector-Data Audit Summary

Blunt finding: **no real per-sector or per-instrument price/participation data exists anywhere in
this codebase today.**

- **Live fetch is capped at 4 non-sector tickers.** `main.py:111–116` (`NASDAQ_TICKERS`): `QQQ`,
  `NVDA`, `VIX` (`^VIX`), `DXY` (`DX-Y.NYB`). `BREADTH_TICKERS` (`mne/breadth.py:4-9`: `SPY`,
  `RSP`, `QQQE`, `IWM`) is fetched but filtered out before it ever reaches
  `run["market_snapshot"]` (`main.py:772`). No sector ETF is ever fetched.
- **Sector ETF tickers exist only as unfulfilled strings in curated config.**
  `config/market_expression_map.json` references `XLE`, `XLI`, `XLU`, `XLP` as instrument labels
  for narrative market-expression roles, but since they're never fetched, they resolve to
  `UNAVAILABLE`/`missing` every time (`mne/market_expression.py:299-342`,
  `EXPRESSION_STATE_THRESHOLDS`). Concretely: `Energy / Commodities`'s primary instruments
  (`CRUDE_OIL`, `XLE`) are never populated, so that narrative's market-expression state is
  structurally guaranteed `UNAVAILABLE` in production, always.
- **A second, legacy, unrelated mapping exists and should not be extended.**
  `mne/narrative_market_map.py` (`NARRATIVE_MARKET_MAP`, lines 7–43) is a hardcoded, static,
  price-free instrument list keyed by theme, called from `main.py:407` and written into a
  *different* run key (`run["market_expression"]`, not the dashboard's
  `market_expression_context`). It's dead weight relative to the live dashboard UI — do not build
  the sector map on top of it or treat it as a second source of truth.
- **Daily snapshots drop market data entirely.** `mne/storage.py`'s aggregation path
  (`_aggregate_raw_runs`, `write_daily_snapshot`) has zero references to `market_snapshot` or
  `market_expression` — only individual run result files transiently carry a market snapshot, at
  the same 4-ticker cap.
- **No sector taxonomy exists anywhere.** No GICS mapping, no sector-to-ticker file, no
  `ticker_symbol` field in the codebase (confirmed via repo-wide grep). `docs/roadmap.md:74,93`
  mentions sector context as an aspirational future item, not built. The prior design-system
  handoff explicitly listed "Sector Isolation and the full heatmap" as a non-goal
  (`design_system_dashboard_foundation_handoff.md:176`) — this sprint is the first to build it.
- **Historical backfill has no price dimension.** `mne/historical_backfill.py` is headline/evidence
  metadata only; nothing there could back a sector time-series either.

What *can* be built honestly this sprint: a curated structural relationship — narrative group to
sector, with a rationale and a display-safe explanation — following the exact same pattern already
shipped and tested for cross-group narrative relationships. What cannot be built honestly: any
`participation_state` value other than `UNAVAILABLE`, because no sector-level market signal exists
to classify.

## 4. Sector-Map Schema Summary

No sector taxonomy exists today, so this sprint creates one, following the same convention as
`NARRATIVE_GROUPS` (`mne/narrative_signals.py:1-6`) — a hardcoded, canonical set of sector keys in
`mne/sector_isolation.py`, since there's no existing JSON-config precedent for a base taxonomy
(group/theme taxonomy itself is Python source too, per the relationship-model handoff's Grounding
Decision 1):

```python
SECTOR_KEYS = {
    "technology": "Technology",
    "communication_services": "Communication Services",
    "consumer_discretionary": "Consumer Discretionary",
    "financials": "Financials",
    "industrials": "Industrials",
    "energy": "Energy",
    "materials": "Materials",
    "utilities": "Utilities",
    "real_estate": "Real Estate",
    "consumer_staples": "Consumer Staples",
    "health_care": "Health Care",
}
```

`config/narrative_sector_map.json`:

```json
{
  "version": "1.0.0",
  "narratives": {
    "AI / Tech Growth": {
      "sectors": [
        {
          "sector": "technology",
          "role": "PRIMARY",
          "rationale": "Semiconductors, cloud infrastructure, and software are direct expressions of AI investment.",
          "display_enabled": true
        }
      ]
    }
  }
}
```

Narrative keys must be exact `NARRATIVE_GROUPS` keys (same convention as
`config/narrative_relationships.json`). `sector` values must be exact `SECTOR_KEYS` keys. The
per-sector `connection_role` presentation record (built at read time, not stored) adds
`participation_state` (always `"UNAVAILABLE"` this sprint), `evidence_count` (0 unless real
evidence-linkage exists — do not fabricate a count), `explanation`, `available`, and `href`
pointing at `/research/{narrative}/sectors#{sector_key}`.

## 5. Structural-Role Behavior

Five roles, curated and structural only — never implying current price confirmation:

| Role | Meaning |
|---|---|
| `PRIMARY` | The sector is the clearest, most direct expression of the narrative. |
| `SECONDARY` | The sector is meaningfully connected but not the narrative's primary channel. |
| `EMERGING` | The structural connection is real but still developing. |
| `OFFSET` | The sector can move in a counter-direction relative to the narrative. |
| `DETACHED` | No meaningful structural connection is curated for this sector. |

**Initial curated set** (sparse, matching the same three groups already populated in
`config/market_expression_map.json` and `config/narrative_relationships.json` — `Geopolitical Risk`
has no market-expression or relationship mapping today either, so it is left unmapped in v1 pending
a real rationale, not forced):

- **AI / Tech Growth** — Technology (`PRIMARY`), Communication Services (`SECONDARY`), Utilities
  (`EMERGING` — data-center power demand, consistent with the relationship model's own example
  language), Industrials (`EMERGING` — data-center/infrastructure buildout).
- **Energy / Commodities** — Energy (`PRIMARY`), Materials (`SECONDARY`), Utilities (`SECONDARY`
  — input-cost sensitivity, distinct rationale from its AI-driven `EMERGING` role above; a sector
  can appear under multiple narratives with different roles and rationale, that's expected).
- **Macro Pressure** — Financials (`PRIMARY` — rate sensitivity), Real Estate (`SECONDARY` — rate
  sensitivity), Consumer Discretionary (`OFFSET` — spending pressure under tightening conditions).

Not every sector needs a role under every narrative — omission means "no curated relationship,"
not `DETACHED`. `DETACHED` is reserved for sectors worth explicitly telling the user are
unconnected (e.g., surfaced in an X-Ray "what's not connected" view), not a default filler for
every unmapped sector — keep the initial config sparse, not exhaustively enumerated.

## 6. Participation-State Rules

`classify_sector_participation(...)` exists in the module with the correct signature for future
real inputs, but this sprint it deterministically returns `UNAVAILABLE` for every sector, every
narrative, unconditionally — documented in the function's own short comment as intentional, not a
stub bug. No sector ETF price, no breadth calculation, no evidence-concentration heuristic is wired
in this sprint (§Ratified Decision). The six other states (`STRONG`, `PARTICIPATING`, `EMERGING`,
`MIXED`, `DETACHED`, `CONTRADICTING`) are defined in `docs/narrative_sector_model.md` for schema
completeness and forward-compatibility with the follow-up sprint (§17), but no code path this
sprint can honestly produce them.

## 7. Heatmap Visual Encoding

- **Border emphasis** = structural connection role (`PRIMARY` gets the strongest border weight,
  `SECONDARY`/`EMERGING` progressively lighter, `OFFSET` a distinct dashed treatment, `DETACHED`
  the lightest/faintest).
- **Accent marker** = current participation. This sprint, every tile shows the same neutral/slate
  "unavailable" marker — expected and correct given §6, not a bug to chase in QA.
- **Color rule** (matches the ratified design-system budget, no new hues): teal reserved for real
  confirmed/strengthening participation (unused this sprint since none exists), amber reserved for
  real contradiction/pressure (also unused this sprint), slate for neutral/detached/unavailable —
  which this sprint means every tile's participation accent is slate.
- No full-card saturated fills, no red/green terminal grid, no color-only meaning — role and
  participation must also be legible from typography/labels alone (accessibility requirement, §14).
- Tile size fixed, not weighted by unavailable participation data — do not let tile size imply a
  participation signal that doesn't exist.

## 8. Sector Breadth Behavior

Because participation is universally `UNAVAILABLE` this sprint, breadth cannot honestly be phrased
as "broad/concentrated participation" — that would imply confirmed market response that doesn't
exist. Instead, `compute_sector_breadth(...)` reports **structural breadth** (count and role mix of
curated sectors), with copy that explicitly separates the two concepts:

> "This narrative is structurally connected across 4 sectors. Current sector-level market
> participation data is not yet available."

Breadth categories (`Broad`, `Moderate`, `Concentrated`, `Limited`, `Unavailable`) apply to
structural connection count only this sprint — never to participation, and the copy must say so
every time breadth is shown, not just on first mention.

## 9. Dashboard Preview Behavior

- Uses the current dominant narrative by default (matching the constellation preview's existing
  convention).
- Shows a bounded number of sectors (recommend top 3–4 by role weight: `PRIMARY` first).
- States structural breadth (§8) plus the honest participation-unavailable line.
- Links to the dedicated `/research/{narrative}/sectors` view.
- Does not render every sector with full detail — bounded preview only, full grid lives on the
  dedicated route.
- Rest of the dashboard (`id="markets"`, `id="events"`, etc.) is unmodified.

## 10. Dedicated Sector Isolation Behavior

Route: `GET /research/{key:path}/sectors`, registered ahead of the existing catch-all
`/research/{key:path}` (dashboard.py:2480) — see §2 for why ordering matters.

- **A. Narrative orientation**: selected narrative, Explanation Layer summary, lifecycle/direction,
  Market Expression context (reused, not duplicated — read the existing
  `market_expression_context`, don't recompute).
- **B. Sector heatmap**: all curated sectors for this narrative, structural role, participation
  state (uniformly `UNAVAILABLE`, honestly explained), calm styling for unavailable tiles — no
  misleading empty-color grid.
- **C. Sector explanation**: why the sector is connected (curated rationale), what current market
  behavior shows (this sprint: "not yet available," explicitly, not omitted), what is missing or
  uncertain.
- **D. Next action**: link back to the narrative investigation, note (without building) that asset
  exploration is a future entry point — matching the existing `future-entry` placeholder-row
  convention in `narrative_investigation.html` rather than inventing a new pattern.

No asset exploration, no price charts, no live instrument detail — those are explicit non-goals
(§16 of the original spec, unchanged).

## 11. Interaction / X-Ray Behavior

Required, matching the constellation's existing interaction model: click/tap tile reveals detail,
full keyboard navigation, visible focus states, touch-friendly targets, details available without
hover (the plain-text fallback block, not just a hover card), stable deterministic ordering
(sort by role weight, then sector key), no continuous animation.

Optional X-Ray reveals (mirroring the constellation's `<details data-constellation-xray>` pattern):
supporting instruments (none exist yet — state that honestly rather than omitting the field),
structural rationale (the curated `rationale` string), market-expression details (reused from the
existing narrative-level Market Expression context, clearly labeled as narrative-level, not
sector-level, to avoid the exact conflation §Ratified Decision prohibits), coverage limitations
(the §12 data-honesty copy).

No dashboard-wide filtering this sprint — out of scope per the original spec.

## 12. Data-Honesty Behavior

Required copy, always present, not just in an edge case:

- *"Sector relationships are curated from MNE's narrative model."*
- *"Current participation reflects available persisted market data."* — this sprint, followed
  immediately by: *"Sector-level market data is not yet available."*
- *"Unavailable sectors are not assumed to be detached."* — critical distinction: `UNAVAILABLE`
  (no data) and `DETACHED` (curated, no structural connection) are different concepts and must
  never share a visual treatment that implies they're the same thing, even though both currently
  render with the same slate accent color for participation (the border/role treatment stays
  distinct).

## 13. Mobile / Accessibility Behavior

- No horizontal overflow at 390px — heatmap becomes a stacked tile list, not a horizontally
  scrolling grid.
- No essential information behind hover only — the plain-text fallback carries role, participation,
  and explanation for every tile regardless of JS/hover state.
- Semantic links/buttons (not `<div onclick>`), screen-reader labels naming role + participation +
  sector, visible focus rings matching the existing design system's focus treatment,
  `prefers-reduced-motion: reduce` support (no tile-hover animation beyond what reduced-motion
  already disables elsewhere per the design-system handoff), full JS-disabled server-rendered
  output (structural role, rationale, and the honest unavailable-participation copy all present
  without JS, matching the constellation's existing JS-disabled fallback pattern).

## 14. Existing-Feature Preservation

Do not remove or break: Narrative Constellation, Cross-Group Relationships, Market Expression,
Explanation Layer, Narrative History, Historical Connections, Evidence Reader, AI Analyst,
personalization/alerts, entitlement/account behavior, admin separation. This sprint is additive —
new module, new route, new dashboard section — and touches no existing module's internals except
`dashboard.py` (route registration + view-model wiring) and `presentation_language.py` (additive
copy block).

## 15. Safety and Language Verification

- No prediction/trading language anywhere in `SECTOR_ISOLATION_COPY`: no "overweight,"
  "underweight," "buy," "sell," "sector call," "alpha signal," "expected return," "bullish setup,"
  "bearish setup" — grep-tested (§19).
- No fabricated participation states — `classify_sector_participation` is unconditionally
  `UNAVAILABLE` this sprint; a test must assert this directly, not just assert the schema shape.
- No scoring/taxonomy mutation — `mne/sector_isolation.py` is read-only, mirroring the
  "no `requests`/`compute_group_scores` calls" guarantee already tested for
  `narrative_constellation.py` and `narrative_relationships.py`.
- No new market-data fetching — `mne/sector_isolation.py` must not import `yfinance`,
  `mne/market_context.py`, or call any live-fetch function.

## 16. Verification Performed

Read-only research pass plus one user-facing scoping decision, no code written or executed:
`mne/market_expression.py` (full module — config loading, instrument classification, state
thresholds), `config/market_expression_map.json` (actual narrative→instrument coverage, confirmed
gap on `Geopolitical Risk`), `mne/narrative_market_map.py` (confirmed legacy/unused/price-free),
`main.py` (`NASDAQ_TICKERS`, `BREADTH_TICKERS` fetch-and-filter path, lines 111–116, 492, 772),
`mne/breadth.py`, `mne/storage.py` (confirmed snapshot aggregation drops market/expression fields
entirely), `mne/historical_backfill.py` (confirmed no price dimension), repo-wide grep for
"sector," "GICS," "ticker_symbol," "ETF" (confirmed no existing sector taxonomy), `mne/narrative_signals.py`
(`NARRATIVE_GROUPS`, unchanged), `mne/narrative_relationships.py` and
`config/narrative_relationships.json` (confirmed implemented since the prior handoff, `7190972`,
used as the direct structural pattern to mirror), `templates/dashboard.html` (full section-id
inventory and order, lines 75–367), `mne/research_workspace.py` (`narrative_key` format,
colon-joined), `dashboard.py` (route registration order for `/research/{key:path}/history` vs. the
catch-all, lines 2474/2480), `mne/presentation_language.py` (copy-block/accessor pattern,
confirmed unchanged). Codex must run the commands in §Verification Commands after implementing —
nothing here substitutes for that.

## 17. Known Remaining Gaps

- **No real sector-level market data.** This is the sprint's central, deliberate boundary, not an
  oversight — see §Ratified Decision and §3.
- `Geopolitical Risk` has no sector mapping, no market-expression mapping, and no relationship
  mapping — a consistent, pre-existing gap across all three curated layers, not something this
  sprint introduces or is obligated to fix.
- The legacy `mne/narrative_market_map.py` remains unused dead weight relative to the live
  dashboard — not this sprint's job to remove, but worth a future cleanup ticket.
- No Playwright/browser suite exists for visual verification of the heatmap's tile styling —
  manual visual pass required (§20).
- `docs/narrative_sector_model.md` does not exist yet — created fresh this sprint.

## 18. Recommended Next Sprint

**Sector Market Data Plumbing and Participation States** (named per the Ratified Decision), in
priority order: (1) expand the live fetch (`main.py`/`mne/market_context.py`) to include real
sector ETF tickers (`XLK`, `XLE`, `XLF`, `XLU`, `XLI`, `XLP`, `XLY`, `XLC`, `XLV`, `XLB`, `XLRE`),
(2) persist that data forward through `mne/storage.py`'s daily-snapshot aggregation, which
currently drops market data entirely, (3) define explicit freshness/staleness rules for sector
data (the existing `market_expression.py` `stale` field is a starting reference), (4) implement
`classify_sector_participation` for real, deriving from actual sector-level price/breadth data —
never from the 4 non-sector tickers already fetched, (5) once genuine participation data exists,
revisit the sector-breadth copy in §8 to reintroduce "broad/concentrated participation" language
now honestly backed. Also candidates for a later sprint, unchanged from the original spec's
non-goals: asset exploration, price charts, historical sector backtesting, predictive sector
rotation.

## 19. Whether Cross-Sector Heatmap and Sector Isolation Can Be Marked Implemented

**Not implemented — ratified and ready to hand to Codex.** Mark "Cross-Sector Heatmap and Sector
Isolation" implemented only after Codex completes the scoped structural-only work and every
command below passes. Do not mark it implemented as a proxy for "participation states are live" —
that is explicitly the deferred follow-up sprint (§18), a separate implementation milestone.

---

## Tests Required (mapped to original spec §19, adjusted for the ratified structural-only scope)

1. Valid sector map loads deterministically.
2. Unknown narrative fails validation.
3. Unknown sector fails validation.
4. Duplicate sector mapping fails validation.
5. Invalid role fails validation.
6. Hidden (`display_enabled: false`) sector excluded from public display.
7. Structural role remains fully separate from participation in the read API and the template.
8. `classify_sector_participation` returns `UNAVAILABLE` unconditionally — dedicated test, not
   incidental.
9. Sector breadth reconciles from structural role counts, never from participation.
10. Dashboard preview renders, bounded sector count, links to the dedicated route.
11. Dedicated Sector Isolation route renders, registered ahead of the `/research/{key:path}`
    catch-all (route-order regression test).
12. User-safe display names render; raw enum values (`PRIMARY`, `UNAVAILABLE`, etc.) never appear
    as primary copy.
13. X-Ray detail reveals structural rationale and the honest "not yet available" participation
    copy together, not the rationale alone.
14. No unsupported instruments are invented — `evidence_count` and any instrument-reference field
    default to zero/empty, never fabricated.
15. JS-disabled view remains fully useful (role, rationale, honest participation copy all present).
16. Keyboard interaction works (tile focus, activation, visible focus ring).
17. 390px view has no horizontal overflow; stacked tile list confirmed.
18. Empty state (narrative has no sector map) renders calmly, no misleading empty grid.
19. Partial-coverage state (some sectors mapped, most not) renders honestly.
20. Existing Narrative Constellation, Cross-Group Relationships, and Market Expression tests remain
    green, unmodified in behavior.
21. Existing Research Workspace and dashboard tests remain green.
22. No source fetching occurs from `mne/sector_isolation.py` (import-boundary test).
23. No scoring or taxonomy mutation occurs.
24. No prediction or trading language appears (grep-based copy test).
25. Same input produces byte-identical context (`json.loads(json.dumps(..., sort_keys=True))`
    round-trip, matching the constellation's existing byte-stability guarantee).
26. Full existing test suite remains green.

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_sector_isolation -v`
- `python -m unittest tests.test_narrative_constellation -v`
- `python -m unittest tests.test_narrative_relationships -v`
- `python -m unittest tests.test_market_expression -v`
- Focused Research Workspace and dashboard tests
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `node --check static/sector_isolation.js` (only if that file is added)
- `git diff --check`

Manual verification:
- Dominant narrative = AI / Tech Growth, Energy / Commodities, Macro Pressure, and a narrative with
  no sector mapping (including `Geopolitical Risk`, which has none today).
- Confirm every tile's participation accent renders as the neutral/unavailable state, and the
  honest copy explaining why is present, not omitted.
- Confirm structural role and participation are visually and textually distinct — never collapsed
  into one ambiguous signal.
- 1280px, 1024px, 390px, keyboard-only, reduced motion, JavaScript disabled.
- Logged-out user, authenticated Free user, Pro/internal-access user.
- Confirm the interface reads as visual and approachable, not a red/green terminal grid — every
  tile this sprint should look calm and structural, not like a populated live board.

Implement to a verified local state and stop — do not stage, commit, or push.
