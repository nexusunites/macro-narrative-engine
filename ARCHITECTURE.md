# Macro Narrative Engine Architecture

MNE is a macro narrative intelligence engine for tracking financial news narratives, market context, and macro regime signals. It is not a trading bot.

## Current Priority

Keep the core engine clean before adding external integrations.

Recommended build order:

1. Stabilize RSS ingestion.
2. Clean headline storage.
3. Deduplicate headlines.
4. Count themes and narratives.
5. Measure narrative concentration.
6. Track historical narrative trends.
7. Add market context overlays.
8. Generate automated daily reports.
9. Later, add TradingView, Discord, and stream dashboard integrations.

## Data Storage

Raw headlines are saved by date and time inside `data/headlines/`.

This preserves a historical dataset so old headlines can be reanalyzed later as theme logic, scoring, and narrative models improve.

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
- Nasdaq and market context
- Example headlines for top themes
- Change vs previous run

## Module Direction

`main.py` should orchestrate the flow. Engine logic belongs in modules:

- `mne/rss_fetch.py`
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
