# Sector Market Data Plumbing and Participation States — Implementation Handoff

## Purpose

Sector Isolation shipped structurally (`cf8ad53`, "Add structural sector isolation"): a curated
narrative-to-sector map with real connection roles, and `participation_state` deliberately
hardcoded to `UNAVAILABLE` because no sector-level market data existed
(`mne/sector_isolation.py:104-106`, `docs/narrative_sector_model.md:9` names this exact follow-up
sprint as deferred work). This sprint adds genuine sector ETF coverage to the existing live-run
market fetch, persists it through the normal run pipeline (not a new persistence system), defines
freshness/staleness rules, and computes real participation states — while keeping the structural
model (built last sprint) architecturally untouched and conceptually separate.

**Status: brief only, not yet ratified.** One architectural resolution below is load-bearing
(§Grounding Decision) and should be treated as settled, not optional. Two first-pass modeling
choices (§7 direction schema, §9 breadth thresholds) are flagged as tunable and documented rather
than asked as open questions, per the prior sprint's own "keep the first model simple" instruction.

Do not implement code from this document directly. This is the Codex-ready brief.

---

## Grounding Decision: sector_isolation.py must never import the new module

`tests/test_sector_isolation.py:94-97` asserts the literal substring `"market_context"` is absent
from `mne/sector_isolation.py`'s source — a boundary test proving the structural model doesn't
secretly depend on market data. **The spec's own suggested module name, `sector_market_context.py`,
contains that exact substring** (`"sector_market_context"` ⊃ `"market_context"`). If
`sector_isolation.py` ever imports it — even indirectly — that guard breaks, and worse, quietly
reintroduces the coupling the test exists to prevent.

Resolution: keep the layering strict. `mne/sector_market_context.py` (fetch-config + real
classification) reads `run["market_snapshot"]` and returns a plain dict of
`{sector_key: {participation_state, participation_label, data_freshness, ...}}`.
**`dashboard.py` is the only caller of `sector_market_context`.** It computes that dict and passes
it into `build_sector_isolation_context(...)` as a new parameter. `sector_isolation.py` itself
never imports `sector_market_context`, `market_context`, or `yfinance` — it merges an
already-computed dict into its row structure, same as it merges curated structural data today. The
existing test guard needs exactly one line changed (the hardcoded-`UNAVAILABLE` assertion becomes
"passes through whatever the caller provides"), not removed.

---

## 1. Objective Summary

Add a curated `config/sector_instruments.json` sector→ETF registry, extend the existing
`main.py`/`mne/market_context.py` live fetch to include those ETFs (same fetch path, same failure
isolation already in place), stamp every instrument record with an `observed_at` timestamp (new —
none exists today), and add `mne/sector_market_context.py` to classify real participation states
from that data using a curated, per-narrative `expected_expression` field (new, additive to
`config/narrative_sector_map.json`). Wire the result into the existing Sector Isolation route and
dashboard preview without touching their layout or the structural model's architecture.

## 2. Files Changed

**Create:**
- `config/sector_instruments.json` — curated sector→ETF registry (§4). No naming conflict exists
  today; confirmed via repo-wide grep that no canonical sector-to-ticker registry exists anywhere
  (the ETF strings in `config/market_expression_map.json` are ad hoc, embedded in narrative
  instrument lists, not a sector registry).
- `mne/sector_market_context.py` — loader/validator for the new config, ticker-map builder for the
  fetch step, and the real `classify_sector_participation` implementation + breadth calculation
  (§5–§9). Follows the `narrative_relationships.py`/`sector_isolation.py` semver + fail-closed
  config convention already established in this codebase.
- `tests/test_sector_market_context.py` — unittest-style, mirroring `tests/test_sector_isolation.py`
  and `tests/test_market_expression.py` fixture conventions.

