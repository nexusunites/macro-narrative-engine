# Asset Coverage Expansion and Instrument-Map Consolidation — Implementation Handoff

## Purpose

Asset Exploration shipped (`3e9507c`) exactly as specified: a bounded 19-instrument registry, a
sparse curated narrative-asset map, and a strict structural/live-data boundary. But it now sits
alongside two older, overlapping systems — `config/market_expression_map.json` and
`mne/narrative_market_map.py` — that were never reconciled with it. This sprint (1) expands the
live asset universe conservatively with 6 new, individually-justified tickers, prioritizing the
Energy gap, and (2) defines a clean, documented ownership model across all instrument-related
systems so a fourth overlapping map never gets created by accident.

**Status: candidate ticker set ratified by Daniel, 2026-08-04 (below). Ready to hand to Codex.**

Do not implement code from this document directly. This is the Codex-ready brief.

---

## Ratified Decision (Daniel, 2026-08-04): approved new asset set

**MSFT, XOM, CVX, SLB, TLT, HYG** — 6 additions, within the spec's 4-10 preferred range. Full
per-candidate rationale in §5. Explicitly rejected this sprint (documented, not permanently
closed): AVGO, ANET, VRT, DELL, COP, GLD, USO, IEF, UUP.

---

## Critical Finding: a latent lookup bug that this sprint's own Energy recommendation could trigger if not handled correctly

