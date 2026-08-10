# Research v2 Shell - Implementation Handoff

**Status: not implemented - ready to hand to Codex. Do not implement from this document in this
session, and do not stage, commit, or push.** This is a Codex-ready brief for the v2 CHROME +
RESEARCH tier rework, delivered as four strictly serial sprints (J -> K -> L -> M). It restyles
existing research surfaces, generalizes the existing dashboard top bar, and wires two existing
run-data sources into the investigation view; it changes no scoring, no thresholds, and no taxonomy.
Every claim below was re-verified against the codebase; the file:line references are current as of
2026-08-10.

---

## 1. Purpose and canonical references

This handoff covers the **v2 chrome + Research tier only**, in four sequential, independently
shippable, browser-audited sprints:

- **Sprint J** - generalize the existing dashboard top bar into a shared partial and apply v2 chrome
  across the research tier (drop the legacy left rail on those pages, clean the filename leak).
- **Sprint K** - rebuild the `/research` index into the deterministic client-side **finder + index**
  (search box, 5 theme chips + a disabled Crypto chip, narrative index with nested stories).
- **Sprint L** - restyle the narrative investigation page to Design System v2 matching the mockup,
  **preserving every existing module**; add the two inline charts (strength sparkline,
  lead-instrument candle); **promote the existing narrative-matched catalyst events into a dedicated
  "On the clock" section** (presentation only, no new backend); add the jump-nav.
- **Sprint M** - wire two existing run-data sources into the investigation context and render them as
  real modules: **Stories in this narrative** (from the persisted `run.story_extraction`, filtered to
  the narrative's group) and **Sectors expressing it** (from the existing sector classification scoped
  to the narrative). Real data, honest empty states, no fabrication.

**Studio (the artboard canvas + Compare tool + personalization rail) is a SEPARATE later arc and is
OUT OF SCOPE here.** Only leave clean seams for it. Do not build the Studio view, the artboard, the
Compare tool, or the saved/watchlist rail.

**Canonical references (in precedence order):**

1. **Visual contract:** `docs/mockups/research_studio_concept_v1.html` - a self-contained,
   pure-ASCII HTML+CSS+JS mockup checked in beside this handoff (a sibling executor is placing it
   there; the byte-identical source is at
   `/private/tmp/claude-501/-Users-danielpark-macro-narrative-engine/cc0f3965-931c-4b70-b1f3-93b6781b36a2/scratchpad/mne-research-studio-mockup.html`).
   It carries a slim TOP BAR plus three views: a Research FINDER/INDEX (`#view-research`), a Research
   INVESTIGATION (`#view-investigation`), and STUDIO (`#view-studio`). **Only the Research + chrome
   parts are in scope.** Open it in a browser while building. **Where this document and the mockup
   disagree on pixels, the mockup wins; where they disagree on scope or data honesty, this document
   wins.**
2. **Written visual contract:** `docs/design_system.md` (Design System v2) - the token set, card
   system, semantic color rules, and component patterns bind this work.
3. **Charter:** `AGENTS.md` - standing rules, especially never stage/commit/push, terminology
   discipline (rule 3: all user-facing copy via `mne/presentation_language.py`), and honest empty
   states.

**Accurate description of the mockup (read it before starting).**

- **Top bar** (`.topbar`, mockup L723-741): brand mark + wordmark on the left; a primary nav
  (`.app-nav`) of `Overview - Research - Studio - Preferences` with dot separators and an active
  underline; a pill `Sign in` control on the right. **Note the divergence:** the mockup's nav
  includes a **Studio** item; the ratified production nav omits Studio for now (section 2). The
  mockup has **no** History and **no** Admin item, and **no** run-selector or data-quality pill in
  the bar - these are the ratified production nav and are a deliberate reduction from today's
  dashboard bar.
- **Research finder + index** (`#view-research`, L746-790): an eyebrow + `status-line`
  ("Markets closed - Thu Aug 6, 2026"), a display headline "Find the story you need", a subtitle, a
  **saved banner** (Studio-tier, see section 2), a **finder bar** (search input + clear button + two
  helper lines, one of which explicitly points deeper questions at the AI Analyst), a **chip row**
  of 5 theme chips + a disabled "Crypto - not tracked yet" chip with a live-region hint, and a
  **narrative index** (`#nrvList`) with an honest empty state (`#indexEmpty`).
- **Narrative investigation** (`#view-investigation`, L793-1125): a back-link + breadcrumb, a
  **jump-nav** (`.jump-nav`, 9 in-page anchors), then a stack of cards: a hero carrying the single
  teal glow (`.card.glow-teal`) with a Save star; a Snapshot vitals tile-grid; a **Recent Memory**
  card that contains the **strength sparkline** (`.strength-chart`, teal line + area gradient +
  endpoint `.spark-dot`, L869-885) above a memory strip; a Why card; a From-the-tape evidence list;
  an On-the-clock catalyst grid; a **Market Expression** card that contains the **compact
  lead-instrument candle** (`.mini-candle`, teal-up / red-down rects + "Open asset view ->" link,
  L977-1035) above an instrument list; a Sectors strip; a Stories grid; an Ask-the-analyst panel; a
  Related-narratives row; and a Limitations card whose footer reads "Latest verified read - Thu
  Aug 6, 2026" (never a filename).
- **Studio** (`#view-studio`, L1128-1220): OUT OF SCOPE. Do not build.

The mockup's finder/index data (`STORIES`, `NARRATIVES` at L1232-1338) and all investigation copy
are **illustrative literals**. The production build replaces them with the persisted engine data
named below, but must preserve the rendered anatomy and interaction behavior of the in-scope views.

**Important: the mockup's investigation view is a representative SUBSET, not the full page.** The
real investigation page (`templates/narrative_investigation.html`) has more modules than the mockup
shows (Historical Connections, Coverage breadth, Source summary, the full Research-entry-points
zone, admin diagnostics, and more). **Sprint L preserves every real module.** The mockup cards for
On the clock, Stories in this narrative, and Sectors expressing it are **not fabricated and not
omitted - they are built from real existing run data**: On the clock is a re-presentation of the
narrative-matched catalyst events the investigation builder already produces (promoted in Sprint L,
section 6.5), and Stories + Sectors are wired from `run.story_extraction` and the existing sector
classification (Sprint M, section 7). Each has an honest empty state when the narrative has no
matched events / stories / sectors.

---

## 2. Ratified decisions (state prominently; do not re-litigate)

These are pre-ratified by the owner. Do not re-open them; flag only genuinely new ambiguity
(AGENTS.md).

- **Reuse the existing dashboard top bar.** The dashboard "/" already replaced the legacy app rail
  with a slim top bar in Sprint F - it is inline in `templates/dashboard.html:17-62`, styled at
  `static/styles.css:3821-3848`, and its copy comes from `DASHBOARD_PARITY_COPY`
  (`mne/presentation_language.py:199-206`) via `dashboard_parity_copy`
  (`mne/presentation_language.py:236`) and `DASHBOARD_PARITY_COPY_KEYS` (`dashboard.py:1258-1266`).
  **Sprint J generalizes that SAME top bar into a shared partial and applies it to the research
  tier - do not invent a new nav component.**
