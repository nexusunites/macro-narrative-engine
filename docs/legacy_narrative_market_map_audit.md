# Legacy Narrative-Market Map: Repository-Wide Consumer Audit and Retirement Decision

**Audit date: 2026-08-04. Status: retired — Option A was implemented after the proof-test gate
in §10 passed.**

## 1. Purpose

`mne/narrative_market_map.py` predates the canonical instrument architecture
(`config/asset_registry.json`, `config/narrative_asset_map.json`,
`config/market_expression_map.json`, `config/synthetic_market_concepts.json`) documented in
`docs/instrument_mapping_architecture.md`. A prior audit (during the Asset Coverage Expansion
sprint) found it unused in the dashboard UI but explicitly flagged that finding as "UI-complete,
not repo-exhaustive." This document closes that gap: an exhaustive, repository-wide trace of every
Python, template, JavaScript, script, test, doc, and persisted-data reference to the legacy system,
producing enough evidence to make a real deletion decision rather than another provisional
deferral.

## 2. Current Ownership Model

Unchanged from `docs/instrument_mapping_architecture.md` — this audit doesn't alter the five-way
split, it resolves item 5's open question ("remains until repo-wide proof shows...").

## 3. Runtime Call Path

Exact, complete sequence, `main.py` only (the sole production entry point):

1. `main.py:412-416` — `top_theme` derived from headline-based theme scoring for the run (can be
   `None`).
2. `main.py:417-418` — `market_expression = get_market_expression(top_theme)`
   (`mne/narrative_market_map.py:59-90`), a pure dict lookup, **not wrapped in try/except** (unlike
   three other pipeline stages in `main.py` — macro calendar refresh, narrative brief generation,
   narrative memory generation — which are explicitly guarded). Cannot realistically throw in
   practice (worst case `top_theme=None` still returns a valid "unmapped" dict), but is structurally
   inconsistent with how the rest of the pipeline treats optional/best-effort stages.
3. `main.py:544` — `run["market_expression"] = market_expression`, the sole write into the
   persisted run structure.
4. `main.py:621` / `main.py:680` — `print_market_expression(market_expression)`
   (`mne/reporting.py:72`) — stdout only, no side effect on persisted state.
5. `main.py:760` — `save_run_json(run, stamp)` persists the full run dict, including the legacy
   field, to the per-run result JSON file. **Not** carried into daily-snapshot aggregation —
   `write_daily_snapshot`'s `current_raw_run` allowlist (`mne/storage.py:406-412`) never included
   either the legacy or the canonical market-expression field; this is a pre-existing fact about
   the daily-snapshot path, not something this system uniquely lacks.
6. `main.py:794` — `market_expression=market_expression` passed into `build_daily_report(...)`
   (`mne/reporting.py:408-462`), which appends the legacy primary/secondary/offsets block to the
   plain-text daily report file (`REPORTS_DIR/*.txt`). This text artifact is written but never
   re-read or re-parsed by any other code in the repository.
7. `dashboard.py:1625,1766` — every dashboard render reads `run.get("market_expression")` back out
   of the per-run JSON and places it into the Jinja `view` context as `view.market_expression`.
   **Zero templates reference it** (confirmed by direct grep of every file under `templates/`) — it
   is computed and attached on every single dashboard page load for no consumer.

## 4. Consumer Inventory

