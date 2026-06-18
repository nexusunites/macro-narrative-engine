# Roadmap

## Completed

### Engine

- Runtime data directory support through `MNE_DATA_DIR`.
- RSS ingestion.
- Headline persistence and deduplication.
- Theme detection and narrative group scoring.
- Structured taxonomy framework.
- Taxonomy auditing.
- Narrative persistence tracking.
- Narrative acceleration tracking.
- Crowding risk detection.
- Catalyst framework for company and macro events.
- Daily text report generation.
- Saved JSON run outputs for auditability and dashboard use.

### Intelligence Layer

- Market Environment classification.
- Breadth Confirmation.
- Positioning Environment classification.
- Regime Alignment scoring.
- Mode Context for macro and Nasdaq reads.
- Narrative Leadership.
- Narrative Pulse.
- Narrative concentration, dominant narrative share, and narrative dynamics.

### Dashboard

- User Dashboard.
- Admin Dashboard.
- Market Snapshot.
- Regime Alignment History.
- Narrative Leadership cards.
- Narrative Pulse display.
- Dashboard UX refinements for spacing, hierarchy, readability, and workflow separation.
- Better latest-run presentation and dashboard-ready summaries.

## Upcoming Priorities

### 1. Leadership Rotation

Brief description: Build a dedicated view and supporting output for tracking when narrative leadership changes, which themes are gaining or losing control, and how leadership evolves across recent runs.

Why it matters: Narrative Leadership shows the current leaders, but rotation explains the transition. This helps users identify whether the market story is stable, broadening, narrowing, or handing off to a new theme.

Rough implementation priority: Highest. This is the next natural layer on top of existing Narrative Leadership, Narrative Pulse, persistence, and acceleration work.

### 2. Dedicated Navigation Pages

Brief description: Split major dashboard concepts into dedicated pages for market snapshot, regime alignment, narrative leadership, narrative pulse, catalysts, taxonomy/audit detail, and admin diagnostics.

Why it matters: The dashboard has grown beyond a single-page summary. Dedicated navigation will make the product easier to scan, reduce cognitive load, and give each intelligence surface room for clearer visual treatment.

Rough implementation priority: High. This should follow Leadership Rotation or progress alongside it where routing and page structure are needed.

### 3. Dashboard Enhancement: Daily Regime Alignment History

Brief description: Convert the user-facing Regime Alignment History chart from recent-run based history to daily-based aggregation so it better communicates regime changes over time, ideally with one point per day.

Why it matters: Run-level history is useful for development and diagnostics, but daily aggregation is clearer for user-facing dashboard interpretation once MNE is run multiple times per day. Repeated same-day runs can otherwise create cluttered or repetitive chart points.

Implementation notes: Reuse existing daily-run/history helpers if possible. Keep run-level history available in admin and diagnostic views, and do not remove raw run data. Consider applying the same daily-vs-run distinction to other dashboard history charts later.

Rough implementation priority: Soon / Dashboard polish.

### 4. Market Expression Map

Brief description: Create a view that links active narratives and regime states to possible market expressions, such as relevant indices, sectors, symbols, risk factors, or directional watch items.

Why it matters: MNE currently explains narrative and market context. A Market Expression Map would help translate that context into a clearer research bridge between macro stories and observable market behavior.

Rough implementation priority: Medium-high. It depends on stable leadership, pulse, and regime outputs, but can start with a simple mapping layer before deeper analytics.

### 5. Taxonomy V2

Brief description: Refine and expand the theme taxonomy based on audit findings, repeated runs, ambiguous classifications, and gaps found in current narrative grouping.

Why it matters: The taxonomy is the foundation for theme detection and narrative scoring. Improving it will increase signal quality, reduce false grouping, and make leadership and rotation outputs more reliable.

Rough implementation priority: Medium. Continue collecting audit evidence while higher-priority product views mature, then apply a focused Taxonomy V2 pass.

## Future / Backlog

- Discord report delivery.
- TradingView visualization or overlay layer.
- Streaming dashboard mode.
- Additional market symbols and sector context.
- More robust catalyst source integrations.
- Historical backfill and reanalysis tools.
- Exportable research packets or weekly summaries.