`mne/asset_participation.py:55`'s `classify_assets_for_run` looks up
`snapshot.get(mapping.ticker)` — by **ticker symbol** (e.g. `"XLK"`). But sector-ETF entries in
`run["market_snapshot"]` are keyed by **sector slug** (e.g. `"technology"`), confirmed both in
`mne/sector_market_context.py:159` and in the actual fetch-dict construction
(`main.py:493-495`, `build_sector_ticker_map()` returns `{sector_key: ticker}`). This is currently
dormant — `config/narrative_asset_map.json` has never mapped a sector-ETF ticker directly to a
narrative, so the mismatch has never fired. **It would fire immediately if this sprint "solved"
Energy's sparse coverage the obvious-looking way — adding `XLE` as a new `narrative_asset_map.json`
entry.** Don't do that. `XLE` already reaches Asset Exploration correctly via the existing
sector-row-reuse mechanism (`mne/asset_exploration.py`, reusing `mne.sector_isolation`'s already-
computed participation for that sector's ETF) — this sprint's new Energy tickers are `XOM`, `CVX`,
`SLB` only, all genuinely new company-level tickers with their own ticker-keyed
`market_snapshot` entries, which do not hit this bug.

**This sprint also fixes the underlying bug directly**, since leaving a known, provable defect
undocumented-and-unfixed while writing a design doc about instrument-map correctness would be
dishonest. `classify_assets_for_run` gains a fallback: if a direct ticker-key lookup misses and the
asset's registry entry has a `sector_key`, retry the lookup under that sector slug before falling
through to `UNAVAILABLE`. Cheap, low-risk, and closes the trap for whoever touches this mapping
next — see §7, §13.

---

## 1. Objective Summary

Expand the live fetch from 19 to 25 tickers (6 new: `MSFT`, `XOM`, `CVX`, `SLB`, `TLT`, `HYG`),
reusing the exact existing fetch path with no new fetch system. Define and document canonical
ownership across four instrument-related concerns (real identity, structural narrative relevance,
market-expression interpretation, synthetic concepts) so `config/market_expression_map.json` and
`mne/narrative_market_map.py` stop being parallel, undocumented sources of truth. Deprecate (not
yet delete) `mne/narrative_market_map.py`, backed by new evidence that it's already dead in the UI.
Fix the sector-ETF lookup-key bug found during this audit. No charts, no new provider, no
portfolio/prediction language, no security master.

## 2. Files Changed

**Create:**
- `config/synthetic_market_concepts.json` — typed registry for `RATES`, `CLOUD`, `DATA_CENTER`,
  `CRUDE_OIL`, `COMMODITY_FX`, `GROWTH_CONCERNS` (§9).
- `docs/instrument_mapping_architecture.md` — the canonical ownership doc (§11 of the original
  spec).
- `tests/test_asset_registry.py` — dedicated registry tests, currently folded into
  `tests/test_asset_exploration.py`; split out now that the registry is growing and gaining a new
  `fetched` field (§4) that deserves isolated coverage.
- `tests/test_narrative_market_map.py` — **did not exist before this audit.** New: proves
  `run["market_expression"]` (the legacy key) is never read by any live dashboard/template path —
  the explicit "prove no usage" checkpoint the original spec's migration approach (§8) requires
  before any future deletion.

**Modify:**
- `config/asset_registry.json` — grows from 19 to 25 entries; gains a new `fetched: bool` field on
  every entry, distinguishing "real and currently live" from "real but not in the fetch universe"
  (needed for `SMH`, see §9) — existing 19 entries default `fetched: true`.
- `config/narrative_asset_map.json` — adds `MSFT` (AI / Tech Growth), `XOM`/`CVX`/`SLB` (Energy /
  Commodities), `TLT`/`HYG` (Macro Pressure). Energy / Commodities moves from an empty list to
  3 entries — **not including `XLE`**, per the Critical Finding above.
- `mne/asset_participation.py` — fix the sector-slug fallback lookup (§Critical Finding, §7).
- `mne/market_expression.py` — `load_market_expression_map`'s validation gains one new check:
  every `asset` string must resolve either through `asset_registry.json` (real, any `fetched`
  value) or `config/synthetic_market_concepts.json` (synthetic) — nothing else. Closes the door on
  a future typo'd or forgotten instrument silently passing validation (§9).
- `main.py` — add the 6 new tickers to the existing fetch merge (§12), no new fetch call.
- `mne/narrative_market_map.py` — module docstring updated to state it's deprecated, its call site
  in `main.py:408` annotated as legacy-compatibility-only pending removal (§10). **Not deleted this
  sprint** — see §10 for why.
- `docs/narrative_asset_model.md` (from the Asset Exploration sprint) — cross-link to the new
  `docs/instrument_mapping_architecture.md` rather than duplicating ownership explanation.
- `tests/test_asset_exploration.py`, `tests/test_asset_participation.py`,
  `tests/test_market_expression.py`, `tests/test_market_context.py` — extend for the 6 new tickers
  and the new registry field, per §14.

**Do not touch:** `mne/sector_isolation.py`, `mne/sector_market_context.py`,
`mne/market_calendar.py`, `config/sector_instruments.json`, `config/narrative_sector_map.json`,
route registrations, templates beyond what's strictly needed to surface the 6 new rows (no new
template files), scoring, taxonomy, Historical Replay.

## 3. Existing Instrument-System Audit

Confirmed fresh at `3e9507c` (HEAD). **43 distinct identifiers exist across the four systems
today; only 19 are ever fetched/persisted-capable; of those 19, only 8 are actually present in the
most recent real run file** (`2026-08-03_160440.json`, which predates the sector-fetch commit
`5758a5b` — the capability shipped, but no run has exercised it yet; this is a continuation of the
same finding from the calibration audit, not a new regression).

Condensed matrix (full 43-row detail available in the research transcript; every real, currently-
fetched instrument plus every synthetic concept shown below — omitted rows are `narrative_market_map.py`-
only tickers with zero registry/fetch/persistence presence, listed in full in §10):

| Identifier | Type | Fetched | Registry | Narrative Asset Map | Market Expression Map | narrative_market_map.py |
|---|---|---|---|---|---|---|
| QQQ, NVDA, VIX, DXY | real | yes | yes | yes | yes | yes (offsets/secondary only) |
| SPY, RSP, QQQE, IWM | real | yes | yes | no | no | no |
| XLK/XLC/XLY/XLF/XLI/XLE/XLB/XLU/XLRE/XLP/XLV (11 sector ETFs) | real | yes | yes | no (reused via sector-row) | 4 of 11 referenced (XLI, XLE, XLU, XLP) | 4 of 11 referenced (XLY, XLF, XLU, XLP) |
| SMH | real | **no** | **no** | no | yes (AI/Tech primary) | no |
| RATES, CLOUD, DATA_CENTER, CRUDE_OIL, COMMODITY_FX, GROWTH_CONCERNS | **synthetic** | no | no | no | yes | no |
| MSFT, AVGO, ANET, VRT, DELL, CVX, XOM, SLB, HAL, OXY, TLT, IEF, KRE, GLD, DBC, FCX, SHY | real | no | no | no | no | yes only |