- **Production nav = Overview - Research - Preferences + the account/sign-in control. No History,
  no Admin, no Studio.** Today's dashboard bar still lists History (`dashboard.py:24-26` renders
  Overview / Research / History / Preferences). Sprint J drops History and keeps Overview / Research
  / Preferences. Admin never appears. Studio is omitted until the Studio arc ships (below).
- **History leaves the primary nav; its routes and entitlements REMAIN and keep working.** The
  `/history` "Historical Archive" routes, templates (`templates/historical_*.html`), and
  entitlements are untouched - History is simply not a top-line nav item anymore (it becomes the
  Studio "Compare" tool in the later arc; the mockup labels the Compare card "Was: History"). In the
  interim users still reach the archive through **existing in-page links** - e.g. the investigation
  History-preview link `history_full_link` (`templates/narrative_investigation.html:180`, ->
  `narrative_history` route) and the Historical-Connections cards (`:184-212`). **Do not delete those
  routes or links.** How prominently the archive should stay reachable is an owner decision
  (section 10).
- **Admin is a separate owner surface.** Remove Admin from the shared nav. Admin pages
  (`templates/admin.html` and the `/admin/*` chain) keep their existing chrome and are OUT OF SCOPE
  for the v2 restyle - do not break them. The owner reaches `/admin` directly.
- **Studio is omitted from the nav until the Studio arc ships.** Build the shared top bar so a Studio
  item can be added later (a data-driven nav list makes this trivial), but do NOT render a
  dead/coming-soon Studio item now. This diverges from the mockup's nav, which shows Studio - the
  omission is the ratified default. (If you think a disabled placeholder is preferable, flag it as an
  owner decision; the default is omit.)
- **Clean the header - no run filename in the UI.** The research-tier pages currently leak a raw run
  filename: `templates/narrative_investigation.html:20`, `templates/research_selector.html:17`,
  `templates/asset_exploration.html:3`, and `templates/asset_execution.html:13` all render
  `Latest meaningful run: {{ selected_file or "Unavailable" }}`. `selected_file` is a raw
  `YYYY-MM-DD_HHMMSS.json` name (`dashboard.py:2255`). **Replace it with plain-language status** - a
  date / "latest verified read" - using the existing `fmt_run_label(path)` helper
  (`dashboard.py:421-435`, which returns "Today 3:44 PM" / "Aug 6" / "Aug 6, 2026"), never a raw
  filename. Do not invent a new timestamp.
- **v2 palette extends into the research tier.** Like the Asset Execution View already did (see
  `docs/handoffs/asset_execution_view_handoff.md` section 5.1), the research pages adopt Design
  System v2 (obsidian / teal / amber / slate; **red = downside price moves only**). Note this
  prominently in each PR as the deliberate, owner-ratified continuation of the v2 extension into the
  research tier, so the auditor does not read it as palette drift. (One live artifact of the old
  palette to fix: the dashboard nav active underline uses `var(--up)` at `static/styles.css:3840`;
  the mockup uses `var(--teal)`. Sprint J moves the shared partial to `--teal`.)
- **The finder is deterministic + client-side for v1.** No new search backend and no AI. The finder
  filters the already-rendered narratives + stories client-side (a small set: ~4 narrative groups +
  ~15 stories) by matching typed text against name / keyword / sector / catalyst, and the topic
  chips filter by the 5 real taxonomy themes. Mirror the mockup's `renderIndex` /
  `storyMatchesQuery` / `storyMatchesTheme` logic (L1401-1514). **The AI Analyst already exists**
  (`templates/_partials/ai_analyst.html` + `mne/ai_analyst.py`, included on the investigation page at
  `narrative_investigation.html:308`) and answers deeper questions - the finder does not replace it,
  and the finder helper copy must point deeper questions at it (mockup L768).
- **Honest theme coverage.** The topic chips are the 5 real taxonomy themes only - **AI, Rates,
  Inflation, Energy, Recession** (verified: `config/theme_taxonomy.json` themes are exactly
  `ai, rates, inflation, energy, recession`) - plus an honest DISABLED "Crypto - not tracked yet"
  chip that fabricates nothing (mockup `#chipCrypto`, L778, and its no-op hint at L1540-1542).
  **Geopolitical Risk** renders in the index with an honest "Defined, not currently scored" tag: it
  is defined in `NARRATIVE_GROUPS` (`mne/narrative_signals.py:5`) as themes `war / china / tariffs`,
  **none of which are scored taxonomy themes**, so `compute_group_scores`
  (`mne/narrative_signals.py:9-18`) never emits a score for it. Show it, but never with a fabricated
  score or stories (mockup `scored:false` branch, L1332-1337 and L1469-1471).
- **Star / save scope (verified against the store).** The personalization store follows narratives
  at **group / theme granularity only**: `follow_narrative(profile, narrative_level, narrative_key)`
  validates `narrative_level in _NARRATIVE_LEVELS` and stores
  `{"narrative_level", "narrative_key"}` records (`mne/personalization.py:131-147`); the write path
  is `POST /preferences/narratives` (`dashboard.py:2638-2659`, which requires auth, the
  `FOLLOWED_NARRATIVES` entitlement, and capacity). **There is no story-slug granularity in the
  store.** Therefore:
  - **Narrative star -> wire to the existing follow mechanism** (`follow_narrative` /
    `unfollow_narrative` via `POST /preferences/narratives`). This is the same watchlist the
    dashboard already uses.
  - **Story-level starring and the "Saved collection" surface are DEFERRED to the Studio arc.** The
    store cannot key by story slug today. Keep the story star and the mockup's "Saved N" banner as
    **visual affordances only** that honestly flag "coming with Studio" (or omit the banner) - do
    **not** wire them to a fake persistence path and do not invent a story-slug store here. State
    which you chose in the PR. (Whether to add story-slug granularity now or wait for Studio is an
    owner decision, section 9.)

---

## 3. Data reality and honesty rules (read before writing any code)

- **The finder set is small and fully client-side.** ~4 narrative groups (`NARRATIVE_GROUPS`,
  `mne/narrative_signals.py:1-6`) and ~15 stories (`config/story_registry.json` -> `stories`, keyed
  by slug, each with `display_name`, `group`, `themes`, `keywords{strong,medium,weak}`,
  `driving_sectors`, `catalyst_names`, `connected`). Filtering happens in the browser against
  server-rendered data - **no search endpoint, no network round-trip, no AI.**
- **Only scored narratives get a score/direction/investigate link.** `build_narrative_selector`
  (`mne/research_workspace.py:86-131`) only emits narratives whose score is `> 0`. A narrative with
  nothing to score today (Geopolitical Risk) shows "Defined, not currently scored" and **no**
  investigate button - never a fabricated score.
