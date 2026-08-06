# Asset Execution View - Implementation Handoff

**Status: not implemented - ready to hand to Codex. Do not implement from this document in this
session, and do not stage, commit, or push.** This is a Codex-ready brief for a new per-asset
"execution view" and its two backend prerequisites, delivered as three strictly serial sprints
(G -> H -> I). It extends the engine's existing research surfaces; it changes no scoring, no
thresholds, and no taxonomy. Every claim below was re-verified against the codebase; the file:line
references are current as of 2026-08-06.

---

## 1. Purpose and canonical references

The **Asset Execution View** is a per-asset research page reached from a sector's instrument list.
It answers one reader question - "how has the market actually been behaving around this asset, and
against what?" - with:

- a **hero** naming the asset and how it expresses its story, plus a **Today's Launch panel**;
- a **bounded daily-candle chart** (candles drawn inside their own trailing 20-session high/low
  rails, with a dashed launch line), range pills (1M / 3M / 6M), a crosshair OHLC readout, and
  **event markers** with filter pills, hover merge, and a docked detail panel;
- an **On the clock** countdown row of the scheduled prints most likely to move the story;
- **story-context cards** (role in the narrative, connected stories, how it has been participating);
- a **restyled sector instrument grid** carrying participation stripes, each card linking to the
  execution view of another instrument;
- an **honesty footer** ("what this view is not").

**Canonical references (in precedence order):**

1. **Visual contract:** `docs/mockups/asset_execution_concept_v1.html` - a self-contained,
   pure-ASCII HTML+CSS+JS mockup checked in beside this handoff. It is byte-identical to the
   approved artifact **https://claude.ai/code/artifact/d545ad38-1578-4c42-9774-186cbd4cebf4**.
   Open it in a browser while building. **Where this document and the mockup disagree on pixels,
   the mockup wins; where they disagree on scope or data honesty, this document wins.**
2. **Written visual contract:** `docs/design_system.md` (Design System v2) - the token set, card
   system, semantic color rules, and component patterns bind this feature.
3. **Charter:** `AGENTS.md` - standing rules, especially rule 1 (never stage/commit/push), rule 5
   (long-term trends read daily snapshots, one representative point per day, never per-run
   history), and honest degradation.

**Accurate description of the mockup (read it before starting).** The mockup renders NVIDIA (NVDA)
as an "AI Chips" instrument. Anatomy top to bottom:

- A **concept top bar** (wordmark, Dashboard / Research / Admin nav, a "Markets closed" clock) and a
  **breadcrumb** (Dashboard > AI Chips > NVIDIA (NVDA)). These belong to the standalone concept -
  see the production-chrome ruling in Sprint H.
- **Hero grid** (`.hero-grid`, 1.55fr / 1fr): left card with eyebrow "Asset view", headline
  "NVIDIA", mono id-line "NVDA - Equity - Technology", a plain-English subtitle, and three chips
  ("Primary expression"; a teal "Moving with the story"; a teal mono "+2.10% today"). Right card is
  the **Today's Launch panel** carrying the single teal glow (`.glow-teal`): a 56px mono launch
  number `1,199.20`, a mono "Launch line 1,182.40" sub-label, a teal "+1.42% above launch" delta, a
  small intraday sparkline with a **dashed launch line at the open level**, and a caption
  explaining the launch line.
- **The tape, in context** card: a `label` "NVDA daily candles", a controls row with **event-filter
  pills** (All events / Earnings / News / Macro / Hide, left) and **range pills** (1M / 3M / 6M,
  right; 3M is `aria-pressed="true"` by default). The chart body (`#chartMain`) is a one-column grid
  that becomes two columns (`minmax(0,1fr) 280px`) when an event panel docks; below 960px it
  collapses back to one column. The SVG (`viewBox="0 0 960 440"`) is rendered entirely by JS: faint
  bands above the 20-day high and below the 20-day low, teal up-candles / red down-candles with
  wicks, two solid slate rails labelled "20-day high/low", a bright dashed launch line with a raised
  "Launch 1,199.20" chip, ~5 mono x-axis date labels, and **slate circled event glyphs** placed
  above each event day's candle (flipped below when they would collide with the top or the high
  rail; multi-event days show a count). A `.readout` (top-left, mono) shows O/H/L/C on crosshair and
  merges the day's event tag+title+blurb when the crosshair lands on a marker day. A legend row and
  a `<noscript>` fallback ("Chart requires JavaScript. Latest close: 1,199.20 (+2.1%).") sit below.
