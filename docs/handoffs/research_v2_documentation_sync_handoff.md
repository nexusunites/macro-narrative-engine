# Research-Tier & v2 Presentation Documentation Synchronization — Implementation Handoff

**Status: ready to hand to Codex. Do not implement in this authoring session; do not stage, commit, or push.**
**Author:** Claude (orchestrator) · **Implements:** Codex, from this document only · **Verify:** per the checklist at the end, before Daniel commits.
**Sibling handoff:** `docs/handoffs/studio_documentation_sync_handoff.md` already covers the Studio surface — **do not re-document Studio here.** This handoff covers everything that sync explicitly deferred: the Research-tier v2 rework and its supporting engine layers.

## What this is (and is NOT)

A **documentation-only** synchronization. An entire wave of shipped work — the v2 Research tier (finder, restyled investigation, Stories/Sectors/Assets surfaces), the per-asset execution view with event markers, the v2 visual system, the Overview candlestick, and the engine modules that back them — is **absent** from the canonical current-state docs, and in two places the docs assert the **opposite** of current reality. This brings the docs into agreement with verified implementation, using the same discipline as the Studio sync: record what is true, distinguish bounded-now from generally-future, preserve historical documents' scoped meaning, and never over-claim.

**No application code, tests, schemas, templates, static assets, migrations, config, or runtime behavior may change.** Prose only, in the files named in Scope. If you touch anything under `mne/`, `dashboard.py`, `templates/`, `static/`, `alembic/`, `config/`, or `tests/`, stop.

## Why this is needed (the problem, precisely)

- `docs/project_status.md` and `docs/product_backlog.md` contain **zero** mentions of the finder, per-asset execution view, event markers, story registry, Stories module, Sectors module, "On the clock," the v2 top bar, or the Overview candlestick (verified 2026-08-15).
- Two `project_status.md` "Known Limitations" lines are now **false**:
  - L95: *"Several dashboard areas still share the same main surface instead of having dedicated navigation pages."* — the v2 top bar plus dedicated Research finder, Sectors, Assets, and Studio pages largely resolve this.
  - L96: *"Market Expression Map is not yet available as a first-class view linking narratives to market instruments or expressions."* — the Sectors and per-asset execution views now link narrative → sector → instrument with price history and event markers. A first-class view exists; only **broader coverage** remains future.
- `ARCHITECTURE.md` ("how the engine works," Module Direction §) does not mention the new engine modules: `story_extraction.py`, `story_registry.py`, `asset_price_history.py`, `asset_events.py`, `asset_exploration.py`, `asset_participation.py`, `sector_isolation.py`, `sector_market_context.py`.

The fix: record the shipped surfaces and modules, correct the two contradictions honestly (bounded, not blanket), extend ARCHITECTURE.md's module map, and note the retirements — without rewriting any historical spec.

---

## Verified implementation ground truth (authoritative inventory)

Verified against the codebase on 2026-08-15. Each surface maps to a route/template, a backing module, and a canonical reference handoff. **Codex must confirm each claim against its cited handoff and the code before writing it; do not assert anything you cannot verify.**

**Research-tier v2 surfaces (Sprints J–N, plus E and G–I prerequisites):**