- **Honest empty states everywhere.** A search / filter that matches nothing shows the index empty
  message (mockup `#indexEmpty`, L789), not a blank page. A narrative with no qualifying stories in
  today's read shows that plainly. A lead instrument with no persisted candle shows the honest empty
  chart state (section 6.4), never invented candles.
- **No engine-language leak, no filenames.** All user-facing copy routes through
  `mne/presentation_language.py` (AGENTS.md rule 3). Raw engine terms (`persistence_score`,
  `narrative_pulse`, `concentration_gap`, role codes) and raw run filenames never render in primary
  copy.

---

## 4. Sprint J - v2 chrome across the research tier

**Goal:** generalize the dashboard top bar into a shared partial, apply it to the research-tier
templates in place of the legacy left rail, remove History/Admin from the nav, clean the filename
leak, and re-center the page shells now that the left rail column is gone. No finder and no
investigation restyle yet - those are Sprints K and L.

### 4.1 The legacy chrome being replaced

`templates/_partials/app_rail.html` is the legacy vertical left rail (verified): brand at L2, nav
list Overview / Research / Preferences / History (L5-23), a conditional Admin item (L24-30), an
account/sign-in link (L32), and a tier label (L33-40). It is included by (verified via
`grep app_rail templates/*.html`):

- **Research tier (Sprint J replaces the rail here):** `research_selector.html:11`,
  `narrative_investigation.html:14`, `sector_isolation.html:3`, `asset_exploration.html:3`,
  `asset_execution.html:13`, `narrative_history.html:12`.
- **Utility pages (apply the shared top bar per the nav):** `preferences.html:10`, `account.html:1`.
- **Out of scope - keep the legacy rail, do not touch:** `admin.html:11`, `entitlement_denied.html:6`,
  and every `historical_*.html` template (`historical_comparison.html:11`,
  `historical_comparison_user.html:12`, `historical_request.html:12`,
  `historical_request_status.html:12`, `historical_research.html:12`,
  `historical_investigation.html:13`, `historical_workflow.html:11`, `historical_selector.html:11`).
  **Do not delete `app_rail.html`** - it remains in use by these surfaces. Flag this split chrome
  (some pages on the new top bar, admin/historical on the legacy rail) to the auditor as an
  intentional interim seam (section 10).

### 4.2 Create the shared top-bar partial

- Extract the dashboard top bar (`templates/dashboard.html:17-62`) into a new partial
  **`templates/_partials/app_topbar.html`**, then include it from `dashboard.html` (replacing the
  inline block) and from the research-tier + utility templates in 4.1. Reuse the existing
  `.dashboard-topbar` CSS (`static/styles.css:3821-3848`); do not fork a second stylesheet.
- **Nav list (ratified):** Overview -> `/`, Research -> `/research`, Preferences -> `/preferences`,
  then the account/sign-in control. **Remove the History link** (currently
  `dashboard.html:25`). **No Admin, no Studio.** Drive the active state from the existing
  `active_tier` variable the research templates already set (`{% set active_tier = "research" %}`)
  so the correct item underlines per page. Copy comes from the existing keys
  `nav_overview / nav_research / nav_preferences / nav_sign_in / brand_short / brand_full`
  (`mne/presentation_language.py:202-206`); **do not hardcode nav labels.** Leave the `nav_history`
  key in place (it is still used elsewhere) - just stop rendering it in this bar.
- **Utilities slot is optional/conditional.** The dashboard bar also renders a data-quality pill
  (`dashboard.html:29-50`, gated on `view.dashboard_trust_summary`) and a run-selector
  (`dashboard.html:52-59`, driven by `recent_runs`/`selected_file`). Research-tier pages do not
  provide those, and the mockup top bar shows neither. Make the partial render the data-quality pill
  and run-selector **only when their context is present** (so the dashboard keeps them and research
  pages show brand + nav + sign-in only, matching the mockup). Account/preferences: keep their forms
  working; they get the top bar but no run selector. Flag the "should research ever get a run
  selector" question to the owner (section 10) rather than adding one.
- **Account/sign-in control:** render the signed-in display name or a "Sign in" link, mirroring the
  existing dashboard logic (`dashboard.html:60`, `current_user` present) and the app_rail account
  logic (`app_rail.html:32`). Style it to the mockup's `.signin` pill only insofar as the shared
  `.dashboard-topbar` styles already allow; do not invent a new component.
- Switch the active-underline color from `var(--up)` to `var(--teal)` at
  `static/styles.css:3840` (the only palette drift in the shared bar; matches the mockup).

### 4.3 Clean the header (remove the filename leak)

On each of the six research-tier templates, **remove the separate `site-header` /
`investigation-header-static` block that renders
`Latest meaningful run: {{ selected_file }}`** (verified at `narrative_investigation.html:15-22`,
`research_selector.html:12-19`, `asset_exploration.html:3`, `asset_execution.html:13`; the same leak
also sits in `sector_isolation.html` and `narrative_history.html` header blocks - grep each and
remove). Where a freshness line is still wanted, render a plain-language status using
`fmt_run_label(current_file)` (`dashboard.py:421-435`) or a "latest verified read" line - **never
`selected_file`**. The finder/index and investigation pages carry their own in-view eyebrow/status
line in Sprints K/L (mockup `status-line`, L749; and the Limitations footer "Latest verified read",
L1120); Sprint J only needs to delete the raw-filename block and keep the pages rendering.

### 4.4 Re-center the page shells

The research templates use `page-shell research-shell` main wrappers that were laid out beside the
left rail (e.g. `narrative_investigation.html:24`, `research_selector.html:21`). With the rail gone
and a full-width top bar above, the content must center under the 1200px bar. Match the mockup's
`.wrap { max-width: 1200px; margin: 0 auto; padding: 0 20px; }` (mockup L42). Adjust the
`research-shell` / `page-shell` rules in `static/styles.css` so the content column centers with no
left-rail offset and no horizontal scroll at 1280 / 1024 / 390. Do not restyle module internals in
this sprint - only the shell/centering and the chrome.

### 4.5 Files to touch (Sprint J)

- `templates/_partials/app_topbar.html` - **new** shared partial (extracted from `dashboard.html`).
- `templates/dashboard.html` - replace the inline top bar (L17-62) with the include; drop the
  History link.
- `templates/research_selector.html`, `templates/narrative_investigation.html`,
  `templates/sector_isolation.html`, `templates/asset_exploration.html`,
  `templates/asset_execution.html`, `templates/narrative_history.html` - swap the `app_rail` include
  for the `app_topbar` include; delete the filename header block; keep `active_tier` set.
- `templates/preferences.html`, `templates/account.html` - swap `app_rail` for `app_topbar`
  (keep their forms/logic intact).
- `static/styles.css` - `--up` -> `--teal` on the nav underline (`:3840`); optional/conditional
  utilities styling; `research-shell` / `page-shell` centering.