**Key findings**:
- `mne/narrative_market_map.py`'s `NARRATIVE_MARKET_MAP` is computed every run (`main.py:408`),
  persisted into every run JSON (`main.py:534`, `run["market_expression"]`), and printed to console
  (`main.py:611,670`) — but a full grep of every template confirms **zero UI rendering** of this
  legacy dict. The only market-expression content actually shown to users
  (`templates/dashboard.html:89,272-285`) comes from the newer curated system
  (`mne/market_expression.py` + `market_expression_map.json`). This is direct evidence for
  deprecation (§10), though not yet a complete proof of zero consumers repo-wide (§16).
- `SMH` is a real ticker referenced by `market_expression_map.json` but present in neither the
  registry nor the live fetch — it's real, just not live. This needs its own bucket, not a forced
  fit into "real+fetched" or "synthetic" (§9, §4).
- The 6 synthetic concepts (`RATES`, `CLOUD`, `DATA_CENTER`, `CRUDE_OIL`, `COMMODITY_FX`,
  `GROWTH_CONCERNS`) appear only in `market_expression_map.json`, always resolve to `UNAVAILABLE`
  in narrative-level expression classification (no snapshot data ever backs them), and are
  correctly never referenced by Asset Exploration.
- Registry/mapping/fetch counts are internally consistent today (19 = 19 = 19) — this sprint is the
  first to introduce controlled asymmetry (25 registry entries, only 19+6=25 fetched, `SMH` real-
  but-unfetched) and must do so without breaking that consistency invariant elsewhere.

## 4. Canonical Ownership Decision

Five-way split, matching the original spec's A-E exactly, now with concrete file ownership:

| Domain | Owns | File |
|---|---|---|
| **A. Asset Registry** | Real instrument identity: ticker, display name, asset type, sector, broad-market role, **`fetched` (new)**, display eligibility | `config/asset_registry.json`, loaded by `mne/asset_exploration.py` |
| **B. Narrative Asset Map** | Curated structural narrative→real-instrument relevance: role, expected direction, rationale, display state | `config/narrative_asset_map.json` |
| **C. Market Expression Map** | How narrative-level expression is evaluated; may reference real instruments (via A) or synthetic concepts (via D); never an identity registry itself | `config/market_expression_map.json` |
| **D. Synthetic Concept Registry** | Non-ticker concepts (`RATES`, `CLOUD`, etc.) — typed, documented, explicitly never tradable | `config/synthetic_market_concepts.json` (new) |
| **E. Legacy `narrative_market_map.py`** | **Deprecated, not deleted.** Remains as a documented compatibility shim pending a proven-zero-consumers checkpoint | `mne/narrative_market_map.py` |

The registry (A) is now the single place "is this a real, currently-live instrument" is answered —
Market Expression (C) and Narrative Asset Map (B) both defer to it rather than each maintaining
their own notion of instrument reality.

## 5. Approved New Asset Set