- **On the clock**: a three-card grid (`#eventGrid`) of live mono countdowns; the soonest card
  carries the teal glow, a pulsing dot, and an "Up next" tag.
- **The story it carries**: a two-card grid - "Role in the narrative" (connected-story mini-chips)
  and "How it's been participating" (a state pill + a mono freshness line).
- **Technology instruments**: a `#assetGrid` of restyled instrument cards, each with a top
  participation **stripe** (teal / slate / amber), name, mono "TICKER - state" line, role line,
  participation line, and a mono "+/-x.xx% today" change (teal up, red down, slate flat). The
  card being viewed carries a teal glow and a "Viewing" tag. A three-item legend (Moving with /
  Steady / Moving against) closes the section. Cards are `<button>`s; in the concept they scroll to
  top, but in production each links to that instrument's execution route (Sprint H).
- **What this view is not**: an honesty card, then a concept footer.

The mockup's OHLC, events, and countdowns are **illustrative literals** baked into the script - the
production build replaces them with persisted engine data (Sprints G and I) but must preserve the
rendered anatomy and interaction behavior.

---

## 2. Definitions (ratified by the owner via mockup approval, 2026-08-06)

These are pre-ratified per AGENTS.md rule 2 - do not re-litigate them; flag only genuinely new
ambiguity.