- `dashboard.py` - if the research/investigation contexts do not already pass `dashboard_copy` and
  `current_user`/`selected_file` needed by the shared partial, add them (they already pass
  `selected_file`; wire `dashboard_copy` from `DASHBOARD_PARITY_COPY_KEYS` as `dashboard.py:2590-2592`
  already does for the parity dashboard). Do **not** add a run selector to research contexts.
- Do **not** touch `app_rail.html`, `admin.html`, `entitlement_denied.html`, or any
  `historical_*.html`.

### 4.6 Verification (Sprint J)

- Full suite green apart from the two known failures (section 9).
- Dashboard up; these routes return **200** and render with the new top bar: `/`, `/research`,
  `/research/{key}` (investigation), `/research/{key}/history`, `/research/{key}/sectors`,
  `/research/{key}/sectors/{sector}/assets`, `/research/{key}/sectors/{sector}/assets/{ticker}`,
  `/preferences`, `/account`. `/admin` still returns **200** on its legacy rail.
- **No run filename anywhere in the rendered research pages** (grep the served HTML for the
  `YYYY-MM-DD_HHMMSS` pattern; expect none).
- Nav shows Overview / Research / Preferences + account only - **no History, no Admin, no Studio**.
- Widths 1280 / 1024 / 390: no horizontal scroll; content centers under the 1200px bar. JS-disabled:
  pages render. Reduced-motion honored. Color budget: teal / amber / slate / red only, red
  downside-only.
- `git diff --check` clean; nothing staged, committed, or pushed.

---

## 5. Sprint K - Research finder + index

**Depends on Sprint J's chrome.** Rebuild the `/research` index into the finder: a client-side
search input, the 5 theme chips + a disabled Crypto chip, and a narrative index with stories nested
under each narrative. Match `#view-research` in the mockup (L746-790) and its JS (L1391-1542).

### 5.1 Server context

