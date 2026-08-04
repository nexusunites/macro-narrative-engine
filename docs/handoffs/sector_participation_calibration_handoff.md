# Sector Participation Calibration and Exchange-Calendar Freshness — Implementation Handoff

## Purpose

Real sector participation classification shipped in `5758a5b` ("Add sector market participation
data") — `mne/sector_market_context.py`, `config/sector_instruments.json`, real
`STRONG`/`PARTICIPATING`/`EMERGING`/`DETACHED`/`CONTRADICTING`/`UNAVAILABLE` states, real breadth,
and a naive 36-hour elapsed-time freshness check. This sprint has two independent jobs: (1) audit
real persisted observations and calibrate thresholds against them where data exists, and (2)
replace naive wall-clock staleness with exchange-session-aware freshness so a Friday close doesn't
falsely go stale over the weekend. It also resolves one already-ratified product-rule change to the
shipped classifier (§Ratified Decision).

**Status: brief only, one decision already ratified by Daniel, 2026-08-04 (below); everything else
ready to hand to Codex as-is.**

Do not implement code from this document directly. This is the Codex-ready brief.

---

## Central Finding: zero persisted sector observations exist

`5758a5b` landed at `2026-08-04 00:50:34`. The most recent narrative run
(`2026-08-03_160440.json`) predates it — its `market_snapshot` only has the old
`QQQ`/`NVDA`/`VIX`/`DXY`/`SPY`/`RSP`/`QQQE`/`IWM` keys, no sector entries, no `observed_at` field
at all. Counting all 165 files in the real run store (`$MNE_DATA_DIR/results/`, not the repo's
untracked `data/results/` sample folder): **zero contain a sector-keyed `market_snapshot` entry.**
No run has executed since the feature shipped. There is no distribution to compute, no frequency
table to build, no "overly concentrated vs. overly permissive" judgment to make from real data —
not a small sample, exactly zero.

The original spec's own instruction governs this directly: *"If insufficient real observations
exist, do not pretend the thresholds are statistically validated. Use conservative provisional
tuning and label it clearly."* This handoff follows that: **no threshold numbers change based on
data this sprint** (§5) — there is no data. What *does* change: the one classifier logic error
found by code review (§Ratified Decision), and the freshness model, which is a pure engineering
improvement independent of data volume (§10). The calibration report (§10 of the original spec,
`docs/sector_participation_calibration.md`) documents this honestly as its headline finding, not a
footnote.

---

## Ratified Decision (Daniel, 2026-08-04): remove the EMERGING-role participation cap

**Finding**: the shipped classifier (`mne/sector_market_context.py:117-120`) special-cases
structural role — a sector with `structural_role: EMERGING` can only ever classify as `EMERGING` or
`DETACHED` participation, regardless of how large its real move is. A test explicitly locks this in
(`tests/test_sector_market_context.py`, "EMERGING role capped at EMERGING even for a 4% move"). This
conflicts with the new spec's §4 principle: structural maturity should not suppress a genuine
observed move.

**Ratified**: remove the cap entirely. `structural_role` and `participation_state` become fully
independent — role no longer gates *any* participation state at runtime. A structurally `EMERGING`
sector may classify as `STRONG`, `PARTICIPATING`, `EMERGING`, `DETACHED`, `CONTRADICTING`, or
`UNAVAILABLE`, exactly like `PRIMARY`/`SECONDARY`/`OFFSET` sectors, governed solely by the normal
data-quality, freshness, `expected_expression`, and threshold rules. `CONTRADICTING` is likewise no
longer restricted to `PRIMARY`/`SECONDARY` roles — it applies to any sector with a curated
`expected_expression`, sufficient fresh movement, and an opposing direction. (`DETACHED`-structural-
role sectors remain excluded from ever confirming or contradicting, but not via a role check in the
classifier — they're excluded because they never carry an `expected_expression` in the curated
config to begin with, which is the correct mechanism: a config-time curation fact, not a runtime
branch. See §7.)

**Practical effect on the code**: this *simplifies* `classify_sector_participation` — role drops out
of the classification precedence entirely (old step 5's `role == "EMERGING"` short-circuit is
deleted; old steps 6/7's `role in {"PRIMARY", "SECONDARY"}` guards are deleted). `structural_role`
remains present on the output row for display, just no longer read by the classification logic
itself.

**Required test replacement** (the existing capped-behavior test is deleted, not skipped):
1. A structurally `EMERGING` sector shows `STRONG` participation when real movement crosses the
   strong threshold, aligned with `expected_expression`.
2. The row's `structural_role` field remains exactly `"EMERGING"` — unmutated by the participation
   result (proves independence, not just the absence of a cap).
3. Smaller aligned movement on an `EMERGING`-role sector still classifies as `EMERGING`
   participation (unchanged case, still correct).
4. Contradiction requires explicit `expected_expression` **and** sufficient fresh opposing
   movement — test this on an `EMERGING`-role sector specifically (previously impossible; the old
   code forced it to `DETACHED`).
5. Missing, stale, or malformed data remains `UNAVAILABLE` regardless of role (regression,
   unchanged).

**Required documentation, verbatim, in `docs/sector_participation_calibration.md`**:
> "Structural maturity does not limit the strength of observed market participation. MNE displays
> both dimensions separately so an early-stage connection can still show a strong current
> response."

---

## 1. Objective Summary

Remove the EMERGING-role participation cap (ratified, above). Produce an honest calibration audit
documenting zero available real observations rather than fabricating a distribution. Replace the
naive 36-hour elapsed-time freshness check with exchange-session-aware freshness (Friday close
valid through the weekend, holiday-aware, deterministic via injectable `as_of`). Leave all
threshold *values* (`STRONG_MOVE_PCT`, `MEANINGFUL_MOVE_PCT`, `DETACHED_MOVE_EPSILON`, breadth
counts) unchanged and explicitly labeled provisional, pending real data. No new sectors, no new
instruments, no new market-data provider.

## 2. Files Changed

**Create:**
- `mne/market_calendar.py` — small, isolated module owning exchange-session-boundary computation
  (§9, §10). Kept separate from `sector_market_context.py` so the calendar dependency (§9) has one
  clear owner and one clear test surface, and so `sector_isolation.py`'s existing import boundary
  (§Compatibility) is trivially easy to keep correct — nothing new to reason about there.
- `docs/sector_participation_calibration.md` — the calibration report (§Central Finding, §10).
- `tests/test_market_calendar.py` — session-boundary logic, `as_of`-injectable, deterministic.

**Modify:**
- `mne/sector_market_context.py` — remove the role-based branch from
  `classify_sector_participation` (§Ratified Decision); replace the body of `_freshness` (currently
  lines 93-100, naive `reference - observed > timedelta(hours=36)`) with a call into
  `mne.market_calendar`'s session-aware freshness function, keeping the same `_freshness(record,
  now)` signature and the same three-value `DATA_FRESHNESS_STATES` output (`FRESH`/`STALE`/
  `UNAVAILABLE`) — no new public freshness values, no template/UI changes required from this field
  alone. Also fix the found-but-unrelated gap: a future `observed_at` (later than `now`) currently
  falls into `FRESH` with no lower-bound check — the session-aware rewrite naturally closes this
  (an observation newer than the last completed session relative to `now` is not a coherent state
  and resolves to `UNAVAILABLE`).
- `tests/test_sector_market_context.py` — delete the capped-EMERGING test, add the five replacement
  tests (§Ratified Decision), update freshness fixtures to use `mne.market_calendar`'s `as_of`
  injection instead of raw `timedelta` offsets from `SECTOR_STALE_MAX_AGE`.
- `requirements.txt` — add the calendar dependency if Option A is taken (§9).
- `mne/presentation_language.py` — extend `SECTOR_ISOLATION_COPY` with the freshness copy from §12
  (replacing any raw-hours-based phrasing, if present, with session-relative language).
- `docs/narrative_sector_model.md` — update to reflect the uncapped EMERGING-role behavior and the
  session-aware freshness model.

**Do not touch:** `mne/sector_isolation.py`'s import boundary (still only `narrative_signals` +
`presentation_language` — confirmed intact, no reason to change it this sprint),
`config/sector_instruments.json`, `config/narrative_sector_map.json`, `main.py`'s fetch call shape,
`mne/market_context.py`'s `get_market_snapshot` signature, breadth precedence logic (unchanged, no
data to justify a change — see §8), Historical Replay, taxonomy, or scoring.

## 3. Calibration Dataset Summary

- **165** run files exist in the real store (`$MNE_DATA_DIR/results/`).
- **0** contain any sector-keyed `market_snapshot` entry.
- **0** sector `pct_change` observations exist to distribute.
- **0/0** — no `observed_at` values to check for validity, because no sector entries exist at all.
- The repo's tracked `data/results/` (2 old May files) is not the live store and was never in
  scope.
- **No live fetch, large or small, is authorized by this handoff to manufacture data.** The
  original spec explicitly excludes "fetch large historical datasets" and only allows "a small
  bounded current smoke fetch if required" — the smoke fetch in §Verification exists to prove the
  pipeline works end-to-end, not to generate a calibration sample; one or two data points are not a
  distribution and must not be treated as one in the report.
- Reproducibility: the audit script that produced the 165/0 count should be preserved (e.g. as a
  small script referenced from `docs/sector_participation_calibration.md`, not necessarily shipped
  as production code) so the same count can be re-run once real runs accumulate post-deploy.

## 4. Existing Threshold Audit

Current, unchanged-by-data-this-sprint values (`mne/sector_market_context.py:15-18`):

| Constant | Value | Role |
|---|---|---|
| `SECTOR_STALE_MAX_AGE` | `timedelta(hours=36)` | **Replaced** by session-aware logic (§9), not tuned |
| `STRONG_MOVE_PCT` | `1.0` | Unchanged — no data to justify a change |
| `MEANINGFUL_MOVE_PCT` | `0.25` | Unchanged |
| `DETACHED_MOVE_EPSILON` | `0.01` | Unchanged |

These four values were themselves provisional estimates from the plumbing sprint, not derived from
data (there was none then either). This sprint does not pretend otherwise — they remain labeled
provisional in the calibration report, carried forward unchanged, with a named recalibration
trigger (§16) rather than a fabricated justification.

Breadth precedence (`_participation_breadth`, `mne/sector_market_context.py:133-148`): `confirming
>= 3 → BROAD`, `== 2 → MODERATE`, `== 1 → CONCENTRATED`, else any `EMERGING` present `→ LIMITED`,
else `→ UNAVAILABLE`; any `CONTRADICTING` present overrides to `CONTRADICTED`. Also unchanged this
sprint — same reasoning.

## 5. Final Participation Thresholds

**No numeric threshold changes.** `STRONG_MOVE_PCT = 1.0`, `MEANINGFUL_MOVE_PCT = 0.25`,
`DETACHED_MOVE_EPSILON = 0.01` remain exactly as shipped. The one logic change is structural, not
numeric — removing the role-based branch (§Ratified Decision). Per the original spec's own
instruction ("do not tune thresholds to maximize confirmation" and "if insufficient real
observations exist... use conservative provisional tuning and label it clearly"), changing these
numbers with zero observations to justify a direction would be exactly the "hidden scoring model"
/ "curve fitting" the Core Principle prohibits.

## 6. Structural-Role Interaction Decision

Fully resolved by §Ratified Decision: structural role no longer participates in classification
logic at all. It remains a display field on every sector row (unchanged from the prior sprint) and
continues to gate *inclusion* in the row set and *whether `expected_expression` exists at all*
(config-time curation, not a runtime branch) — but it never caps, floors, or otherwise adjusts a
computed participation state.

## 7. Contradiction Rules

Confirmed and clarified, not changed in mechanism (already correct in the shipped code, now simply
no longer role-restricted):

- `CONTRADICTING` requires: fresh data (`data_freshness == FRESH`), a real parseable `pct_change`,
  an explicit `expected_expression` on the sector+narrative pairing, movement opposing that
  direction, and `|pct_change| >= MEANINGFUL_MOVE_PCT`.
- A `DETACHED`-structural-role sector **cannot** become `CONTRADICTING` — not via a role check, but
  because `DETACHED`-role entries never carry a curated `expected_expression` in
  `config/narrative_sector_map.json` (confirmed: the existing validation already requires
  `expected_expression` be set for roles where a direction claim is meaningful, and `DETACHED`
  sectors structurally have none). Step 1 of the classifier (`mapping.expected_expression` falsy →
  `UNAVAILABLE`) already enforces this — no new code needed, just confirm the config-curation
  discipline holds and add a regression test proving it (§19).
- Contradiction is never inferred from broad-market context (`QQQ`/`NVDA`/`VIX`/`DXY`) or from
  narrative-level Market Expression — only from the sector's own fresh ETF data, unchanged from the
  prior sprint's boundary.
- The `DETACHED_MOVE_EPSILON` check (near-zero move) still takes precedence over the contradiction
  check in the classifier's order — a muted move is `DETACHED`, never `CONTRADICTING`, regardless
  of nominal direction. This ordering is preserved from the shipped code.

## 8. Breadth Calibration

Unchanged this sprint (§4, §5) — no real data exists to evaluate whether the 3/2/1 confirming-count
breakpoints are too permissive or too strict. The precedence order (`CONTRADICTED` overrides
everything; `BROAD`/`MODERATE`/`CONCENTRATED` by confirming count; `LIMITED` as the
`EMERGING`-only fallback; `UNAVAILABLE` when nothing is fresh) is documented as-is in the
calibration report, explicitly flagged as unvalidated, with the same recalibration trigger as §5.
No sector-count-vs-coverage confusion exists in the current logic to fix — `_participation_breadth`
already only counts `FRESH`, non-`UNAVAILABLE` rows, so "partial coverage" already correctly
degrades toward `LIMITED`/`UNAVAILABLE` rather than being miscounted as `LIMITED` when it should be
`UNAVAILABLE`; confirm this with a dedicated test (§19) rather than assuming it's correct because
it looks right.

## 9. Exchange-Calendar Implementation

**Recommended: Option A — `pandas_market_calendars`.** `pandas>=2.2.0` is already a declared
dependency (installed `3.0.3`); `pandas_market_calendars` is small, purpose-built, and actively
maintained — not the "large dependency without justification" the spec warns against, and far more
correct than hand-maintaining a holiday list. Use its NYSE calendar (`get_calendar("NYSE")`) to
compute valid trading sessions and their close times.

**Fallback if dependency addition is blocked at implementation time: Option C**, a small internal
weekday + fixed-date NYSE holiday list (New Year's, MLK, Presidents', Good Friday, Memorial Day,
Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas — plus their observed-date shift
rules) confined to `mne/market_calendar.py`, documented as a known-incomplete approximation (no
early-close half-days) in the calibration report's Limitations section. Do not silently fall back
to this without flagging it — Option A is the stated preference; Option C is a named contingency,
not an equally-weighted choice.

**Do not** add `pandas_market_calendars`'s heavier alternatives (`exchange_calendars`, which pulls
in more transitive dependencies) without a specific reason to prefer it — no such reason exists
here.

**Timezone handling**: mirror the existing precedent in `mne/event_lifecycle.py:50,328-335` —
stdlib `zoneinfo.ZoneInfo("America/New_York")` for local market-close computation, converted to
UTC, exactly the pattern already used elsewhere in this codebase. Do not introduce `pytz` (already
present only as `yfinance`'s undeclared transitive dependency, not a direct one — adding a direct
dependency on it would be worse than using stdlib `zoneinfo`, which costs nothing).

## 10. Freshness / Session Rules

Replace the naive `elapsed > 36h → STALE` check with a session-counting rule, deterministic and
`as_of`-injectable (mirrors the existing `_freshness(record, now)` signature convention):

1. `observed_at` missing, malformed, or later than `now`/`as_of` → `UNAVAILABLE` (fail closed;
   also fixes the found future-timestamp gap, §2).
2. Count the number of NYSE trading sessions whose close time falls strictly between `observed_at`
   and `now` (via `mne.market_calendar`).
3. `0` sessions closed since the observation → `FRESH`. This is what makes a Friday close valid all
   weekend (no session closes Sat/Sun) and a pre-holiday close valid through the holiday (no
   session closes on the holiday) — the *session count*, not raw elapsed hours, is what decides
   freshness.
4. `1` session closed since the observation, **and** `now` is still within a grace window after
   that session's close (recommend `STALE_GRACE_WINDOW = timedelta(hours=8)`, provisional — gives
   the daily pipeline run room to execute without being penalized for not running at the exact
   closing bell) → still `FRESH`.
5. `1` session closed and past the grace window, or `2+` sessions closed → `STALE`.
6. Intraday nuance: this data source (`yfinance` `history(period="5d")`, daily closes only) has no
   true intraday granularity, so "current session" freshness in practice means "as of the most
   recently available daily close, fetched after that close was set" — document this honestly in
   the calibration report rather than implying sub-day precision the source can't support (matches
   the original spec's "do not invent intraday precision the data source cannot support").
7. Keep a generous absolute backstop (e.g. 10 calendar days) as a pure defensive fallback against
   calendar-library bugs or unexpected gaps — not the primary mechanism, just a safety net, clearly
   commented as such.

**Simplification from the original spec's suggested session-state enum** (`CURRENT_SESSION`,
`PREVIOUS_VALID_SESSION`, `MARKET_CLOSED_VALID`, `STALE`, `UNAVAILABLE`): these remain internal
computation concepts inside `mne/market_calendar.py`, not a new public field. The existing
three-value `data_freshness` (`FRESH`/`STALE`/`UNAVAILABLE`) already satisfies "the public UI does
not need to expose raw enum names" and avoids proliferating a second, redundant public enum for the
same underlying concept — keeps the model simple, per the spec's own repeated instruction.

## 11. Compatibility Behavior

- Old snapshots/runs without sector data or `observed_at`: unchanged behavior — `_freshness`
  returns `UNAVAILABLE` exactly as it does today (fail-closed path is untouched by the session-aware
  rewrite, just re-implemented with a better STALE boundary for records that *do* have a valid
  timestamp).
- `market_snapshot`'s existing flat structure: unchanged.
- `mne/sector_isolation.py`'s independence from market-context modules: unchanged, still enforced
  by the existing test (`tests/test_sector_isolation.py:96-99`) — this sprint doesn't touch that
  file at all.
- The `dashboard.py` injection boundary (participation dict computed externally, passed into
  `build_sector_isolation_context`): unchanged.
- Historical Replay: untouched, no code path in this sprint reads or writes replay data.
- No historical files are rewritten — the session-aware freshness function operates on read data at
  render/classification time, it doesn't migrate or touch persisted JSON.

## 12. User-Facing Copy Changes

Replace any elapsed-hours-flavored freshness copy with session-relative language:
- *"Based on the latest completed market session."*
- *"Current sector data is from the most recent available session."*
- *"This observation is older than the latest expected market session."*
- *"Sector participation is unavailable because the observation time is missing."*

Never expose: calendar-library internals, raw age-in-seconds/hours, the threshold constants
themselves, or exchange-calendar session codes. This is a direct continuation of the prior sprint's
"keep ETF symbols secondary, plain language primary" convention — no new exception introduced here.

## 13. Safety and Boundary Verification

- `mne/sector_isolation.py` still imports neither `market_context`, `sector_market_context`, nor
  `yfinance`, nor (new) `market_calendar` — confirmed by the existing test, unmodified.
- No new market-data provider — `yfinance` usage is unchanged; `pandas_market_calendars` (or the
  Option C fallback) supplies calendar/session metadata only, never price data.
- No scoring or taxonomy mutation — `mne/market_calendar.py` and the modified `_freshness` are
  read/compute-only.
- No predictive or trade language introduced in any new copy (§12) — grep-tested alongside the
  existing prohibited-terms test.
- Calibration is presentation-honesty work, not a hidden scoring model — the report format (§10 of
  the original spec) forces every number to be labeled empirical, provisional, or assumption, per
  the Core Principle's explicit prohibition on backtesting-flavored tuning.

## 14. Verification Performed

Read-only research pass plus one ratified product-rule decision, no code written: confirmed
`5758a5b` shipped the participation classifier, read `mne/sector_market_context.py` in full (exact
constants, exact precedence, exact breadth logic, exact `_freshness` implementation including the
missing future-timestamp bound); read the updated `mne/market_context.py` (`observed_at` parameter
confirmed present and wired); read `main.py`'s current fetch-and-merge call (lines ~493-497,
`stamp` defined line ~181); read `config/narrative_sector_map.json`'s `expected_expression` field
across all three covered narratives; confirmed `mne/sector_isolation.py`'s import boundary is
intact and one-directional (`sector_market_context` may import `sector_isolation`, never the
reverse); counted all 165 real run files in `$MNE_DATA_DIR/results/` directly, confirmed zero
contain sector-keyed `market_snapshot` data, confirmed the timing reason (feature shipped after the
last run); read `tests/test_sector_market_context.py` and `tests/test_market_context.py` in full
(confirmed the exact capped-EMERGING test this sprint replaces, per Daniel's ratified decision);
checked `requirements.txt` and the installed environment for calendar-library availability
(confirmed `pandas_market_calendars` and `exchange_calendars` are both absent, `pandas` already
present, `pytz` present only transitively via `yfinance`); confirmed `zoneinfo` + `America/New_York`
is an existing convention via `mne/event_lifecycle.py:50,328-335`. Codex must run the commands in
§Verification Commands after implementing — nothing here substitutes for that.

## 15. Known Remaining Gaps

- **Zero real calibration data** — the sprint's central, honest boundary (§Central Finding), not an
  oversight. Numeric thresholds remain provisional until real runs accumulate post-deploy.
- **`STALE_GRACE_WINDOW = 8h` is a first-pass, undocumented-by-data value**, same status as the
  other constants — flagged for the same future recalibration pass (§16).
- **No early-close (half-day) session awareness** if Option C (internal calendar) is used instead
  of Option A — `pandas_market_calendars` handles this correctly; the fallback does not. Document
  this explicitly if Option C is ever taken.
- **True intraday freshness is not supported by the data source** (§10, item 6) — a documented
  limitation of `yfinance` daily-close fetching, not something this sprint can fix without a
  different data source (explicitly out of scope, non-goal).
- No Playwright/browser suite exists for visual verification of the updated freshness copy —
  manual visual pass required (§Verification).

## 16. Recalibration Trigger

Recalibrate `STRONG_MOVE_PCT`, `MEANINGFUL_MOVE_PCT`, `DETACHED_MOVE_EPSILON`, the breadth
confirming-count breakpoints, and `STALE_GRACE_WINDOW` once **at least 20 trading days of real
persisted sector observations exist** (roughly 220 sector-classification events across all 11
sectors, assuming daily runs resume) — a concrete, checkable condition rather than an open-ended
"once we have more data." Until that trigger is met, no further threshold changes should be made
without equally explicit, equally honest justification.

## 17. Recommended Next Sprint

In priority order: (1) once the 20-trading-day trigger is met, run the real calibration this sprint
could not — actual distribution analysis, actual threshold tuning, actual breadth-breakpoint
validation, replacing every "provisional" label in `docs/sector_participation_calibration.md` with
an empirical one; (2) revisit `STALE_GRACE_WINDOW` specifically once real run-cadence data shows how
consistently the daily pipeline executes relative to market close; (3) if Option C (internal
calendar) was taken instead of Option A, evaluate upgrading to `pandas_market_calendars` once/if
dependency review clears it; (4) evaluate whether sector-specific thresholds are warranted once real
volatility differences across the 11 sectors are observable (explicitly deferred per the original
spec's "avoid sector-specific complexity in this sprint" instruction — do not start this early).

## 18. Whether Sector Participation Calibration and Exchange-Calendar Freshness Can Be Marked Implemented

**Not implemented — ready to hand to Codex.** The EMERGING-role cap removal is fully ratified and
requires no further sign-off. Mark this implemented only after Codex completes the scoped work and
every command below passes — including the five replacement tests for the ratified decision and the
new session-boundary tests. Do not mark "calibration" as complete in the sense of "thresholds are
now data-validated" — that milestone is explicitly gated behind §16's trigger, which this sprint
does not and cannot meet.

---

## Tests Required (mapped to original spec §12, adjusted for confirmed current architecture and the ratified decision)

1. The zero-observation audit is reproducible and deterministic (script or test asserting the count
   over a fixture directory, not the live store itself).
2. Malformed sector observations are excluded from any distribution computation (fixture-based,
   since no real malformed data exists yet either).
3. All threshold constants remain named, unchanged, and imported (not re-declared) from
   `sector_market_context.py`.
4. `STRONG` threshold boundary works (regression, unchanged numeric value).
5. `PARTICIPATING` threshold boundary works (regression).
6. `EMERGING` threshold boundary works (regression, still reachable for smaller aligned moves).
7. `DETACHED` (epsilon) threshold boundary works (regression).
8. `CONTRADICTING` threshold boundary works, now including a `PRIMARY`/`SECONDARY` case (regression)
   **and** an `EMERGING`-role case (new, per Ratified Decision item 4).
9. A `DETACHED`-structural-role sector never becomes `CONTRADICTING` (proves the config-curation
   mechanism from §7, not a role check).
10. Missing `expected_expression` fails closed to `UNAVAILABLE` (regression).
11. **EMERGING-role sector reaches `STRONG` on a large aligned move** (Ratified Decision item 1).
12. **`structural_role` remains `"EMERGING"`, unmutated, when participation is `STRONG`** (Ratified
    Decision item 2).
13. **EMERGING-role sector still reaches `EMERGING` participation on a smaller aligned move**
    (Ratified Decision item 3, regression under the new logic).
14. Breadth `BROAD` fixture (regression, unchanged thresholds).
15. Breadth `MODERATE` fixture (regression).
16. Breadth `CONCENTRATED` fixture (regression).
17. Breadth `LIMITED` fixture (regression).
18. Breadth `CONTRADICTED` fixture (regression).
19. Partial coverage correctly resolves to `UNAVAILABLE`/`LIMITED` per §8, never miscounted as a
    higher breadth state than the fresh data actually supports.
20. Friday-close observation remains `FRESH` through Saturday and Sunday (`as_of` injected).
21. A holiday closure preserves the prior session's data as `FRESH` through the holiday (`as_of`
    injected, using the chosen calendar's holiday list).
22. An observation becomes `STALE` after the next expected session's close plus the grace window
    (`as_of` injected).
23. Missing `observed_at` returns `UNAVAILABLE`.
24. Malformed (unparseable) `observed_at` returns `UNAVAILABLE`.
25. A future `observed_at` (later than `now`) returns `UNAVAILABLE`, not `FRESH` (the found-and-fixed
    gap).
26. `as_of` injection makes freshness fully deterministic — same inputs, same output, no wall-clock
    read inside the test.
27. Older snapshots (no sector data, no `observed_at`) remain compatible — full render, no
    exceptions.
28. No historical files are rewritten by any test or by the classification path itself.
29. No market-data fetch occurs during page rendering or during freshness classification —
    `mne/market_calendar.py` and the updated `_freshness` operate on already-persisted data only.
30. `tests/test_sector_isolation.py:96-99`'s import-boundary guard remains intact and green,
    unmodified.
31. Existing narrative-level Market Expression behavior (`tests/test_market_expression.py`) is
    unaffected by the freshness rewrite in `sector_market_context.py` (separate module, separate
    staleness constant, no shared code path).
32. No scoring or taxonomy mutation occurs (regression, unchanged from prior sprints).
33. No predictive or trade language appears in any new copy (grep-based).
34. Same input and same `as_of` produce byte-identical classification output
    (`json.loads(json.dumps(..., sort_keys=True))` round-trip, matching the existing pattern).
35. `tests/test_sector_market_context.py` (with the deleted/replaced tests) remains green.
36. Full suite passes apart from any documented pre-existing failures unrelated to this sprint.

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_sector_market_context -v`
- `python -m unittest tests.test_market_calendar -v`
- `python -m unittest tests.test_sector_isolation -v`
- `python -m unittest tests.test_market_expression -v`
- `python -m unittest tests.test_market_context -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`
- The zero-observation audit script/report against the real persisted run store (read-only, no
  fetch).
- One bounded, single-call smoke test using the existing fetch abstraction (confirms the pipeline
  still works end-to-end after any `mne/market_context.py` touch) — do not repeat this call, and do
  not treat its output as calibration data (§3).
- Fixture-based Friday/weekend, market-holiday, and old-snapshot scenarios, all via `as_of`
  injection — no dependency on the real calendar date the tests happen to run on.

Manual verification: populated, partial, stale, and unavailable UI states at 1280px, 1024px, 390px,
JavaScript disabled, logged-out and authenticated states. Confirm freshness copy reads as
session-relative language, not raw hours. Confirm the EMERGING-role change is visible in at least
one fixture-driven UI state (an EMERGING-role sector showing `STRONG` participation, with its
structural role still clearly labeled "Emerging connection" alongside it) so the two dimensions'
independence is visually obvious, not just true in the data.

Implement to a verified local state and stop — do not stage, commit, or push.