| Surface | Route(s) | Template | Backing module(s) | Reference handoff(s) | Commit |
|---|---|---|---|---|---|
| v2 top bar across research tier | (all `/research*`) | shared chrome | — | `research_v2_shell_handoff.md` | Sprint J `5e63b4c` |
| Research finder + narrative index | `GET /research` | `research_selector.html` | `narrative_history.py` (index inputs) | `research_v2_shell_handoff.md` | Sprint K `0400703` |
| v2 investigation restyle + charts + "On the clock" | `GET /research/{key}` | `narrative_investigation.html` | — | `research_v2_shell_handoff.md` | Sprint L `15bc7e2` |
| Stories module (per-story attention cloud) | in investigation | `narrative_investigation.html` | `story_extraction.py`, `story_registry.py` | `story_extraction_handoff.md` | Sprints E `9094112` / M `00e0521` |
| Sectors module + sector isolation | `GET /research/{key}/sectors` | `sector_isolation.html` | `sector_isolation.py`, `sector_market_context.py`, `asset_participation.py` | `cross_sector_heatmap_sector_isolation_handoff.md`, `sector_market_data_plumbing_handoff.md`, `sector_participation_calibration_handoff.md` | Sprint M `00e0521` |
| Asset exploration view | `GET /research/{key}/sectors/{sector}/assets` | `asset_exploration.html` | `asset_exploration.py`, `asset_participation.py` | `asset_exploration_view_handoff.md`, `asset_coverage_expansion_consolidation_handoff.md` | — |
| Per-asset execution view + candlestick | `GET /research/{key}/sectors/{sector}/assets/{ticker}` | `asset_execution.html` | `asset_price_history.py` | `asset_execution_view_handoff.md` | Sprint H `9f2585f` |
| Persisted event markers on execution view | (same) | `asset_execution.html` | `asset_events.py` (macro calendar + EDGAR company news) | `asset_execution_view_handoff.md`, `company_news_edgar_handoff.md` | Sprint I `9424043` |
| Story-level Saved + Research stars | write route + `/research` | research templates | `SavedStory` model (`mne/models.py:76`, table `saved_stories`) | `studio_foundation_handoff.md` (Sprint N) | Sprint N `9c881e9` |

**v2 visual system & chrome (dashboard rework wave, distinct from the July-2026 V1 rework already documented):**
- Design System v2 teal palette / v2 top bar / color-leading resaturation. Handoffs: `design_system_dashboard_foundation_handoff.md`, `dashboard_visual_rework_v2_handoff.md`, `color_leading_resaturation_handoff.md`, `dashboard_v2_sprint_recap_for_gpt.md`.
- Preferences/account brought onto the v2 teal palette (`preferences_account_v2_palette_handoff.md`, `0b1127e`).
- Cross-group narrative relationship surfacing (`cross_group_narrative_relationship_handoff.md`).

**Overview:**
- Overview "Markets Right Now" replaced by a primary-instrument **candlestick** (up=teal / down=price-only red), compact chip strip, click-through. Handoff `overview_markets_candlestick_handoff.md`; commit `7be4c8a`. Currently undocumented in `project_status.md`.

**Retirements / redirects (record as history, honestly):**
- Legacy narrative market map retired (`0c1d2d7`); constellation node graph replaced by the attention cloud (Sprint C `3cd5843`).
- User-facing history **compare** retired and redirected to Studio's Compare-over-time; surviving historical pages migrated to the v2 top bar/palette. Handoff `historical_tier_cleanup_handoff.md` (Sprints R1 `f32d60f`, R2 `7e5163d`).

---

## The three required semantic buckets (preserve these distinctions)

### A. Implemented — the v2 Research tier & supporting engine layers
The surfaces and modules in the inventory above are implemented and verified. Studio (in the sibling sync) is the conviction end of the same arc.

### B. Partially implemented — bounded now, general concept still future
- **Market Expression as a first-class view.** The Sectors and per-asset execution views now link narrative → sector → instrument with price and events for the **mapped** sectors/assets. This is a *bounded* realization. **Broader instrument/narrative coverage** ("Market Expression Map expansion," backlog L322) and **historical market-price context / narrative-vs-market outcome analysis** remain **future**.
- **Dedicated navigation pages.** The v2 tier gives Research/Sectors/Assets/Studio dedicated pages; if any admin/diagnostic areas still share a surface, say so specifically rather than claiming total resolution — verify before wording.

### C. Genuinely deferred — NOT implemented (must not be claimed)
- Narrative-vs-market **outcome analysis**, historical **market-price** reconstruction, **backtesting**.
- **Broader market coverage** for unmapped narratives/instruments.
- Predictions, recommendations, trade signals (permanently out of scope).