- **Daily Launch Line.** A horizontal dashed reference drawn at the asset's **official daily open**
  (the last candle's `open`). The hero's "Today's Launch" panel quotes the live/last price and the
  delta versus the launch line. It is **hand-derivable**: any reader can recompute it from the
  session's open. `docs/ui_naming_framework.md:25` currently **reserves** the term: *"Daily Launch
  Line: reserved until a real daily-open reference and behavior exist."* Sprint G creates the real
  open data; **the sprint that first renders the launch line (Sprint H) must un-reserve that line**
  - move it out of the "Reserved - not implemented" list and give it a backing-field row, since a
  real daily-open reference will then exist. Do not un-reserve it earlier.
- **HTF (higher-time-frame) bounded candles.** Daily candles are always drawn **inside explicit
  trailing 20-session high/low rails**. The y-domain is computed to include the visible candles,
  **both rails, and the launch line**, so none of them ever clips. (In the mockup: `renderChart`
  widens `hi`/`lo` with `ext.hi`/`ext.lo`/`LAUNCH` before padding - mirror that domain logic.) The
  point is that a move is always read against what came before, not on a naked auto-scaled axis.
- **Event markers.** Slate **circled glyphs** placed above the event day's candle: `E` earnings,
  `N` news, `M` macro (a numeral for multi-event days). **Markers are slate on purpose** - in
  Design System v2 hue encodes *state*, and an event marker is not a state, so it must not steal
  teal/amber/red. Filter pills **All / Earnings / News / Macro / Hide** sit top-left of the chart.
  Hovering a marker day **merges** the event tag+title+blurb into the OHLC readout. Clicking a
  marker **docks a detail panel to the right of the chart** (below it under 960px); Escape or the
  panel's Close button dismisses it; **only one panel is open at a time**. See section 3 for the
  News-pill reality.
- **Participation stripe vocabulary (restyled grid).** The top stripe and the legend use exactly
  three participation states: **teal = moving-with the story**, **bright slate = steady / sitting
  out**, **amber = moving-against the story**. **Red never encodes participation.** Red is reserved
  for **downside price moves only** - down candles and negative percentage deltas. (Note the mockup
  reuses the `stripe-red` *class name* but paints it `var(--amber)` - the moving-against stripe is
  amber, not red. Keep that: the class name is legacy, the color is amber.)

---

## 3. Data reality and honesty rules (read before writing any code)

The engine today persists, per ticker, only `latest_close` and `pct_change`
(`mne/market_context.py:23-28`). It does **not** store OHLC history, and there is **no company news
/ announcement feed** anywhere in the codebase (earnings and macro prints exist as catalysts; free
company news does not). The execution view must therefore degrade honestly:

- **No candle store data for a ticker -> an honest empty chart state.** Render the chart card with a
  plain "No price history yet for this instrument" message. **Never invent candles**, never
  interpolate, never fall back to a single flat line pretending to be history. Zero candles is a
  correct outcome, not a bug (AGENTS.md honest empty states).
- **The News filter pill is aspirational.** No news source exists. **Recommendation (ratified):
  ship the production filter row as `All / Earnings / Macro / Hide` - omit the News pill entirely**
  until a real company-news source is persisted (a future tier-2 effort, section 9). Do not ship a
  disabled-looking dead pill and do not fabricate `type: "news"` events. The mockup's News pill and
  its two `type: "news"` sample events are explicitly **aspirational placeholders** for that future
  source; call this out in the Sprint H/I PR so the auditor does not expect News to work.
- **Prices are last-verified closes, not live quotes.** The honesty footer and the freshness line
  must say so, using the persisted observation time - never manufacture a "live" timestamp.

---

## 4. Sprint G - daily OHLC price store (backend only, no UI)

**Goal:** persist one representative daily candle per (ticker, day) for the registry tickers, drawn
from the **same** yfinance history call `market_context` already makes - additive only, breaking no
downstream consumer. No UI in this sprint.

### 4.1 Extend `mne/market_context.py` (additive, non-breaking)

`get_market_snapshot` (`mne/market_context.py:4`) already calls
`yf.Ticker(ticker).history(period="5d")` (L9) and reads `data["Close"]` (L18-19). That same
DataFrame carries `Open`, `High`, `Low`, `Close` - so **no new provider and no second network call
are needed** for today's candle.

- Add a helper (e.g. `latest_daily_candle(data)`) that reads the **last row's** `Open/High/Low/Close`
  from the existing DataFrame and returns a plain dict `{"open": ..., "high": ..., "low": ...,
  "close": ...}`, each `round(float(x), 2)` to match the existing `latest_close` rounding (L25).
- **Keep the existing snapshot dict shape at L23-28 exactly as-is** - every downstream consumer
  (`main.py:506-789`, breadth, market environment, etc.) reads the current keys. **Additive shape
  (ratified): add an optional `"candle"` key (the 4-field dict) onto the existing per-ticker
  snapshot dict, absent when no candle is available; no separate function.** Downstream consumers
  are unaffected because they read only the existing keys. Acceptance: all existing
  snapshot-consumer tests pass untouched.
- Preserve the existing **fail-soft** contract: exception or empty/short DataFrame -> no candle for
  that ticker (mirror L10-16), never a partial/None-filled candle.

### 4.2 New module `mne/asset_price_history.py` (fail-closed triad, mirror `story_registry`)

Mirror the fail-closed idiom of `mne/story_registry.py` (`StoryRegistryError(ValueError)` at L22,
`DEFAULT_*_PATH` at L16, frozen dataclasses at L26+, `validate_*` raising on any deviation, `load_*`
wrapping `OSError`/`json.JSONDecodeError`). Concretely:

- `class AssetPriceHistoryError(ValueError)`.
- A **frozen** `Candle` dataclass with fields `date: str` (ISO `YYYY-MM-DD`), `open: float`,
  `high: float`, `low: float`, `close: float`. **Volume decision (ratified): omit volume from the
  candle record.** The candle mockup uses no volume, `market_context` never reads `Volume`, and the
  execution-view chart renders price bodies/wicks only - adding volume now would persist an
  unvalidated field with no consumer. State this explicitly in the PR. (Revisit under section 9 if a
  volume pane is ever specced.)
- A per-ticker store: one JSON file per ticker at `DATA_DIR/asset_prices/{TICKER}.json`, shaped
  `{"ticker": "NVDA", "version": "1.0.0", "candles": {"YYYY-MM-DD": {open,high,low,close}, ...}}`.
  **Date-keyed, not a list** - this is what makes the upsert idempotent (see 4.3). `DATA_DIR` is the
  runtime data root outside the repo (the same `DATA_DIR` `mne/macro_catalysts.py:11` uses); never
  write into the repository (AGENTS.md environment note).
- `validate_asset_price_history(data) -> <frozen record>`: object check -> version semver check
  (reuse the `_SEMVER` pattern from `story_registry.py:17`) -> `candles` must be a dict; each key a
  valid ISO date; each value a dict with exactly the four float fields and `high >= low`. Raise
  `AssetPriceHistoryError` with a `candles[<date>].<field>` message on the first violation.
- `load_asset_price_history(ticker, path=...)`: wrap `Path(path).open` + `json.load` in
  `except (OSError, json.JSONDecodeError)` -> `AssetPriceHistoryError`. A **missing file is not an
  error** for read callers - expose a thin loader that returns an empty candle map when the file is
  absent (the honest empty state), while a **corrupt** file still raises. State which function does
  which.
- Deterministic serialization: write candles sorted by date key so the file is byte-stable
  regardless of insertion order.

### 4.3 One representative candle per (ticker, day) - upsert, never accumulate

Follow the daily-snapshot discipline in `mne/storage.py` (AGENTS.md rule 5). Model the writer on
`write_daily_snapshot` (`mne/storage.py:398`):

- `upsert_daily_candle(ticker, candle)` reads the ticker file (empty map if absent), sets
  `candles[candle.date] = candle` (**final write of the day wins** - a later run the same day
  overwrites, exactly like `_upsert_raw_run` at `storage.py:419`), then rewrites the file. Because
  candles are keyed by date, **repeated runs on the same day never accumulate rows** - this is the
  whole point of rule 5. Do **not** append per-run history.
- Only persist **today's** candle from the live path (mirror `write_daily_snapshot`'s
  `snapshot_date != today` early-return at `storage.py:401-402`), so a re-run of an old result never
  rewrites a historical day with stale data.
