# Project Status

## Project Overview

Macro Narrative Engine (MNE) is a lightweight macro narrative intelligence system for ingesting headlines, scoring market narratives, classifying context, and presenting the latest run in a dashboard. It is designed as an analysis engine, not a trading bot.

## Current Capabilities

- Dashboard V1 with user and admin views.
- Operating modes for broad macro and Nasdaq-focused reads.
- RSS headline ingestion, headline storage, and deduplication.
- Theme and narrative group scoring using the structured taxonomy in `config/theme_taxonomy.json`.
- Narrative concentration, narrative signals, narrative dynamics, and crowding risk.
- Market context overlays for core symbols such as QQQ, NVDA, VIX, and DXY.
- Narrative / market relationship classification and breadth confirmation.
- Catalyst environment and positioning environment classification.
- Regime Alignment scoring across narrative, market, catalyst, and positioning inputs.
- Company catalyst support through earnings data.
- Macro calendar support through the runtime macro calendar file.
- Saved JSON results and text reports in the configured runtime data directory.

## Recent Major Additions

- Dashboard V1 with a primary user view and a deeper admin/research view.
- Operating mode context that changes the summary read for macro vs Nasdaq workflows.
- Regime Alignment scoring and explanatory state output.
- Catalyst Environment, Positioning Environment, and catalyst source metadata.
- Auto company earnings catalyst support and auto macro calendar catalyst support.
- Narrative Dynamics output, including crowding risk.
- Market context cards and narrative / market relationship output in the dashboard.

## Current Focus

The current focus is turning the engine output into a clearer product surface: improving Dashboard V1 hierarchy, navigation, and readability while keeping the core engine inspectable and stable.

## Known Limitations

- Dashboard V1 is functional but still early; visual hierarchy and navigation need polish.
- Historical analytics are limited compared with the current-run snapshot.
- Regime Alignment history is not yet exposed as a first-class product view.
- Narrative leadership rotation and pulse-style monitoring are not yet complete product features.
- Taxonomy V1 is useful but will need Taxonomy V2 refinement as more runs are reviewed.
- External integrations such as Discord, TradingView overlays, and streaming dashboards remain future work.

## Current Architecture Summary

`main.py` orchestrates ingestion, analysis, context classification, persistence, and reporting. Engine logic lives in modules under `mne/`, including RSS fetching, storage, theme analysis, narrative signals, market context, catalysts, positioning, regime alignment, and reporting. Runtime outputs are written outside the repository to the configured `MNE_DATA_DIR` location.

`dashboard.py` serves the FastAPI dashboard and loads saved run JSON files from the runtime results directory. The dashboard templates provide a user-facing summary view and an admin view for diagnostics, raw JSON, scoring detail, catalyst detail, and audit metadata.

## Latest Product Milestone

Dashboard V1 is the latest product milestone. It brings together the engine's current intelligence layer into navigable user/admin views with operating mode context, Regime Alignment, Market Context, Catalyst Environment, Positioning Environment, Narrative Dynamics, Company Catalyst Support, and Macro Calendar Support visible from saved runs.
