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

- User Dashboard reworked (Dashboard Experience Rework, July 2026): Robinhood-inspired presentation with a Market Support hero (large score, delta chip, interactive snapshot-history chart with scrubbing and range selection), plain-language narrative cards, Robinhood-style market rows, Upcoming Events, and What We Read evidence sections.
- Plain-language presentation layer (`mne/presentation_language.py`): deterministic dictionary translating all engine metric names and state strings into everyday language; engine terminology appears only inside Why-expanders.
- Strict color budget on the user dashboard: neutral base plus the `--up`/`--down` directional pair only; states convey meaning through typography.
- Data Quality trust summary rendered as a compact expandable header pill.
- Detail score tables, Daily Leadership table, and duplicate environment grids removed from the user surface (available via Admin/Research).
- Admin Dashboard for diagnostics, scoring detail, raw JSON, catalyst detail, and audit metadata (unchanged by the rework).
- Daily snapshots now persist a representative Regime Alignment score/state (latest scored run of the day, explicit nulls otherwise), feeding the hero chart from snapshots only.

## Recent Major Additions

- **Historical-to-Current Narrative Connection** — the latest meaningful live narrative state now connects deterministically to recent daily narrative history and up to three relevant completed historical reconstructions. The Research Workspace shows recent peak and trajectory context, descriptive resemblance, meaningful differences, coverage caveats, and safe historical investigation links; the dashboard adds one concise sentence only for reliable comparisons. The connection is read-only, uses persisted inputs, preserves the replay-to-replay comparison contract, and performs no fetching, replay, backfill, scoring, taxonomy changes, prediction, or trade recommendation.
- **Dashboard Experience Rework (four sprints, July 2026)** — plain-language presentation layer, new page architecture with Market Support hero and interactive chart, Robinhood-grade visual system under a strict color budget, progressive disclosure of engine terminology via Why-expanders, and a data-completeness/visual-energy pass (change-chip translation and dedupe, unavailable-state suppression, green promoted to dual up/brand accent). Specifications: `docs/dashboard_rework_handoff.md`, `docs/handoffs/dashboard_sprint_d_handoff.md`.
- **Snapshot Support Score Persistence** — daily snapshots persist `regime_alignment` (score/state/source_run_id) using a latest-scored-run representative rule with explicit nulls; idempotent repair backfill added (`scripts/repair_snapshot_support_scores.py`). Null-day recovery is deferred to Historical Replay. Specification: `docs/handoffs/snapshot_support_score_handoff.md`.

- Dashboard V1 has matured into user and admin surfaces with clearer hierarchy and scanability.
- Regime Alignment History is now exposed for reviewing state changes over time.
- Narrative Leadership cards and Narrative Pulse display are now visible in the dashboard.
- The Overview page now surfaces the persisted Narrative Brief near the top, while Admin exposes sentence-level evidence, template diagnostics, conflict logs, and the raw evidence registry.
- Engine support now includes persistence, acceleration, crowding risk, taxonomy auditing, and the catalyst framework.
- Intelligence output now includes Market Environment, Breadth Confirmation, Positioning Environment, Regime Alignment, Mode Context, Narrative Leadership, and Narrative Pulse.

## Current Focus

The current focus is expanding the product surface beyond the latest-run dashboard: leadership rotation, dedicated navigation pages, a Market Expression Map, and Taxonomy V2.

## Known Limitations

- Daily snapshots created before Snapshot Support Score Persistence carry null support scores; the hero chart renders these as gaps. Historical recovery is a designated future Historical Replay use case.
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