**Modify:**
- `mne/market_context.py` — additive only. `get_market_snapshot(tickers, observed_at=None)`: each
  instrument record gains an `"observed_at"` key. **The function must not call a clock itself** —
  `observed_at` is a caller-supplied parameter (the run's own timestamp), keeping the module
  deterministic and matching this codebase's existing aversion to non-deterministic reads inside
  low-level functions. Per-instrument failure isolation already exists (`try/except` + empty-data
  check inside the fetch loop, `market_context.py` current lines ~10-24) — no change needed there,
  just confirm sector tickers flow through the same loop.
- `main.py` — build a sector ticker dict from `mne.sector_market_context.build_sector_ticker_map()`
  and merge it into the existing fetch call at line 492:
  `market_snapshot = get_market_snapshot({**NASDAQ_TICKERS, **BREADTH_TICKERS, **sector_tickers}, observed_at=stamp)`,
  reusing the run's own `stamp` (already computed for the run timestamp, `main.py:506` area) rather
  than a new clock read. `NASDAQ_TICKERS`/`BREADTH_TICKERS` and their existing behavior are
  untouched — this is a pure dict-merge extension, matching how `BREADTH_TICKERS` was already
  merged in. Sector ticker map keys are the sector keys themselves (e.g. `"technology"`), not ETF
  symbols — see §5 for why this avoids a second schema.
- `mne/sector_isolation.py` — `build_sector_isolation_context(...)` gains a new parameter (the
  precomputed participation dict from `mne/sector_market_context.py`, supplied by `dashboard.py`)
  and merges `participation_state`, `participation_label`, `data_freshness`, and
  `participation_explanation` from it into each sector row, replacing the current hardcoded call to
  the always-`UNAVAILABLE` stub (`sector_isolation.py:104-106`). The function remains pure/read-only
  — it receives data, it does not fetch or classify. **No import of `sector_market_context` added**
  (§Grounding Decision).
- `dashboard.py` — call `sector_market_context.classify_sectors_for_run(run, narrative_sector_map)`
  (or similarly named) before calling `build_sector_isolation_context`, passing the result in. This
  is the single integration point where the two modules meet.
- `config/narrative_sector_map.json` — additive `expected_expression` field per sector entry
  (§7) — required for `PRIMARY`/`SECONDARY`/`OFFSET` roles to support real classification; optional
  for `EMERGING`. Existing fields (`sector`, `role`, `rationale`, `display_enabled`) are unchanged;
  old entries without `expected_expression` simply cap at `UNAVAILABLE` participation (fail closed,
  not guessed).
- `mne/presentation_language.py` — extend `SECTOR_ISOLATION_COPY` with participation-specific
  entries (data-freshness copy, the honesty strings from §14), following the existing
  `sector_isolation_copy()` accessor pattern.
- `templates/sector_isolation.html`, `templates/_partials/sector_heatmap.html` — surface
  participation state, data freshness, and the ETF symbol as secondary reference text, alongside
  the existing structural-role display. No layout restructuring — same tile grid, more fields per
  tile.
- `templates/dashboard.html` — no structural change; the existing Sector Isolation preview section
  (already inserted between `id="markets"` and `id="events"` per the prior sprint) now renders real
  participation data through the same markup.
- `static/styles.css` — activate the teal/amber accent classes already reserved but unused
  (confirming/strengthening participation → teal, contradicting → amber, detached/unavailable/mixed
  → slate), same two-hue budget, no new colors.
- `tests/test_sector_isolation.py` — the hardcoded-`UNAVAILABLE` assertion
  (`tests/test_sector_isolation.py:47-50`) becomes a pass-through assertion (given a fixture
  participation map, the context reflects it exactly); the "no market_context in source" guard
  (lines 94-97) stays, now proving the Grounding Decision holds.
- `tests/test_market_context.py` (or wherever `get_market_snapshot` is currently tested) — extend
  for the new `observed_at` parameter/field and multi-ticker merge including sector instruments.
- `docs/narrative_sector_model.md` — update to remove the "explicitly deferred" framing for
  participation states (`docs/narrative_sector_model.md:9`) and document the freshness rules,
  `expected_expression` schema, and classification precedence from this handoff.
- `README.md` — mention `config/sector_instruments.json` if the README documents configuration
  files (confirm current pattern before editing; don't add a new "Configuration" section if one
  doesn't already exist).

## 3. Existing Market-Data Audit

- **Fetch function**: `mne.market_context.get_market_snapshot(tickers: dict[str, str]) -> dict[str, dict | None]`
  (`mne/market_context.py`, ~24 lines) — the only market-data fetch path, using `yfinance`
  (`yf.Ticker(ticker).history(period="5d")`). Instrument record today: `{"ticker", "latest_close", "pct_change"}`
  — **no timestamp field exists**. `classify_market_move(pct_change)` in the same module defines
  thresholds `1.0`/`0.25` for `STRONG UP`/`UP`/`STRONG DOWN`/`DOWN`/`FLAT`/`UNKNOWN` — reused as the
  numeric reference for §8's participation thresholds, not re-derived from scratch.
- **Current fetch call**: `main.py:492`, `market_snapshot = get_market_snapshot({**NASDAQ_TICKERS, **BREADTH_TICKERS})`,
  only inside the `if nonzero:` branch (`main.py:486-500`); otherwise `market_snapshot = {}`
  (default at `main.py:409`). `NASDAQ_TICKERS` (`main.py:111-116`): `QQQ`, `NVDA`, `VIX` → `^VIX`,
  `DXY` → `DX-Y.NYB`. `BREADTH_TICKERS` (`mne/breadth.py:4-9`): `SPY`, `RSP`, `QQQE`, `IWM`. Written
  into the run dict verbatim at `main.py:530` as `run["market_snapshot"]`.
- **Failure isolation already exists per-instrument** — the `try/except Exception` and
  empty-data check both live inside the fetch loop in `get_market_snapshot`, so one bad ticker sets
  that entry to `None` and the loop continues. Requirement "one failed sector ETF must not fail the
  entire market snapshot" is already satisfied by the existing function; adding sector tickers
  needs no new isolation logic.
- **No retry logic exists anywhere** — confirmed, none to preserve or avoid duplicating.
- **Daily-snapshot persistence drops market data entirely, confirmed still true.**
  `mne/storage.py`'s `write_daily_snapshot`/`_aggregate_raw_runs` path only extracts
  `run_id`, `timestamp`, `narratives`, `event_lifecycle`, `regime_alignment` — `market_snapshot`
  is not among the extracted fields (`storage.py:406-412`, `storage.py:282-313`). **This sprint does
  not need to change that.** The dashboard's existing Market Expression layer already reads
  `run.get("market_snapshot")` directly from the live run object passed into `build_view_model`,
  not from the daily-snapshot archive — proof the same pattern works for sector participation
  without touching `mne/storage.py`. Per the spec's own §12 ("this sprint is for current live
  persisted market snapshots... avoid changing persistence modules unless the existing schema
  demands it"), no `storage.py` change is needed.
- **`mne/market_expression.py` already has a staleness constant and a timestamp parser that never
  fire in production**: `STALE_DATA_MAX_AGE = timedelta(hours=36)` (line 37) and `_parse_timestamp`
  (lines 152-167, handles both the run-stamp format and ISO format), reading
  `snapshot_record.get("timestamp") or snapshot_record.get("as_of")` per instrument
  (`market_expression.py:199-201`). This code path exists but has never activated because
  `get_market_snapshot` never wrote a timestamp — adding `observed_at` this sprint incidentally
  activates staleness detection for the *existing* narrative-level Market Expression layer too,
  which is a reasonable, low-risk side benefit, not something to actively wire up further this
  sprint (it's already there; do not build new integration around it).
- **Test fixtures already model an optional per-instrument `timestamp` field**
  (`tests/test_market_expression.py:37-56`, `market_record(pct_change, timestamp=None)`) —
  forward-looking scaffolding that predates production support. This confirms `timestamp`/`as_of`
  is the established field-naming idiom in this codebase; use `observed_at` for the new sector
  writes for clarity (raw fetch time) while `mne/sector_market_context.py`'s own staleness check
  reads it directly — no need to also populate `timestamp`/`as_of` on sector records, those are
  `market_expression.py`'s naming for its own (different, narrative-level) instruments.
- **No canonical sector→ETF registry exists anywhere** — confirmed via grep for `XLK`, `XLE`,
  `XLU`, `XLF`, `XLI`, `XLP`, `XLY`, `XLC`, `XLV`, `XLB`, `XLRE` across the repo. The only hits are
  ad hoc entries inside `config/market_expression_map.json`'s narrative instrument lists (`XLE`,
  `XLI`, `XLU`, `XLP` — narrative-keyed, not sector-keyed), the unrelated legacy
  `mne/narrative_market_map.py`, and `ARCHITECTURE.md:96-98` listing `XLK`/`XLE`/`XLF` as "future
  symbols." `config/sector_instruments.json` is genuinely new — nothing to migrate, nothing to
  rename to avoid conflict.
- **Backward-compatibility precedent** — two direct models exist for extending a schema without
  breaking old persisted records: `mne/storage.py:159-173`'s `_extract_regime_alignment`, which
  returns a safe default (`{"score": None, "state": None}`) when the field is absent from an older
  run rather than erroring, and `mne/dashboard_trust_summary.py`'s `LEGACY_SOURCE` provenance
  tagging, which labels a result's origin as `"legacy"` when a newer field is missing rather than
  guessing. The sector participation path should follow the same shape: a run/snapshot with no
  `observed_at` on a sector instrument, or no sector entries at all (any run persisted before this
  sprint), simply classifies as `UNAVAILABLE` via the normal fail-closed precedence (§8) — no
  special-cased "legacy" branch needed, because `UNAVAILABLE` already is the correct, honest answer
  for "no data," old or new.

## 4. Sector-Instrument Registry Summary

`config/sector_instruments.json`, versioned, validated against `mne.sector_isolation.SECTOR_KEYS`
(imported, not duplicated — the 11-sector canonical set already lives there):

```json
{
  "version": "1.0.0",
  "sectors": {
    "technology": {
      "display_name": "Technology",
      "instrument": "XLK",
      "instrument_type": "sector_etf",
      "display_enabled": true
    }
  }
}
```

One ETF per sector for MVP (the spec's own instruction — "do not add multiple ETFs per sector in
MVP unless the current architecture clearly supports it without ambiguity"; it doesn't today, one
ETF per sector keeps the fetch, the snapshot schema, and the classification precedence all
unambiguous). Fail closed on: unknown sector key (not in `SECTOR_KEYS`), duplicate `instrument`
value across sectors, malformed `version`, missing `display_name`, missing `instrument`, invalid
`display_enabled` type. `NarrativeSectorInstrumentError(ValueError)` or similar, mirroring
`SectorIsolationError`/`NarrativeRelationshipError`'s naming convention.

`build_sector_ticker_map()` returns `{sector_key: instrument}` for sectors with
`display_enabled: true` only — this is the dict merged into the live fetch call in `main.py`. Using
sector keys (not ETF symbols) as the map's keys means the resulting `market_snapshot` entries are
addressable as `market_snapshot["technology"]`, no separate sector/ticker namespace needed, and no
collision risk with the existing `QQQ`/`NVDA`/`VIX`/`DXY`/`SPY`/`RSP`/`QQQE`/`IWM` keys.

## 5. Fetch and Persistence Behavior

- Fetch: single call, same function, same failure isolation, extended ticker dict (§2, §3). No
  second market-data system, no new provider, no retry loop added.
- Persistence: **Option A from the original spec — add sector instruments directly into the
  existing flat `market_snapshot` dict**, not a separate `sector_market_context` field. The
  existing `market_snapshot` structure is already an undifferentiated flat name→record dict mixing
  index/breadth/macro tickers with no type discrimination; adding sector entries under their sector
  keys is consistent with that existing shape, not a schema fork. `run["market_snapshot"]`
  (`main.py:530`) needs no structural change — it already persists whatever dict it's given.
- Compatibility: runs/snapshots persisted before this sprint have no sector keys in
  `market_snapshot` at all. `.get(sector_key)` returns `None`, which the existing "missing = None"
  convention already handles identically to a failed live fetch — no migration, no rewrite of old
  data, and old snapshots load exactly as they do today (§3's backward-compatibility precedent).

## 6. Freshness / Staleness Rules

Three states — `FRESH`, `STALE`, `UNAVAILABLE` — exposed as a distinct `data_freshness` field on
each sector row, separate from `participation_state` (§8's precedence folds staleness into
`UNAVAILABLE` for participation purposes, but the UI still needs to say *why* it's unavailable —
missing vs. stale is a materially different message per §14).

- `observed_at` missing on the record → `UNAVAILABLE`, fails closed, never guessed as fresh.
- `age(observed_at, now) > SECTOR_STALE_MAX_AGE` → `STALE`, excluded from participation
  classification (folds to `UNAVAILABLE` participation, but `data_freshness: STALE` is shown
  distinctly).
- Otherwise → `FRESH`, eligible for real classification.
- `SECTOR_STALE_MAX_AGE`: reuse `market_expression.py`'s existing `STALE_DATA_MAX_AGE = 36h`
  constant value for consistency across the codebase's two market-data-consuming layers, rather
  than inventing a second staleness window with no stated rationale.
- **Honest, documented limitation, not solved this sprint**: no exchange-calendar awareness exists
  anywhere in this codebase (confirmed — no calendar/holiday library, no session-context logic).
  A 36-hour window means Friday's closing data (fetched Friday afternoon) can cross into `STALE`
  by Sunday morning, before Monday's new close is fetched — a false-stale weekend gap. Do not
  invent a "skip weekends" heuristic to paper over this; document it plainly in
  `docs/narrative_sector_model.md` and in the UI's limitations copy (§14) instead. This is
  explicitly acceptable per the original spec's own instruction to "document weekend/holiday
  limitations honestly if no exchange-calendar support exists," not a defect to silently fix with a
  fabricated calendar rule.
- `now` (the comparison time) is the dashboard's render-time clock — a normal, already-established
  pattern in this codebase (unlike inside `market_context.py`'s fetch function, which must stay
  deterministic per §2).

## 7. Participation-State Rules

Real classification, `mne/sector_market_context.py`, evaluated in this precedence order (first
match wins):

1. Sector not structurally mapped for this narrative → not included in the row set (unchanged
   existing behavior).
2. Sector has no `display_enabled: true` entry in `config/sector_instruments.json` → `UNAVAILABLE`.
3. No `market_snapshot` record for the sector, or record is `None` → `UNAVAILABLE`.
4. `data_freshness` is `UNAVAILABLE` or `STALE` (§6) → `UNAVAILABLE`.
5. No `expected_expression` configured for this sector+narrative pairing → `UNAVAILABLE` (fail
   closed — never assume "rising is good" as a default direction).
6. Otherwise, compute `pct_change` vs. the existing `market_context.classify_market_move`
   thresholds (`STRONG_MOVE_PCT = 1.0`, `MEANINGFUL_MOVE_PCT = 0.25` — same numeric values, defined
   locally in `sector_market_context.py` to avoid a fragile cross-module dependency on a function
   whose return shape is a label, not a participation state) and whether the move direction matches
   `expected_expression`:
   - **`CONTRADICTING`**: fresh, opposing `expected_expression`, `|pct_change| >= MEANINGFUL_MOVE_PCT`,
     role is `PRIMARY` or `SECONDARY`. (Because `expected_expression` is itself curated per
     sector+narrative — including for `OFFSET` roles, where the expected direction is already the
     counter-direction — "opposing" always means opposing the *curated* expectation, never the
     narrative's naive primary direction. An `OFFSET` sector moving as expected is aligned, not
     contradicting.)
   - **`STRONG`**: fresh, aligned, `|pct_change| >= STRONG_MOVE_PCT`, role is `PRIMARY` or
     `SECONDARY`.
   - **`PARTICIPATING`**: fresh, aligned, `MEANINGFUL_MOVE_PCT <= |pct_change| < STRONG_MOVE_PCT`,
     role is `PRIMARY`, `SECONDARY`, or `EMERGING`.
   - **`EMERGING`** (participation): fresh, aligned, `0 < |pct_change| < MEANINGFUL_MOVE_PCT`, any
     structurally connected role. A structurally `EMERGING`-role sector caps at `EMERGING`
     participation even on a large move — the structural connection itself is still developing, so
     participation shouldn't outrun it; this is a deliberate, documented first-pass rule (§Known
     Remaining Gaps), not a hard law.
   - **`DETACHED`** (participation — distinct concept from the structural `DETACHED` role; both
     reuse the same word by design per the original spec's own schema, but must never be rendered
     with identical copy — see §9): fresh, muted movement (`|pct_change|` near zero, below a small
     epsilon), regardless of direction.
   - **`MIXED`**: kept in the enum for architecture-readiness (`PARTICIPATION_STATES` already
     includes it), but **not reachable in MVP** — with one ETF per sector there is only ever one
     input, so no genuine conflicting-signal case exists. Do not fabricate a path to `MIXED`; a test
     (§19, item 18) asserts it stays unreached given single-instrument fixtures.

## 8. Structural Role Versus Participation Separation

Both fields present on every sector row, always, never collapsed:

```json
{"structural_role": "PRIMARY", "participation_state": "STRONG"}
```

A `DETACHED`-structural-role sector whose ETF happens to move is **never** presented as
"contradicting" or as any narrative signal at all — participation classification (§7) only
evaluates sectors with a curated `expected_expression`, and `DETACHED`-role sectors don't get one
by definition (no structural connection means no expected direction to compare against). This is
enforced by §7 step 5's fail-closed rule, not a special case — a `DETACHED` sector simply never has
an `expected_expression` entry, so it always resolves to `UNAVAILABLE` participation, correctly
communicating "we're not claiming this sector confirms or denies anything" rather than a fabricated
reading of unrelated market noise.

## 9. Participation Breadth Behavior

New `participation_breadth`, computed only from `FRESH`, structurally-mapped sectors — kept fully
separate from the existing `structural_breadth` (both present, both shown, never merged into one
number):

- `CONTRADICTED`: any `PRIMARY`/`SECONDARY` sector is `CONTRADICTING` — surfaced directly rather
  than diluted into a lower "moderate" reading, since a contradiction is the most decision-relevant
  signal.
- `BROAD`: 3 or more sectors in `STRONG`/`PARTICIPATING`.
- `MODERATE`: exactly 2 sectors in `STRONG`/`PARTICIPATING`.
- `CONCENTRATED`: exactly 1 sector in `STRONG`/`PARTICIPATING`.
- `LIMITED`: no `STRONG`/`PARTICIPATING` sectors, but at least one `EMERGING`.
- `UNAVAILABLE`: no fresh, classifiable sector data at all for this narrative.

Documented explicitly as a **first-pass, tunable rule** (§Known Remaining Gaps) — the 3/2/1
breakpoints mirror the structural breadth categories' own precedent from the prior sprint for
consistency, not a data-driven calibration (there's no real participation history yet to calibrate
against). Copy must state this reflects current observed data, never future performance, matching
§14.

## 10. Sector Isolation UI Behavior

Each sector row now shows: structural connection (unchanged from last sprint), current
participation state + plain-English interpretation, data freshness (with honest "why unavailable"
copy when applicable), and the ETF symbol as secondary reference text (small, not the primary
label — matches the original spec's "keep ETF symbols secondary" instruction and this codebase's
existing pattern of leading with plain language, e.g. `NARRATIVE_CONSTELLATION_COPY`).

Example copy pairs (both present together, never just one):
- *"Technology is both structurally central to the AI narrative and currently showing a clear
  market response."* (`PRIMARY` + `STRONG`)
- *"Utilities are connected to this narrative, but current sector-level market data is
  unavailable."* (`EMERGING` + `UNAVAILABLE`, missing/stale data)
- *"Financials are not structurally connected to this narrative. Their current market move is not
  treated as a signal about it."* (`DETACHED` structural + no participation claim at all — critical
  that this copy never implies the move itself is meaningless, only that it isn't being read as
  narrative confirmation.)

## 11. Dashboard Preview Behavior

Update only — no second sector section added. Same bounded sector count as last sprint (top 3-4 by
structural role weight), now showing real participation state alongside structural role, plus the
concise `participation_breadth` summary line, still linking to the full Sector Isolation route. No
dense performance table — tile count and layout are unchanged from the prior sprint's shipped
preview.

## 12. Compatibility Behavior

- This sprint covers current live persisted market snapshots only — **no historical sector-price
  backfill**, matching the explicit non-goal.
- Historical Replay artifacts without sector context are untouched — they were never in scope for
  `sector_isolation.py` or `sector_market_context.py`, and no code path in this sprint reads or
  writes replay data.
- Older live runs (persisted before this sprint) render calmly with `participation_state:
  UNAVAILABLE` and `data_freshness: UNAVAILABLE` across all sectors — the natural, correct output of
  §7's fail-closed precedence given no `observed_at`/sector data exists on those records, requiring
  no special-cased legacy branch (§3).

## 13. Data-Honesty and Safety Verification

Required, always-present copy (not edge-case-only):
- *"Current participation reflects available persisted sector ETF data."*
- *"Structural relationships are curated separately from current market behavior."*
- *"Missing or stale data is shown as unavailable, not detached."* — critical: `UNAVAILABLE`
  (participation) and `DETACHED` (structural role) must remain visually and textually distinct even
  though both may render with the same neutral/slate accent color; the accompanying text is what
  carries the distinction, not color alone (accessibility requirement carried over from last
  sprint's color rules).
- *"Sector participation describes current market expression, not a forecast."*

Never: sector leadership prediction, expected returns, causal certainty, trade recommendation,
claims of complete market coverage (one ETF per sector is a sampling proxy, not exhaustive sector
truth — say so in `docs/narrative_sector_model.md`, not necessarily in every UI string).

Boundary checks: `mne/sector_isolation.py` still imports neither `market_context` nor
`sector_market_context` nor `yfinance` (§Grounding Decision, test-enforced). No scoring/taxonomy
mutation — `sector_market_context.py` is read/classify-only, never writes to `run` or persisted
state. No new market-data provider — `yfinance` only, same fetch function.

## 14. Verification Performed

Read-only research pass, no code written: confirmed `cf8ad53` implemented Sector Isolation
structurally (contradicting the prior handoff's "not implemented" status, now stale); read
`mne/sector_isolation.py` in full (`SECTOR_KEYS`, `STRUCTURAL_ROLES`, `PARTICIPATION_STATES`,
`classify_sector_participation` stub, `build_sector_isolation_context` row shape); read
`config/narrative_sector_map.json` (confirmed 3-of-4 `NARRATIVE_GROUPS` coverage, matching the gap
already present in `config/market_expression_map.json`); read `mne/market_context.py` in full
(fetch function, failure isolation, `classify_market_move` thresholds); read `main.py`'s fetch call
and run-dict assembly (lines 111-116, 409, 486-500, 492, 506, 530); read `mne/storage.py`'s
snapshot-aggregation extraction functions (confirmed market fields still dropped, unchanged from
yesterday); read `mne/market_expression.py` in full (422 lines — config shape, thresholds,
unused-in-production staleness constant and timestamp parser); repo-wide grep for 11 sector ETF
symbols (confirmed no existing registry); read `tests/test_market_expression.py`'s fixture
conventions (confirmed forward-looking `timestamp` field in fixtures unmatched by production code);
read `tests/test_sector_isolation.py` in full (confirmed the `market_context`-substring test guard
that motivated this handoff's Grounding Decision); confirmed `yfinance` is still the only
market-data library (`mne/market_context.py:1`, unrelated local import in
`mne/company_catalysts.py:118`); read `mne/storage.py`'s `_extract_regime_alignment` and
`mne/dashboard_trust_summary.py`'s `LEGACY_SOURCE` pattern as backward-compatibility precedent.
Codex must run the commands in §Verification Commands after implementing — nothing here
substitutes for that.

## 15. Known Remaining Gaps

- **Weekend/holiday staleness false-positive** (§6) — documented, deliberate, not solved this
  sprint; no exchange-calendar library exists in this codebase to solve it properly.
- **Participation breadth thresholds (§9) and the `EMERGING`-role participation ceiling (§7) are
  first-pass, uncalibrated rules** — reasonable given "keep the first model simple," but
  explicitly flagged as tunable once real classified data accumulates.
- **`MIXED` is architecturally present but unreachable in MVP** (§7) — requires a second
  instrument per sector or a different signal source to ever fire; not this sprint's job.
- **One ETF per sector is a sampling proxy, not exhaustive sector coverage** — worth stating in
  `docs/narrative_sector_model.md` so the model's limits are documented, not just implied.
- **`Geopolitical Risk`** still has no sector mapping, no market-expression mapping, and no
  relationship mapping — a pre-existing, consistent gap across three curated layers now, not
  something this sprint is obligated to close.
- No Playwright/browser suite exists for visual verification of the newly-activated participation
  accent colors — manual visual pass required (§Verification).

## 16. Recommended Next Sprint

In priority order: (1) recalibrate `participation_breadth` and the `EMERGING` ceiling once real
classified data accumulates across enough trading days to see actual distribution, (2) add
lightweight exchange-calendar awareness to fix the weekend staleness false-positive honestly rather
than widening the staleness window as a blunt workaround, (3) close the `Geopolitical Risk` gap
across sector mapping, market expression, and relationships together in one pass rather than three
separate follow-ups, (4) revisit whether `Communication Services` and other secondary/emerging
sector rows need per-narrative `expected_expression` nuance beyond a single rising/falling flag
(e.g., conditional on a secondary factor) — explicitly out of scope this sprint per the original
spec's "do not encode ad hoc route-level rules."

## 17. Whether Sector Market Data Plumbing and Participation States Can Be Marked Implemented

**Not implemented — ready to hand to Codex.** The one load-bearing design decision
(§Grounding Decision) is settled by the existing test architecture, not a matter of preference, so
no additional ratification is needed before implementation starts. Mark this feature implemented
only after Codex completes the scoped work and every command below passes, including the modified
`tests/test_sector_isolation.py` assertion and the new `tests/test_sector_market_context.py` suite.

---

## Tests Required (mapped to original spec §16, adjusted for the confirmed current architecture)

1. Sector instrument config loads deterministically.
2. Unknown sector key fails validation.
3. Duplicate ETF (`instrument`) value fails validation.
4. Existing QQQ/NVDA/VIX/DXY fetch behavior is unchanged (same keys, same values) after the merge.
5. Sector ETFs flow through the same `get_market_snapshot` call — no second fetch path introduced.
6. One sector fetch failure does not fail the full snapshot (regression test on existing isolation
   behavior, now exercised with sector tickers specifically).
7. Sector market data persists into `run["market_snapshot"]` under sector keys.
8. Older runs/snapshots (no sector keys, no `observed_at`) load without error.
9. Fresh data (`observed_at` within the staleness window) is accepted for classification.
10. Stale data (`observed_at` beyond `SECTOR_STALE_MAX_AGE`) is excluded, `data_freshness: STALE`.
11. Missing `observed_at` fails closed to `UNAVAILABLE`/`UNAVAILABLE`, never treated as fresh.
12. `STRONG` participation fixture.
13. `PARTICIPATING` fixture.
14. `EMERGING` (participation) fixture, including the role-ceiling case (structurally `EMERGING`
    role capping at `EMERGING` participation despite a large move).
15. `DETACHED` (participation) fixture — muted move, fresh data.
16. `CONTRADICTING` fixture — opposing `expected_expression` for a `PRIMARY`/`SECONDARY` sector.
17. `UNAVAILABLE` fixture — each fail-closed path in §7's precedence individually (missing config,
    missing snapshot record, stale, missing `expected_expression`).
18. `MIXED` is not fabricated — single-instrument fixtures never reach it, asserted directly.
19. Structural role is unchanged by market movement (row assembly doesn't mutate curated data based
    on classification output).
20. Participation is never derived from QQQ/NVDA/VIX/DXY — a fixture with only those four populated
    and no sector entries yields `UNAVAILABLE` across all sectors.
21. Participation breadth reconciles correctly against a fixed fixture set of classified sectors.
22. Structural breadth remains computed independently, unaffected by participation values.
23. Dashboard preview renders real participation state, not the old hardcoded stub.
24. Dedicated Sector Isolation route renders participation, freshness, and structural role together.
25. ETF ticker symbols render as secondary text, never as the primary label (template assertion).
26. Stale/unavailable copy matches the exact honesty strings in §13, not a paraphrase.
27. Older live runs (pre-sprint schema) render calmly — full page render test, no exceptions.
28. Historical Replay pages are unmodified (regression, not new coverage).
29. No market-data call occurs during page rendering — `dashboard.py`'s render path calls
    classification on already-persisted `run["market_snapshot"]`, never `get_market_snapshot`
    itself at render time.
30. No new provider — `yfinance` import count and usage sites unchanged outside the sector-ticker
    merge.
31. No scoring/taxonomy mutation occurs.
32. No prediction or trade language appears (grep-based copy test, extending the existing pattern
    from `tests/test_sector_isolation.py`).
33. Same input produces byte-identical context (`json.loads(json.dumps(..., sort_keys=True))`
    round-trip, matching the existing constellation/sector-isolation byte-stability guarantee).
34. Existing `tests/test_market_expression.py` suite remains green — confirms the newly-added
    `observed_at` field doesn't regress narrative-level Market Expression's existing (currently
    dormant) staleness path.
35. Existing `tests/test_sector_isolation.py` suite remains green apart from the one deliberately
    updated assertion (§2).
36. Full test suite passes apart from any documented pre-existing failures unrelated to this
    sprint.

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_sector_market_context -v`
- `python -m unittest tests.test_sector_isolation -v`
- `python -m unittest tests.test_market_expression -v`
- Storage and market-context regression suites (whichever files currently cover
  `mne/storage.py` and `mne/market_context.py`)
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`
- One bounded, single-call market-context smoke test using the existing fetch abstraction (real
  `get_market_snapshot` call with the full merged ticker dict) — do not script repeated live calls
  or add this to a loop; one manual/CI-gated smoke run is sufficient to confirm the merge works
  end-to-end against the real API.

Manual verification:
- Populated current sector data, one missing sector, partial coverage, stale data, an older
  snapshot with no sector fields at all.
- AI / Tech Growth, Energy / Commodities, Macro Pressure (Geopolitical Risk has no mapping —
  confirm it still renders calmly, unchanged from last sprint).
- 1280px, 1024px, 390px, JavaScript disabled.
- Logged-out and authenticated states.
- Confirm structural role and observed participation remain clearly, textually separate — never
  collapsed into one signal or one color.
- Confirm the heatmap now reflects genuine sector data where available, and honestly explains
  unavailability where it doesn't — never presenting missing/stale data as detachment.
- Confirm no dense trading-terminal presentation appears — tiles stay calm even where participation
  is now real and populated.
- Confirm no regression in existing Market Expression, Narrative Constellation, Cross-Group
  Relationships, or Research Workspace behavior.

Implement to a verified local state and stop — do not stage, commit, or push.