**Rule:** the existence of the Sectors/Assets views must never be used to claim broader coverage, outcome analysis, or price-history context beyond what actually ships for the mapped set.

---

## Scope — the ONLY files Codex may edit

1. `docs/project_status.md`
2. `docs/product_backlog.md`
3. `ARCHITECTURE.md`

Do not touch any other file. (Studio docs are handled by the sibling handoff; do not edit RWA or AGENTS.md here.)

---

## Change 1 — `docs/project_status.md`

Additive and corrective; preserve existing structure and the engine/intelligence sections.

1. **Add a Research-tier v2 capability block** under "## Current Capabilities" recording bucket A in canonical terminology: v2 top bar; Research **finder + narrative index**; restyled **Narrative Investigation** with charts and the **"On the clock"** catalyst read; the **Stories** module (curated story registry + deterministic story extraction; per-story attention cloud); the **Sectors** module (sector isolation, participation); the **Asset exploration** and **per-asset execution** views (price-history candlestick + persisted **event markers** from the macro calendar and EDGAR company news); and **story-level Saved + Research stars** (`SavedStory`). Frame these as **deterministic presentation of existing/adjacent intelligence** consistent with the RWA (no new scoring/taxonomy).
2. **Add an Overview note:** the Overview "Markets Right Now" section is now a primary-instrument **candlestick** with a compact status chip strip and click-through to the asset view (up=teal / down=price-only red). Cite `overview_markets_candlestick_handoff.md`.
3. **Add a v2 visual-system note** distinguishing it from the July-2026 V1 Dashboard Experience Rework already recorded: Design System v2 teal palette, generalized top bar, color-leading resaturation, preferences/account on the v2 palette. Cite the visual-rework handoffs. Preserve the color-budget discipline language (price-only red is legitimate on price surfaces).
4. **Correct the two false Known-Limitations lines** — honestly, per bucket B, not by blanket deletion:
   - L95 (shared main surface / no dedicated nav): rewrite to reflect that the v2 tier provides dedicated Research/Sectors/Assets/Studio pages; keep any genuinely-remaining shared-surface caveat only if verified.
   - L96 (Market Expression Map not a first-class view): rewrite to state a **bounded** first-class narrative→sector→instrument view now exists (Sectors + per-asset execution), while **broader coverage and historical price context remain future.**
5. **Add a "Recent Major Additions" entry** for the Research-tier v2 rework (one paragraph), citing `research_v2_shell_handoff.md` and the asset/sector/story handoffs.
6. **Record the retirements** briefly (legacy narrative market map; constellation→attention cloud; user history-compare→Studio) so their absence isn't later read as regressions. Do not delete the historical framing of prior features.
7. Do **not** claim anything in bucket C. Do not rewrite the Auth "Latest Product Milestone" (you may note that Studio + the Research v2 tier are the more recent product surfaces, cross-referencing the backlog).

## Change 2 — `docs/product_backlog.md`

1. **Add "Completed Foundations" bullets** (bucket A, precise scope, citing handoffs) for: **Research v2 Shell & Tier Rework** (finder/index, restyled investigation, Stories/Sectors wiring); **Sub-Narrative Story Extraction** (curated registry + deterministic extraction); **Sector Isolation & Participation**; **Asset Exploration & Per-Asset Execution View** (price history + persisted event feeds incl. EDGAR company news); **Design System v2 / v2 Visual Rework**; and the **Overview Markets Candlestick**.
2. **Reconcile Epic 1 and the "Market Expression Map expansion" item (L322)**: mark the **first-class narrative→instrument view Complete (bounded)**, and keep **broader coverage / historical price context / outcome analysis Future** (bucket B/C). Update the closing future-sequencing paragraph (≈L519) so it no longer implies the first-class view is unbuilt while still listing broader coverage, historical market-price context, and outcome analysis as future.
3. **Leave all bucket-C items Future**, unchanged in status (backtesting, outcome analysis, predictions/recommendations, broader coverage).
4. Do not alter the Historical Replay epic or unrelated epics.