- Extend `build_research_context` (`dashboard.py:2249-2265`) and/or `build_narrative_selector`
  (`mne/research_workspace.py:86-131`) to hand the template the index data as a server-rendered,
  JSON-serializable structure the client filter can read (mirror the mockup's `STORIES` and
  `NARRATIVES` shape, L1232-1338):
  - **Narratives** in display order from `NARRATIVES` / `NARRATIVE_GROUPS`
    (`mne/narrative_signals.py:1-6`): for each, `name`, `scored` (bool), `score` + direction/state +
    share when scored (from `build_narrative_selector`'s `group_scores`), the nested story slugs from
    `config/story_registry.json` (filter to that narrative's `group`), and search keywords. Scored
    narratives get an "Investigate ->" link to the existing investigation route
    (`url_for('narrative_investigation', key=narrative.key)`, same as
    `research_selector.html:45`). Geopolitical Risk is `scored:false` -> "Defined, not currently
    scored", no score, no stories, no investigate link.
  - **Stories** from `config/story_registry.json` -> `stories` (and/or the deterministic
    `mne/story_extraction.py` `build_story_extraction` output): per slug, `display_name`, `group`,
    `theme` (first of `themes`), direction/state if available, and the search keyword blob
    (`display_name` + `keywords` + `driving_sectors` + `catalyst_names`). Keep this deterministic -
    no live fetch.
- Direction/state -> glyph + color must obey the semantic rules: up = strengthening (teal),
  down = fading (amber), steady = slate (mockup `GLYPH`, L1340-1344; design_system.md section 4).
  Reuse existing direction/presentation copy from `mne/presentation_language.py`; do not hardcode
  state words in the template.

### 5.2 Template + client filter

- Rebuild `templates/research_selector.html`'s body to the mockup's finder anatomy: the view eyebrow
  + plain-language status line (via `fmt_run_label`), the display headline + subtitle, the finder bar
  (`#finderInput` + `#finderClear` + the two helper lines, one pointing deeper questions at the AI
  Analyst), the theme chip row (`ai / rates / inflation / energy / recession` + the disabled
  `Crypto - not tracked yet` chip with its live-region hint), and the narrative index (`#nrvList`)
  with the honest empty state (`#indexEmpty`). Reuse the Design System v2 card system and tokens; do
  not invent one-off styles.
- Port the mockup's client filter (`renderIndex`, `storyMatchesQuery`, `storyMatchesTheme`, chip
  toggles; L1401-1542) into a small progressive-enhancement script (vanilla JS, no build step,
  following the `static/chart.js` pattern). Matching is case-insensitive substring against
  `name + keywords` for narratives and stories; theme chips union-filter by theme; the disabled
  Crypto chip is a no-op that sets the honest hint. **With JS disabled, the full server-rendered
  index must still be visible** (the filter only hides/shows already-rendered rows) - verify the
  noscript path.
- **Narrative star:** wire to the existing follow mechanism (`POST /preferences/narratives` with
  `action=follow|unfollow`, `narrative_level`, `narrative_key`; `dashboard.py:2638-2659`). For
  signed-out users or missing entitlement the control must degrade honestly (e.g. link to sign-in),
  mirroring how the dashboard watchlist handles it - do not fake a successful follow.
- **Story star + "Saved N" banner:** DEFERRED to Studio (section 2). Render the story star as a
  visual affordance that flags "coming with Studio" (or omit), and either omit the saved banner or
  render it as an inert Studio teaser. Do not wire either to a fake store.
- All copy via `mne/presentation_language.py` - add new keys for the finder headline, subtitle,
  helper lines, chip labels, the Crypto hint, the "Defined, not currently scored" tag, and the empty
  state; never inline them.

### 5.3 Files to touch (Sprint K)

- `dashboard.py` - extend `build_research_context` to pass the index/finder data.
- `mne/research_workspace.py` - extend/`build_narrative_selector` to assemble narratives + nested
  stories from `NARRATIVE_GROUPS` + `config/story_registry.json` (+ `mne/story_extraction.py`).
- `templates/research_selector.html` - rebuild body into the finder + index.
- `static/` - a new small finder script (progressive enhancement), or an inline `<script>` per the
  mockup; follow the `static/chart.js` no-build pattern.
- `mne/presentation_language.py` - new copy keys.
- `static/styles.css` - finder / chip / narrative-index styles ported from the mockup (`.finder`,
  `.chip`, `.nrv-*`, `.story-chip`, mockup L425-545).

### 5.4 Verification (Sprint K)

- `/research` returns **200** and renders the finder + full index against the latest real run, a
  populated synthetic run, and an honest empty/degraded run.
- Typing filters narratives and stories client-side; a no-match query shows the empty state; the
  theme chips union-filter; the disabled Crypto chip shows the honest hint and returns no results;
  Geopolitical Risk shows "Defined, not currently scored" with no score/stories/investigate link.
- Each scored narrative's "Investigate ->" opens the existing investigation route (200).
- JS-disabled: the full server-rendered index is visible. Reduced-motion honored. Widths
  1280 / 1024 / 390: no horizontal scroll. Color budget respected (teal/amber/slate; red
  downside-only; no new glow beyond the design_system's one-per-section rule).
- `git diff --check` clean; nothing staged, committed, or pushed.

---

## 6. Sprint L - Investigation v2 restyle + the two charts

**Depends on Sprints J and K.** Restyle `templates/narrative_investigation.html` to Design System v2
matching the mockup's `#view-investigation`, **PRESERVING EVERY EXISTING MODULE**, then ADD: the two
inline charts (6.2, 6.3), the promoted On-the-clock section (6.5), and the jump-nav (6.4). Sprint L
is presentation-only - no new data wiring (the Stories + Sectors data wiring is Sprint M, section 7).

### 6.1 Preserve every existing module (verified inventory)

Re-verify against `templates/narrative_investigation.html` + `mne/research_workspace.py`
(`build_narrative_investigation`, L134-188). The real page's modules, in order, are:

- **Hero / explanation** (L37-43): eyebrow, `explanation.headline`, `what_changed`, `why_it_matters`,
  `supporting_points`.
- **Sticky zone/jump nav** (L45-50): currently 4 anchors (Snapshot / Explanation / Evidence /
  Research). Restyle + expand in 6.4.
- **Zone 1 Snapshot** (L52-97): score + `leadership`, Pulse (+ confidence), Regime Alignment
  (score + state), Evidence Breadth (`coverage.coverage_state`), inside a `details` progressive
  disclosure, plus the `explanation.limitations` list.
- **Zone 2 Explanation / brief** (L99-119): brief headline, `Data Completeness` confidence, brief
  sections, and the honest empty state when no brief is persisted.
- **Recent Memory** (L121-166): state badge + summary + `Appearances / Dominance / Streak /
  Momentum / Score Delta / Share Delta` grid inside a `details`, plus the empty state. **This is
  where the strength sparkline goes (6.2).**
- **History preview / sparkline** (L168-182): `history_summary(...)` macro + the existing
  `history.score_chart` polyline (L172-176) or the `thin` message or the full-history link
  (`history_full_link`). **Keep the full-history link** (interim archive reachability, section 2).
- **Historical Connections** (L184-212): connection cards, empty message, limitations.
- **Market Expression** (L214-238): expression `explanation` (headline / what_changed /
  why_it_matters / supporting_points / limitations) + a `details` list of `instruments`
  (`label`, `role`, `move`, `status`). **This is where the lead-instrument candle goes (6.3).**
- **Zone 3 Evidence** (L240-306): accepted attributed evidence (`evidence_list`), the evidence
  reader (`evidence_reader`), Coverage / Evidence breadth (`coverage` dl), Source Summary
  (contributing sources), and every empty state.
- **AI Analyst panel** (L308, `{% include "_partials/ai_analyst.html" %}`).
- **Related narratives** (L309-325).
- **Zone 4 Research entry points** (L326-386): review-evidence, compare-with-dashboard, the
  admin-diagnostics row (gated on `is_admin and investigation.platform_observability`), the two
  future-doorway placeholders, and the catalyst-events loop or its empty state.
- **Evidence reader script** partial (L389).

**Do not drop, merge, or silently re-scope any of these.** The X-ray / progressive-disclosure
`details` blocks, all honesty/limitations copy, and every empty state are load-bearing - carry them
into the v2 markup. Restyle to the v2 card system (`.card`, tokens, one glow on the hero only);
route any new copy through `mne/presentation_language.py`.

### 6.2 Add the strength-history sparkline (Recent Memory module)

Promote/restyle the existing history preview into a teal line + area sparkline with an endpoint dot,
placed inside the Recent Memory card (mockup `.strength-chart`, L869-885).

- **Data:** reuse the score series from `build_narrative_history(narrative_id)`
  (`mne/narrative_history.py:178-...`), whose `score_chart` (`_chart`, L126-175) already returns
  `available` + `segments` of `{x, y}` points over a 640x180 viewBox. The investigation context
  already carries a `history` object with `score_chart` (used at
  `narrative_investigation.html:171-176`) - reuse it rather than recomputing. `available` requires
  >= 3 scored points; when it is false, keep the existing honest fallbacks (`history.thin` / no
  chart).
- **Render:** a teal line (`--teal`) + a low-opacity teal area gradient fill + an emphasized endpoint
  dot, matching the mockup's `#strengthFill` gradient and `.spark-dot` (L873-884). This restyles the
  existing bare polyline (`.regime-line`) - it does not add a new data source. Provide an SVG
  `aria-label` describing the trend (mockup L873). No new glow.

### 6.3 Add the compact lead-instrument candle (Market Expression module)

Add a compact daily-candle teaser for the narrative's lead/primary instrument inside the Market
Expression card (mockup `.mini-candle`, L977-1035), above the existing instrument list.

- **Pick the lead instrument:** the `primary`-role instrument from
  `build_market_expression_for_run(run, narrative_id)` (`mne/research_workspace.py:183-186`;
  instruments carry `role in {primary, secondary, offset}`, `asset` = registry ticker, `label`,
  `move`, `status`; see `mne/market_expression.py:154, 188-190`). Use the first `primary` instrument;
  if none, honest-empty (below).
- **Load candles:** reuse the Sprint-G store via
  `load_asset_price_history_or_empty(ticker, ...)` (`mne/asset_price_history.py:125-134`), which
  returns an empty `AssetPriceHistory(candles=())` when the file is absent (the honest empty state).
  **Translate the registry ticker -> yfinance symbol before loading**, because the store is keyed by
  yfinance symbol filenames (`^VIX.json`, `DX-Y.NYB.json`), not registry tickers. Reuse the existing
  maps as the single source of that translation: `NASDAQ_TICKERS` (`main.py:115-119`, e.g.
  `VIX -> ^VIX`, `DXY -> DX-Y.NYB`), `ASSET_EXPANSION_TICKERS` (`main.py:122`), and
  `build_sector_ticker_map()` (`main.py:504`, imported from `mne.sector_market_context`). Do not
  hardcode a second copy. Most tickers (NVDA, QQQ, XLK, ...) map to themselves.
- **Render:** a compact teal-up / red-down candle SVG (mockup rects, L984-1031) using `--teal` for up
  days and `--red` for down days (downside only) - no rails, no launch line, no event markers, no
  new glow (this is a teaser, not the full asset-execution chart). Provide an SVG `aria-label`. When
  there are no candles, render the honest empty state ("No price history yet for this instrument"),
  never invented candles (AGENTS.md honest empty states; mirror the asset-execution honesty rule in
  `docs/handoffs/asset_execution_view_handoff.md` section 3).
- **"Open asset view ->" link:** link to the existing asset execution route
  `/research/{key}/sectors/{sector}/assets/{ticker}` (`dashboard.py:2811`). **Seam to resolve/flag:**
  that route needs a `{sector}` segment, but Market Expression instruments do not currently carry a
  sector. Derive the lead instrument's sector from the sector map (mirror how the existing asset grid
  builds `research_href` at `mne/asset_exploration.py:203`), or, if a single sector cannot be
  determined cleanly, link to the sector index (`/research/{key}/sectors`) and **flag the tension to
  the auditor** rather than guessing (AGENTS.md - unratified linking decisions get flagged, not
  decided silently).

### 6.4 Jump-nav

Restyle and expand the existing sticky zone-jump nav (`narrative_investigation.html:45-50`) into the
mockup's `.jump-nav` (L802-812), adding in-page anchors for the modules that exist on the real page
(e.g. What's happening / Recent memory / Why / From the tape / Market / Evidence / Related / Ask the
analyst). Only anchor modules that actually render; do not add anchors to mockup-only sections that
have no backing data (6.5). Reduced-motion: anchor jumps use `behavior: auto`.

### 6.5 On the clock - promote the existing narrative-matched catalyst events (presentation only)

The investigation builder **already produces narrative-matched catalyst events**:
`build_narrative_investigation` sets `context["events"]` from `run.event_lifecycle` matched to the
narrative (`mne/research_workspace.py:173-178`, `_events(...)`), and the template already renders
those events - but **buried at the bottom of Zone 4** (`narrative_investigation.html:370-384`, inside
the Research-entry-points grid), each linking to `/#catalysts` with a lifecycle-state label, plus an
honest empty state (`event-empty-state`, L381-383) when there are none.

**Sprint L PROMOTES that existing `investigation.events` data into a dedicated "On the clock for this
narrative" section** with the mockup's catalyst-countdown treatment (mockup `.cat-grid` /
`.cat-card`, L943-969: a "Soonest / Upcoming" label, a mono countdown, the event name, and a one-line
"why this matters"; the soonest card carries the single teal glow, design_system.md section 6
"Event countdowns"). This is **re-presentation only** - it reads the same `investigation.events`
already in context; **no new data wiring, no new backend, no new run field.** Keep the honest empty
state (reuse the existing empty message) when the narrative has no matched events. If Zone 4 also
listed those events, remove the now-duplicated event rows from Zone 4 so events live in one place;
leave the rest of Zone 4 (review-evidence, compare-with-dashboard, admin diagnostics, future
doorways) intact. Any new label copy (e.g. "On the clock", "Soonest") routes through
`mne/presentation_language.py`.