- Wire the live write into the run assembly in `main.py` near the existing market_snapshot handling
  (`main.py:502-542`) - after the snapshot with candles is built, upsert today's candle for each
  registry ticker that produced one. Fail-soft: a ticker with no candle is simply skipped.

### 4.4 Backfill entry point (~6 months, skip-existing)

Add a backfill function mirroring `backfill_daily_snapshots` (`mne/storage.py:425`), including its
**skip-existing** behavior (`storage.py:442-444`):

- For each registry ticker, call `yf.Ticker(ticker).history(period="6mo")` once, iterate its rows,
  and upsert each day's candle - but **do not overwrite a date already present** in the ticker file
  (skip-existing per day, so a backfill never clobbers a live-captured candle). Log created vs
  skipped counts like `backfill_daily_snapshots` does.
- **Backfill depth decision (ratified for now): 6 months (`period="6mo"`)**, which comfortably
  covers the chart's longest range (6M / 126 sessions). This is an owner-revisitable knob (section
  9).
- Persist the source and depth honestly in each file's metadata (e.g. a `"source": "yfinance"` /
  `"backfill_period": "6mo"` block) so the provenance is inspectable. Registry-owned thresholds/
  metadata, not magic numbers buried in code (AGENTS.md rule 7 spirit).

**Hand-derivability note (state in the PR).** Every persisted candle is a verbatim
`round(float(x), 2)` of the corresponding `Open/High/Low/Close` cell in the yfinance history
response for that date. A human can re-fetch `yf.Ticker(T).history(...)`, read the same row, and
reproduce the stored candle exactly. No smoothing, no synthesis, no derived fields (AGENTS.md core
philosophy: hand-derivable from persisted inputs).

### 4.5 Files to touch (Sprint G)

- `mne/market_context.py` - additive candle helper; existing shape untouched.
- `mne/asset_price_history.py` - **new** module (fail-closed triad, writer, backfill).
- `main.py` - wire the live per-day upsert near `L502-542`.
- `tests/test_asset_price_history.py` - **new**, full triad (below).

### 4.6 Test plan (Sprint G)

Mirror the four-part triad of `tests/test_story_registry.py` (methods at L29 / L38 / L53 / L62),
adapted:

1. **Load/validate as frozen records:** a well-formed ticker file loads to frozen `Candle` records
   (`FrozenInstanceError` on mutate); a missing file yields the empty honest map, not an error.
2. **Schema fails closed:** bad version, non-dict `candles`, malformed date key, missing/extra
   candle field, non-float field, and `high < low` each raise `AssetPriceHistoryError` with a
   `candles[<date>].<field>` message; a corrupt/unreadable file wraps `OSError`/`JSONDecodeError`.
3. **Upsert idempotency (rule 5):** upserting the same date twice yields **one** row, last write
   wins; upserting two dates yields two rows sorted by date; the serialized output is byte-stable.
4. **Candle extraction from a fake DataFrame:** feed `latest_daily_candle` a stub with known
   `Open/High/Low/Close` and assert the rounded dict; feed an empty/short frame and assert no candle
   (fail-soft), with the existing `get_market_snapshot` shape unchanged.

Run: `./venv/bin/python -m unittest discover tests` (pytest is **not** installed in this venv - do
not use it). Two pre-existing `test_authorization` failures are known and unrelated; nothing in
Sprint G should add a failure.

---

## 5. Sprint H - execution view route + chart + grid restyle

