# Overview "Markets Right Now" → Candlestick (Implementation Handoff)

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser, before commit.
**Design spec (read first):** `docs/superpowers/specs/2026-08-14-overview-markets-candlestick-design.md`
**North star:** `docs/product_blueprint_v3.md` — Overview is the front door; accents lead and communicate state.

## What this is

Replace the Overview **"Markets Right Now"** section (`#markets`, `templates/dashboard.html`) — currently an ~883px stack of 7 status rows — with a **candlestick of the primary-expression instrument** plus a **compact status chip strip**. The candle already works (real price data exists) but is buried at `/research/{key}/sectors/{sector}/assets/{ticker}`; this surfaces it on the front door. **Surfacing/design change, not a data rebuild.**

## Grounding (verified anchors)

- **Candle builder:** `dashboard.py:_build_lead_instrument_candle(investigation, narrative_key)` (~line 2604). It finds the `role=="primary"` instrument in `investigation["market_expression"]["instruments"]`, resolves a symbol via `ticker_symbols = {**NASDAQ_TICKERS, **ASSET_EXPANSION_TICKERS, **build_sector_ticker_map()}`, loads `load_asset_price_history_or_empty(symbol)`, and returns **server-rendered SVG geometry**: `{ticker, label, symbol, available, href, candles:[{x, wick_y, wick_height, body_x, body_y, body_width, body_height, direction:"up"|"down"}]}`. The candle is drawn as SVG in the template (no `chart.js` dependency for it).
- **Overview instruments:** the Overview context exposes `view.market_expression_context.instruments` (rows with `.asset`, `.role`, `.label`, `.status`); `#markets` already iterates these. The `role=="primary"` row is the hero instrument.
- **Symbol maps:** `ASSET_EXPANSION_TICKERS`, `NASDAQ_TICKERS` are defined in **`main.py`** (imported at `dashboard.py:55`). `VIX`→0 candles but `^VIX`→128; `DXY`→0. These are the false-"Unavailable" causes.
- **Investigation candle output must stay byte-for-byte identical** — the investigation page renders the same builder; do not regress it.

## Workstream A — shared candle helper (dashboard.py)

Refactor `_build_lead_instrument_candle` so the candle geometry is a **shared helper** both surfaces call:
- Extract `_build_candle_geometry(instruments, href)` (or similar) containing everything from "find primary" through the geometry rows. Keep the exact output shape and math.
- `_build_lead_instrument_candle(investigation, narrative_key)` becomes a thin caller passing `investigation["market_expression"]["instruments"]` and `href=f"/research/{narrative_key}/sectors"` — **investigation output unchanged**.
- Add `build_overview_markets_candle(...)` (thin caller) that passes the Overview `market_expression_context.instruments` and an href to the **dominant narrative's** drill path (`/research/{dominant_key}/sectors` — reuse the dominant/lead narrative key already present in the Overview context; this is the honest reachable route to the deep asset view, matching the existing candle `href`).
- Wire the result into the Overview context (the builder that sets `market_expression_context`, ~`dashboard.py:2016-2045`) as e.g. `markets_candle`.

## Workstream B — symbol-mapping fix (main.py)

- Add the missing mappings to `ASSET_EXPANSION_TICKERS` so the price store resolves: `VIX → ^VIX` (0→128 candles). For `DXY`, map to a real available series if one exists in the price store; if none does, leave it to resolve as honest-unavailable (do **not** fabricate). Principle: map where a real series exists; honest-unavailable otherwise.
- Verify with `load_asset_price_history_or_empty` that the mapped symbols return candles.

## Workstream C — template + styles (dashboard.html, styles.css)

Rework `#markets`:
- **Hero:** render `markets_candle` as an SVG candlestick when `available` — wicks + bodies from the geometry rows, **`direction=="up"` teal, `direction=="down"` red** (`--down`; this is legitimate price-only red). Server-rendered SVG (works JS-disabled).
- **Compact status chip strip:** the primary/secondary/offset instruments as small inline chips (`symbol · one-word status` with the existing `tone-*` classes), replacing the 7-row `.market-role-group` stack.
- **Click-through:** wrap the chart in a link to `markets_candle.href` (the drill path to the asset view).
- **Honest fallback:** when `available` is false (no series), render the chip strip alone — never an empty chart frame. Keep the existing `.section-empty` copy for the truly-empty case.
- **Styles:** the section must be **materially shorter** than 883px; compact chart + one-line chip strip. Preserve the color budget — price-only red is allowed **here** (it's price); no other stray hues.

## Workstream D — `/undefined` 404 hygiene

On `/research`, the browser logs `GET /undefined 404` — an element `src`/`href` (or a small script) is resolving to the string `"undefined"`. Locate and fix so the finder loads no undefined resource. Small, self-contained.

## Verification (per AGENTS.md — audit before Daniel commits)

- Full suite green (**baseline 890, 2 known auth failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`) + tests:
  - shared helper: investigation candle output unchanged (regression guard); Overview candle builds from the primary instrument; honest empty (`available=false`) when no series.
  - symbol map: `VIX`/mapped tickers resolve to candles.
- Browser audit (real run data, cache-bust CSS): Overview `#markets` renders a candlestick for the primary instrument (up=teal/down=red), section **materially shorter than 883px**, chip strip shows expression statuses, clicking the chart drills to the asset path, honest fallback when no data; `VIX`/`DXY` no longer falsely "Unavailable"; **no `/undefined` console error on `/research`**; 1280 / 1024 / 390; JS-disabled render intact (candle SVG server-rendered); color budget respected (price-only red only).
- Investigation page candle **unchanged** (open one, confirm the candle still renders as before).
- `/`, `/admin`, `/research` return 200; `git diff --check` clean; **nothing staged/committed/pushed** (Daniel commits).

**Recurring gotchas:** cache-bust CSS before reading computed styles; `pkill -f uvicorn` before starting the audit server.

## Out of scope

News/macro overlay on the candle (deferred follow-up). The deep asset-execution page's own layout. Engine/threshold/persistence changes. Studio. The parked assets/sectors-as-evidence sprint.