### 6.6 Stories + Sectors are wired from real data in Sprint M (not omitted, not fabricated)

The mockup also shows "Stories in this narrative" (a story grid) and "Sectors expressing it" (a
sector strip). Unlike On the clock, these two need real data assembled into the investigation context
before they can render honestly - so they are their own sprint. **They are neither fabricated nor
omitted:** Sprint M (section 7) wires `run.story_extraction` (filtered to the narrative's group) and
the existing sector classification (scoped to the narrative) into the context and renders both mockup
modules with honest empty states. Do not build them in Sprint L, and do not stub them with invented
data. Leave a clean seam (an empty section anchor or a "wired in M" comment) if helpful.

### 6.7 Files to touch (Sprint L)

- `templates/narrative_investigation.html` - v2 restyle preserving every module; add the sparkline
  (Recent Memory), the lead-instrument candle (Market Expression), the promoted On-the-clock section
  (from `investigation.events`), and the expanded jump-nav.
- `mne/research_workspace.py` - if needed, surface the lead (`primary`) instrument + its
  yfinance-symbol candle series into the investigation context (reuse
  `build_market_expression_for_run` + `load_asset_price_history_or_empty` + the ticker map). No new
  wiring is needed for On the clock - `investigation.events` already exists.
- `static/styles.css` - investigation v2 styles + `.strength-chart` / `.spark-dot` /
  `.mini-candle` / `.candle-svg` + `.cat-grid` / `.cat-card` recipes ported from the mockup
  (L609-682).
- `dashboard.py` - only if the investigation route needs to pass the lead-instrument candle data /
  sector for the link.
- `mne/presentation_language.py` - new copy keys only if the mockup needs a phrase that does not
  exist yet (e.g. On-the-clock section labels).

### 6.8 Verification (Sprint L)

- `/research/{key}` returns **200** and renders every preserved module against the latest real run, a
  populated synthetic run, and honest empty/degraded states.
- The strength sparkline renders teal line + area + endpoint dot when `score_chart.available`, and
  falls back honestly (thin / absent) otherwise.
- The lead-instrument candle renders teal-up / red-down for the `primary` instrument when candles
  exist, and the honest empty state when the store has none (verify with a ticker that has no
  persisted file); the "Open asset view ->" link resolves (or links to the sector index with the
  seam flagged).
- The On-the-clock section renders the promoted `investigation.events` with the countdown treatment
  and the single teal glow on the soonest card, and shows the honest empty state for a narrative with
  no matched events; events are no longer duplicated in Zone 4.
- Jump-nav anchors scroll to real modules only; reduced-motion uses `behavior: auto`.
- No invented data: On the clock reads only `investigation.events`; Stories/Sectors are not present
  yet (Sprint M).
- No run filename in the UI; no engine-language leak in primary copy.
- Widths 1280 / 1024 / 390: no horizontal scroll. JS-disabled: page renders (charts are progressive
  enhancement with an SVG/text fallback). Color budget: teal/amber/slate; red downside-only; a single
  glow on the hero only (design_system.md sections 4-5).
- `git diff --check` clean; nothing staged, committed, or pushed.

---

## 7. Sprint M - Narrative stories + sectors modules (real data wiring)

**Depends on Sprint L.** Wire two existing run-data sources into the investigation context and render
the mockup's "Stories in this narrative" and "Sectors expressing it" modules from real data. Do not
fabricate; honest-empty everywhere. Both sources already exist and are already consumed elsewhere -
this sprint assembles them into the investigation context, which is the heavier part of this handoff.

### 7.1 Stories in this narrative (from the persisted story extraction)

- **Data source (verified):** the run persists `run["story_extraction"]`
  (`main.py:705`, built by `build_story_extraction`, `mne/story_extraction.py:77-102`), shaped
  `{"registry_version": ..., "stories": {slug: {"slug", "score", "matched_count", "examples",
  "share_delta"}}}`. Only stories with `score > 0` are present (`extract_stories` skips `score <= 0`,
  `mne/story_extraction.py:53-54`). **The extraction output does not carry a `group` field** - join
  each slug to its group via the story registry (`config/story_registry.json` -> `stories[slug].group`,
  loaded through `mne/story_registry.py`), and keep only slugs whose `group` equals this narrative's
  group name (the `NARRATIVE_GROUPS` key, e.g. `"AI / Tech Growth"`, `mne/narrative_signals.py:1-6`).
- **Wire it:** add the filtered, group-scoped stories to the context in `build_narrative_investigation`
  (`mne/research_workspace.py:134-188`), each carrying: `display_name` (registry
  `stories[slug].display_name`), a direction/glyph derived from `share_delta` (positive -> up/teal,
  negative -> down/amber, ~0 -> steady/slate, consistent with the finder's direction mapping), and
  optional supporting detail from `matched_count` / `examples`. **Do not fabricate a "why" line** -
  the registry has no per-story rationale; render a curated one-liner only if a
  `mne/presentation_language.py` key exists for it, otherwise show the name + direction + an example
  headline honestly.
- **Render:** the mockup's story grid (`.inv-story-grid` / `.inv-story-card`, mockup L1078-1084 and
  the card builder L1598-1623) - name + glyph, the honest one-line detail, and the **story star
  affordance per the ratified star scope (section 2): a visual "coming with Studio" affordance, not
  wired to a fake store** (the personalization store has no story-slug granularity). Honest empty
  state when the narrative has no matched stories in this run.

### 7.2 Sectors expressing it (from the existing sector classification)

- **Data source (verified):** the sector isolation route already computes this for a narrative -
  `load_sector_map()` -> `classify_sectors_for_run(run, sector_map, narrative_id, now=...)` ->
  `build_sector_isolation_context(narrative_id, sector_map, participation)` (`dashboard.py:2772-2776`;
  builders in `mne/sector_isolation.py:99, 116` and `mne/sector_market_context.py`
  `classify_sectors_for_run`). `build_sector_isolation_context` returns `sectors` rows with
  `sector_key`, `sector_name`, `participation_state` (DRIVING / STEADY / DETACHED / UNAVAILABLE),
  `participation_label`, and an assets `href` (`/research/{group:key}/sectors/{sector}/assets`), plus
  `has_mapping` (`mne/sector_isolation.py:127-141`).
- **Wire it:** in `build_investigation_context` (`dashboard.py:2268-...`, the group-level context
  builder), reuse the **exact same call pattern** the sector route uses (with
  `now=datetime.now().astimezone()` as the asset-execution route does) to compute the narrative's
  sector participation, and pass the resulting `sectors` + `has_mapping` into the context. Do not
  re-implement the classification - reuse the existing functions.
- **Render:** the mockup's compact sector strip (`.sector-strip` / `.sector-tag` / `.legend`, mockup
  L1058-1075) - one tag per sector with a stripe/glyph encoding **teal = driving, bright slate =
  steady, amber = detached** (design_system.md section 4 and the sector-heatmap pattern, section 6;
  **detached is AMBER, never red** - red stays downside-price-only), the `participation_label` copy,
  and an **"Explore assets ->" link to the existing sector isolation route** (`/research/{key}/sectors`,
  `dashboard.py:2762`) or each row's `href`. Honest empty state when `has_mapping` is false (e.g.
  Geopolitical Risk, which has no sector mapping and never scores).
