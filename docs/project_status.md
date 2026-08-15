# Project Status

## Project Overview

Macro Narrative Engine (MNE) is a lightweight macro narrative intelligence system for ingesting headlines, scoring market narratives, classifying context, and presenting the latest run in a dashboard. It is designed as an analysis engine, not a trading bot.

For current-state questions, documentation precedence is: this status document, then `docs/product_backlog.md`, then implemented handoffs in `docs/handoffs/` and `docs/superpowers/specs/`, then historical architecture and design documents. A statement such as "not implemented by this document" in an architecture document describes that document's scope at its authoring time, not necessarily the current repository state.

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
- The subsequent Design System v2 wave adds the teal palette, generalized v2 top bar, color-leading resaturation, and matching preferences/account treatment. Price surfaces retain price-only red alongside teal rather than using color for non-price state. Specifications: `docs/handoffs/design_system_dashboard_foundation_handoff.md`, `docs/handoffs/dashboard_visual_rework_v2_handoff.md`, `docs/handoffs/color_leading_resaturation_handoff.md`, and `docs/handoffs/preferences_account_v2_palette_handoff.md`.
- Overview's Markets Right Now section now presents the primary instrument as a candlestick with a compact status-chip strip and click-through to the asset view; up candles are teal and down candles use price-only red. Specification: `docs/handoffs/overview_markets_candlestick_handoff.md`.
- Plain-language presentation layer (`mne/presentation_language.py`): deterministic dictionary translating all engine metric names and state strings into everyday language; engine terminology appears only inside Why-expanders.
- Strict color budget on the user dashboard: neutral base plus the `--up`/`--down` directional pair only; states convey meaning through typography.
- Data Quality trust summary rendered as a compact expandable header pill.
- Detail score tables, Daily Leadership table, and duplicate environment grids removed from the user surface (available via Admin/Research).
- Admin Dashboard for diagnostics, scoring detail, raw JSON, catalyst detail, and audit metadata (unchanged by the rework).
- Daily snapshots now persist a representative Regime Alignment score/state (latest scored run of the day, explicit nulls otherwise), feeding the hero chart from snapshots only.

### Research Tier v2

- A shared v2 top bar connects the dedicated Research finder, Narrative Investigation, Sectors, Asset Exploration, per-asset execution, and Studio surfaces.
- `/research` provides a purpose-led finder and narrative index; the restyled Narrative Investigation adds history charts and an "On the clock" catalyst read.
- The Stories module combines a curated story registry with deterministic story extraction and presents per-story attention in an attention cloud.
- The Sectors module provides deterministic sector isolation and observed participation context, with drill-down into Asset Exploration for mapped sectors and instruments.
- Per-asset execution views present persisted price-history candlesticks and persisted event markers from the macro calendar and EDGAR company news.
- The account-owned story-level Saved store and Research stars let users retain stories and feed the Studio Saved/Watchlist rail.
- These surfaces present existing or adjacent deterministic intelligence without changing narrative scoring or taxonomy. Narrative-to-sector-to-instrument coverage is bounded to configured mappings and available data; broader coverage, historical market-price reconstruction, outcome analysis, backtesting, predictions, recommendations, and trade signals are not implemented.

### Studio (Thesis Workspace)

- Studio is an implemented, bounded, single-user, fixed-schema thesis workspace, not a general custom or collaborative workspace system.
- `/studio` provides a thesis library of multiple named thesis boards with create, open, and delete flows.
- Each board persists one editable thesis line and supports pointer-driven placement of story, headline, and catalyst evidence, plus labeled connections from a fixed relationship vocabulary.
- Boards are account-owned, autosaved, and protected by verified ownership isolation; the story-level Saved store and Watchlist rail provide inputs to the board.
- Selecting a story exposes whitelisted current-run node intelligence, from which headline and catalyst evidence can be promoted onto the board with deterministic deduplication and a supporting connection.
- Compare-over-time reuses completed historical reconstructions to place a thesis board in historical context.
- General saved-investigation and Research Session persistence, and general custom workspaces, are only partially realized by this bounded thesis artifact. Collaborative/shared workspaces, annotations and research journals, portfolio overlays, trade journals, and unrestricted custom workspaces are not implemented.

### Authentication and Accounts

- Self-hosted email/password authentication with Argon2id password hashing.
- Database-backed sessions with secure cookie handling, logout, and invalidation.
- `USER` and `ADMIN` roles with centralized authorization helpers; `/admin` routes require `ADMIN` access.
- Explicit first-admin bootstrap and CLI/admin-assisted single-use password reset tokens.
- Server-controlled `FREE`, `PRO`, and `TEAM` plan assignments with centralized server-side feature enforcement, deterministic monthly usage accounting, live capacity limits, and audited internal operator access. Billing is not implemented.
- Account-owned personalization, alerts, saved investigations, saved comparisons, and historical requests, with explicit anonymous-profile migration and verified cross-account isolation.
- SQLAlchemy models and Alembic migrations; SQLite works for the MVP and Postgres is supported through `MNE_DATABASE_URL`.

## Recent Major Additions