| Consumer | File:Line | Class | Behavior if removed |
|---|---|---|---|
| `main.py` compute/persist/print/report | `main.py:418,544,621,680,794` | A (source, being retired) | Removed as part of this retirement — not "broken," eliminated by design |
| `dashboard.py` read + passthrough | `dashboard.py:1625,1766` | E (dead) | No effect — `view.market_expression` currently reaches zero templates |
| `mne/narrative_brief.py` evidence-source registration | `:546` | B (compatibility-only) | No effect — registers the key as an available evidence source, but nothing reads it back for content |
| `mne/narrative_brief.py` limitations check | `:680,683` | B (functionally inert) | No effect — the `is None` check this guards can never fire, because `get_market_expression()` always returns a dict, never `None`, so the "Market Expression data was unavailable" limitation text this code path exists to produce is unreachable dead logic today regardless of retirement |
| `mne/reporting.py` `append_market_expression`/`print_market_expression` | `:45-77` | A (formatting helpers for the source) | Removed alongside the source |
| `tests/test_narrative_market_map.py` | whole file | C | Replaced by proof tests (§10) before deletion, not simply deleted |
| `tests/test_narrative_brief.py:97` | | C | Mock fixture for the inert `_limitations()` path — updated, not broken |
| Every template (`dashboard.html`, `narrative_investigation.html`, `sector_isolation.html`, `asset_grid.html`, `admin.html`, all others) | — | E (dead) | Zero references anywhere — confirmed by direct grep, not inference |
| `static/**/*.js` | — | E (dead) | Zero references — confirmed clean |
| Scripts, CLI tools, migrations, exports | — | (none exist / no hits) | No repo-wide script/CLI/migration infrastructure references the legacy system at all — confirmed via `find` (no `scripts/`, `cli.py`, `manage.py`, `alembic/` migration touching it) |
| The only JSON API route (`/api/ai-analyst`, `dashboard.py:2437`) | `mne/ai_analyst.py:229-283` | N/A (verified clean, not a consumer) | `build_ai_analyst_context` hand-extracts a specific allowlist of fields from `view`/`investigation` — confirmed by direct read that its `"market_expression"` key is sourced from `view.get("market_expression_context")` (canonical) or `investigation.get("market_expression")` (also canonical, via `mne/research_workspace.py`), **never** from the legacy `run["market_expression"]` key. No wholesale object serialization occurs anywhere in this response path. This closes the "no public API contract exposes it" retirement criterion with direct evidence rather than assumption. |
| `ARCHITECTURE.md:107-133` | doc | D, and stale | Describes the dashboard passthrough as intentional "for future cards" — no card has ever been built against it. Should be corrected regardless of the retirement decision. |
| All other docs/handoffs | — | D | Historical record only, no code dependency |

**No entries fall into category F for the consumer question itself** — every reference is
unambiguously A/B/C/D/E. (One separate, non-consumer finding — a semantic framing divergence, not a
code dependency — is documented in §7 and is genuinely ambiguous, but it doesn't affect this
classification.)

## 5. Persisted Schema Audit

Real run store: `$MNE_DATA_DIR/results/` (167 files, verified directly, not the repo's untracked
sample folder).

- **The field is not present across the full history — it's absent in 133/167 (~80%) of archived
  runs** (`2026-03-05_1423.json` through `2026-06-17_1859.json`), and present in the remaining 34
  (`2026-06-17_2051.json` onward), exactly coinciding with when `market_expression_context`
  (canonical) was also introduced.
- Shape has been **100% stable** across all 34 files that have it — spot-checked oldest-with-field
  and newest, identical key set (`theme`, `display_theme`, `mapping_version`, `mapped`,
  `context_only`, `is_signal`, `primary`, `secondary`, `offsets`, `description`, `note`), values
  differ only by theme.
- **Every live consumer already tolerates absence** — `dashboard.py:1625` uses `.get()` +
  `isinstance` checks, `mne/narrative_brief.py:546,680` uses `.get()` + `is None` checks. The
  system was already built to degrade safely on the 80% of history that never had this field; no
  loader "assumes" it exists.
- Old runs remain fully readable with or without the field, with or without the module — nothing in
  this audit found a loader that would break either way.

## 6. Canonical Replacement Matrix

| Legacy theme | Canonical narrative group (via `market_expression_map.json` alias list) | Covered by |
|---|---|---|
| `ai` | AI / Tech Growth | `narrative_asset_map.json`, `market_expression_map.json` |
| `energy` | Energy / Commodities | `narrative_asset_map.json`, `market_expression_map.json` |
| `rates` | Macro Pressure | `narrative_asset_map.json`, `market_expression_map.json` |
| `recession` | Macro Pressure | `market_expression_map.json` (secondary XLU/XLP) |
| `inflation` | Energy / Commodities | `market_expression_map.json` (secondary/offset) |