**Depends on Sprint G's candle store.** This sprint adds the page, the candle renderer, and the grid
restyle. **No event markers yet** (that is Sprint I) - ship the chart with launch line, rails,
crosshair readout, and range pills only. **Filter-row decision (ratified): Sprint H ships the
range pills only; the event-filter row is added wholesale in Sprint I. No inert placeholder
pills.**

### 5.1 Ratified decision - v2 styling extends into a research route (call this out)

AGENTS.md rule 6 describes the **old two-hue** user-dashboard budget (`--up` green + `--down`
red-orange). **`docs/design_system.md` v2 supersedes rule 6 for user-dashboard surfaces**, and
research surfaces have historically retained the legacy palette. **Ratified decision for this
feature: the Asset Execution View - although it lives under `/research/...` - adopts the Design
System v2 obsidian/teal/amber/red language per the approved mockup.** This is the **first time v2
styling extends into a research-tier route**; flag it prominently in the Sprint H PR as a
deliberate, owner-ratified extension so the auditor does not read it as palette drift. The rest of
the research chrome (see 5.4) keeps its existing look.

### 5.2 Route + context builder

- Add a route **adjacent to** the existing assets route
  (`dashboard.py:2778` - `GET /research/{key:path}/sectors/{sector}/assets`):
  **`GET /research/{key:path}/sectors/{sector}/assets/{ticker}`**. Reuse the same guard structure
  (`build_investigation_context`, `split_narrative_key`, group-only check, sector-row lookup,
  `AssetRegistryError`/`SectorIsolationError`/`NarrativeSectorInstrumentError` fail-closed handling)
  the existing route uses at `dashboard.py:2779-2802`. Validate `{ticker}` against the loaded asset
  registry; an unmapped ticker sets an honest `message` and a `None` execution context (same idiom
  as the sector-not-mapped branch at `dashboard.py:2792-2794`).
- Add a context builder **`build_asset_execution_context(...)` in `mne/asset_exploration.py`**
  (alongside `build_asset_exploration_context` at `mne/asset_exploration.py:186`). **Decision: put it
  in `asset_exploration.py`, not a new module** - it reuses that file's registry loading, participation
  classification, `research_href` construction (L203), and copy helpers, and keeping the two builders
  together mirrors the existing organization. State this in the PR.
- The builder assembles: hero fields (display name, ticker, asset type, story/role copy, today's
  delta), the launch panel (last close + launch open + delta vs launch, all from the candle store),
  the candle series for the chart (the ticker's persisted candles, or an **empty list -> honest
  empty state**), the story cards (reuse role/participation fields already produced at
  `asset_exploration.py:202-210`), and the restyled sector-grid rows (below). On-the-clock events
  are populated in Sprint I; in Sprint H render the section empty or omit it and note it.

### 5.3 Template + chart + grid

- **`templates/asset_execution.html`** - **new** template matching the mockup anatomy (section 1):
  breadcrumb, hero + Today's Launch panel with the **single** teal glow, chart card, On the clock,
  story cards, sector grid, honesty footer. Reuse the Design System v2 card system and tokens
  (`docs/design_system.md` sections 3 and 5); do not invent one-off card styles.
- **`static/asset_chart.js`** - **new** vanilla SVG candle renderer (no build step, no framework;
  follow the `static/chart.js` progressive-enhancement pattern). Port the mockup's `renderChart`
  geometry: 20-day rails, faint bands, teal up / red down candles with wicks, the dashed launch line
  + raised chip, ~5 mono x-axis labels, the crosshair `.readout` with O/H/L/C, range pills
  (1M / 3M / 6M mapped to 21 / 63 / 126 sessions), and the y-domain that always includes both rails
  and the launch line. Server-precomputed geometry is optional - the mockup computes geometry
  client-side from the literal OHLC; the production version consumes the persisted candle series
  handed to it (e.g. as a JSON script block), and must render a **`<noscript>` fallback line**
  (latest close) exactly like the mockup. **Event markers, filters, hover-merge, and the docked
  panel are Sprint I** - leave clean seams for them.
- **Restyle `templates/_partials/asset_grid.html`** to the mockup's card recipe: the top
  participation **stripe** (teal / slate / amber), name, mono "TICKER - state" line, role and
  participation lines, and the mono "+/-x.xx% today" change (teal up, red down, slate flat). Map the
  existing `participation_state` to the three stripe states via the existing
  `dashboard_sector_presentation` helper (`mne/presentation_language.py:241`, which already maps to
  `driving` / `steady` / `detached`) - **reuse it, do not invent a parallel mapping**. **Link each
  card to the new execution route** for that instrument (replace the concept's scroll-to-top with a
  real `href` to `/research/{key}/sectors/{sector}/assets/{ticker}`), constructed the same way
  `research_href` is built at `asset_exploration.py:203`. Keep the existing X-Ray `details` block -
  progressive disclosure per Design System v2 section 2.

