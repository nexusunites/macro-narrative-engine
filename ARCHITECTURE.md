# Macro Narrative Engine Architecture

MNE is a macro narrative intelligence engine for tracking financial news narratives, market context, and macro regime signals. It is not a trading bot.

`docs/product_vision.md` is the top-level product philosophy reference for MNE. Architecture decisions should preserve that product vision: evidence before opinion, understanding before prediction, investigation before conclusions, deterministic intelligence before AI, and transparency before automation.

`docs/product_backlog.md` is the master implementation backlog for MNE. Future sprint handoffs and sequencing decisions should originate there, while architecture documents remain the canonical references for system design.

`docs/security_ip_model.md` is the permanent strategic and platform-protection reference for MNE. Architecture, access, data, documentation, and collaboration decisions should preserve the security and intellectual property principles defined there.

## Current Priority

Keep the core engine clean before adding external integrations.

Recommended build order:

1. Stabilize RSS ingestion.
2. Clean headline storage.
3. Deduplicate headlines before narrative analysis.
4. Count themes and narratives.
5. Measure narrative concentration.
6. Track historical narrative trends.
7. Add market context overlays.
8. Generate automated daily reports.
9. Later, add TradingView, Discord, and stream dashboard integrations.

## Narrative Brief Engine

`mne/narrative_brief.py` owns the Narrative Brief Engine, a deterministic read-side composition layer that consumes already-computed run outputs and persists `narrative_brief` into the result JSON. It does not call an LLM, does not score narratives, and does not alter upstream taxonomy, catalyst, market, breadth, positioning, or regime logic.

The engine selects fixed templates in section order, resolves evidence objects for every emitted sentence, computes data-completeness confidence, and records diagnostics for admin review. `change_summary` and `leadership_rotation` are persisted before brief generation so historical snapshots render from stored run JSON instead of recomputing the story later.

The permanent authoring standard for brief templates is documented in `docs/narrative_style_guide.md`. Future templates must follow that style guide and pass template-library validation before they can render.

## Intelligence Experience Architecture

`docs/intelligence_experience_architecture.md` defines MNE's permanent
experience-layer philosophy. Its core rule is that the Intelligence Engine
generates deterministic intelligence and the Experience Layer only delivers,
organizes, explains, compares, visualizes, searches, and enables exploration of
that intelligence. Dashboard, research, AI analyst, reports, mobile, and API
surfaces consume Intelligence; none of them produce or override it.

## Canonical Architecture References

MNE's permanent architecture references include:

- `docs/product_vision.md` -- Product Vision
- `docs/product_backlog.md` -- Product Backlog
- `docs/security_ip_model.md` -- Security & Intellectual Property Model
- `docs/source_intelligence_platform.md` -- Source Intelligence Platform (SIP)
- `docs/historical_replay_engine.md` -- Historical Replay Engine (HRE)
- `docs/narrative_memory_system.md` -- Narrative Memory System (NMS)
- `docs/intelligence_experience_architecture.md` -- Intelligence Experience Architecture (IXA)
- Platform Observability Layer (POL)
- `docs/research_workspace_architecture.md` -- Research Workspace Architecture (RWA)

The Research Workspace Architecture defines how investigation is organized inside
MNE. It is an architecture reference only; implementation details, UI routes,
APIs, and future workspace scaffolding remain separately scoped.

## Data Storage

Raw and deduplicated headlines are saved with second-resolution date/time filenames inside the configured runtime data directory. By default this is `~/Google Drive/MNE-data/headlines/`, and it can be overridden with `MNE_DATA_DIR`. Results, headlines, and reports receive a numeric suffix when a filename for the same second already exists, so historical files are not overwritten. Result JSON records its filename stem as `run_id`.

This preserves a historical dataset so old headlines can be reanalyzed later as theme logic, scoring, and narrative models improve.

Daily snapshots retain each source run's `run_id` and timestamp. Snapshot writes are idempotent for a run ID, with timestamp matching retained as compatibility behavior for historical runs that do not have an ID.

## Headline Deduplication

RSS ingestion returns raw headlines. `mne/headline_deduplication.py` then removes duplicates before theme analysis using simple, inspectable normalization:

- case normalization
- whitespace normalization
- basic punctuation normalization
- exact matching on the normalized headline

MNE stores both raw and deduplicated headline files. Downstream narrative scoring, concentration, dynamics, and reporting use the deduplicated headline list. Saved run JSON keeps `raw_headline_count`, `deduped_headline_count`, and `duplicate_count` visible for auditability.