- **Research-Tier v2 Rework** — the shared v2 shell, Research finder and narrative index, restyled Narrative Investigation, Stories attention cloud, Sectors and participation views, Asset Exploration, per-asset execution candlesticks, persisted macro/EDGAR event markers, and story-level Saved controls are implemented. Specifications: `docs/handoffs/research_v2_shell_handoff.md`, `docs/handoffs/story_extraction_handoff.md`, `docs/handoffs/cross_sector_heatmap_sector_isolation_handoff.md`, `docs/handoffs/asset_exploration_view_handoff.md`, `docs/handoffs/asset_execution_view_handoff.md`, and `docs/handoffs/company_news_edgar_handoff.md`.
- **Research-Tier Retirements and Redirects** — the legacy narrative market map was retired, the constellation node graph was replaced by the deterministic attention cloud, and the user-facing history comparison route was retired and redirected to Studio Compare-over-time. Surviving historical pages use the v2 top bar and palette; the admin historical surfaces remain separate. Specifications: `docs/legacy_narrative_market_map_audit.md` and `docs/handoffs/historical_tier_cleanup_handoff.md`.
- **Studio Thesis Workspace (Sprints N–Q plus evidence types)** — the story-level Saved foundation, Studio shell and Watchlist rail, Compare-over-time tool, persistent thesis board, multiple named-thesis library, and headline/catalyst evidence promotion are implemented as a bounded, single-user, fixed-schema workspace. Specifications: `docs/handoffs/studio_foundation_handoff.md`, `docs/handoffs/studio_artboard_q1_handoff.md`, `docs/handoffs/studio_thesis_library_q2_handoff.md`, and `docs/handoffs/studio_evidence_types_handoff.md`.
- **Entitlements and Usage Limits** — centralized fail-closed feature rules, UTC calendar-month distinct-object consumption, atomic idempotent usage events, live capacity counts, downgrade-safe preservation, audited plan/internal-access assignment, and restrained account usage summaries are implemented. No billing provider, payment, checkout, subscription, invoice, coupon, or trial code is present.

- **Authentication and Account Architecture** — self-hosted account creation and login, Argon2id password storage, database-backed sessions, role-based authorization, protected admin access, account-owned persistence, explicit anonymous-profile migration, reset-token and admin-bootstrap operations, and SQLAlchemy/Alembic database persistence are implemented. Billing, paid entitlements, email verification/delivery, self-service email reset, Team workspaces, and social login/SSO remain pending.
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

The next likely sequence is billing provider integration, paid upgrade flows, paid beta lifecycle testing, email delivery and self-service password reset, and production hardening.

## Known Limitations

- Billing provider integration, payments, checkout, subscriptions, invoices, and trials are not implemented. Entitlement enforcement exists independently of billing.
- Email verification, email delivery, and self-service email password reset are not implemented. Password recovery currently requires the CLI/admin-assisted single-use token flow.
- Team workspaces, social login/SSO, and full account-management administration are not implemented.
- External alert delivery remains future work; alerts are in-app only.
- Daily snapshots created before Snapshot Support Score Persistence carry null support scores; the hero chart renders these as gaps. Historical recovery is a designated future Historical Replay use case.
- Leadership Rotation is not yet a dedicated workflow for showing narrative handoffs and changes in leadership over time.
- The v2 tier provides dedicated Research, Sectors, Assets, and Studio pages; admin and diagnostic workflows intentionally retain separate operational surfaces rather than joining the user-facing navigation tier.
- A bounded first-class narrative-to-sector-to-instrument path now exists through Sectors, Asset Exploration, and per-asset execution views. Broader narrative/instrument coverage, historical market-price context, and narrative-versus-market outcome analysis remain future work.
- Taxonomy V1 is useful, but Taxonomy V2 is needed as more runs are reviewed and the narrative set matures.
- External integrations such as Discord, TradingView overlays, and streaming dashboards remain future work.

## Current Architecture Summary

`main.py` orchestrates ingestion, analysis, context classification, Narrative Brief composition, persistence, and reporting. Engine logic lives in modules under `mne/`, including RSS fetching, storage, theme analysis, narrative signals, market context, catalysts, positioning, regime alignment, narrative brief composition, and reporting. Runtime outputs are written outside the repository to the configured `MNE_DATA_DIR` location.

`dashboard.py` serves the FastAPI dashboard and loads saved run JSON files from the runtime results directory. The dashboard templates provide authenticated user-facing account and preference views plus ADMIN-protected views for the market snapshot, Regime Alignment History, Narrative Leadership, Narrative Pulse, diagnostics, raw JSON, scoring detail, catalyst detail, and audit metadata. Account and session state is persisted through SQLAlchemy/Alembic-backed relational storage configured by `MNE_DATABASE_URL`.

## Latest Product Milestone

The latest product milestone is Authentication and Account Architecture. MNE now adds self-hosted identity, database-backed sessions, account-owned persistence, role-based authorization, and protected admin access to the dashboard-backed intelligence layer. Commercial billing, paid entitlements, email delivery, and Team collaboration features remain pending.