### 5.4 Production chrome vs concept chrome (do not replace research nav)

The mockup's **top bar and breadcrumb belong to the standalone concept**. **Production keeps the
existing research-tier chrome (the app rail / research navigation)** that every other `/research/...`
page renders - do **not** swap the research nav for the concept top bar. Adopt the concept's
breadcrumb *content* (Dashboard > Story > Instrument) only insofar as the research chrome already
supports a breadcrumb; if it does not, render a lightweight in-page breadcrumb and **flag the
tension to the auditor rather than resolving it silently** (AGENTS.md rule 2 - unratified chrome
decisions get flagged, not decided). Do not restyle the surrounding research shell.

### 5.5 Copy discipline

All user-facing copy routes through **`mne/presentation_language.py`** only - no hardcoded engine
terms in the template or JS (AGENTS.md rule 3; Design System v2 section 2). Reuse the existing
participation labels/copy (`presentation_language.py:16-30`, sector labels `:223-225`) and the
asset-exploration copy helpers the current grid already uses. Add new copy keys to
`presentation_language.py` if the mockup needs a phrase that does not exist yet; never inline it.

### 5.6 Files to touch (Sprint H)

- `dashboard.py` - new route adjacent to `L2778`.
- `mne/asset_exploration.py` - `build_asset_execution_context` beside `L186`.
- `templates/asset_execution.html` - **new**.
- `static/asset_chart.js` - **new**.
- `templates/_partials/asset_grid.html` - restyle + execution-route links.
- `mne/presentation_language.py` - new copy keys only if needed.
- `docs/ui_naming_framework.md` - **un-reserve the Daily Launch Line** (move L25 out of "Reserved",
  add a backing-field row) now that Sprint G persists a real daily open.

### 5.7 Verification (Sprint H)

- Full suite: `./venv/bin/python -m unittest discover tests` (unittest, **not** pytest); the two
  known `test_authorization` failures aside, nothing new fails.
- Dashboard up: `./venv/bin/python -m uvicorn dashboard:app --port 8643`. Routes return **200**:
  `/`, the `/research` chain (`/research/{key}`, `.../sectors/{sector}/assets`), and the **new**
  `.../sectors/{sector}/assets/{ticker}`.
- Render against **both** the latest real run and a populated synthetic run; **and** against a
  ticker with **no candle store data** -> confirm the honest empty chart state (no invented candles).
- **JS-disabled**: the `<noscript>` fallback line renders; no blank chart card.
- **Reduced-motion** (`prefers-reduced-motion: reduce`): no hover translate, no chart animation.
- **Widths 1280 / 1024 / 390**: no horizontal page scroll; the chart's two-column dock collapses to
  one column under 960px per the mockup.