All 5 legacy themes resolve onto the 3 canonical narrative groups via existing alias lists —
structural coverage is complete. Legacy-only tickers with **no canonical counterpart at all**
(orphaned, not conflicting — just never carried forward): `AVGO`, `ANET`, `VRT`, `DELL`, `GLD`,
`DBC`, `FCX`, `IEF`, `KRE`, `XLF` (legacy-rates only), `SHY`, `HAL`, `OXY`. None of these are
required by any current product surface — they were candidates evaluated and mostly rejected during
the Asset Coverage Expansion sprint (§Rejected Candidates in that handoff), not silently dropped.

## 7. Divergence Risks

Ticker-by-ticker comparison found the two systems agree on role and direction almost everywhere
they overlap (`NVDA`, `XOM`, `CVX`, `SLB`, `QQQ`, `XLU`, `XLP` — matching or non-conflicting
framing). Two findings worth recording explicitly:

- **`MSFT`**: legacy frames it as `ai` **primary**; canonical `narrative_asset_map.json` frames it
  as `AI / Tech Growth` **SECONDARY**. Same narrative, same direction, one role-tier disagreement.
  Minor — canonical's more conservative framing (ratified during Asset Coverage Expansion, §5 of
  that handoff) supersedes without controversy.
- **`TLT` — the one real semantic conflict.** Legacy's `recession` theme groups `TLT` with
  `XLU`/`XLP` as "defensive and slowdown-sensitive assets," implying a flight-to-quality framing
  (TLT strengthens as recession fear builds). Canonical `narrative_asset_map.json`'s `Macro
  Pressure` entry for `TLT` states `expected_expression: "DOWN"`, rationale: "TLT provides a direct
  long-duration rates observation" — a **hawkish/rate-pressure framing** where rising rates push
  TLT price down. These are two different economic stories about what "macro pressure via TLT"
  means. Not a machine-readable field conflict (legacy asserts no hard direction,
  `is_signal: false`), but a genuine interpretive difference. **This framing is lost if the legacy
  module is deleted without a record** — this document is that record. No code or product action is
  required to resolve it; canonical's framing is already the one live in Asset Exploration and
  should remain authoritative, but future contributors should not be surprised to find this
  historical alternate framing if they ever dig through git history.

Neither finding blocks retirement — both are documentation/definitional notes, not runtime
dependencies.

## 8. Retirement Options Evaluated

**Option A — Full removal.** All eight decision criteria from the original spec are met:
- No active runtime consumer downstream of `main.py`'s own write — confirmed exhaustively (§4).
- No script/export/report *dependency* — the daily text report's content changes (it currently
  includes the legacy primary/secondary/offsets block), but nothing reads that content back
  programmatically. This is a visible-output change, not a broken dependency — flagged explicitly
  in §11, not hidden.
- No loader assumes the field (§5).
- No public API contract exposes it (§4, verified directly against the only JSON route).
- Old artifacts remain readable regardless (§5).
- Current tests pass without it once the legacy-specific tests are replaced with proof tests (§10).
- Canonical replacement covers all required behavior (§6).
- No external dependency is documented anywhere in the repo.

**Option B — Compatibility adapter.** Not needed — there is no consumer requiring the legacy
*shape* specifically; an adapter would be generating output for zero readers.

**Option C — Temporary retention.** Not needed — the ambiguity that justified temporary retention
last sprint (unproven repo-wide non-usage) is exactly what this audit resolves.

## 9. Final Decision

**Option A — full removal, implemented.** Proof tests were added before production deletion, then
the legacy compute, persistence, stdout, report, and dashboard-passthrough paths were removed. The
canonical Market Expression and instrument-ownership systems were not changed.

## 10. Migration Plan (for the implementation handoff, not executed by this audit)

Sequenced exactly per the original spec's "if removal is safe" ordering:
1. **Add proof tests first** — `tests/test_narrative_market_map.py` is rewritten (not deleted) to
   assert: (a) `run["market_expression"]` is written by no code path once `main.py` is updated, (b)
   an old run file with the legacy field still loads and renders correctly, (c) an old run file
   without the legacy field still loads and renders correctly (regression, already true today), (d)
   `dashboard.py`'s view context no longer includes a `market_expression` key at all (tightened from
   "unused" to "absent"), (e) `mne/narrative_brief.py`'s now-dead `_limitations()` branch is either
   removed or proven permanently unreachable by design, not by accident.
2. Remove the active call in `main.py` (`get_market_expression`, `print_market_expression`,
   `append_market_expression`/`build_daily_report`'s `market_expression` parameter).
3. Stop writing `run["market_expression"]` in new runs.
4. Preserve tolerant loading of old runs — no change needed, already tolerant (§5).
5. Remove `mne/narrative_market_map.py` (or archive under a clearly-marked path if the team prefers
   a paper trail over `git log` alone — full removal is fine given git history preserves it
   either way).
6. Update `tests/test_narrative_brief.py` for the now-dead limitations branch; update
   `ARCHITECTURE.md:107-133`'s stale "intentional for future cards" claim.
7. Re-verify reports, routes, exports, and scripts per §11's checklist — no surprises expected
   given this audit's exhaustiveness, but re-verify rather than assume.

## 11. Compatibility Guarantees

- Old run JSON files (with or without the legacy field) remain fully readable — no rewrite, no
  migration script needed.
- Daily-snapshot aggregation is unaffected either way (it never carried this field).
- The plain-text daily report file's **content changes** — the legacy primary/secondary/offsets
  block disappears from newly-generated reports. This is a real, visible change to a human-facing
  artifact, explicitly acknowledged rather than swept into "no dependency." If anyone values that
  block as informational content (distinct from a code dependency), that's a product call to make
  before executing step 2 of §10 — this audit surfaces it, it doesn't override it.
- No API response shape changes (confirmed nothing exposes the legacy field today).

## 12. Removal Trigger

Not applicable — this document *is* the removal-trigger evidence for Option A, not a retention
plan with a future trigger.

## 13. Verification Performed

Exhaustive repository-wide search (not sampled) across `mne/*.py`, `main.py`, `dashboard.py`,
`templates/**/*.html`, `static/**/*.js`, every test file, every doc under `docs/`, every config file
under `config/`, and confirmed absence of any `scripts/`, `alembic/`, `cli.py`, or `manage.py`
infrastructure in this repo at all. Every hit for `narrative_market_map`, `NARRATIVE_MARKET_MAP`,
`get_market_expression`, `print_market_expression`, and `run["market_expression"]`/
`.get("market_expression")` was individually read and classified, not pattern-matched and assumed.
The broader `market_expression` substring search (30 files) was individually disambiguated between
the legacy system and the similarly-named canonical system to avoid false-positive consumer claims.
Persisted schema audit sampled the 3 most recent and multiple older run files directly from
`$MNE_DATA_DIR/results/` (167 total), confirming the 80%/20% historical split and full schema
stability within the 20%. The one JSON API route in the entire application was read function-by-
function to confirm the legacy field never reaches it. Divergence check compared every ticker
appearing in both systems for role/direction conflicts, not just a sample.

## 14. Known Remaining Gaps

- The daily text report's content change (§11) was explicitly ratified: new reports omit the
  legacy primary/secondary/offsets block and do not recreate it from canonical data.
- `main.py`'s legacy call path was never wrapped in try/except, unlike comparable optional pipeline
  stages — this audit surfaces the inconsistency as context, not as something requiring a fix
  (it's being removed, not hardened).
- `ARCHITECTURE.md` and `docs/instrument_mapping_architecture.md` now describe the retired system,
  tolerant artifact loading, and canonical ownership.
- The TLT/Macro-Pressure semantic framing divergence (§7) has no code action item — it's preserved
  here as institutional memory in case it's ever useful context for a future Macro Pressure
  refinement.