- All sector copy routes through `mne/presentation_language.py` / the existing
  `sector_isolation_copy` labels the builder already returns; do not hardcode state words.

### 7.3 Files to touch (Sprint M)

- `mne/research_workspace.py` - `build_narrative_investigation`: add the group-scoped stories from
  `run.story_extraction` joined to the registry `group`.
- `dashboard.py` - `build_investigation_context`: add the narrative-scoped sector participation
  (reuse `load_sector_map` / `classify_sectors_for_run` / `build_sector_isolation_context`).
- `templates/narrative_investigation.html` - the Stories grid module and the Sectors strip module,
  each with its honest empty state; add their jump-nav anchors (section 6.4).
- `mne/presentation_language.py` - new copy keys only if needed (section headings, empty states, any
  curated story one-liner).
- `static/styles.css` - `.inv-story-grid` / `.inv-story-card` and `.sector-strip` / `.sector-tag` /
  `.legend` recipes ported from the mockup (L627-638).
- `config/story_registry.json` / `mne/story_registry.py` - **read-only** (the slug -> group join
  source); do not modify.

### 7.4 Verification (Sprint M)

- `/research/{key}` returns **200** and renders the Stories grid and Sectors strip from real data
  against the latest real run and a populated synthetic run.
- **Honest empty states confirmed:** a narrative whose stories did not match this run shows the
  stories empty state (not a blank grid); **Geopolitical Risk** (no sector mapping, never scores)
  shows the sectors empty state; neither fabricates rows.
- Story direction/glyph follows `share_delta` sign; the story star is a visual "coming with Studio"
  affordance only (not wired to a store).
- Sector stripes use teal (driving) / bright slate (steady) / **amber (detached)** - never red for
  participation; the "Explore assets ->" link resolves to the sector isolation route.
- No engine-language leak; no run filename. Widths 1280 / 1024 / 390: no horizontal scroll.
  JS-disabled: modules render server-side. Reduced-motion honored. Color budget respected.
- `git diff --check` clean; nothing staged, committed, or pushed.

---

## 8. Sprint ordering and gating

**J -> K -> L -> M, strictly serial.** K's finder assumes J's chrome; L's restyle assumes J's chrome
and shares copy patterns with K; M's two real-data modules assume L's restyled investigation page.
Each sprint is **independently shippable** and **audited in-browser before any commit** (committing is
Daniel's step, never the agent's). Do not start K before J is verified, L before K, or M before L. Do
not fold two sprints into one PR.

---

## 9. Verification standard (applies to every sprint)

The repo standard:

- Full test suite via **`./venv/bin/python -m unittest discover tests`**. **pytest is not installed
  in this venv - do not use it.** Two pre-existing `test_authorization` failures are known and
  unrelated; do not "fix" them and do not let them mask new failures.
- Dashboard up: `./venv/bin/python -m uvicorn dashboard:app --port 8643`. Routes return **200**:
  `/`, `/admin`, and the full `/research` chain - `/research`, `/research/{key}` (investigation),
  `/research/{key}/history`, `/research/{key}/sectors`,
  `/research/{key}/sectors/{sector}/assets`, `/research/{key}/sectors/{sector}/assets/{ticker}` -
  plus `/preferences` and `/account`.
- Rendering checked against **both** the latest real run and a populated **synthetic** run, and
  against **honest empty/degraded** states (empty index / no-match filter; missing brief; no candle;
  Geopolitical "Defined, not currently scored").
- **UI checks (all UI sprints J / K / L / M):** widths **1280 / 1024 / 390** with no horizontal scroll;
  **JS-disabled** rendering; **reduced-motion** honored; **color budget** against
  `docs/design_system.md` (teal / amber / slate / red only; **red is downside-only**; no more than
  one glow per section); **no run filename in the UI**; **no engine-language leak** in primary copy.
- `git diff --check` clean; **nothing staged, committed, or pushed.** Runtime data lives at the
  `DATA_DIR` outside the repo; never write runtime outputs into the repository.

---

## 10. Open decisions for the owner (flag, do not decide silently)

