# Overview "Markets Right Now" → Candlestick (Design Spec)

**Date:** 2026-08-14 · **Author:** Claude (orchestrator) · **Status:** approved design, pre-handoff
**North star:** `docs/product_blueprint_v3.md` — Overview is the front door (awareness); accents must lead and communicate state.

## Why this exists

Diagnosed live (2026-08-14): the Overview **"Markets Right Now"** section (`#markets` in `templates/dashboard.html`) is **883px tall — the single largest section on Overview** (~a full viewport of a 5.3-screen page) yet shows only **7 status rows** (primary/secondary/offset instrument + a one-word status). Low density, high space cost.

Separately, MNE's **candlestick chart works but is unreachable**: real price data exists (SPY/QQQ/NVDA/XLU/^VIX ≈127 candles each), but the chart renders only at `/research/{key}/sectors/{sector}/assets/{ticker}` — four drill-downs deep, no nav path, and a couple of symbol mappings are broken (`VIX`→0 vs `^VIX`→128; `DXY`→0) so rows read "Unavailable."

**One move fixes both:** the "Markets Right Now" real estate shows the same asset/price data as a cramped list — replace it with a real candlestick of the primary instrument. This is a **surfacing/design change, not a data rebuild.**

## Section 1 — the redesigned section

`#markets` keeps its question ("how is this story showing up in markets?") but leads with a chart:

- **Hero: the primary-expression instrument as a candlestick** — ~24 sessions from the persisted price store. **Up candles teal, down candles red** (the legitimate price-only red, consistent with the ratified palette and the asset-evidence decision).
- **Compact status strip** below the chart: primary / secondary / offset instruments as small inline chips (`symbol · one-word status`), replacing the current 7-row stack. Preserves the market-expression read; removes the bloat.
- **Click the chart → the asset-execution page** (`/research/{key}/sectors/{sector}/assets/{ticker}`). This makes the previously-buried deep view reachable for the first time, as a natural drill-down.
- **Honest fallback:** if the primary instrument has no price series, render the compact status strip alone — never a fake/empty chart.

Result: an ~883px text list becomes a compact chart + chip strip — less space, more signal.

## Section 2 — plumbing & symbol fix

- **Reuse the existing candle builder.** `_build_lead_instrument_candle(investigation, narrative_key)` (`dashboard.py`) already turns a primary instrument + `load_asset_price_history_or_empty(symbol)` into SVG candle geometry. Refactor so the investigation page and Overview both call **one shared candle-geometry helper** (no new charting code; `static/chart.js` already ships on Overview). Overview builds its candle from its own primary instrument in `market_expression_context`.
- **Fix broken symbol mappings** that cause false "Unavailable": `VIX → ^VIX`; map `DXY` to a real series or honestly omit it. Principle: map to a real price series where one exists; show honest-unavailable (not a broken row) where none does. Mappings live in the ticker maps (`NASDAQ_TICKERS`, `ASSET_EXPANSION_TICKERS`, `build_sector_ticker_map()`).
- **Fix the stray `/research → /undefined` 404** console error (a rendered undefined URL) — small related hygiene.

## Section 3 — verification

- Full suite green (**baseline 890, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + tests for the shared candle helper (geometry unchanged for the investigation path; Overview candle builds from the primary instrument; honest empty when no series) and the symbol-mapping fix.
- Browser audit: Overview `#markets` renders a candlestick for the primary instrument (up=teal / down=red), section is materially shorter than 883px, chip strip shows expression statuses, clicking the chart drills to the asset-execution page, honest fallback when no data; `VIX`/`DXY` no longer falsely "Unavailable"; **no `/undefined` console error**; color budget (price-only red is allowed here — it's price; no other stray hues); 1280 / 1024 / 390; JS-disabled render intact (candle SVG is server-rendered).
- `/`, `/admin`, `/research` return 200; `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

## Out of scope (this sprint)

- **News/macro overlay on the candle** — the annotated timeline (headlines + catalyst/macro markers aligned to the candle axis). Deferred to a fast follow-up; feasible because headlines/catalysts carry dates.
- Any engine/threshold/persistence changes; the deep asset-execution page's own layout; Studio.

## New / changed surface (for the handoff)

- **Changed:** `dashboard.py` (extract shared candle-geometry helper; build the Overview primary-instrument candle in the Overview context builder; symbol-mapping fix; `/undefined` fix); `templates/dashboard.html` (`#markets`: candlestick hero + compact status chip strip + click-through, honest fallback); `static/styles.css` (candle + chip-strip styling, shorter section); possibly `static/chart.js` (only if the candle render needs a shared entry point); `mne/presentation_language.py` (any copy); tests.
- **Unchanged:** the investigation candle output (shared helper must preserve it); engine logic; price store.