## Market Context

Yahoo Finance through `yfinance` is the first market overlay source.

Initial symbols:

- `QQQ`
- `SPY`
- `^VIX`
- DXY proxy, when available
- yield proxy, when available

Future symbols:

- `SMH`
- `XLK`
- `XLE`
- `XLF`

The purpose is to compare narrative strength against market confirmation.

Examples:

- AI narrative rising while QQQ/SMH are green and VIX is down suggests narrative support.
- AI narrative rising while QQQ/SMH are red and VIX is up suggests narrative divergence.

## Market Expression Map

`mne/narrative_market_map.py` owns the Phase 1 Market Expression Map. It is a
curated static mapping from the dominant theme to common public-market
expression proxies:

- primary expressions
- secondary expressions
- potential offsets
- a plain-language description

The map is context only. It is not a signal, ranking, recommendation engine, or
market-confirmation layer. It does not change theme scoring, narrative signals,
concentration, momentum, persistence, crowding, market relationships, breadth
confirmation, catalyst logic, or regime alignment.

`main.py` attaches the helper output to saved run JSON as `market_expression`.
`mne/reporting.py` formats the same structure in the daily text report and
terminal output. `dashboard.py` passes the optional field through the dashboard
view model so future cards or pages can consume it without changing the saved
JSON contract.

The structure keeps simple symbol arrays for immediate report use and includes
metadata such as `mapping_version`, `mapped`, `context_only`, and `is_signal` so
future phases can add live prices, confirmation fields, dashboard cards, or
expression performance tracking without redefining the top-level output.

## TradingView Role

TradingView should not be the first backend data source.

Use it later for:

- Visualization
- Alerts
- Overlays
- Pine Script display
- Streaming dashboards

## Report Format

Daily reports should include:

- Timestamp
- Number of headlines loaded
- Number of feeds loaded
- Theme counts
- Dominant narrative
- Dominant narrative share
- Concentration gap
- Narrative signals
- Catalyst source path
- Nasdaq and market context
- Example headlines for top themes
- Theme match audit for top themes
- Change vs previous run

## Theme Taxonomy

Theme definitions live in `config/theme_taxonomy.json`.

The taxonomy file contains:

- `taxonomy_version`
- weighted keyword tiers: `strong`, `medium`, and `weak`
- theme IDs used by scoring, narrative groups, reports, and trend history

`mne/theme_analysis.py` owns matching and scoring logic. It loads the structured
taxonomy config, normalizes theme IDs and keywords, and applies the existing
weighted keyword scoring model:

- `strong` = 3
- `medium` = 2
- `weak` = 1

Within a single theme/headline, overlapping keyword matches use a longest-match
wins rule before score and audit updates. This prevents broader keywords such as
`rates` or `yields` from adding score when they are nested inside more specific
phrases such as `interest rates` or `treasury yields`, while still allowing
separate non-overlapping concepts in the same headline to count.

`theme_analysis.py` also emits lightweight theme match audit metadata. The audit
tracks which configured keywords or phrases matched each theme, how many times
they matched, and a few example headlines per term. This is diagnostic output for
taxonomy review only. It does not change theme scores, concentration, narrative
dynamics, market environment classification, or any downstream signal logic.
`mne/reporting.py` formats this metadata in the `Theme Match Audit` report
section, and saved run JSON includes `theme_match_audit` for later inspection.
Taxonomy observations from real runs should be recorded in `TAXONOMY_NOTES.md`
before making taxonomy definition changes or planning Taxonomy V2 work.

`themes.txt` remains supported as a legacy/simple input format. Entries in that
file are treated as additional weak keywords, which preserves the older workflow
without making it the primary taxonomy source.

Saved run JSON includes `taxonomy_version` so historical runs can be audited as
theme definitions evolve. Momentum, persistence, acceleration, crowding, and
market-confirmation logic should compare taxonomy versions before relying on
longer historical series when future taxonomy versions materially change theme
definitions.

## Module Direction

`main.py` should orchestrate the flow. Engine logic belongs in modules:

- `mne/rss_fetch.py`
- `mne/headline_deduplication.py`
- `mne/storage.py`
- `mne/theme_analysis.py`
- `mne/narrative_signals.py`
- `mne/market_context.py`
- `mne/reporting.py`

## Future Features

- Headline deduplication
- Narrative momentum detection
- Narrative persistence
- Narrative acceleration
- Narrative divergence vs price
- Automated morning report
- Discord output
- TradingView visualization layer