| Ticker | Narrative | Role | Expected Direction | Sector | Product Value | Overlap Check | Fetch/Persistence Cost | Decision |
|---|---|---|---|---|---|---|---|---|
| `MSFT` | AI / Tech Growth | `SECONDARY` | `UP` | `technology` | Distinct from `NVDA` — cloud/software/OpenAI-partnership angle on the same narrative, not a second chip-maker proxy | Low overlap with `NVDA` (different value-chain position); some overlap with `QQQ` (both broad-tech-adjacent) but `MSFT` is company-specific | 1 sequential fetch call, real ticker, no reliability concern | **Approved** |
| `XOM` | Energy / Commodities | `PRIMARY` | `UP` | `energy` | Large integrated producer — clean, liquid, widely-recognized Energy narrative proxy | Some overlap with `CVX` (both integrated majors) — accepted deliberately for breadth/robustness, not redundancy (single-company noise risk if only one major is tracked) | 1 sequential fetch call | **Approved** |
| `CVX` | Energy / Commodities | `PRIMARY` | `UP` | `energy` | Second integrated major, same rationale as `XOM` | See `XOM` | 1 sequential fetch call | **Approved** |
| `SLB` | Energy / Commodities | `SECONDARY` | `UP` | `energy` | Oilfield-services/investment-cycle proxy — genuinely distinct value-chain position from `XOM`/`CVX` (capex-cycle signal, not commodity-price signal) | No meaningful overlap with `XOM`/`CVX`/`XLE` | 1 sequential fetch call | **Approved** |
| `TLT` | Macro Pressure | `PRIMARY` | `DOWN` | `null` (`broad_market_role: RATES_DURATION`) | Direct, clean, widely-recognized long-duration rates proxy — distinct from `VIX`(volatility)/`DXY`(currency) | No overlap with existing Macro Pressure instruments | 1 sequential fetch call | **Approved** |
| `HYG` | Macro Pressure | `SECONDARY` | `DOWN` | `null` (`broad_market_role: CREDIT_SPREAD`) | Credit-risk/spread proxy — distinct dimension from `TLT`'s pure-duration signal | Low overlap with `TLT` (duration vs. credit spread are genuinely different risk factors, correlated but not redundant) | 1 sequential fetch call | **Approved** |

**Rejected candidates** (documented, not permanently closed — revisit if a later sprint's product
rationale sharpens):

| Ticker | Narrative | Reason for rejection |
|---|---|---|
| `AVGO` | AI / Tech Growth | Same semiconductor niche as `NVDA` — insufficiently distinct signal for a first bounded pass |
| `ANET` | AI / Tech Growth | Networking/data-center equipment — narrower, less broadly recognized, overlaps conceptually with the already-unfetched `DATA_CENTER` synthetic concept |
| `VRT` | AI / Tech Growth | Power/cooling infrastructure — same narrowness concern as `ANET` |
| `DELL` | AI / Tech Growth | Diversified hardware business (including consumer PCs) — weaker, less clean AI-narrative signal than `MSFT`/`NVDA` |
| `COP` | Energy / Commodities | Third large-cap producer — redundant with `XOM`+`CVX`, would push toward the "many correlated producers" pattern the spec explicitly warns against |
| `GLD` | Energy / Commodities | Gold's fit under this narrative group is real but imprecise (inflation/macro-hedge signal more than energy-sector expression) — the spec's own "only if the narrative role is precise" bar isn't clearly met yet |
| `USO` | Energy / Commodities | Futures-based ETF with known roll/contango drift — introduces data-quality complexity beyond this sprint's simple daily-close-pct-change model, and duplicates `XLE`'s directional signal without a company-level ETF's cleaner read |
| `IEF` | Macro Pressure | Highly correlated with `TLT` (both long-duration treasury proxies) — redundant, `TLT` alone covers the duration dimension |
| `UUP` | Macro Pressure | Redundant with existing `DXY` coverage — the spec's own "only if DXY does not already satisfy the use case" bar isn't met |

## 6. Energy Coverage Detail

Final Energy / Commodities model: `XLE` (sector expression, unchanged, reused via sector-row —
**not** a new `narrative_asset_map.json` entry, per the Critical Finding), `XOM` + `CVX` (two
integrated majors, distinct company-level signals with shared macro exposure — deliberate breadth,
not redundancy), `SLB` (oilfield-services, a genuinely different value-chain position: capex-cycle
proxy rather than commodity-price proxy). Four total instruments visible on the Energy Asset
Exploration page (one sector ETF + three company-level), up from zero company-level assets before
this sprint. No ranking, no "best," no performance language — role and rationale only (§14).

## 7. Asset Registry Behavior

