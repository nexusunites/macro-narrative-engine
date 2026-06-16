# Macro Narrative Engine Architecture

MNE is a macro narrative intelligence engine for tracking financial news narratives, market context, and macro regime signals. It is not a trading bot.

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

## Data Storage

Raw and deduplicated headlines are saved by date and time inside the configured runtime data directory. By default this is `~/Google Drive/MNE-data/headlines/`, and it can be overridden with `MNE_DATA_DIR`.

This preserves a historical dataset so old headlines can be reanalyzed later as theme logic, scoring, and narrative models improve.

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
