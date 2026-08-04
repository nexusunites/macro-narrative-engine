# Asset Exploration View — Implementation Handoff

## Purpose

Sector Isolation (structural + live participation + exchange-session-aware freshness, all now
shipped through `10e5308`) tells a user which sectors are connected to a narrative and how they're
currently behaving, but stops short of the actual instruments. This sprint completes the
Macro Discovery → Sector Isolation → Asset Exploration journey: a curated, deterministic view of
which specific assets express a narrative+sector, why, and whether they're currently confirming,
contradicting, or unavailable — reusing the exact classification/freshness machinery already built
for sectors rather than inventing a parallel system.

**Status: brief only, one grounding architecture decision below (data-forced, not a preference
call), ready to hand to Codex.**

Do not implement code from this document directly. This is the Codex-ready brief.

---

## Ratified Decisions (Daniel, 2026-08-04)

1. **Asset-universe count, corrected.** The prior draft of this handoff stated "15 tickers" while
   listing 19 — an uncaught arithmetic error, not a real number. Verified directly against
   `main.py:112-117` (`NASDAQ_TICKERS`), `mne/breadth.py:4-9` (`BREADTH_TICKERS`), and
   `config/sector_instruments.json` (11 sector entries) at the point of correction
   (2026-08-04): the canonical, deduplicated, persisted asset universe is **19 unique
   instrument symbols, zero overlap between the three source dicts** (checked by key and by
   ticker value — no name collides across `NASDAQ_TICKERS`, `BREADTH_TICKERS`, or the sector-slug
   keys `build_sector_ticker_map()` returns). Every count and reference below reflects 19, not 15.
2. **Asset mapping source — ratified.** Neither `config/market_expression_map.json` (mixes real
   tickers with synthetic, non-fetchable concepts) nor `mne/narrative_market_map.py` (mostly
   unfetched tickers) is the canonical asset map. A new, bounded, versioned map is built containing
   only instruments genuinely present in the persisted live market universe. Sparse coverage is
   acceptable and must be explained honestly, not padded.
3. **Structural/live-data boundary — ratified and binding, not just this sprint's default.**
   `mne/asset_exploration.py` owns curated structural relevance only. `mne/asset_participation.py`
   owns observed participation from persisted market data. `asset_exploration.py` must not import
   the participation or market-data module, ever — `dashboard.py` injects a plain participation
   dictionary into the presentation context. **Do not weaken this boundary later merely for
   convenience** — if a future sprint wants to skip the injection step, that is a decision requiring
   the same level of explicit ratification this one required, not a quiet shortcut.
4. **Participation vocabulary — ratified.** `MUTED` (asset-level) stays distinct from `DETACHED`
   (sector-level) — do not rename either for cross-surface uniformity. Definitions, binding:
   `MUTED` = fresh asset data exists, but current movement is limited. `UNAVAILABLE` = usable data
   is absent or stale. `CONTRADICTING` = fresh movement opposes an explicit expected direction.
   Structural relevance remains a separate field from all of the above, always.
5. **Entitlement behavior — ratified.** Follow the current access behavior of existing
   `/research/*` routes exactly — no new entitlement gating, no change to plan limits or packaging,
   this sprint. Any future gating decision is a separate, explicitly-named product/entitlement
   sprint, not a default this document sets.
6. **Sparse Energy coverage — ratified.** Do not add unfetched company tickers merely to make the
   Energy / Commodities page look more complete. Use only supported, persisted assets, and render a
   calm, honest limited-coverage state where the real universe is thin. Sector ETFs (`XLE` for
   Energy) may appear where genuinely supported, but must never be presented as if they were
   company-level assets — `asset_type: "ETF"` is shown, not implied away.

---

## Grounding Decision: build a new, bounded asset map — do not reuse either existing map as-is

Two existing files look like candidates for "the" narrative-to-asset map. Neither is directly
usable:

