# Company News Markers via SEC EDGAR 8-K - Implementation Handoff

**Status: not implemented - ready to hand to Codex. Do not implement from this document in this
session, and do not stage, commit, or push.** This is a Codex-ready brief for a single sprint that
adds a real, persisted company-news event source (SEC EDGAR 8-K filings) and activates the News
filter pill and "N" marker glyph that the approved execution-view mockup already defines. It extends
the existing per-asset event store; it changes no scoring, no thresholds, and no taxonomy. Every
file:line reference below was opened and re-verified against the codebase as of 2026-08-07.

This sprint follows the completed asset-execution work (Sprints G -> H -> I in
`docs/handoffs/asset_execution_view_handoff.md`). Read that handoff first for the chart, marker, and
store idioms this sprint reuses. Where this document and that one disagree on the News pill, **this
document wins**: the earlier handoff deliberately deferred News ("The News filter pill is
aspirational", section 3 there) because no company-news source was persisted. This sprint persists
one, so News is now real - not aspirational - and the earlier deferral is superseded for News only.

---

## 1. Purpose, scope boundary, and canonical references

**Goal.** Add company-news event markers to the per-asset daily-candle chart, sourced from SEC
EDGAR 8-K filings, persisted into the existing per-asset event store, and rendered through the
generic marker/filter/hover/panel machinery that already exists. The mockup's **News filter pill**
and **slate "N" glyph** are **activated** by this sprint - they were **omitted** in the prior sprint
(Sprint I), not left unbuilt. Confirm this yourself:

- `static/asset_chart.js:46` - the marker glyph is currently
  `glyph = events.length>1 ? events.length : (events[0].type==="earnings" ? "E" : "M")`. There is no
  `"N"` branch; a `type:"news"` event would silently render as `"M"`. This sprint adds the `"news"
  -> "N"` branch.
- `templates/asset_execution.html:18` - the event-filter row renders exactly four pills
  (`data-event-filter` = `all` / `earnings` / `macro` / `hide`). There is no News pill. This sprint
  inserts a `news` pill between Earnings and Macro.
- `static/asset_chart.js:20-23` (`visibleEvents`), `:45-48` (marker layer), `:59` (`openPanel`),
  `:64` (the generic `.event-filter-btn` click handler that reads `data-event-filter` and re-renders)
  are all **type-agnostic** already: they filter, hover-merge, and dock by `event.type` without
  hardcoding the type set. So the marker layer, filter behavior, hover-merge, and docked panel need
  **no new logic** for News beyond the glyph branch and the pill.

**Scope boundary (state this prominently in the PR).** This is an **EDGAR-only** sprint and a
**per-asset chart-marker feature only**. It is **not** wired into the source-intelligence or
narrative-detection pipeline: EDGAR 8-Ks do not become narrative evidence, do not feed
`mne/rss_fetch.py` / source health, do not affect any score, theme, or group. They are chart
annotations persisted beside earnings/macro markers and nothing more. **IR RSS enrichment**
(company newsroom feeds for NVDA / MSFT / CVX / SLB) is **explicitly deferred** to a later "official
source layer" effort and is out of scope here - do not build it, do not add a placeholder for it.

**Canonical references (in precedence order):**

1. **Prior handoff:** `docs/handoffs/asset_execution_view_handoff.md` - the chart, marker, event-store,
   and fail-closed-triad idioms this sprint extends. Its Sprint I (sections 6.1-6.4) defines the
   event store this sprint adds `"news"` to.
2. **Visual contract:** the approved execution-view mockup (the News pill and slate "N" glyph are
   part of the approved marker vocabulary; `docs/handoffs/asset_execution_view_handoff.md:102-109`
   ratifies markers as slate circled glyphs `E`/`N`/`M`, numeral for multi-event days).
3. **Charter:** `AGENTS.md` - honest degradation (never fabricate a marker), hand-derivability (a
   marker must be reproducible from persisted inputs), registry-owned configuration (rule 7), and
   **never stage/commit/push** (rule 1).

---

## 2. Ratified decisions (do not re-litigate; flag only genuinely new ambiguity)

Per AGENTS.md rule 2 these are pre-ratified by the owner. Build them as written; flag only new
ambiguity.

- **Source = SEC EDGAR submissions JSON.** Fetch
  `https://data.sec.gov/submissions/CIK{cik10}.json`, where `{cik10}` is the CIK zero-padded to 10
  digits (e.g. NVDA CIK 1045810 -> `CIK0001045810.json`). The response is JSON with top-level `name`
  and `tickers`, and `filings.recent` as a dict of **parallel arrays** keyed by
  `accessionNumber, filingDate, reportDate, form, items, primaryDocument, primaryDocDescription`
  (each array is index-aligned - element `i` of every array describes filing `i`). Filter to
  `form == "8-K"`. For NVDA this yields ~61 recent 8-Ks; each carries `filingDate` (YYYY-MM-DD),
  `items` (comma-separated 8-K item codes such as `"5.02"` or `"8.01,9.01"`), `accessionNumber`
  (e.g. `"0001045810-26-000060"`), and `primaryDocument` (e.g. `"nvda-20260628.htm"`).

- **Filing URL (the honest source link for a marker).** Build the human filing index from the
  accession:
  `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodashes}/{primaryDocument}`
  where `{cik_int}` is the CIK as a plain integer (no zero-pad) and `{accession_nodashes}` is
  `accessionNumber` with all dashes removed (e.g. `0001045810-26-000060` -> `000104581026000060`).
  This URL is persisted as the event `url` and is the reader-verifiable provenance link.

- **Curated CIK map, NOT auto-derived (verified trap).** Do **not** derive CIKs from EDGAR's
  `company_tickers.json`. Use this curated map:
  - NVDA -> `["1045810"]`
  - MSFT -> `["789019"]`
  - CVX  -> `["93410"]`
  - SLB  -> `["87347"]`
  - XOM  -> `["34088", "2115436"]`

  **The XOM trap (ratified handling).** The current ticker map points XOM at CIK `2115436`
  ("ExxonMobil Holdings Corp", a 2026 reorg entity) which has only ~2 8-Ks. The real filing history
  lives under the **legacy** CIK `34088` ("EXXON MOBIL CORP", 107 8-Ks back to 2020, current through
  2026-07-01). **XOM uses `34088` as primary and additionally includes `2115436`** to catch the
  newest post-reorg filings. This is exactly why the map value is a **list** of CIKs per ticker:
  fetch every CIK in the list, merge the results, and **dedupe by accession number**. Any future
  ticker affected by a merger/reorg gets the same list treatment.

- **8-K item-code -> label map (for honest, informative titles).** Curate this small map; unknown
  codes fall back to a generic label. Do not invent labels beyond what the item code states.
  - `2.02` -> "Results of operations and financial condition"
  - `5.02` -> "Leadership / director & officer changes"
  - `8.01` -> "Other events"
  - `9.01` -> "Financial statements and exhibits"
  - `7.01` -> "Regulation FD disclosure"
  - `1.01` -> "Material definitive agreement"
  - `2.01` -> "Completion of acquisition or disposition"
  - unknown / unmapped code -> "Material event (8-K)"

- **SEC fair-access networking rules (mandatory).** Every request MUST send a `User-Agent` header
  that identifies the app and a real contact email; a missing or generic UA returns HTTP 403. The
  rate ceiling is 10 req/s - **design conservatively (<= ~5 req/s) with retry/backoff**. Send
  `Accept-Encoding: gzip, deflate`. Put the UA/contact string in config (seed value:
  `"MNE company-news ingest danielpark1620@gmail.com"`) so it is not hardcoded - and **flag to the
  owner that SEC requires a real contact address** (open decision 1). Mirror the existing network
  idiom in `mne/rss_fetch.py:1-14` (a `requests` call with an explicit `User-Agent` header
  constant) and its fail-soft error handling (`rss_fetch.py:92,140` - `requests.get(...)` wrapped so
  `Timeout`/`ConnectionError` degrade, never raise into the run).

- **Hand-derivability.** A news marker is reproducible: its `date`, `title`, `source`, and `url` all
  come from the persisted EDGAR 8-K record. **Persist the record into the asset_events store** (like
  earnings/macro today), and never re-fetch EDGAR live at render time. A reader can re-fetch the same
  submissions JSON, read the same accession row, and reproduce the stored marker exactly (AGENTS.md
  core philosophy).

- **Earnings-item (2.02) 8-Ks still show as News (ratified default).** A `2.02` "Results of
  operations" 8-K may land on the same day as a yfinance earnings marker. Ship it **as a News event
  anyway** - it is a different attributable source (SEC EDGAR filing vs the yfinance earnings
  calendar) - and let the existing **multi-event marker collapse** handle same-day stacking
  (`static/asset_chart.js:46` already renders `events.length` as the glyph when more than one event
  shares a day). Note this in the PR; see open decision 2.

---

## 3. New module `mne/sec_edgar.py` (fail-closed, mirror the asset_events/story_registry idiom)

Create `mne/sec_edgar.py`. Mirror the fail-closed idioms already in
`mne/asset_events.py` and `mne/story_registry.py`:

- A domain error: `class SecEdgarError(ValueError)` (mirror
  `AssetEventsError(ValueError)` at `mne/asset_events.py:27` and
  `StoryRegistryError(ValueError)` at `mne/story_registry.py:22`).
- A **frozen** normalized record dataclass, e.g. `Edgar8K` with fields
  `filing_date: str` (ISO YYYY-MM-DD), `items: tuple[str, ...]`, `accession: str`,
  `primary_document: str`, `url: str`, `title: str` (mirror the frozen `AssetEvent` at
  `mne/asset_events.py:31-38`).
- `ITEM_LABELS` - the curated item-code -> label dict from section 2; a `title_for_items(items)`
  helper that maps item codes to labels, joins multiple mapped labels honestly (e.g.
  "Results of operations and financial condition; Financial statements and exhibits"), and returns
  the generic "Material event (8-K)" when no code maps. Keep the join order stable (input order) so
  titles are deterministic.
- `build_filing_url(cik, accession, primary_document)` - constructs the archive index URL exactly as
  section 2 specifies (integer CIK, dash-stripped accession). Pure function, no network - unit-test
  it directly.
- A parser `parse_submissions(payload, cik)` that takes an already-decoded submissions dict and
  returns `tuple[Edgar8K, ...]`: read `filings.recent`, zip the parallel arrays, filter
  `form == "8-K"`, and build one `Edgar8K` per filing. This is **pure** (no network) so tests feed it
  a captured fixture. Fail-closed on shape: a non-dict payload, a missing `filings.recent`, or arrays
  of mismatched length raise `SecEdgarError`; an individual filing with a missing/blank required
  field is **skipped**, not fatal (honest partial degradation - one bad row must not drop the rest).
- A fetch wrapper `fetch_8k_filings(ciks, *, contact, session=None, as_of=None, since=None)` that:
  iterates the CIK list, GETs each `https://data.sec.gov/submissions/CIK{cik10}.json` with the
  mandatory headers (`User-Agent`=contact, `Accept-Encoding: gzip, deflate`), decodes JSON, calls
  `parse_submissions`, **merges across CIKs and dedupes by accession**, optionally filters to
  `filing_date >= since`, and returns the merged tuple sorted by `filing_date`. **Wrap all network
  and JSON decode paths so any failure degrades to an empty tuple - never raise into the run**
  (mirror `rss_fetch.py:140` and `asset_events.py`'s fail-soft loops). Apply conservative pacing
  (<= ~5 req/s) and simple retry/backoff on transient errors and 429/503. Accept an injectable
  `session`/transport so tests can supply a fake and never touch the network.

Keep this module free of any narrative/scoring imports - it is a self-contained EDGAR client plus
normalizer.

---

## 4. Curated CIK config `config/sec_edgar_map.json` (registry-owned, fail-closed validated)

Add `config/sec_edgar_map.json`, seeded with the five tickers below. This is **registry-owned
configuration** (AGENTS.md rule 7): the CIK map and the SEC contact string live in config, not in
code. Match the existing config shape - a top-level `"version"` semver string plus the payload
(every config in `config/` uses `"version": "1.0.0"`; confirmed for `asset_registry.json`,
`story_registry.json`, `narrative_asset_map.json`).

```json
{
  "version": "1.0.0",
  "contact": "MNE company-news ingest danielpark1620@gmail.com",
  "ciks": {
    "NVDA": ["1045810"],
    "MSFT": ["789019"],
    "CVX": ["93410"],
    "SLB": ["87347"],
    "XOM": ["34088", "2115436"]
  }
}
```

Add a fail-closed loader/validator in `mne/sec_edgar.py` (mirror
`validate_asset_event_feed` at `mne/asset_events.py:65-92` and `load_story_registry` at
`mne/story_registry.py:136`): object check -> `version` semver check (reuse the `_SEMVER` pattern,
`mne/story_registry.py:17` / `mne/asset_events.py:24`) -> `contact` must be a non-empty string ->
`ciks` must be a dict of `ticker -> non-empty list of CIK strings` (each CIK a non-empty numeric
string). Raise `SecEdgarError` with a precise `ciks[<ticker>]` location message on the first
violation; wrap `OSError`/`json.JSONDecodeError` from the file read into `SecEdgarError`. A missing
file is an error for this loader (the map is required config), matching the strict `load_*` variant,
not the empty-tolerant one.

**Flag to owner:** the seeded `contact` email must be confirmed as the real SEC contact before this
ships (open decision 1). Do not silently ship an unverified contact.

---

## 5. Extend `mne/asset_events.py` (add "news", parallel to earnings/macro)

The per-asset event store already persists earnings and macro markers. Extend it - additively - so
it also persists news:

- **Add `"news"` to the type set.** `EVENT_TYPES` at `mne/asset_events.py:22` is
  `frozenset({"earnings", "macro"})` -> `frozenset({"earnings", "macro", "news"})`. Update the
  validator's type-error branch at `mne/asset_events.py:82-83` (currently raises
  `"{location}.type must be earnings or macro"`) to include news.

- **Add an OPTIONAL `url` field to the frozen `AssetEvent`** (`mne/asset_events.py:31-38`), defaulting
  to empty/absent (e.g. `url: str = ""`). This is **backward-compatible**: earnings and macro events
  leave it unset. Rationale (state in the PR): an SEC filing URL is a long string that reads badly as
  plain text in the detail panel, and a filing marker's core value is **clicking through to the actual
  filing** - so the URL belongs in a first-class, clickable field, not buried in prose. A
  backward-compatible optional field is the right model and is contained to news.
  - **Validator change (`mne/asset_events.py:79-80`):** relax the current EXACT-set field match to:
    the six core fields (`date/type/title/blurb/detail/source`) are **required**, and `url` is the
    **only permitted optional extra** (present-and-non-empty-string, or absent - reject any other
    unexpected key, and reject a present-but-empty/whitespace `url`). **Existing persisted
    earnings/macro feeds (written with no `url`) MUST still validate** - state this explicitly and
    cover it in tests (section 7).
  - **Serializer change (`mne/asset_events.py:118-130`):** the writer must **omit `url` entirely when
    empty** so earnings/macro feed files stay **byte-identical** (no spurious `"url": ""` added to
    existing feeds). `EVENT_FIELDS` (`:23`) and the `asdict`-based serialization must be adjusted to
    include `url` only when set.

- **Add a news builder `_news_event(edgar_8k)`** beside `_earnings_event`
  (`mne/asset_events.py:166-174`) and `_macro_event` (`:148-163`), producing:
  - `date` = the 8-K `filing_date`
  - `type` = `"news"`
  - `title` = the curated title from `items` (section 2 map; multi-item joins; unknown -> generic)
  - `blurb` = an honest one-liner, e.g. `"SEC 8-K filing (material event)."`
  - `detail` = filing date + accession + the item labels, e.g.
    `"Filed 2026-06-28. Accession 0001045810-26-000060. Items: Results of operations and financial
    condition; Financial statements and exhibits."` (record what the filing IS, not what it means -
    do not editorialize the market reaction, matching the earnings builder's discipline at
    `mne/asset_events.py:172-173`)
  - `source` = `"SEC EDGAR"`
  - `url` = the filing index URL from `build_filing_url`. This is the reader-verifiable click-through
    link and lands in the new optional `url` field above; `detail` keeps the filing date + accession +
    item labels for provenance but **no longer carries the raw URL string**.
  - `_earnings_event` (`mne/asset_events.py:166-174`) and `_macro_event` (`:148-163`) are
    **unchanged** - they set no `url`.

- **Add the EDGAR fetch step inside `refresh_asset_event_feeds`** (`mne/asset_events.py:177-215`),
  parallel to the existing macro loop (`:205-209`) and earnings step (`:210-211`). Key points:
  - The current earnings step is gated on `canonical_ticker in MAJOR_COMPANY_CATALYSTS`
    (`mne/asset_events.py:210`). Of the five equities only NVDA and MSFT are in that watchlist
    (`mne/company_catalysts.py:7-18`), so **do not gate news on `MAJOR_COMPANY_CATALYSTS`** - gate it
    on the **`sec_edgar_map`** instead: a ticker gets news events iff it has CIKs in the map. This is
    what lets XOM / CVX / SLB (absent from the earnings watchlist) still get news markers.
  - Make the EDGAR fetch **injectable** for tests, exactly as the existing `earnings_loader`
    parameter is (`mne/asset_events.py:185`): add a parameter like
    `news_fetcher: Callable = <default that loads sec_edgar_map and calls fetch_8k_filings>` plus a
    `sec_edgar_map_file` path parameter. Tests pass a fake `news_fetcher` and never hit the network
    (see section 7). Load the map fail-soft: a missing/invalid map -> no news for anyone (honest
    empty), never a raise into the run.
  - **Bound to the candle window (~6 months).** Pass `since = as_of - ~183 days` (or reuse the
    chart's 6M / 126-session depth from the prior handoff) so news markers land on dates the chart
    actually renders. EDGAR returns years of 8-Ks; an out-of-window marker would never be visible and
    would bloat the file.
  - **Fail-soft per ticker.** A fetch failure for one ticker -> **no news events for that ticker**
    (honest empty), never a fabricated marker and never aborting the other tickers' feeds. The
    existing loop already continues past tickers with no symbol (`:200-202`); apply the same
    tolerance to news.
  - **Dedup.** News events flow through the same `_event_key`-keyed dedup dict already used at
    `mne/asset_events.py:212` (`_event_key` at `:95-96` keys on date/type/title/source). A repeated
    accession that yields an identical (date, "news", title, "SEC EDGAR") tuple collapses to one row;
    two different 8-Ks on the same day remain two rows and stack as a multi-event marker. Persist via
    the existing `write_asset_events` (`:118-130`), keyed by the **yfinance symbol** filename exactly
    as today (`:213`).

Nothing about the earnings or macro paths changes.

---

## 6. UI restore: News pill + "N" glyph + copy

All the generic marker/filter/hover/panel machinery already exists (section 1). Restore the two
News-specific pieces the prior sprint omitted, plus copy:

- **`static/asset_chart.js:46`** - extend the glyph expression to map `"news" -> "N"`:
  `earnings -> "E"`, `news -> "N"`, `macro -> "M"` (keep the multi-event numeral branch first). The
  marker stays the same slate circle (`stroke="#8b95a3"`, `fill="#171d25"`, `:47`) - hue encodes
  state, not event type, so News is slate like the others (ratified at
  `docs/handoffs/asset_execution_view_handoff.md:102-105`). The filter (`:20-23`, `:64`) and
  hover-merge (`:56`) already key off `event.type` generically and need no change; the only other JS
  change is the panel link below.

- **`static/asset_chart.js:59`** - the docked event panel builds each article's markup around
  `item.detail`. Add a **conditional clickable link** rendered only when `item.url` is present (i.e.
  news events): a `<a href="` + `esc(item.url)` + `" target="_blank" rel="noopener">` + the copy
  label + `</a>` placed next to the source line. When `item.url` is absent (earnings/macro), render
  nothing - no empty link. Use the existing `esc(...)` helper on the URL and route the link text
  through copy (below), never hardcode it.

- **`templates/asset_execution.html:18`** - insert the News pill into the event-filter row between
  the Earnings and Macro pills:
  `<button type="button" class="event-filter-btn" data-event-filter="news">{{ copy.filter_news }}</button>`.
  The final row is All / Earnings / News / Macro / Hide, matching the mockup. The generic handler at
  `static/asset_chart.js:64` picks it up with no change.

- **`mne/presentation_language.py`** - add the `"filter_news"` copy key to the
  `ASSET_EXECUTION_COPY` bundle beside the existing filter keys (`filter_all`/`filter_earnings`/
  `filter_macro`/`filter_hide` at `mne/presentation_language.py:285-288`), value `"News"`. Also add a
  `"view_filing"` key for the panel link label (e.g. `"View filing on SEC EDGAR"`) - the link text
  must route through copy, not be hardcoded in the JS. Add any other new user-facing phrase here too -
  **never hardcode user-facing copy in the template or JS** (AGENTS.md rule 3). The template already
  pulls the bundle
  via `asset_execution_copy_bundle()` (`mne/presentation_language.py:351-353`) and the JSON copy
  block at `templates/asset_execution.html:23`, so a new key is available to both template and JS
  automatically.

Do not restyle adjacent chart code, and do not touch the range pills, launch panel, story cards, or
sector grid.

---

## 7. Tests (unittest, fixture-based, no live network)

Run with **`./venv/bin/python -m unittest discover tests`** (this venv has no pytest; do not use
it). Add coverage; do not remove existing coverage except the one flip noted below.

- **Update `tests/test_asset_events.py:29-42`.** That test
  (`test_fail_closed_triad_and_exact_no_news_schema`) currently asserts `"news"` is **rejected** by
  `validate_asset_event_feed` (it loops `("news", "NEWS", "")` expecting `AssetEventsError`). Adding
  `"news"` to `EVENT_TYPES` will make the lowercase `"news"` case now **valid**, so this test will
  fail as written. **Flip it:** assert a well-formed `"news"` event now **validates**, while the
  genuinely invalid cases (`"NEWS"` wrong-case, `""` empty, and some unmapped type like `"rumor"`)
  still raise. Rename the method to drop the "no_news" implication. Do not weaken the other
  fail-closed assertions in that test (missing file -> empty, corrupt file -> raise).

- **Optional-`url` validator cases** (in `tests/test_asset_events.py`): a well-formed event **without**
  `url` still validates (protects existing earnings/macro feeds); a well-formed event **with** a
  non-empty `url` validates; a **present-but-empty/whitespace** `url` (and any other unexpected extra
  key) is **rejected** with `AssetEventsError`.

- **New `tests/test_sec_edgar.py`** with a **captured fixture** (a small, hand-trimmed submissions
  JSON with a handful of 8-K rows plus a non-8-K row to prove the filter). No network in tests -
  feed `parse_submissions` the fixture dict directly. Cover:
  1. **Parse:** the fixture yields the expected `Edgar8K` records; the non-8-K row is excluded;
     parallel-array zipping is index-aligned.
  2. **Item-code -> title mapping:** single mapped code, **multi-item** join (e.g. `"8.01,9.01"`),
     and an **unknown code** falling back to "Material event (8-K)".
  3. **URL construction:** `build_filing_url` produces the exact archive index URL from a known
     CIK + accession + primaryDocument (integer CIK, dash-stripped accession).
  4. **Merge + dedupe across CIKs:** two CIKs whose filings overlap on an accession dedupe to one
     record (the XOM two-CIK case), and distinct accessions are all kept.
  5. **Fail-closed config:** `sec_edgar_map.json` validation raises on bad version, missing
     `contact`, non-list CIK value, empty CIK list, and non-string CIK; a missing file raises.
  6. **Honest empty on fetch failure:** a `fetch_8k_filings` whose injected transport raises
     returns an empty tuple, not an exception.

- **Extend `tests/test_asset_events.py`** (mirror the existing
  `test_refresh_persists_earnings_and_only_story_relevant_macro` at
  `tests/test_asset_events.py:68-86`, which already injects `earnings_loader` and a temp calendar):
  1. **News schema + optional `url` round-trip:** a `"news"`-type `AssetEvent` writes and re-loads via
     `write_asset_events`/`load_asset_events` deterministically (mirror `:44-57`), and its `url`
     round-trips (present on the news event). Also assert an earnings/macro event round-trips with
     **no** `url` and that the serialized file **omits** the `url` key entirely (byte-stability of
     existing feeds).
  2. **Refresh persists news via an injected fetcher:** pass a fake `news_fetcher` returning known
     `Edgar8K` records for a ticker (e.g. XOM, which is **not** in `MAJOR_COMPANY_CATALYSTS`), and
     assert the persisted feed contains the news events - proving news is gated on the CIK map, not
     the earnings watchlist. Assert the derived `title`/`detail`/`source`/`url` (the URL lands in the
     `url` field, not in `detail`).
  3. **Window bound:** a fetched 8-K older than the ~6-month `since` cutoff is **not** persisted.
  4. **Fail-soft:** a `news_fetcher` that raises for a ticker yields an honest empty news set for
     that ticker while other tickers' feeds still write.
  5. **Same-day dedup/stacking:** two distinct 8-Ks on one date persist as two rows; an identical
     re-fetched accession collapses to one via `_event_key`.

**Do not add any test that performs a live SEC fetch.** All EDGAR access in tests goes through the
injected `news_fetcher` / fixture. **Two pre-existing `test_authorization` failures are known and
unrelated** - do not "fix" them and do not let them mask a new failure.

---

## 8. Verification standard (the repo standard - copy it exactly)

Per AGENTS.md verification standard and the prior handoff (section 8 there):

- **Full suite** via `./venv/bin/python -m unittest discover tests` (unittest, **not** pytest); apart
  from the two known `test_authorization` failures, nothing new fails.
- **Routes return 200:** `/`, `/admin`, `/research`, and the asset execution route
  `GET /research/{key}/sectors/{sector}/assets/{ticker}`. Run the dashboard with
  `./venv/bin/python -m uvicorn dashboard:app --port 8643`.
- **Seed real data, then browser-audit.** Run the refresh path (the `refresh_asset_event_feeds` call
  wired at `main.py:521-526`, or a direct invocation) to seed **real EDGAR** news events into the
  per-asset event store, then confirm in the browser:
  - **"N" markers render** on NVDA and on **at least one other** equity, **including XOM via CIK
    34088** (the legacy CIK is what produces XOM's markers - if XOM is empty, the two-CIK merge is
    wrong).
  - The **News pill is present** and the row reads All / Earnings / News / Macro / Hide; each filter
    counts correctly (News shows only news markers; All shows the union; Hide clears them; Earnings
    and Macro are unaffected).
  - **Hover-merge** appends the filing tag+title+blurb to the OHLC readout on a news-marker day;
    **clicking** docks exactly one detail panel showing the filing title, detail (filing date,
    accession, and item labels), source "SEC EDGAR", and a separate clickable "View filing" link to
    the source URL; Escape and Close dismiss.
  - **Honest empty:** a ticker with no in-window 8-K shows no News markers (not a fabricated one),
    and the chart is otherwise unaffected.
- **Reduced-motion** (`prefers-reduced-motion: reduce`) honored; **widths 1280 / 1024 / 390** with
  **no horizontal scroll**; the two-column dock collapses below 960px per the existing template
  media query (`templates/asset_execution.html:10`).
- **Color budget:** the News marker is **slate**, never a new hue; red stays downside-only.
- `git diff --check` clean; **nothing staged, committed, or pushed** (AGENTS.md rule 1).

---

## 9. Files to touch

- `mne/sec_edgar.py` - **new**: fail-closed EDGAR client + normalizer + item-label map + URL builder
  + `sec_edgar_map` loader/validator.
- `config/sec_edgar_map.json` - **new**: curated ticker -> CIK-list map + SEC contact (registry-owned).
- `mne/asset_events.py` - add `"news"` to `EVENT_TYPES` (`:22`), update the type-error branch
  (`:82-83`), add the **optional `url` field** to `AssetEvent` (`:31-38`) with the relaxed
  required-plus-optional-`url` validator (`:79-80`) and empty-omitting serializer (`:118-130`,
  `EVENT_FIELDS` `:23`), add `_news_event` (setting `url`), add the CIK-map-gated, window-bounded,
  fail-soft EDGAR step inside `refresh_asset_event_feeds` (`:177-215`) with an injectable
  `news_fetcher`.
- `static/asset_chart.js` - add the `news -> "N"` glyph branch (`:46`) and the conditional filing-link
  render in the docked panel (`:59`).
- `templates/asset_execution.html` - insert the News filter pill (`:18`).
- `mne/presentation_language.py` - add `"filter_news"` and `"view_filing"` (plus any new label) to
  `ASSET_EXECUTION_COPY` (`:285-288` area).
- `tests/test_asset_events.py` - flip the no-news schema test (`:29-42`); add news round-trip,
  CIK-gated refresh, window-bound, fail-soft, and dedup tests.
- `tests/test_sec_edgar.py` - **new**: fixture-based EDGAR parsing, title mapping, URL construction,
  merge/dedupe, config validation, honest-empty-on-failure.

Optionally, `main.py:521-526` if the refresh call needs to thread the `sec_edgar_map_file` /
`news_fetcher` default through - prefer defaulting them inside `refresh_asset_event_feeds` so the
existing call site needs no change.

---

## 10. Open decisions for the owner (flag, do not decide silently - AGENTS.md rule 2)

1. **SEC User-Agent contact.** Confirm the real contact email for the mandatory `User-Agent` header
   (seed value `"MNE company-news ingest danielpark1620@gmail.com"`). SEC returns 403 without a valid
   contact; a placeholder must not ship unverified.
2. **2.02 earnings-item 8-Ks as News.** Ratified default: show them as News (different attributable
   source than the yfinance earnings marker) and let the existing same-day multi-event marker
   collapse handle stacking. Confirm the owner is content with an "E" and an "N" stacking (rendered
   as a count glyph) on an earnings day, rather than suppressing one.
3. **IR RSS enrichment timing.** Company-newsroom RSS (NVDA / MSFT / CVX / SLB) is deferred to a
   later "official source layer" effort. When should that sprint be scheduled, and does it fold News
   into the source-intelligence pipeline (a bigger change than this chart-marker feature)?
4. **Backfill depth for longer chart ranges.** News is bounded to the ~6-month candle window. If the
   range pills ever gain a 1Y+ option, how far back should EDGAR 8-Ks be pulled and persisted (XOM's
   legacy CIK reaches back to 2020)?