## Change 3 — `ARCHITECTURE.md`

Bounded update to keep "how the engine works" honest:

1. **Extend the Module Direction section (≈L208)** to list the new engine modules with one-line responsibilities: `story_extraction.py`, `story_registry.py`, `asset_price_history.py`, `asset_events.py`, `asset_exploration.py`, `asset_participation.py`, `sector_isolation.py`, `sector_market_context.py`. Keep entries terse and consistent with existing module descriptions.
2. **Cross-reference** from the "Market Context" / "Market Expression and Instrument Ownership" sections to the new Sectors/Assets presentation surfaces and their handoffs, noting these **present** existing/adjacent deterministic outputs (no new scoring). Preserve the engine/experience/architecture boundary language.
3. Do not restructure ARCHITECTURE.md or edit unrelated sections.

---

## Required wording / semantic guardrails

- New engine modules and surfaces are described as **deterministic presentation / bounded market context**, never as prediction, outcome analysis, backtesting, or recommendation.
- Bucket-C terms appear **only** as future/out-of-scope. Bucket-B terms appear **only** as bounded-now / general-form-future.
- Price-only red is legitimate on price/candle surfaces; do not describe it as a color-budget violation. The user-dashboard two-hue budget language stays intact.
- Canonical engine terminology preserved; no new user-facing copy invented in docs (that lives in `mne/presentation_language.py`).
- No historical spec/handoff is rewritten to pretend later work already existed; corrections to `project_status.md` limitations are current-state fixes, not history edits.
- Every retirement is stated as such; do not silently erase prior features from the record.

---

## Verification (before Daniel commits — nothing staged/committed/pushed)

1. **No-code-change proof:** `git status --porcelain` shows only the three in-scope docs modified; nothing under `mne/`, `dashboard.py`, `templates/`, `static/`, `alembic/`, `config/`, `tests/`.
2. **Surfaces now discoverable:**
   - `rg -ni 'finder|per-asset|execution view|event marker|story extraction|sectors|candlestick|on the clock' docs/project_status.md` → non-empty.
   - `rg -ni 'story extraction|sector isolation|asset execution|candlestick|research v2' docs/product_backlog.md` → non-empty.
   - `rg -ni 'story_extraction|asset_price_history|asset_events|sector_isolation' ARCHITECTURE.md` → present.
3. **Contradictions resolved, honestly:**
   - `rg -n 'share the same main surface|Market Expression Map is not yet available' docs/project_status.md` → **no longer present** (or demonstrably rewritten in place); manual read confirms bounded phrasing, not over-claim.
   - Manual read: no doc claims broader market coverage, historical price context, outcome analysis, backtesting, prediction, or recommendation is implemented.
4. **Retirements recorded:** `rg -ni 'retired|redirect|attention cloud|market map' docs/project_status.md docs/product_backlog.md` → the retirements/redirects are noted.
5. **Link/path integrity:** every handoff/spec/module path cited by the new prose resolves (`ls`/`test -f`). No broken relative links.
6. **`git diff --check`** clean.
7. **Final full-diff review:** read the entire `git diff`; confirm additive/corrective prose only in the three files, buckets A/B/C respected, no history falsified, retirements honest.
8. **Nothing staged, committed, or pushed.**

## Out of scope (explicit)

- Any application code, template, static asset, schema, migration, config, or test change.
- Studio documentation (owned by `studio_documentation_sync_handoff.md`), RWA, and AGENTS.md.
- New user-facing copy.
- Rewriting or deleting historical spec/architecture prose (beyond correcting the two false current-state limitation lines in `project_status.md`).
- Re-verifying or re-deriving engine behavior beyond confirming each documented claim against its cited handoff and the code.