- **`config/market_expression_map.json`** (3 narratives, primary/secondary/offset instrument
  lists) mixes real tickers (`QQQ`, `NVDA`, `SMH`, `XLE`, `XLI`, `XLU`, `XLP`, `VIX`, `DXY`) with
  **synthetic, non-fetchable labels** — `CLOUD`, `DATA_CENTER`, `RATES`, `CRUDE_OIL`,
  `COMMODITY_FX`, `GROWTH_CONCERNS` — that never appear in `run["market_snapshot"]` and never will
  under the current fetch. It also has no sector linkage, display name, or asset-type field
  (`mne/market_expression.py:90-114`'s validated schema is only `{asset, label, role,
  confirming_direction|pressure_direction}`). Importing it wholesale would put permanently-
  `UNAVAILABLE` fake assets in front of users.
- **`mne/narrative_market_map.py`**'s `NARRATIVE_MARKET_MAP` (still live, wired through `main.py`
  into `run["market_expression"]` — not legacy/dead as previously assumed, confirmed via fresh
  read) is theme-keyed (`ai`/`energy`/`rates`/`inflation`/`recession`), not group-keyed, and while
  its listed tickers are real symbols (not synthetic labels), **most are not actually fetched**:
  `MSFT`, `AVGO`, `ANET`, `VRT`, `DELL`, `CVX`, `XOM`, `SLB`, `HAL`, `OXY`, `GLD`, `DBC`, `FCX`,
  `IEF`, `KRE`, `SHY` never appear in `market_snapshot` either. Same problem, different flavor.

**Decision**: build `config/asset_registry.json` and `config/narrative_asset_map.json` fresh,
bounded strictly to the **19 tickers actually fetched and persisted today** (confirmed via direct
read of `main.py:112-117,493-497`, `mne/breadth.py:4-9`, `config/sector_instruments.json` —
canonical list at §4): `QQQ`, `NVDA`, `VIX`, `DXY`, `SPY`, `RSP`, `QQQE`, `IWM` (8 macro/breadth),
and the 11 sector ETFs (`XLK`, `XLC`, `XLY`, `XLF`, `XLI`, `XLE`, `XLB`, `XLU`, `XLRE`, `XLP`,
`XLV`) — 19 total, no overlap between the two groups. Rationale language may borrow from the two
existing maps' real-ticker entries where they overlap (no need to write new prose for `QQQ`/`NVDA`
from scratch), but the synthetic/unfetched entries are not imported — satisfying the original
spec's own instruction to reuse *or normalize*, not duplicate broken truth. This is a data-fidelity
conclusion forced by the audit, not a product preference — no sign-off needed to proceed.

---

## 1. Objective Summary

Add a bounded, curated asset registry and narrative-to-asset map covering only real, persisted
tickers; a read-only classification module reusing the exact sector-sprint pattern (curated
structural role, kept separate from real participation computed from `run["market_snapshot"]` via
the same session-aware freshness already built in `mne/market_calendar.py`); a sector-scoped
Asset Exploration route; and an "Explore assets" link from Sector Isolation. No charts, no
recommendation language, no new market-data fetching, no large ticker-universe expansion.

## 2. Files Changed

**Create:**
- `config/asset_registry.json` — canonical registry, 19 entries, ticker-keyed (§4).
- `config/narrative_asset_map.json` — curated narrative→asset structural map (§5).
- `mne/asset_participation.py` — real classification module: reads `run["market_snapshot"]`,
  calls `mne.market_calendar`'s existing session-aware freshness function directly (already
  generic, not sector-specific — no need to duplicate it), applies the same
  `STRONG_MOVE_PCT`/`MEANINGFUL_MOVE_PCT`/epsilon thresholds already calibrated for sectors
  (`mne/sector_market_context.py:17-19`) for cross-codebase consistency, returns a plain dict.
  **Named to avoid the substring collision already found and worked around in the sector
  sprint** — `sector_market_context` contains the literal string `market_context`, which broke a
  test guard there; `asset_participation` contains neither `market_context` nor `sector_isolation`
  as a substring, so it's safe to reference from documentation and tests without that trap
  resurfacing.
- `mne/asset_exploration.py` — pure, read-only module (structural data + curated rationale +
  breadth), mirroring `mne/sector_isolation.py`'s shape exactly: `build_asset_exploration_context(...)`
  accepts a precomputed participation dict as a parameter, **never imports
  `asset_participation`, `market_context`, `sector_market_context`, or `yfinance`** — same
  architectural boundary that protects `sector_isolation.py` today, extended to this new module
  from day one instead of being retrofitted later.
- `templates/asset_exploration.html`, `templates/_partials/asset_grid.html`.
- `tests/test_asset_exploration.py`, `tests/test_asset_participation.py`.
- `docs/narrative_asset_model.md`.

**Modify:**
- `dashboard.py` — register the new route (§6) between the existing `/sectors` block (ends line
  ~2509) and the catch-all `/research/{key:path}` (line 2512) — same ordering requirement already
  solved once for `/sectors` itself, just one more entry in the same list, not a new problem to
  re-derive. Compute the participation dict via `asset_participation` and pass it into
  `build_asset_exploration_context(...)`, mirroring the exact `dashboard.py`-as-sole-integration-
  point pattern already established for sectors.
- `templates/sector_isolation.html` — add an "Explore assets" link per mapped sector, pointing at
  the new route, following the existing `href` pattern already present on sector rows
  (`mne/sector_isolation.py:136`, currently an in-page anchor — this becomes a real page link).
- `mne/presentation_language.py` — add `ASSET_EXPLORATION_COPY` + `asset_exploration_copy(key)`,
  following the exact established `{FEATURE}_COPY` dict + accessor-with-`KeyError` pattern (11
  existing copy blocks all follow this shape, e.g. `sector_isolation_copy` at
  `presentation_language.py:163-164`).
- `static/styles.css` — asset card grid styling, reusing the sector heatmap's tile-card visual
  language and two-hue token budget — no new colors.
- Route-ordering tests, design-system structure tests — extend for the new route.

**Do not touch:** `mne/sector_isolation.py`, `mne/sector_market_context.py`,
`mne/market_calendar.py`, `mne/market_expression.py`, `mne/narrative_market_map.py`,
`config/market_expression_map.json`, `config/narrative_sector_map.json`,
`config/sector_instruments.json`, `main.py`'s fetch call, scoring, taxonomy, entitlements module
internals.

## 3. Asset-Data Audit

- **Real, persisted universe today, confirmed exhaustively (not approximated): 19 tickers, zero
  overlap.** `QQQ`, `NVDA`, `VIX` (`^VIX`), `DXY` (`DX-Y.NYB`), `SPY`, `RSP`, `QQQE`, `IWM` — 8
  macro/breadth instruments (`main.py:112-117`, `mne/breadth.py:4-9`) — plus 11 sector ETFs from
  `config/sector_instruments.json` (`XLK`, `XLC`, `XLY`, `XLF`, `XLI`, `XLE`, `XLB`, `XLU`,
  `XLRE`, `XLP`, `XLV`). `8 + 11 = 19`, confirmed with no name or ticker-value collision between
  the two groups — the naive sum is also the correct deduplicated count here, but this was verified
  directly (`main.py:495`'s dict merge `{**NASDAQ_TICKERS, **BREADTH_TICKERS, **sector_tickers}`),
  not assumed. Sector entries are keyed in `market_snapshot` by **sector slug**, not ticker symbol
  (`mne/market_context.py:7,23` uses the fetch dict's name key) — asset lookups for sector ETFs
  must key off the sector slug, not assume ticker-symbol keys uniformly across the whole snapshot.
- **Everything else referenced anywhere in this codebase's config or Python (SMH, CLOUD,
  DATA_CENTER, RATES, CRUDE_OIL, COMMODITY_FX, GROWTH_CONCERNS, MSFT, AVGO, ANET, VRT, DELL, CVX,
  XOM, SLB, HAL, OXY, GLD, DBC, FCX, IEF, KRE, SHY) has no real market data and never will under
  current fetch scope.** These are explicitly excluded from `config/asset_registry.json`, not
  included-and-marked-unavailable — an asset with zero path to ever becoming available doesn't
  belong in a registry meant to represent "what MNE tracks," per the spec's own "do not invent
  asset relevance" principle extended to registry membership itself.
- **`mne/sector_isolation.py` already exposes one asset per sector for free.** Each sector row
  carries `instrument`/`instruments` (the sector's ETF ticker, e.g. `"XLK"` for technology,
  `mne/sector_isolation.py:126`). Asset Exploration should **reuse this existing computed value for
  the sector-ETF row**, not recompute it independently — single source of truth for that one
  instrument's participation state, avoiding two slightly-different classifications of the same
  ETF on two pages.
- **Real per-run sector observations are still zero** in the live store as of the last calibration
  audit (`docs/sector_participation_calibration.md`, 2026-08-04) — sector fetching is code-complete
  but hasn't produced persisted data yet. Asset Exploration inherits this same reality for its
  sector-ETF rows; broad-market rows (`QQQ`/`NVDA`/`VIX`/`DXY`/breadth) have been fetched for
  longer and are more likely to have real recent observations, but this handoff does not assume a
  specific data state — the UI must render correctly whether data is populated or entirely absent
  (§14).
- **Existing routes/entitlements**: none of `/research/{key:path}`, `/history`, or `/sectors`
  gate on authentication or entitlements today (`dashboard.py:2429-2525` — no `user` dependency, no
  `require_entitlement` call anywhere in their handlers or context builders, confirmed by direct
  read). This differs from `/history/*` routes, which do gate via `require_authenticated_user`/
  `require_entitlement` (`mne/entitlements.py`). **Decision: match the `/sectors` precedent — no
  new gating introduced.** Adding entitlement tiering to Asset Exploration would be a deliberate
  product change outside this sprint's scope (not requested, not a stated non-goal either — flagged
  explicitly here so it isn't assumed silently in either direction).

## 4. Asset-Registry Summary

`config/asset_registry.json`, versioned, ticker-keyed, bounded to all 19 real, fetchable tickers
(the example below shows 3 of the 19 for brevity — the actual deliverable must contain all 19,
listed in full in §3):

```json
{
  "version": "1.0.0",
  "assets": {
    "QQQ": {
      "display_name": "Invesco QQQ Trust",
      "asset_type": "ETF",
      "sector_key": null,
      "broad_market_role": "GROWTH_INDEX",
      "display_enabled": true
    },
    "NVDA": {
      "display_name": "NVIDIA Corporation",
      "asset_type": "EQUITY",
      "sector_key": "technology",
      "broad_market_role": null,
      "display_enabled": true
    },
    "VIX": {
      "display_name": "CBOE Volatility Index",
      "asset_type": "INDEX",
      "sector_key": null,
      "broad_market_role": "VOLATILITY",
      "display_enabled": true
    }
  }
}
```

`sector_key` is `null` for broad-market/context instruments (`QQQ`, `VIX`, `DXY`, `SPY`, `RSP`,
`QQQE`, `IWM`) and set for company-level or sector-ETF entries (`NVDA` → `technology`, each sector
ETF → its own sector). `broad_market_role` (`GROWTH_INDEX`/`VOLATILITY`/`CURRENCY`/`BREADTH`) is
populated only where `sector_key` is `null` — mutually exclusive with `sector_key`, validated as
such.

**Canonical 19-entry list Codex must produce** (ticker → `asset_type`, `sector_key`,
`broad_market_role`):

| Ticker | `asset_type` | `sector_key` | `broad_market_role` |
|---|---|---|---|
| QQQ | ETF | `null` | `GROWTH_INDEX` |
| NVDA | EQUITY | `technology` | `null` |
| VIX | INDEX | `null` | `VOLATILITY` |
| DXY | INDEX | `null` | `CURRENCY` |
| SPY | ETF | `null` | `BREADTH` |
| RSP | ETF | `null` | `BREADTH` |
| QQQE | ETF | `null` | `BREADTH` |
| IWM | ETF | `null` | `BREADTH` |
| XLK | ETF | `technology` | `null` |
| XLC | ETF | `communication_services` | `null` |
| XLY | ETF | `consumer_discretionary` | `null` |
| XLF | ETF | `financials` | `null` |
| XLI | ETF | `industrials` | `null` |
| XLE | ETF | `energy` | `null` |
| XLB | ETF | `materials` | `null` |
| XLU | ETF | `utilities` | `null` |
| XLRE | ETF | `real_estate` | `null` |
| XLP | ETF | `consumer_staples` | `null` |
| XLV | ETF | `health_care` | `null` |

`asset_type: "ETF"` for every sector instrument is deliberate and required (§Ratified Decisions
item 6) — a sector ETF must never be presented as a company-level asset, even where it's the only
supported instrument for that sector's page.

Fail closed (`AssetRegistryError(ValueError)`, mirroring `SectorIsolationError`) on: duplicate
ticker, invalid `sector_key` (not in `mne.sector_isolation.SECTOR_KEYS` when set), malformed
`version`, missing `display_name`, invalid `asset_type`, invalid `display_enabled` type, or a
`sector_key`+`broad_market_role` both set/both null simultaneously.

## 5. Narrative-to-Asset Mapping Behavior

`config/narrative_asset_map.json`, versioned, mirroring `config/narrative_sector_map.json`'s shape:

```json
{
  "version": "1.0.0",
  "narratives": {
    "AI / Tech Growth": {
      "assets": [
        {
          "ticker": "NVDA",
          "role": "PRIMARY",
          "expected_expression": "UP",
          "rationale": "NVIDIA is one of the clearest company-level expressions of the AI infrastructure narrative.",
          "display_enabled": true
        },
        {
          "ticker": "QQQ",
          "role": "SECONDARY",
          "expected_expression": "UP",
          "rationale": "QQQ provides broad exposure to large-cap growth and technology companies connected to the AI-led narrative.",
          "display_enabled": true
        },
        {
          "ticker": "VIX",
          "role": "OFFSET",
          "expected_expression": "DOWN",
          "rationale": "Falling volatility is consistent with confidence in growth-oriented narratives; rising volatility can pressure them.",
          "display_enabled": true
        }
      ]
    }
  }
}
```

Roles: `PRIMARY`, `SECONDARY`, `OFFSET`, `CONTEXT` — never `BUY`/`SELL`/`LONG`/`SHORT`/`HEDGE`
(grep-tested, §16). `expected_expression` reuses the exact `UP`/`DOWN` field convention already
established in `config/narrative_sector_map.json`, not a new vocabulary.

**Initial curated set** (sparse, bounded to real tickers, following the "sparse and credible over
dense and decorative" precedent already set in the relationship and sector-map sprints):

- **AI / Tech Growth**: `NVDA` (`PRIMARY`), `QQQ` (`SECONDARY`), `VIX` (`OFFSET`). Per the original
  spec's own explicit instruction, `DXY` is deliberately **not** mapped here — "DXY may create
  pressure but should not be interpreted as a direct asset expression without explicit mapping,"
  and no explicit mapping is being written for this narrative.
- **Energy / Commodities**: no company-level asset exists in the fetched universe (`XLE` is
  reachable only via the sector-ETF row, not duplicated here — see §9 on avoiding double
  classification). This narrative's asset map is intentionally near-empty this sprint — an honest
  reflection of coverage, not a bug (§13).
- **Macro Pressure**: `VIX` (`PRIMARY`), `DXY` (`PRIMARY`), `QQQ` (`OFFSET`), `NVDA` (`OFFSET`) —
  matches `config/market_expression_map.json`'s real-ticker subset for this narrative almost
  exactly, confirming the normalization approach (§Grounding Decision) preserves the parts of the
  existing curation that were already sound.

`Geopolitical Risk` remains unmapped — consistent with its existing gap across relationships,
market expression, and sector mapping; not this sprint's job to close.

Fail closed on: unknown narrative (not in `NARRATIVE_GROUPS`), unknown ticker (not in
`asset_registry.json`), duplicate ticker within a narrative's asset list, invalid role, missing
`rationale`, missing `expected_expression` for `PRIMARY`/`SECONDARY`/`OFFSET` roles (optional for
`CONTEXT`, matching the sector map's precedent of requiring direction only where a directional
claim is meaningful).

## 6. Structural-Role Behavior

Fully separate from participation, same discipline as sectors: `structural_role` never changes
based on classification output, and — per the ratified sector-sprint decision carried forward for
consistency — role never gates *which* participation states are reachable. An `OFFSET`-role asset
can classify as `STRONG` on a large, correctly-directional move exactly like a `PRIMARY`-role
asset; only the curated `expected_expression` and the real data determine the outcome.

## 7. Participation-State Rules

Six states — note the spec's own naming here uses `MUTED` rather than sectors' `DETACHED` for the
near-zero-move case. **Keep this distinction deliberately** — it avoids the exact dual-meaning
naming collision already identified in the sector sprint, where `DETACHED` means one thing as a
structural role and another as a participation state. Do not "fix" this by renaming `MUTED` to
match sectors; the difference is a feature, not an inconsistency to resolve.

`mne/asset_participation.py`, same precedence shape as `mne/sector_market_context.py`'s (post the
already-ratified EMERGING-role-cap removal — role never restricts state here either, so there's no
analogous cap to avoid introducing):

1. Instrument not `display_enabled`, no `market_snapshot` record, freshness not `FRESH`
   (via `mne.market_calendar`), or no `expected_expression` on the mapping → `UNAVAILABLE`.
2. `pct_change` fails to parse → `UNAVAILABLE`.
3. `|pct_change| < DETACHED_MOVE_EPSILON` (reuse the sector sprint's `0.01` value) → `MUTED`.
4. Not aligned with `expected_expression` and `|pct_change| >= MEANINGFUL_MOVE_PCT` (reuse `0.25`)
   → `CONTRADICTING`.
5. Aligned and `|pct_change| >= STRONG_MOVE_PCT` (reuse `1.0`) → `STRONG`.
6. Aligned and `|pct_change| >= MEANINGFUL_MOVE_PCT` → `PARTICIPATING`.
7. Aligned and `|pct_change| > 0` → `EMERGING`.
8. Else → `MUTED`.

Never derived from headline counts, narrative score, sector participation state, structural role,
another asset's movement, or unsupported proxies — each asset's state comes only from its own
`market_snapshot` record.

## 8. Expected-Direction Behavior

Curated per narrative+asset pairing in `config/narrative_asset_map.json`, never inferred from role
name (`PRIMARY` does not imply `UP` — `VIX` is `PRIMARY` for Macro Pressure with no fixed
directional assumption baked into the role itself, direction is a separate field). No ad hoc
direction rules in route handlers or template logic — `asset_participation.py` is the only place
direction is evaluated, mirroring the sector sprint's boundary discipline exactly.

## 9. Asset Breadth Behavior

`compute_asset_breadth(...)`, same precedence shape as sector breadth
(`mne/sector_market_context.py:133-148`): any `CONTRADICTING` present → `CONTRADICTED`; `confirming
>= 3` (`STRONG`/`PARTICIPATING`) → `BROAD`; `== 2` → `MODERATE`; `== 1` → `CONCENTRATED`; else any
`EMERGING` → `LIMITED`; else → `UNAVAILABLE`. Given most narratives this sprint have only 1-3 real
mapped assets (§5), breadth will realistically land on `CONCENTRATED`/`LIMITED`/`UNAVAILABLE` far
more often than `BROAD` — this is the honest output of a genuinely bounded universe, not a
threshold bug. Never call one confirming asset "broad" (matches the spec's explicit instruction);
the `>= 3` threshold already prevents this structurally.

## 10. Sector Isolation Integration

"Explore assets" link added to each mapped sector row in `templates/sector_isolation.html`,
pointing at the new route (§11), reusing the sector row's existing `href`-building convention
(`mne/sector_isolation.py:136`) as the pattern to extend rather than a new one to invent. No large
new dashboard section — the dashboard's existing Sector Isolation preview is unchanged; Asset
Exploration is reached only by drilling in from the dedicated Sector Isolation page or (once built)
directly via URL, matching the spec's explicit "Narrative → Sector → Assets" transition model.

## 11. Dedicated Asset Exploration Behavior

**Route: `GET /research/{key:path}/sectors/{sector}/assets`** — sector-scoped, chosen over the
narrative-wide alternative because it matches the emphasized Narrative → Sector → Asset journey and
avoids introducing a second, largely-redundant route this sprint. Registered between the existing
`/sectors` route block and the catch-all `/research/{key:path}` (§2) — same ordering discipline
already solved once for `/sectors` itself.

**Sector-less `CONTEXT`/`OFFSET` assets are not orphaned by the sector-scoped route.** `VIX`, `DXY`,
`QQQ` (when `sector_key: null`) appear on **every** sector-scoped assets page for their narrative,
under a visually distinct "Broader context" subsection — never mixed into the sector-specific list
without a clear boundary, so a user never wonders why `VIX` shows up under "Technology." This
avoids needing a second narrative-wide route just to house 1-3 context assets.

Page sections, per the original spec:
- **A. Orientation**: selected narrative, selected sector, concise explanation, current narrative
  direction (reused from existing Explanation Layer / Market Expression context, not recomputed),
  sector structural + participation context (reused directly from `build_sector_isolation_context`'s
  existing output for this sector, not duplicated).
- **B. Asset grid**: asset name (primary), ticker (secondary, small), structural role, current
  participation, concise plain-English explanation, latest persisted move where useful (not
  leading), freshness (reusing the exact freshness label copy already established for sectors),
  link to Research context for that narrative.
- **C. Breadth summary**: §9's output, plain-English framing.
- **D. Evidence and limitations**: why each asset is mapped, what current data shows, what's
  missing — no recommendation language anywhere on this page (§13).

## 12. X-Ray Behavior

Reuse the existing `<details data-*-xray>` disclosure pattern already established for the
constellation and sector heatmap — not a new interaction model. Asset X-Ray reveals: ticker,
structural rationale, expected direction, latest move classification, freshness, sector
relationship, Market Expression role where one genuinely exists for that ticker (only for the
handful of tickers that appear in both `config/narrative_asset_map.json` and
`config/market_expression_map.json`'s real-ticker subset — do not fabricate a cross-reference for
tickers that don't appear in both), and limitations. No charts, no candles — explicit non-goal,
unchanged from the original spec.

## 13. Data-Honesty Behavior

Required, always-present copy:
- *"Asset relationships are curated from MNE's narrative model."*
- *"Current participation reflects available persisted market data."*
- *"Unavailable assets are not assumed to be detached."*
- *"This view describes current market expression and is not a recommendation."*

Never: best asset, top pick, strongest opportunity, likely winner, expected return, optimal entry,
conviction score — grep-tested alongside the existing prohibited-terms pattern already used for
sectors. Given how sparse the real asset universe is (§3, §5), the honesty copy carries real weight
this sprint — several narratives will show only one or two assets, and the page must read as
"here's what we can honestly show" rather than implying broader coverage exists.

## 14. Mobile / Accessibility Behavior

Same requirements already met by the sector heatmap, extended to asset cards: semantic
links/buttons, full keyboard navigation, visible focus states, no color-only meaning (role and
participation both carry text labels, not just accent color), no hover-only essential content,
390px stacked card layout with no horizontal overflow, `prefers-reduced-motion: reduce` support,
full JS-disabled server-rendered usefulness, and screen-reader labels naming asset, role, and
participation together (not three separate unlabeled elements).

## 15. Existing-Feature Preservation

Do not modify: `mne/sector_isolation.py`, `mne/sector_market_context.py`,
`mne/market_calendar.py`, `mne/market_expression.py`, `mne/narrative_market_map.py`, Narrative
Constellation, Cross-Group Relationships, Explanation Layer, Narrative History, Historical
Connections, Evidence Reader, AI Analyst, authentication/entitlements/personalization/alerts,
admin separation. This sprint is additive: two new config files, two new Python modules, one new
route, one new link on an existing page.

## 16. Safety and Language Verification

- No `BUY`/`SELL`/`LONG`/`SHORT`/`HEDGE`-as-recommendation, no best-asset/top-pick/conviction-score
  language anywhere in `ASSET_EXPLORATION_COPY` or template copy (grep-tested).
- `mne/asset_exploration.py` imports neither `asset_participation`, `market_context`,
  `sector_market_context`, nor `yfinance` (test-enforced from day one, §2).
- No asset relevance inferred from price movement alone — every asset present in
  `config/narrative_asset_map.json` got there through curation, and every row rendered traces back
  to either that curated entry or the reused sector-ETF participation value (§3), never a
  freestanding "this ticker moved a lot" heuristic.
- No new market-data provider, no scoring/taxonomy mutation, no fetch during page render
  (`asset_participation.py` classifies already-persisted `run["market_snapshot"]` data only).

## 17. Verification Performed

Read-only research pass, no code written: confirmed `10e5308` shipped exchange-session-aware
freshness (`mne/market_calendar.py`, `docs/sector_participation_calibration.md`,
`scripts/audit_sector_observations.py`) since the last handoff; read
`config/market_expression_map.json` in full across all three narratives, identifying the exact
synthetic vs. real instrument split; read `mne/market_expression.py`'s config schema and loader
(lines 67-114); read `main.py`'s current fetch call (lines 493-497) and `mne/breadth.py`; read
`config/sector_instruments.json` fresh for the exact 11 sector→ticker pairs; read
`mne/sector_market_context.py` in full, confirming current constants and the now-shipped
session-aware `_freshness` (no longer the naive 36-hour check); read `mne/sector_isolation.py` in
full, confirming the existing `instrument`/`instruments` fields and `href` pattern; read
`dashboard.py`'s exact current route registration order (lines 2429-2525) for `/research`,
`/history`, `/sectors`, and the catch-all; confirmed via fresh grep that no asset registry, asset
type field, or narrative-asset map exists anywhere yet; confirmed `mne/narrative_market_map.py` is
**not** legacy/unused (corrected from an earlier research pass) — it's actively wired through
`main.py` into `run["market_expression"]` and rendered in `dashboard.py`; confirmed no
`/research/*` route currently gates on authentication or entitlements, contrasted against the
`/history/*` routes' `require_authenticated_user`/`require_entitlement` pattern; confirmed the
`{FEATURE}_COPY` + accessor pattern remains stable across all 11 existing copy blocks in
`mne/presentation_language.py`. Codex must run the commands in §Verification Commands after
implementing — nothing here substitutes for that.

## 18. Known Remaining Gaps

- **The real asset universe is genuinely narrow** — 19 tickers total, and only `NVDA`/`QQQ` are
  company-level (everything else is an index, volatility measure, currency proxy, or sector ETF).
  Energy / Commodities' asset map is nearly empty as a direct, honest consequence. This is the
  sprint's central, deliberate boundary (§Grounding Decision), not an oversight.
- **Two competing narrative→instrument sources now exist and remain unreconciled**:
  `config/market_expression_map.json` (narrative-level aggregate classification, includes synthetic
  labels) and the new `config/narrative_asset_map.json` (asset-level curation, real tickers only).
  They serve different purposes and were deliberately not merged this sprint — reconciling or
  visibly cross-linking them is a real future opportunity, not solved here.
- `mne/narrative_market_map.py` remains a third, separate, actively-used narrative→instrument
  source (`run["market_expression"]`, theme-keyed) — three overlapping-but-distinct systems now
  coexist in this codebase. Worth a dedicated consolidation sprint, explicitly out of scope here.
- `Geopolitical Risk` remains unmapped across relationships, sector map, market expression, and now
  asset map — a fourth consecutive sprint carrying this same gap forward.
- No Playwright/browser suite exists for visual verification of the new asset cards — manual visual
  pass required (§Verification Commands).

## 19. Recommended Next Sprint

Per the original spec's own two-step scope instruction: **Asset Coverage Expansion** — a named,
explicitly-approved follow-up deciding whether to expand the live fetch beyond today's 19 tickers
(candidates already exist in `mne/narrative_market_map.py`'s unfetched entries: `MSFT`, `AVGO`,
`XOM`, etc.) to give Energy / Commodities and other sparse narratives a credible company-level
asset view. Also worth prioritizing: (2) reconcile or clearly cross-link the three
narrative→instrument sources (§18), (3) close the `Geopolitical Risk` gap across all four curated
layers in one consolidated pass rather than a fifth separate follow-up, (4) revisit whether
Asset Exploration warrants entitlement gating once real usage patterns are visible.

## 20. Whether Asset Exploration View Can Be Marked Implemented

**Not implemented — ready to hand to Codex.** The one grounding decision (§Grounding Decision) is
data-forced and needs no further ratification. Mark this feature implemented only after Codex
completes the scoped work and every command below passes.

---

## Tests Required (mapped to original spec §18, adjusted for confirmed current architecture)

1. Asset registry loads deterministically.
2. Duplicate ticker fails validation.
3. Invalid `sector_key` fails validation.
4. Narrative asset map validates against `asset_registry.json` and `NARRATIVE_GROUPS`.
5. Unknown narrative fails validation.
6. Unknown ticker (not in the registry) fails validation.
7. Duplicate narrative-asset mapping fails validation.
8. Hidden (`display_enabled: false`) asset excluded from public display.
9. Structural role remains fully separate from participation, including reachability — an
   `OFFSET`-role asset can reach `STRONG` (consistency with the ratified sector-sprint decision).
10. `STRONG` participation fixture.
11. `PARTICIPATING` fixture.
12. `EMERGING` fixture.
13. `MUTED` fixture (near-zero move, distinct enum from sector `DETACHED`).
14. `CONTRADICTING` fixture.
15. `UNAVAILABLE` fixture (each fail-closed path: missing config, missing snapshot record, stale,
    missing `expected_expression`).
16. Missing `expected_expression` fails closed to `UNAVAILABLE`.
17. Freshness reuses `mne.market_calendar`'s existing session-aware function directly — a test
    asserting no independent/duplicated freshness logic exists in `asset_participation.py`.
18. Asset breadth reconciles against a fixed fixture set.
19. Sector-specific asset filtering works (sector-scoped route shows only that sector's assets plus
    the broader-context subsection).
20. The sector-ETF row's participation value matches `mne.sector_isolation`'s own computed value
    exactly — proving reuse, not duplicate computation (§3).
21. Route ordering is safe — the new route resolves correctly and is not swallowed by the
    `/research/{key:path}` catch-all.
22. Sector Isolation page links to Asset Exploration for mapped sectors only (not unmapped ones).
23. Asset cards render plain-English rationale as the lead content, not the ticker or percentage.
24. Ticker renders as secondary text (template assertion).
25. Raw enums (`PRIMARY`, `MUTED`, etc.) never render as primary copy.
26. X-Ray reveals technical details (ticker, direction, freshness, sector relationship) together.
27. JavaScript-disabled page remains fully useful.
28. Keyboard navigation works (card focus, activation, visible focus ring).
29. 390px has no horizontal page overflow; stacked card layout confirmed.
30. Empty (no assets mapped for a sector) and partial-coverage states render calmly, not as a
    misleading empty grid.
31. No market-data fetch occurs during page rendering.
32. No new provider is introduced.
33. No asset relevance is inferred from price movement alone (a fixture with a large move on an
    unmapped ticker never produces a row).
34. No prediction or trade language appears anywhere in `ASSET_EXPLORATION_COPY` or rendered output.
35. Existing `tests/test_sector_isolation.py` suite remains green, unmodified.
36. Existing `tests/test_market_expression.py` suite remains green, unmodified.
37. Existing Research Workspace and dashboard tests remain green.
38. Same input produces byte-identical context
    (`json.loads(json.dumps(..., sort_keys=True))` round-trip, matching the established pattern).
39. Full test suite passes apart from any documented pre-existing failures unrelated to this
    sprint.

## Verification Commands (run after implementation, not before)

- `python -m unittest tests.test_asset_exploration -v`
- `python -m unittest tests.test_asset_participation -v`
- `python -m unittest tests.test_sector_isolation -v`
- `python -m unittest tests.test_sector_market_context -v`
- `python -m unittest tests.test_market_expression -v`
- Focused route-ordering and design-system structure tests
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `node --check static/asset_exploration.js` (only if that file is added)
- `git diff --check`

Manual verification: AI / Tech Growth, Energy / Commodities (near-empty asset map — confirm it
renders calmly, not broken), Macro Pressure; a mapped sector with assets and one with none; fresh,
stale, partial, and unavailable data states; logged-out, authenticated Free, and Pro/internal-access
users (confirm identical access, matching the no-new-gating decision, §3); 1280px, 1024px, 390px;
keyboard-only; reduced motion; JavaScript disabled. Confirm the Narrative → Sector → Asset path
reads as an obvious progression, every asset has a clear curated reason for being shown, ticker and
price movement stay visually secondary to the plain-English explanation, and the page feels
exploratory rather than advisory at every state — especially the sparse ones, where the honest
"here's what we can show" framing matters most.

Implement to a verified local state and stop — do not stage, commit, or push.