Schema gains one field, `fetched: bool`, alongside the existing `sector_key`/`broad_market_role`
mutual-exclusivity rule:

```json
"MSFT": {
  "display_name": "Microsoft Corporation",
  "asset_type": "EQUITY",
  "sector_key": "technology",
  "broad_market_role": null,
  "fetched": true,
  "display_enabled": true
}
```

`fetched: false` is reserved for real-but-not-live instruments (`SMH` is added to the registry this
sprint with `fetched: false, display_enabled: false` — registered as "a real, known instrument
Market Expression may reference," never surfaced by Asset Exploration). Validation additions (fail
closed, no silent repair): `fetched: false` entries must also have `display_enabled: false` (an
unfetched asset can never be marked currently available — directly satisfies the original spec's
§7 requirement); duplicate ticker; invalid `sector_key`; malformed `version`; missing
`display_name`; invalid `asset_type`; a ticker appearing in both `asset_registry.json` and
`config/synthetic_market_concepts.json` (identity collision, fails closed).

## 8. Narrative Asset Map Behavior

Unchanged shape and validation rules from the Asset Exploration sprint — this sprint only adds
rows. Every new entry requires `role`, `expected_expression`, `rationale`, `display_enabled`,
exactly as before. Fails closed on unknown ticker (must exist in `asset_registry.json` with
`fetched: true` — a `fetched: false` asset like `SMH` cannot be mapped here, since Asset Exploration
would then need to render a permanently-unavailable row with no path to ever becoming available,
which is the same "don't invent unfulfillable relevance" principle already applied to
`Geopolitical Risk`'s absence elsewhere).

## 9. Market Expression Compatibility

`config/synthetic_market_concepts.json` (new):

```json
{
  "version": "1.0.0",
  "concepts": {
    "RATES": {
      "description": "Interest-rate policy pressure, not backed by a single tradable instrument.",
      "tradable": false
    },
    "CLOUD": {
      "description": "Cloud infrastructure spend, conceptual aggregate.",
      "tradable": false
    }
  }
}
```

(All 6 current synthetic concepts get an entry: `RATES`, `CLOUD`, `DATA_CENTER`, `CRUDE_OIL`,
`COMMODITY_FX`, `GROWTH_CONCERNS`.) `tradable: false` is invariant — the field exists for schema
clarity, not because any value other than `false` would ever be valid here (a synthetic concept
that becomes tradable graduates to the asset registry instead, it doesn't change this field).

`load_market_expression_map`'s validation gains: every `asset` string in every narrative's
primary/secondary/offsets list must resolve to **either** `asset_registry.json` (any `fetched`
value — `SMH` is valid here specifically because Market Expression, unlike Asset Exploration,
tolerates `UNAVAILABLE` gracefully) **or** `config/synthetic_market_concepts.json`. Nothing else
passes. This is a real tightening — today a typo'd instrument string would silently validate; after
this change it fails closed at config-load time.

Market Expression's own classification logic, thresholds, and narrative-level output are otherwise
**unchanged** — this sprint only tightens what identifiers are considered valid input, it does not
touch how they're evaluated.

## 10. Legacy Map Migration / Deprecation Behavior

**Not deleted this sprint.** Following the original spec's own staged approach exactly:
1. Canonical registry/config already exists (Asset Exploration sprint) — done.
2. Compatibility: `mne/narrative_market_map.py` remains callable, unchanged behavior, but its
   module docstring now states it's deprecated and names the newer system as canonical.
3. Market Expression and Asset Exploration already read from canonical config (they never read
   `narrative_market_map.py` — confirmed, it was never actually a shared dependency, just a
   parallel, unconsumed computation).
4. `main.py:408`'s call site gets an inline comment marking it legacy-compatibility-only, not
   silently left unexplained.
5. **Removal is explicitly deferred**, gated behind `tests/test_narrative_market_map.py` (new)
   proving zero live consumers — this sprint adds that proof-test but does not yet delete the
   module, because the audit confirmed zero *UI* consumers but did not exhaustively trace every
   script/export/report path in the repo (§16). Deleting on UI-only evidence would violate the
   spec's own "trace imports and runtime usage first" instruction.

## 11. Fetch and Persistence Behavior

Six tickers added to the existing single fetch call (`main.py:493-497`), same dict-merge pattern
already used three times (`NASDAQ_TICKERS` + `BREADTH_TICKERS` + `sector_tickers`, now +
`expansion_tickers`). Same `get_market_snapshot` function, same per-instrument `try/except`
failure isolation (already proven — confirmed via direct read, `mne/market_context.py`'s fetch loop
is unchanged and isolates failures per ticker with no batch-wide failure mode), same `observed_at`
stamping. **No concurrency added** — the fetch loop is still sequential
(`mne/market_context.py`, confirmed no retry/timeout/threading exists today). Six more sequential
blocking `yfinance` calls is a modest, bounded addition (19 → 25, a 32% increase in fetch-loop
length) — the spec's own guidance ("if runtime becomes materially worse, recommend a smaller set
rather than adding concurrency... unless existing architecture already supports it safely") means
Codex should **measure actual incremental duration during the smoke test** (§15) rather than assume
it's fine; if the 6-ticker addition measurably degrades run time beyond an acceptable bound (no
hard number specified here — use judgment relative to the existing 19-ticker baseline, and flag if
it's more than roughly proportional to the ticker-count increase), reduce to the Energy-only
3-ticker subset rather than introducing concurrency in this sprint.

Old snapshots (pre-expansion) have no entries for the 6 new tickers — same "missing key →
`UNAVAILABLE`" handling already established, no migration needed.

## 12. Asset Exploration Impact

New rows appear automatically once `config/narrative_asset_map.json` is updated — no template
restructuring, `templates/_partials/asset_grid.html` already iterates the context's asset list
generically. Structural role / participation separation, ticker-secondary display, and the sparse/
unavailable-state handling are all unchanged mechanisms, just exercised with more real rows now.
Energy / Commodities specifically goes from "empty, honestly explained" to "4 real instruments,
honestly explained" — still calm, still not crowded (§Core Principle: this is not a stock
screener).

## 13. Data-Honesty Behavior

Unchanged copy requirements from the Asset Exploration sprint apply to all new rows without
exception. One new honesty case: `SMH` never appears in Asset Exploration at all (it's
`fetched: false`) — it is not shown as an "unavailable" row either, since it was never curated into
`narrative_asset_map.json` to begin with (only Market Expression references it). Don't conflate
"never mapped" with "mapped but unavailable" — they render differently and mean different things.

## 14. Safety and Boundary Verification

- `mne/asset_exploration.py` still imports neither `asset_participation`, `market_context`,
  `sector_market_context`, nor `yfinance` — unchanged, re-verified by the existing test, not
  weakened by this sprint's registry growth.
- The sector-slug fallback fix (§Critical Finding) lives in `asset_participation.py`, not
  `asset_exploration.py` — stays on the correct side of the boundary.
- No trade/prediction/ranking language in any new copy — grep-tested alongside existing prohibited
  terms.
- No new market-data provider — `yfinance` only, same fetch function.
- Registry/fetch/map counts must remain provably consistent — a dedicated drift test (§14 tests)
  fails loudly if `asset_registry.json`'s `fetched: true` count ever diverges from the actual live
  fetch ticker count.

## 15. Verification Performed

Read-only research pass plus one ratified ticker-selection decision, no code written: confirmed
`3e9507c` shipped Asset Exploration exactly as the prior handoff specified (19-entry registry,
sparse map, intact structural/live-data boundary); read all four instrument-related config/Python
files in full, building the complete 43-identifier matrix; discovered and confirmed the sector-ETF
ticker-vs-slug lookup mismatch in `mne/asset_participation.py:55` by tracing the actual
`market_snapshot` key construction in `main.py:493-495` and `mne/sector_market_context.py:73-75,159`;
confirmed via full-template grep that `mne/narrative_market_map.py`'s output is computed and
persisted but never rendered in any UI path; confirmed the real persisted-data state (most recent
run predates the sector-fetch commit, still only 8 tickers on disk, no `observed_at` anywhere yet)
directly against `$MNE_DATA_DIR/results/`; confirmed `mne/market_context.py`'s fetch loop remains
sequential with no retry/timeout/concurrency; read all relevant test files
(`tests/test_asset_exploration.py`, `test_asset_participation.py`, `test_market_expression.py`,
`test_market_context.py`) confirming existing boundary/fixture assertions this sprint must not
break. Codex must run the commands in §Verification Commands after implementing — nothing here
substitutes for that.

## 16. Known Remaining Gaps

- **`narrative_market_map.py`'s zero-consumer proof is UI-complete but not repo-exhaustive.** This
  sprint adds the proof-test for UI non-usage; a future sprint should grep every script, export
  path, and report generator repo-wide before actual deletion.
- **Real persisted asset/sector data is still zero** as of this audit — the 6 new tickers inherit
  the same "code-complete, not yet exercised in a real run" state already true for sectors. Nothing
  in this sprint changes that; it's an orthogonal fact about run cadence, not about this sprint's
  correctness.
- **The sector-ETF ticker/slug lookup mismatch is fixed for the case this sprint touches**
  (Energy's ETF continuing to route through sector-row reuse), but the underlying
  `asset_participation.py` fallback fix should be tested against a hypothetical future
  narrative-asset-map entry that *does* target a sector ETF directly, not just against this
  sprint's own additions, to be sure the fix generalizes.
- **`GLD`/`USO` rejections are judgment calls under real ambiguity**, not hard architectural facts
  — worth revisiting if a future sprint sharpens what "Energy / Commodities" is supposed to mean
  for broad commodities beyond energy specifically.
- Three overlapping-but-now-documented systems (`market_expression_map.json`, `narrative_asset_map.json`,
  `narrative_market_map.py`) still exist simultaneously — this sprint clarifies ownership and adds
  cross-validation, it does not merge them into one file, per the original spec's own instruction
  not to force Market Expression's synthetic-concept needs into the real-asset registry.

## 17. Recommended Next Sprint

In priority order: (1) complete the repo-wide zero-consumer trace for `narrative_market_map.py` and
delete it once proven, closing out the deprecation this sprint starts; (2) once real persisted
asset/sector data accumulates (per the standing calibration trigger from the prior sprint), revisit
whether `MSFT`/`TLT`/`HYG` are producing meaningfully differentiated signal from their neighbors, or
whether the rejected candidates deserve reconsideration with real evidence instead of judgment
calls; (3) resolve the `GLD`/`Energy vs. broad commodities` ambiguity with an explicit product
decision rather than leaving it a documented rejection; (4) if Energy / Commodities usage data
shows demand, evaluate a fourth Energy instrument (`COP` is the natural next candidate) against
real usage rather than a priori.

## 18. Whether Asset Coverage Expansion and Instrument-Map Consolidation Can Be Marked Implemented

**Not implemented — ready to hand to Codex.** The ticker set is fully ratified. Mark this
implemented only after Codex completes the scoped work, fixes the sector-slug lookup bug, and every
command below passes — including the new registry/fetch drift test and the
`narrative_market_map.py` non-usage proof test.

---

## Tests Required (mapped to original spec §14, adjusted for confirmed current architecture)

1. Canonical asset registry loads deterministically with the new 25-entry set and `fetched` field.
2. Real assets and synthetic concepts remain fully distinct (no ticker appears in both files).
3. A synthetic concept can never enter Asset Exploration (regression + new: `SMH` also never enters
   Asset Exploration despite being a real, registered ticker, since `fetched: false`).
4. All `narrative_asset_map.json` entries resolve to `fetched: true` registry assets — a
   `fetched: false` asset in the map fails validation.
5. All 25 `fetched: true` registry assets are genuinely present in the live fetch ticker dict (the
   registry/fetch drift test, §14).
6. All `display_enabled: true` registry assets have complete, safe metadata.
7. Duplicate ticker fails validation (regression).
8. Duplicate narrative-asset mapping fails validation (regression).
9. `mne/narrative_market_map.py`'s legacy consumers remain functionally unchanged (it still
   computes and persists exactly as before — this sprint doesn't alter its behavior, only its
   documented status).
10. **New**: `tests/test_narrative_market_map.py` proves `run["market_expression"]` is never read
    by any template render path (the deprecation-evidence test).
11. Market Expression still validates and classifies synthetic concepts correctly (regression, plus
    new: an unrecognized instrument string now fails config load, where it previously passed
    silently).
12. Asset Exploration renders only real, `fetched: true` assets (regression, extended to the new
    6).
13. `XOM`, `CVX`, `SLB` render correctly on the Energy / Commodities Asset Exploration page.
14. `MSFT` renders correctly on the AI / Tech Growth page.
15. `TLT`, `HYG` render correctly on the Macro Pressure page.
16. Participation for all 6 new tickers uses persisted current data only (regression of the
    existing rule, exercised with new fixtures).
17. One new-ticker fetch failure does not fail the run (regression, extended to the expanded set).
18. The existing 19-instrument universe remains intact and unchanged in behavior.
19. The approved 6-ticker addition produces exactly the specified new canonical set — no more, no
    fewer (a direct assertion against the ratified list in §5, not just "some additions exist").
20. Old snapshots (pre-expansion) render `UNAVAILABLE` for all 6 new tickers, calmly.
21. No market-data fetch occurs during page rendering (regression).
22. Structural relevance is never inferred from price movement for any of the 6 new tickers
    (regression of the existing principle).
23. No new asset appears anywhere without a curated `rationale` entry.
24. Fetch ordering remains deterministic with the expanded ticker dict.
25. **The registry/fetch drift test fails loudly** if `fetched: true` count and the actual live
    fetch dict ever diverge (§14) — this is the single most important new regression guard this
    sprint adds, since it's exactly the kind of silent drift the original three-system problem grew
    from.
26. Synthetic labels (`RATES`, etc.) never render as clickable tickers anywhere (regression).
27. No trade or prediction language appears in any new copy.
28. Existing Sector Isolation suite remains green, unmodified.
29. Existing Market Expression suite remains green apart from the one new validation-tightening
    test.
30. Existing Asset Exploration suite remains green, extended (not replaced) for the new tickers.
31. **New**: the sector-ETF ticker/slug lookup fallback fix is directly tested — a fixture record
    keyed by sector slug is correctly found even when the mapping's `ticker` field doesn't match
    the snapshot key directly.
32. Full suite passes apart from any documented pre-existing failures unrelated to this sprint.

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_asset_registry -v`
- `python -m unittest tests.test_asset_exploration -v`
- `python -m unittest tests.test_asset_participation -v`
- `python -m unittest tests.test_market_expression -v`
- `python -m unittest tests.test_market_context -v`
- `python -m unittest tests.test_narrative_market_map -v`
- `python -m unittest tests.test_sector_isolation -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`
- One bounded live fetch smoke test for **only the 6 new tickers** (`MSFT`, `XOM`, `CVX`, `SLB`,
  `TLT`, `HYG`) — measure and report: success/failure per ticker, incremental fetch duration versus
  the existing 19-ticker baseline, confirmation that a deliberately-broken ticker doesn't fail the
  batch, and that `observed_at` is populated consistently across old and new tickers alike. Do not
  repeat this call or fold it into a loop.

Manual verification: AI / Tech Growth, Energy / Commodities (confirm meaningfully improved but not
crowded), Macro Pressure Asset Exploration pages; an old snapshot rendering the 6 new tickers as
calmly `UNAVAILABLE`; a simulated partial-fetch-failure state; 1280px, 1024px, 390px; JavaScript
disabled. Confirm: Energy coverage reads as genuinely useful now, no page feels like a stock
screener, every new asset's role is understandable at a glance, synthetic concepts never appear as
if they were clickable assets, and no duplicate mapping truth remains unexplained anywhere in
`docs/instrument_mapping_architecture.md`.

Implement to a verified local state and stop — do not stage, commit, or push.
