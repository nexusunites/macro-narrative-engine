# Project Status

## Project Overview

Macro Narrative Engine (MNE) is a lightweight macro narrative intelligence system for ingesting headlines, scoring market narratives, classifying context, and presenting the latest run in a dashboard. It is designed as an analysis engine, not a trading bot.

## Current Capabilities

### Engine

- RSS ingestion.
- Headline storage and deduplication.
- Theme detection and narrative group scoring.
- Structured taxonomy framework through `config/theme_taxonomy.json`.
- Taxonomy auditing for review and refinement.
- Narrative persistence tracking.
- Narrative acceleration tracking.
- Crowding risk detection.
- Catalyst framework for company and macro events.
- Saved JSON results and text reports in the configured runtime data directory.

### Intelligence Layer

- Market Environment classification.
- Breadth Confirmation.
- Positioning Environment classification.
- Regime Alignment scoring.
- Mode Context for macro and Nasdaq-focused workflows.
- Narrative Leadership.
- Narrative Pulse.
- Narrative Brief Engine with deterministic, evidence-backed prose and persisted run JSON output.
- Narrative concentration, dominant narrative share, and narrative dynamics.

### Dashboard

- User Dashboard for current-run narrative and market reads.
- Admin Dashboard for diagnostics, scoring detail, raw JSON, catalyst detail, and audit metadata.
- Market Snapshot.
- Regime Alignment History.
- Narrative Leadership cards.
- Narrative Pulse display.
- Dashboard UX refinements for hierarchy, readability, and workflow separation.

## Recent Major Additions

- Dashboard V1 has matured into user and admin surfaces with clearer hierarchy and scanability.
- Regime Alignment History is now exposed for reviewing state changes over time.
- Narrative Leadership cards and Narrative Pulse display are now visible in the dashboard.
- The Overview page now surfaces the persisted Narrative Brief near the top, while Admin exposes sentence-level evidence, template diagnostics, conflict logs, and the raw evidence registry.
- Engine support now includes persistence, acceleration, crowding risk, taxonomy auditing, and the catalyst framework.
- Intelligence output now includes Market Environment, Breadth Confirmation, Positioning Environment, Regime Alignment, Mode Context, Narrative Leadership, and Narrative Pulse.

## Current Focus

The current focus is expanding the product surface beyond the latest-run dashboard: leadership rotation, dedicated navigation pages, a Market Expression Map, and Taxonomy V2.

## Known Limitations

- Leadership Rotation is not yet a dedicated workflow for showing narrative handoffs and changes in leadership over time.
- Several dashboard areas still share the same main surface instead of having dedicated navigation pages.
- Market Expression Map is not yet available as a first-class view linking narratives to market instruments or expressions.
- Taxonomy V1 is useful, but Taxonomy V2 is needed as more runs are reviewed and the narrative set matures.
- External integrations such as Discord, TradingView overlays, and streaming dashboards remain future work.

## Current Architecture Summary

`main.py` orchestrates ingestion, analysis, context classification, Narrative Brief composition, persistence, and reporting. Engine logic lives in modules under `mne/`, including RSS fetching, storage, theme analysis, narrative signals, market context, catalysts, positioning, regime alignment, narrative brief composition, and reporting. Runtime outputs are written outside the repository to the configured `MNE_DATA_DIR` location.

`dashboard.py` serves the FastAPI dashboard and loads saved run JSON files from the runtime results directory. The dashboard templates provide user-facing and admin views for the market snapshot, Regime Alignment History, Narrative Leadership, Narrative Pulse, diagnostics, raw JSON, scoring detail, catalyst detail, and audit metadata.

## Latest Product Milestone

The latest product milestone is the dashboard-backed intelligence layer. MNE now connects RSS ingestion, deduplication, taxonomy-based theme detection, persistence, acceleration, crowding risk, catalysts, market environment, breadth, positioning, regime alignment, leadership, and pulse outputs into user and admin dashboard views.