1. **Studio in nav now vs later.** Default (ratified): omit the Studio item until the Studio arc
   ships. Alternative: a disabled "Studio - coming soon" placeholder. Flag if you prefer the
   placeholder.
2. **Story-level save now vs deferred to Studio.** Finding (verified): the personalization store
   (`mne/personalization.py:131-147`) follows narratives at group/theme granularity only - it has
   **no story-slug field**. Story-level starring and the "Saved collection" are therefore deferred to
   Studio; the story star ships as a visual "coming with Studio" affordance. Adding story-slug
   granularity to the store now is an owner call.
3. **Interim archive reachability.** History leaves the nav but its routes remain, reachable via the
   investigation History-preview link and Historical-Connections cards. How prominent should the
   archive stay until Studio's Compare tool ships?
4. **Run selector on research pages.** The dashboard bar has a run selector; the mockup research bar
   does not. Default: research pages show brand + nav + sign-in only (latest meaningful run). Add a
   run selector to research later?
5. **Split chrome interim.** Admin and every `historical_*` page keep the legacy `app_rail`; the six
   research-tier pages + preferences/account move to the shared top bar. Is the interim split
   acceptable, or should admin also move to the top bar eventually?
6. **Asset-view link sector.** The Market Expression "Open asset view ->" link needs a `{sector}`
   segment the instrument data does not carry directly (6.3). Derive it from the sector map, or link
   to the sector index? Flagged, not decided.
7. **Effort split of the narrative-depth modules (informational).** On the clock is a pure
   re-presentation of existing `investigation.events` (Sprint L, section 6.5); Stories + Sectors need
   real data assembled into the context and are the heavier part (Sprint M, section 7). All three are
   built from real run data with honest empty states - none are omitted or fabricated. Noted so the
   owner sees why the two are split across sprints; no decision required.

---

## Appendix - quick reference (all re-verified 2026-08-10)

| Claim | Location | What is there |
|---|---|---|
| Legacy left rail (replaced on research pages) | `templates/_partials/app_rail.html:1-41` | brand, nav Overview/Research/Preferences/History, Admin (L24-30), account (L32) |
| Dashboard top bar to generalize | `templates/dashboard.html:17-62` | inline brand + nav (L22-27) + utilities (pill L29-50, run-selector L52-59, sign-in L60) |
| Top-bar CSS | `static/styles.css:3821-3848` | `.dashboard-topbar`; active underline uses `var(--up)` at L3840 |
| Nav copy keys + accessor | `mne/presentation_language.py:199-206, 236` | `DASHBOARD_PARITY_COPY`, `dashboard_parity_copy` |
| Nav copy key list | `dashboard.py:1258-1266` | `DASHBOARD_PARITY_COPY_KEYS` |
| Plain-language run label | `dashboard.py:421-435` | `fmt_run_label` -> "Today 3:44 PM" / "Aug 6" / "Aug 6, 2026" |
| Filename leak (remove) | `narrative_investigation.html:20`, `research_selector.html:17`, `asset_exploration.html:3`, `asset_execution.html:13` | `Latest meaningful run: {{ selected_file }}` |
| Research index route + context | `dashboard.py:2700-2703`, `2249-2265` | `/research`, `build_research_context` |
| Narrative selector builder | `mne/research_workspace.py:86-131` | emits only score > 0; group + theme |
| Investigation route + builder | `dashboard.py:2866-2879`; `mne/research_workspace.py:134-188` | `/research/{key}`; `build_narrative_investigation` |
| Investigation module inventory | `templates/narrative_investigation.html:37-389` | hero, jump-nav, 4 zones, memory, history, connections, market expression, evidence, analyst, related, entry points |
| Narrative groups (index) | `mne/narrative_signals.py:1-6` | AI / Macro / Energy / Geopolitical Risk |
| Geopolitical never scores | `mne/narrative_signals.py:5, 9-18` | themes war/china/tariffs; not in taxonomy -> no score |
| 5 taxonomy themes | `config/theme_taxonomy.json` | `ai, rates, inflation, energy, recession` |
| Story registry | `config/story_registry.json` | `stories` keyed by slug; display_name/group/themes/keywords/driving_sectors/catalyst_names/connected |
| Story extraction | `mne/story_extraction.py:27, 77` | `extract_stories`, `build_story_extraction` |
| Story extraction persisted on run (Sprint M source) | `main.py:705`; `mne/story_extraction.py:102` | `run["story_extraction"] = {"stories": {slug: {slug,score,matched_count,examples,share_delta}}}`; score > 0 only; no group field (join via registry) |
| Narrative-matched catalyst events (Sprint L On the clock) | `mne/research_workspace.py:173-178`; `narrative_investigation.html:370-384` | `investigation.events` from `run.event_lifecycle`; currently rendered in Zone 4 with an empty state |
| Sector classification for a narrative (Sprint M source) | `dashboard.py:2772-2776`; `mne/sector_isolation.py:99,116-141`; `mne/sector_market_context.py` | `load_sector_map` / `classify_sectors_for_run` / `build_sector_isolation_context` -> `sectors[].participation_state` (DRIVING/STEADY/DETACHED) + `href` + `has_mapping` |
| Investigation context builder (Sprint M sector wiring) | `dashboard.py:2268` | `build_investigation_context` (group-level) |
| Sector isolation route (Explore assets link) | `dashboard.py:2762` | `/research/{key}/sectors` |
| Follow store (group/theme only) | `mne/personalization.py:131-147` | `follow_narrative` / `unfollow_narrative`; no story slug |
| Follow write path | `dashboard.py:2638-2659` | `POST /preferences/narratives`; auth + entitlement + capacity |
| History score series (sparkline) | `mne/narrative_history.py:126-175, 178` | `_chart` segments {x,y}; `build_narrative_history`; needs >= 3 points |
| Existing history preview | `templates/narrative_investigation.html:168-182` | `score_chart` polyline / thin / full link |
| Candle store loader (honest empty) | `mne/asset_price_history.py:125-134` | `load_asset_price_history_or_empty` -> empty when file absent |
| Market expression + primary instrument | `mne/research_workspace.py:183-186`; `mne/market_expression.py:154, 188-190` | `build_market_expression_for_run`; roles primary/secondary/offset; asset/label/move/status |
| Ticker -> yfinance symbol maps | `main.py:115-119, 122, 504` | `NASDAQ_TICKERS` (VIX->^VIX, DXY->DX-Y.NYB), `ASSET_EXPANSION_TICKERS`, `build_sector_ticker_map` |
| Asset execution route (link target) | `dashboard.py:2811` | `/research/{key}/sectors/{sector}/assets/{ticker}` |
| AI Analyst already exists | `mne/ai_analyst.py`; `templates/_partials/ai_analyst.html`; included at `narrative_investigation.html:308` | deeper Q&A; finder does not replace it |
| Mockup (visual contract) | `docs/mockups/research_studio_concept_v1.html` | top bar + finder/index + investigation + Studio (Studio out of scope) |