- **Color budget vs `docs/design_system.md`**: only teal / amber / red / slate as non-neutral hues;
  event-marker slate (Sprint I) and participation stripes obey section 2's rules; red only on down
  candles and negative deltas. (Rule 6's two-hue budget does **not** apply here - see 5.1.)
- `git diff --check` clean; **nothing staged, committed, or pushed**.

---

## 6. Sprint I - event markers on the chart

**Depends on Sprint H's chart.** This sprint adds the deterministic per-asset event feed, the marker
layer, the filter pills, the hover-merge readout, and the docked detail panel - all per the mockup.

### 6.1 A deterministic, persisted per-asset event feed

Markers must be **reproducible from persisted inputs**, not re-fetched live each render (AGENTS.md
hand-derivability). Two event sources exist today and **both already include past dates**:

- **Earnings** - `mne/company_catalysts.py` fetches `ticker.get_earnings_dates()`
  (`company_catalysts.py:50`). That DataFrame's index carries **past and future** earnings dates;
  the existing helper `_first_earnings_date_from_get_earnings_dates` (`company_catalysts.py:48`)
  deliberately keeps only the **next** date (`_next_date_on_or_after`, L64). Sprint I needs the
  **past** dates too, so add a sibling extractor that keeps historical earnings dates from the same
  `get_earnings_dates()` response (do not change the existing forward-only helper). The hardcoded
  watchlist already includes NVDA (`company_catalysts.py:8`).
- **Macro prints** - `mne/macro_catalysts.py` reads `MACRO_CALENDAR_FILE`
  (`DATA_DIR/config/macro_calendar.json`, `macro_catalysts.py:11`), whose entries carry absolute
  `scheduled_at` datetimes **including past entries**. Filter these to the asset's story-relevant
  macro events (e.g. via the story's `catalyst_names` in `config/story_registry.json`).

**Persistence (ratified): store per-ticker events in a sibling store at
`DATA_DIR/asset_events/{TICKER}.json`, owned by a NEW module `mne/asset_events.py` with its own
fail-closed triad (same idiom as Sprint G).** Rationale: candle files stay price-only; events
refresh on a different cadence and carry editorial text, so they get their own file and validator.
Each persisted event: `{date, type, title,
blurb, detail, source}` where `type in {"earnings", "macro"}` (**no `"news"`** - section 3).
Persisting them (rather than re-fetching live) means a past marker is reproducible from persisted
inputs on any future render, exactly like the candle store. Seed/refresh this feed on the same run
cadence that writes candles (Sprint G's `main.py` wiring).

### 6.2 Marker layer + interactions (mockup parity)

Port the mockup's marker and interaction code into `static/asset_chart.js`:

- **Marker layer**: slate circled glyphs (`E`/`M`, numeral for multi-event days) above the event
  day's candle, flipped below when they collide with the top or the high rail (mockup lines
  ~798-833). Markers are slate - hue is state only.
- **Filter pills** **All / Earnings / Macro / Hide** (News omitted per section 3). Reflect
  `aria-pressed`; re-render the marker layer on change (mockup ~908-924).
- **Hover merge**: when the crosshair lands on a marker day, append the event tag+title+blurb to the
  OHLC readout (mockup ~879-886).
- **Docked detail panel**: clicking a marker docks a panel to the right of the chart (below under
  960px via `.chart-main.has-panel`); Escape or Close dismisses; **one panel at a time** (mockup
  ~926-962). All copy routes through `presentation_language.py`; event `title`/`blurb`/`detail`
  come from the persisted feed, never invented.
- Wire **On the clock** (`#eventGrid`) to the forward-looking catalysts feed the engine already
  builds (`mne/catalysts.py:205` `load_all_catalysts` / `get_upcoming_catalysts` at `L255`) so the
  countdowns point at real future datetimes; the soonest gets the single teal glow (mockup
  ~994-1033). Honest empty state when there are no upcoming events.

### 6.3 Files to touch (Sprint I)

- `mne/company_catalysts.py` - sibling extractor that keeps **past** earnings dates (existing
  forward-only helper unchanged).
- `mne/asset_events.py` - **new** module: persisted, fail-closed per-ticker event store (see 6.1).
- `main.py` - seed/refresh the per-asset event feed alongside the candle write (`L502-542` area).
- `mne/asset_exploration.py` - feed persisted events + upcoming catalysts into
  `build_asset_execution_context`.
- `static/asset_chart.js` - marker layer, filter pills, hover merge, docked panel.
- `templates/asset_execution.html` - filter row + event-panel container + On-the-clock grid.
- `mne/presentation_language.py` - new copy keys only if needed.

### 6.4 Verification (Sprint I)

Everything in 5.7, plus: past **and** future markers render from the **persisted** feed (verify by
re-rendering without a live fetch); filter pills All/Earnings/Macro/Hide filter correctly and
**News is absent**; hover merges the event into the readout; click docks exactly one panel, Escape
and Close dismiss; the docked panel collapses below the chart under 960px; markers stay slate;
On-the-clock countdowns target real future datetimes with a single teal glow on the soonest.

---

## 7. Sprint ordering and gating

**G -> H -> I, strictly serial.** H consumes G's candle store; I consumes H's chart. Each sprint is
**independently shippable** and is **audited in-browser before any commit** (AGENTS.md rule 1 -
committing is Daniel's step, never the agent's). Do not start H before G is verified, or I before H
is verified. Do not fold two sprints into one PR.

---

## 8. Verification standard (applies to every sprint)

The repo standard (AGENTS.md verification standard):

- Full test suite passing via **`./venv/bin/python -m unittest discover tests`** (pytest is **not**
  installed in this venv - do not use it). The two pre-existing `test_authorization` failures are
  known and unrelated; do not "fix" them and do not let them mask new failures.
- `/`, `/admin`, `/research` return **200**; the new route returns **200**.
- Rendering checked against **both** the latest real run and a populated **synthetic** run.
- **Empty/degraded states** rendered and confirmed honest (no-candle chart; no-event grid; unmapped
  ticker message).
- `git diff --check` clean; **nothing staged, committed, or pushed** (AGENTS.md rule 1).

**UI sprints (H, I) additionally check:** widths **1280 / 1024 / 390** with no horizontal scroll;
**JS-disabled** rendering (noscript fallback); **reduced-motion** honored; and the **color budget**
against `docs/design_system.md` (teal / amber / red / slate only; red is downside-only; markers and
the moving-against stripe are slate/amber, never red for participation).

Dashboard run command: `./venv/bin/python -m uvicorn dashboard:app --port 8643`. Runtime data lives
at `MNE_DATA_DIR` outside the repo; never write runtime outputs into the repository.

---

## 9. Open decisions for the owner

Short list - flag rather than decide silently (AGENTS.md rule 2):

1. **Reachability.** Should the execution route be reachable from the user dashboard's story panels
   later (e.g. a story chip -> primary instrument deep link), or research-only for now?
2. **Volume on candles.** Sprint G omits volume (ratified). Add a volume pane / persisted volume
   field later if a volume story is specced?
3. **Backfill depth.** Sprint G uses 6 months. Extend (1y+) if longer ranges than 6M are ever added
   to the range pills?
4. **News feed source (future tier-2).** The News filter pill and any `type: "news"` markers stay
   omitted until a real, persisted company-news source exists. What source, and is it in scope for a
   later sprint?

---

## Appendix - quick reference (all re-verified 2026-08-06)

| Claim | Location | What is there |
|---|---|---|
| Snapshot reads only Close from a 5d history call | `mne/market_context.py:9,18-19` | `history(period="5d")`; `data["Close"].iloc[-1/-2]` |
| Snapshot dict shape (keep untouched) | `mne/market_context.py:23-28` | `ticker/latest_close/pct_change/observed_at` |
| Fail-soft per ticker | `mne/market_context.py:10-16` | exception/empty -> `None` |
| Snapshot invoked with ticker union | `main.py:502-503` | `{**NASDAQ_TICKERS,**BREADTH_TICKERS,**sector_tickers,**ASSET_EXPANSION_TICKERS}` |
| Snapshot stored on run | `main.py:542` | `"market_snapshot": market_snapshot` |
| Daily snapshot upsert + today-only + aggregate | `mne/storage.py:398-422` | `write_daily_snapshot`, `snapshot_date != today` early return, `_upsert_raw_run` |
| Backfill skip-existing | `mne/storage.py:425,442-444` | `backfill_daily_snapshots`, "Skipped existing" |
| Immutable per-run write mode "x" | `mne/storage.py:53` | `open(results_file, "x", ...)` collision-suffixed |
| Earnings dates fetch (past+future in index) | `mne/company_catalysts.py:48-64` | `get_earnings_dates()`; helper keeps only `_next_date_on_or_after` |
| NVDA in hardcoded watchlist | `mne/company_catalysts.py:8` | `"NVDA": "red"` |
| Combined catalysts loader | `mne/catalysts.py:205,255` | `load_all_catalysts`, `get_upcoming_catalysts` |
| Macro calendar file (absolute scheduled_at, past entries) | `mne/macro_catalysts.py:11` | `DATA_DIR/config/macro_calendar.json` |
| Existing assets route | `dashboard.py:2778-2803` | `GET .../sectors/{sector}/assets` -> `build_asset_exploration_context` -> `asset_exploration.html` |
| Asset context builder | `mne/asset_exploration.py:186,202-210` | `build_asset_exploration_context`; participation rows + `research_href` |
| Participation state -> tile vocabulary | `mne/presentation_language.py:241-255` | `dashboard_sector_presentation` -> driving/steady/detached |
| Existing asset grid partial | `templates/_partials/asset_grid.html` | `participation-{{state}}` cards, X-Ray details |
| Fail-closed registry pattern to mirror | `mne/story_registry.py:16-22` | `_SEMVER`, `DEFAULT_*_PATH`, `StoryRegistryError(ValueError)` |
| Test triad to mirror | `tests/test_story_registry.py:29,38,53,62` | load-frozen / schema-closed / loader-wraps / deterministic-sort |
| Chart pattern (vanilla SVG, no build) | `static/chart.js` | progressive enhancement over precomputed geometry |
| Daily Launch Line reserved | `docs/ui_naming_framework.md:25` | "reserved until a real daily-open reference and behavior exist" |
