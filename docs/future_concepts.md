# MNE Future Concepts: Technical Specifications

## Status and scope

This file defines the future-concept backlog for Macro Narrative Engine (MNE). It is a specification and sequencing reference, not an assertion that any concept is implemented. Example schemas are provisional contracts; implementation work must version and validate them before use.

All concepts must preserve the MNE product boundary:

- **Narrative first, market second.** Narrative state is established independently before market data is used as context or confirmation.
- **Explainability first.** Every classification must expose its inputs, rules, thresholds, confidence, missing inputs, and plain-language reason.
- **Deterministic logic.** Equal versioned inputs and parameters must produce equal outputs. No opaque learned scores or black-box prediction.
- **Context only.** Outputs describe narrative and market conditions. They must not contain entries, exits, position sizes, targets, expected returns, or trade recommendations.
- **Auditable history.** Derived records must retain source run/snapshot identifiers and relevant taxonomy, mapping, and ruleset versions.
- **Explicit uncertainty.** Missing or incompatible data must produce `unavailable` or `insufficient_history`, never an inferred directional result.
- **Institutional voice.** Narrative Brief templates must follow `docs/narrative_style_guide.md` so the public MNE voice remains calm, analytical, evidence-based, and deterministic.

## Shared state and data conventions

MNE has three different time grains. They must not be silently mixed:

| Grain | Source | Update rule | Intended use |
|---|---|---|---|
| Run-based | Saved result JSON | Recompute after every completed engine run | Intraday diagnostics, current context, run-to-run changes |
| Daily-based | Daily snapshots | Update after a completed run; use the snapshot's documented daily aggregation | Trends, transitions, replay, stable user-facing history |
| Dashboard-only | Run JSON and/or snapshots loaded by the dashboard | Derive on read; never treated as authoritative persisted engine state | Filtering, sorting, view preferences, provisional visualization |

The existing daily snapshot uses median narrative share and score across same-day runs and retains raw runs. Future daily features should consume that contract or introduce a versioned replacement; they must not assume that a snapshot is simply the last run of the day.

Common metadata expected on persisted derived outputs:

```json
{
  "schema_version": "1.0",
  "ruleset_version": "future_feature_v1",
  "as_of": "2026-06-18T12:00:00-04:00",
  "grain": "run",
  "source_refs": ["results/2026-06-18_120000.json"],
  "taxonomy_version": "v1",
  "state": "example_state",
  "confidence": "moderate",
  "reason": "Deterministic explanation of the classification.",
  "missing_inputs": [],
  "context_only": true,
  "is_signal": false
}
```

Thresholds below are initial design candidates, not calibrated facts. Before activation, each must be named, centrally configured, versioned, tested at boundary values, and reviewed against historical runs without optimizing for returns.

## 1. Trader Sentiment Layer

### 1. Purpose

Add an explicit, explainable description of observable trader tone around a narrative without changing the underlying narrative score.

### 2. Problem it solves

News attention, positioning context, volatility, and price behavior can imply different market moods even when narrative strength is unchanged. MNE currently lacks one normalized layer that distinguishes cautious, constructive, speculative, defensive, and conflicted participation.

### 3. Required inputs

- Current narrative leadership, share, pulse, acceleration, persistence, and crowding.
- `market_snapshot`, market environment, breadth confirmation, positioning environment, catalyst environment, and regime alignment.
- Optional future transparent sentiment inputs such as put/call, volatility term structure, fund flows, or survey data, each with source timestamp and availability status.
- Taxonomy and ruleset versions.

### 4. Output schema

```json
{
  "trader_sentiment": {
    "state": "constructive_but_crowded",
    "confidence": "moderate",
    "scope": "AI / Tech Growth",
    "evidence": [
      {"input": "breadth_confirmation.state", "value": "NARROW", "effect": "caution"},
      {"input": "narrative_crowding.risk", "value": "HIGH", "effect": "crowding"}
    ],
    "reason": "Participation is constructive, but narrow breadth and high crowding limit confirmation.",
    "missing_inputs": [],
    "context_only": true,
    "is_signal": false
  }
}
```

### 5. Parameters / thresholds

Use a deterministic evidence matrix. Candidate minimums: at least three available evidence families, no state above `low` confidence with fewer than two agreeing families, and a separate `mixed` state when positive and defensive evidence is balanced. Do not reduce the layer to a hidden composite score.

### 6. UI components needed

A sentiment state card, evidence checklist, confidence/missing-data badge, narrative scope selector, and recent daily state strip. Copy must say “market context,” not “bullish/bearish trade.”

### 7. State management logic

The current reading is **run-based** and updates only after a completed run. The history view is **daily-based** from snapshots. Dashboard filters are dashboard-only. Catalysts affect evidence only when their as-of window includes the run timestamp. A state change must reference the prior comparable run or daily snapshot and compatible ruleset.

### 8. Data storage requirements

Store the run result under a versioned `trader_sentiment` field, including evidence. Store optional daily rollups separately or derive them reproducibly from snapshots. External sentiment observations require timestamped source records and provenance; never overwrite historical values.

### 9. Dependencies on existing MNE modules

`mne/narrative_pulse.py`, `analysis/narrative_dynamics.py`, `mne/environment.py`, `mne/breadth.py`, `mne/positioning_environment.py`, `mne/catalyst_environment.py`, `mne/regime_alignment.py`, `mne/storage.py`, and dashboard view-model code.

### 10. Risks / constraints

“Sentiment” can be mistaken for prediction; labels and explanations must remain descriptive. Vendor data may have delays, licensing constraints, inconsistent history, or revised observations. Avoid double-counting market inputs already embedded in regime alignment.

### 11. Recommended implementation phase

**Phase 3 — contextual synthesis**, after stable market-expression confirmation and daily history contracts.

## 2. Narrative Exhaustion

### 1. Purpose

Identify when a persistent, crowded narrative remains prominent while its momentum or market confirmation deteriorates.

### 2. Problem it solves

High attention alone cannot distinguish durable leadership from a mature narrative losing incremental support. The current relationship classifier contains an exhaustion state, but a dedicated concept needs per-narrative history, evidence, lifecycle status, and explicit reset behavior.

### 3. Required inputs

- Per-group share, score, rank, pulse, acceleration/decay, persistence, and crowding.
- Market-expression confirmation for the same group and its mapped instruments.
- Daily snapshots for sustained conditions; run JSON for provisional current state.
- Compatible taxonomy and expression-map versions.

### 4. Output schema

```json
{
  "narrative_exhaustion": {
    "group": "AI / Tech Growth",
    "state": "watch",
    "confidence": "moderate",
    "evidence": {
      "dominant_runs": 7,
      "share": 0.53,
      "acceleration": "cooling",
      "crowding_risk": "HIGH",
      "expression_confirmation": "weakening"
    },
    "triggered_rules": ["persistent", "crowded", "confirmation_deteriorating"],
    "reason": "Attention remains concentrated while mapped market confirmation is weakening.",
    "context_only": true,
    "is_signal": false
  }
}
```

### 5. Parameters / thresholds

Initial candidates, consistent with current relationship logic: dominant persistence at least 5 comparable runs, share at least 0.50, crowding `HIGH`, and weakening in at least one primary expression. Dedicated implementation should require deterioration across two daily observations before `confirmed`; one run may only produce `watch`. Reset after two daily observations below the crowding/share condition or restored confirmation.

### 6. UI components needed

Per-narrative exhaustion badge, evidence ladder, share/confirmation overlay chart, state-history strip, threshold disclosure, and “why this state” drawer.

### 7. State management logic

Compute a **provisional run-based** state after each run. Promote to a **daily-based confirmed** state only from snapshots and daily market observations. Do not increment persistence multiple times solely because MNE ran repeatedly on one day. Catalysts are annotations, not exhaustion triggers. Dashboard-only chart overlays are not authoritative state.

### 8. Data storage requirements

Persist run assessments with source refs; persist daily lifecycle records keyed by date and narrative group. Store trigger and reset transitions, parameters, taxonomy version, and mapping version. Retain `insufficient_history` records for auditability.

### 9. Dependencies on existing MNE modules

`analysis/narrative_dynamics.py`, `mne/narrative_pulse.py`, `mne/narrative_market_relationship.py`, future Market Expression Confirmation, `mne/narrative_market_map.py`, and `mne/storage.py`.

### 10. Risks / constraints

Sparse history and same-day runs can create false persistence. A narrative can stay crowded and confirmed for a long time, so exhaustion must not imply reversal. Taxonomy changes can invalidate longitudinal comparisons.

### 11. Recommended implementation phase

**Phase 3 — narrative lifecycle**, after per-group market confirmation and daily transition infrastructure.

## 3. Narrative Transition Map

### 1. Purpose

Represent explainable handoffs between leading, rising, fading, and successor narratives over time.

### 2. Problem it solves

Rank lists show current leadership but not how attention moved, which narrative lost share, which absorbed it, or whether the change represents rotation, broadening, narrowing, or noise.

### 3. Required inputs

- Consecutive compatible daily snapshots with group share, score, rank, and pulse.
- Leadership rotation output, concentration gap, acceleration, decay, and persistence.
- Optional catalyst associations for annotation.

### 4. Output schema

```json
{
  "narrative_transition_map": {
    "window": {"start": "2026-06-15", "end": "2026-06-18", "grain": "daily"},
    "nodes": [
      {"group": "AI / Tech Growth", "start_share": 0.48, "end_share": 0.34, "role": "ceding"},
      {"group": "Energy", "start_share": 0.15, "end_share": 0.29, "role": "gaining"}
    ],
    "transitions": [
      {"from": "AI / Tech Growth", "to": "Energy", "state": "probable_handoff", "share_delta_pair": 0.28}
    ],
    "classification": "rotation",
    "reason": "The prior leader lost share as Energy gained and moved into leadership.",
    "context_only": true
  }
}
```

### 5. Parameters / thresholds

Candidate transition requires either a rank-one change or opposing share moves above 0.05 for both groups across the selected daily window. `probable_handoff` must be labeled as an attribution heuristic, not a claim that attention literally transferred. Minimum two snapshots; three recommended for confirmed rotation.

### 6. UI components needed

A Sankey-style or directed transition view, timeline scrubber, window selector, node detail panel, classification legend, catalyst markers, and accessible table fallback.

### 7. State management logic

Authoritative transitions are **daily-based** and recompute when a new or backfilled snapshot is available. Run-based transitions may appear only as `provisional`. Catalysts annotate the applicable date/window. Layout coordinates, selected windows, and filters are dashboard-only derived state.

### 8. Data storage requirements

Daily snapshots remain the source of truth. Cache versioned transition records by window only for performance; each cache record must retain snapshot hashes/refs and be invalidated when a source snapshot, taxonomy, or ruleset changes.

### 9. Dependencies on existing MNE modules

`analysis/leadership_rotation.py`, `analysis/narrative_dynamics.py`, `mne/storage.py`, narrative group outputs from `mne/narrative_signals.py`, and catalyst modules.

### 10. Risks / constraints

Share is compositional: one group's gain mechanically affects others. Do not imply causality or capital flow. Too many nodes will make the visualization unreadable; low-share groups need an explicit “Other” rule without destroying audit detail.

### 11. Recommended implementation phase

**Phase 2 — daily narrative history**, after Leadership Rotation output is stable.

## 4. Market Expression Confirmation

### 1. Purpose

Evaluate whether the observable behavior of curated market-expression proxies supports, contradicts, or does not resolve a narrative.

### 2. Problem it solves

The current static Market Expression Map explains where a narrative may appear, while the existing relationship classifier is narrow and centered on specific symbols. A generalized layer is needed for every mapped narrative without turning expression proxies into trade signals.

### 3. Required inputs

- Versioned static output from `mne/narrative_market_map.py`.
- Timestamped price changes for primary, secondary, and offset instruments.
- Narrative share, pulse, acceleration, and state.
- Market-wide context and data freshness/market-session metadata.

### 4. Output schema

```json
{
  "market_expression_confirmation": {
    "group": "AI / Tech Growth",
    "mapping_version": "phase_1_static_v1",
    "state": "partial_confirmation",
    "confidence": "moderate",
    "instruments": [
      {"symbol": "NVDA", "role": "primary", "pct_change": 1.4, "move": "UP", "supports": true},
      {"symbol": "MSFT", "role": "primary", "pct_change": -0.2, "move": "FLAT", "supports": null}
    ],
    "counts": {"supporting": 1, "contradicting": 0, "neutral": 1, "unavailable": 0},
    "reason": "One primary proxy supports the narrative while the other is neutral.",
    "context_only": true,
    "is_signal": false
  }
}
```

### 5. Parameters / thresholds

Reuse versioned `classify_market_move` boundaries unless a documented role-specific threshold is approved. Candidate rules: `confirmed` requires a majority of available primary instruments with at least two available; `contradicted` requires a majority moving against the documented expression; otherwise `partial`, `mixed`, or `unavailable`. Offsets must use explicitly configured expected relationships.

### 6. UI components needed

Narrative expression card, instrument matrix grouped by role, confirmation badge, freshness indicator, mapping-description panel, and rule/evidence disclosure.

### 7. State management logic

Compute **run-based** using the market snapshot captured by that run. Create **daily-based** confirmation from a documented daily market observation, not by medianing categorical run states. Dashboard-only grouping and sorting may be derived on read. Never refresh price data independently in the dashboard and attach it to an older run.

### 8. Data storage requirements

Persist per-run instrument observations and classification beside the run or as a source-linked derived artifact. Daily records must store the market timestamp/session. Preserve mapping version and expected direction per instrument.

### 9. Dependencies on existing MNE modules

`mne/narrative_market_map.py`, `mne/market_context.py`, `mne/narrative_market_relationship.py`, `mne/environment.py`, `mne/storage.py`, and future expanded symbol acquisition.

### 10. Risks / constraints

Static mappings can become stale; a symbol may express several narratives. Close-to-close changes can be misleading around market hours, holidays, or stale quotes. Confirmation is contemporaneous context, not proof, causality, or forecast.

### 11. Recommended implementation phase

**Phase 1 — foundational**, as the next extension of the existing static map.

## 5. Group-Level Market Expression Maps

### 1. Purpose

Extend curated expression mappings from a dominant theme to every narrative group with explicit roles and expected relationships.

### 2. Problem it solves

Theme-only, single-result mapping cannot support group-level comparison, confirmation, heatmaps, or replay. Narrative groups may require baskets that differ from any one constituent theme.

### 3. Required inputs

- Narrative group definitions from `mne/narrative_signals.py`.
- Existing static theme mappings.
- Curated, human-reviewed group-to-instrument configuration.
- Symbol metadata and effective dates.

### 4. Output schema

```json
{
  "group_market_expressions": {
    "AI / Tech Growth": {
      "mapping_version": "group_map_v1",
      "effective_from": "2026-07-01",
      "primary": [{"symbol": "QQQ", "expected_relation": "positive", "rationale": "Growth index proxy"}],
      "secondary": [{"symbol": "SMH", "expected_relation": "positive", "rationale": "Semiconductor proxy"}],
      "offsets": [{"symbol": "TLT", "expected_relation": "context_dependent", "rationale": "Rate sensitivity context"}],
      "context_only": true
    }
  }
}
```

### 5. Parameters / thresholds

No scoring threshold is intrinsic to the map. Configuration limits should require one to five primary expressions, zero to ten secondary expressions, explicit relation/rationale, and effective dates. Duplicate symbols across groups are allowed and must remain visible.

### 6. UI components needed

Group selector, primary/secondary/offset columns, rationale tooltips, mapping version/effective-date display, and admin coverage/validation table. No buy/sell language.

### 7. State management logic

Mappings are **configuration state**, not run- or daily-derived state. A run resolves the mapping effective at its timestamp and stores that version. Dashboard display derives from the selected run and must not retroactively apply the newest map to old runs unless explicitly in a reanalysis mode.

### 8. Data storage requirements

Use a version-controlled configuration file with immutable versions or effective-date history. Saved run JSON should contain the resolved mapping version and preferably the resolved mapping payload or hash for replay.

### 9. Dependencies on existing MNE modules

`mne/narrative_market_map.py`, `mne/narrative_signals.py`, `config/theme_taxonomy.json`, `mne/storage.py`, and future Market Expression Confirmation.

### 10. Risks / constraints

Mappings encode analyst judgment and require governance. Instrument overlap can look like false diversification. Corporate actions, ETF changes, delistings, and shifting narrative exposure require dated revisions rather than silent edits.

### 11. Recommended implementation phase

**Phase 1 — foundational**, before generalized confirmation and expression dashboards.

## 6. Narrative Heatmap

### 1. Purpose

Provide a compact historical view of narrative strength, change, pulse, or confirmation across groups and dates.

### 2. Problem it solves

Cards and rank lists make cross-sectional and time-series comparison slow. Users need to see persistence, emergence, cooling, and missing data without inspecting each run.

### 3. Required inputs

- Daily snapshots with group share, score, rank, and pulse.
- Optional market-expression confirmation and exhaustion states.
- Taxonomy/ruleset compatibility metadata.

### 4. Output schema

```json
{
  "narrative_heatmap": {
    "metric": "share",
    "grain": "daily",
    "rows": ["AI / Tech Growth", "Energy"],
    "columns": ["2026-06-17", "2026-06-18"],
    "cells": [
      {"group": "AI / Tech Growth", "date": "2026-06-18", "value": 0.41, "state": "leading", "source_ref": "snapshots/2026-06-18.json"}
    ],
    "scale": {"type": "fixed", "min": 0, "max": 1},
    "context_only": true
  }
}
```

### 5. Parameters / thresholds

Default to daily share with a fixed 0–1 scale. Do not auto-rescale colors per window because it changes visual meaning. Candidate row inclusion: any group above 0.05 on at least one date, with excluded groups available through filtering. State-valued metrics require a declared ordinal legend, not invented numeric precision.

### 6. UI components needed

Accessible heatmap grid, metric selector, 7/30/90-day range, sortable row labels, cell tooltip with source and explanation, missing-data hatch, color legend, and tabular alternative.

### 7. State management logic

Primary heatmap is **daily-based** and updates when snapshots change. An intraday mode may be **run-based** but must be labeled and separated. Metric/range/sort selections are dashboard-only state. Catalyst markers may appear in tooltips but do not alter cell values.

### 8. Data storage requirements

Prefer derivation from daily snapshots. Cache matrices only for performance and invalidate them on snapshot or ruleset changes. Store user view preferences separately, if at all; never in engine result JSON.

### 9. Dependencies on existing MNE modules

`mne/storage.py`, `mne/narrative_pulse.py`, `analysis/narrative_dynamics.py`, dashboard history helpers, and optionally future confirmation/exhaustion outputs.

### 10. Risks / constraints

Color can imply quality or direction; palettes must communicate magnitude/state and be colorblind accessible. Taxonomy changes can produce discontinuous rows. Missing observations must not render as zero.

### 11. Recommended implementation phase

**Phase 2 — visualization**, once daily snapshot and taxonomy compatibility rules are stable.

## 7. Crowding Dashboard

### 1. Purpose

Expose the existing and future crowding evidence as an auditable multi-narrative monitoring surface.

### 2. Problem it solves

A single crowding risk label hides which inputs triggered the state, how long it persisted, and whether it is broadening, intensifying, or resolving.

### 3. Required inputs

- Narrative crowding output, concentration, dominant share, concentration gap, persistence, acceleration/decay, and pulse.
- Daily snapshots and current run JSON.
- Optional sentiment and market-expression confirmation as clearly separated contextual overlays.

### 4. Output schema

```json
{
  "crowding_dashboard_data": {
    "as_of": "2026-06-18T12:00:00-04:00",
    "groups": [
      {
        "group": "AI / Tech Growth",
        "risk": "HIGH",
        "share": 0.53,
        "persistence_runs": 7,
        "triggered_rules": ["share_high", "persistent", "concentrated"],
        "reason": "High share and persistence coincide with concentrated leadership."
      }
    ],
    "context_only": true,
    "is_signal": false
  }
}
```

### 5. Parameters / thresholds

Initially display the exact thresholds from `analysis/narrative_dynamics.py`; do not create dashboard-specific risk logic. Any daily crowding variant must define daily persistence separately from run persistence. Thresholds must appear in the UI and schema metadata.

### 6. UI components needed

Summary risk cards, ranked group table, share/persistence history, concentration chart, triggered-rule checklist, current-run versus daily toggle, and methodology drawer.

### 7. State management logic

Current diagnostics are **run-based** and update after completed runs. User-facing trend is **daily-based** and must not count repeated same-day runs as separate days. Filters and sorting are dashboard-only. Catalysts and confirmation are annotations and must not mutate the underlying crowding state.

### 8. Data storage requirements

Reuse persisted run crowding evidence. Add daily crowding records only if the daily calculation differs materially and is versioned. Dashboard aggregates should remain derived/cacheable, not a second source of truth.

### 9. Dependencies on existing MNE modules

`analysis/narrative_dynamics.py`, `mne/narrative_signals.py`, `mne/narrative_pulse.py`, `mne/storage.py`, and dashboard view-model/history helpers.

### 10. Risks / constraints

Crowding is not a reversal forecast. Run frequency can inflate persistence. High narrative concentration may reflect a genuinely dominant event rather than speculative positioning. The UI must keep evidence and limitations visible.

### 11. Recommended implementation phase

**Phase 2 — dashboard intelligence**, after daily crowding semantics are defined.

## 8. Narrative Regime Engine

### 1. Purpose

Classify the structural narrative environment—such as concentrated leadership, broad participation, active rotation, fragmentation, or transition—before applying market context.

### 2. Problem it solves

`mne/regime_alignment.py` evaluates alignment across narrative and market contributors, but MNE lacks a narrative-only regime taxonomy that summarizes the organization of attention over time.

### 3. Required inputs

- Narrative group shares, ranks, concentration, concentration gap, pulse, persistence, acceleration, decay, leadership rotation, and transition history.
- At least three compatible daily snapshots for non-provisional states.
- Taxonomy and ruleset versions.

Market prices are explicitly excluded from the primary classification; they may be attached later as context.

### 4. Output schema

```json
{
  "narrative_regime": {
    "state": "rotating",
    "confidence": "high",
    "time_grain": "daily",
    "evidence": {
      "leader_changes_5d": 2,
      "top_share": 0.31,
      "concentration": "moderate",
      "gaining_groups": 2,
      "fading_groups": 2
    },
    "triggered_rules": ["multiple_leader_changes", "opposing_group_momentum"],
    "market_context": null,
    "reason": "Leadership changed repeatedly while gains and losses were distributed across groups.",
    "context_only": true,
    "is_signal": false
  }
}
```

### 5. Parameters / thresholds

Candidate states: `concentrated_leadership`, `broadening`, `rotating`, `fragmented`, `transitioning`, `stable_balanced`, and `insufficient_history`. Use named rules: e.g., concentrated when top share is at least 0.50 and gap exceeds 0.15; rotating when at least two leader changes occur in five daily observations plus opposing momentum; fragmented when no group exceeds 0.25 and concentration is low. Exact definitions require historical distribution review.

### 6. UI components needed

Narrative regime card, evidence panel, regime timeline, state-definition legend, transition markers, and separate market/regime-alignment context panel to preserve narrative-first ordering.

### 7. State management logic

Authoritative regime is **daily-based**, recomputed when snapshots are written/backfilled. The latest run may have a clearly labeled `provisional` regime. Regime transitions require persistence or hysteresis rules to avoid one-observation flips. Dashboard-only state controls windows and overlays; catalysts only annotate transitions.

### 8. Data storage requirements

Persist one versioned narrative-regime record per date with source snapshot refs, rule evidence, prior state, and transition reason. Recompute derived history when the taxonomy/ruleset changes, preserving old-version artifacts for audit.

### 9. Dependencies on existing MNE modules

`mne/narrative_signals.py`, `mne/narrative_pulse.py`, `analysis/narrative_dynamics.py`, `analysis/leadership_rotation.py`, `mne/storage.py`; integrate downstream with, but remain distinct from, `mne/regime_alignment.py`.

### 10. Risks / constraints

Regime labels can imply more stability than the data supports. Hysteresis improves stability but delays transitions. Thresholds may be sensitive to the number and definition of narrative groups. Market inputs must not leak into the narrative-only state.

### 11. Recommended implementation phase

**Phase 3 — synthesis**, after Transition Map and stable daily history.

## 9. Narrative Playbook Library

### 1. Purpose

Maintain a curated library explaining how to interpret recurring combinations of narrative states and contextual evidence.

### 2. Problem it solves

Users need consistent interpretation and research prompts across repeated states. Free-form commentary can become inconsistent, non-auditable, or drift into recommendations.

### 3. Required inputs

- Versioned playbook definitions authored and reviewed by humans.
- Current narrative regime, pulse, transition, exhaustion, crowding, catalyst, and market-expression states.
- Deterministic match conditions and exclusion conditions.

### 4. Output schema

```json
{
  "matched_playbooks": [
    {
      "playbook_id": "rotation_with_catalyst_density",
      "version": "1.0",
      "title": "Rotation near a dense catalyst window",
      "matched_conditions": ["narrative_regime=rotating", "catalyst_density=HIGH"],
      "interpretation": "Leadership is changing while scheduled events may increase context sensitivity.",
      "research_questions": ["Is the new leader persistent across daily snapshots?"],
      "invalidators": ["Rotation falls back to insufficient history"],
      "context_only": true,
      "is_signal": false
    }
  ]
}
```

### 5. Parameters / thresholds

Matching uses exact enumerated states and minimum-confidence gates. Candidate default: all required conditions must match and no exclusion may match. Ordering is by explicit priority, then stable playbook ID—not a learned relevance rank. Limit the default display to three matches while retaining all matches in detail.

### 6. UI components needed

Searchable library, current-match cards, condition checklist, interpretation/research-question sections, invalidators, version history, and admin validation/coverage view.

### 7. State management logic

Library definitions are **configuration state**. Matches are **run-based** for current context and optionally **daily-based** for history. Re-evaluate only after a completed run/snapshot or playbook version change. Dashboard search and bookmarks are dashboard/user state. Catalysts are eligible deterministic conditions, not free-form triggers.

### 8. Data storage requirements

Store playbooks in a versioned structured configuration format. Persist matched playbook IDs/versions and matched conditions in run/daily artifacts; do not duplicate mutable prose without also retaining its content hash or version.

### 9. Dependencies on existing MNE modules

All selected intelligence outputs, particularly `mne/narrative_pulse.py`, `analysis/narrative_dynamics.py`, catalyst modules, future Narrative Regime Engine, and future Market Expression Confirmation.

### 10. Risks / constraints

Playbooks can become disguised trade advice. They must contain observations, research questions, and invalidation conditions—not actions, return claims, or instrument recommendations. Overlapping matches and stale prose require governance and validation.

### 11. Recommended implementation phase

**Phase 4 — interpretive product layer**, after upstream state schemas stabilize.

## 10. Narrative Replay

### 1. Purpose

Reconstruct what MNE knew and classified at a historical point using the versions and data available then.

### 2. Problem it solves

Latest-state dashboards cannot answer how a narrative developed, when rules changed, or whether a historical interpretation is reproducible without hindsight leakage.

### 3. Required inputs

- Immutable run JSON, raw/deduplicated headline references, daily snapshots, and timestamped market observations.
- Taxonomy, mapping, ruleset, catalyst, and playbook versions effective at the replay time.
- Event markers and derived-state source refs.

### 4. Output schema

```json
{
  "narrative_replay": {
    "replay_id": "2026-06-18T12:00:00-04:00__as_recorded",
    "mode": "as_recorded",
    "cursor": "2026-06-18T12:00:00-04:00",
    "source_run": "results/2026-06-18_120000.json",
    "versions": {"taxonomy": "v1", "ruleset": "mne_v1", "expression_map": "group_map_v1"},
    "available_state": {"dominant_group": "AI / Tech Growth", "narrative_regime": "rotating"},
    "future_data_excluded": true,
    "context_only": true
  }
}
```

### 5. Parameters / thresholds

Two explicit modes only: `as_recorded` (display stored outputs) and `recomputed` (apply a selected historical/current version to historical raw inputs). Default to `as_recorded`. The cursor must include only records with source timestamps at or before it. Minimum replay step is one run; user-facing default is one daily snapshot.

### 6. UI components needed

Timeline scrubber, play/pause and step controls, run/daily toggle, as-recorded/recomputed badge, version manifest, synchronized narrative/market/catalyst panels, and source-data inspector.

### 7. State management logic

Replay is primarily **dashboard/session state** over immutable **run-based and daily-based** records. Moving the cursor must not write or update live state. Recomputed replay produces a new isolated artifact, never overwrites original runs/snapshots, and must exclude catalysts not known by the cursor time.

### 8. Data storage requirements

Requires immutable source artifacts, stable identifiers, manifests/hashes, retained configuration versions, and timestamped market/catalyst observations. Optional replay caches must be disposable and keyed by cursor plus all version hashes.

### 9. Dependencies on existing MNE modules

`mne/storage.py`, headline storage/deduplication, `mne/theme_analysis.py`, all derived intelligence modules, catalyst modules, dashboard history loaders, and future Event Markers.

### 10. Risks / constraints

The largest risk is hindsight leakage from revised calendars, current mappings, or future headlines. Current files may not retain every historical config or external observation needed for exact replay. Recomputed results must never be presented as what MNE actually showed then.

### 11. Recommended implementation phase

**Phase 5 — historical research**, after version manifests and immutable event/market storage exist.

## 11. Event Markers

### 1. Purpose

Create a normalized, timestamped annotation layer for scheduled catalysts and observed narrative/market state changes.

### 2. Problem it solves

Catalysts and transitions are difficult to align consistently across charts. A shared event contract prevents each dashboard component from inventing its own marker semantics.

### 3. Required inputs

- Normalized company and macro catalysts with event time/date, source, importance, and availability time.
- Derived MNE transitions such as leader change, regime change, exhaustion state change, or confirmation change.
- Run/snapshot timestamps and source refs.

### 4. Output schema

```json
{
  "event_markers": [
    {
      "event_id": "macro_cpi_2026-06-18",
      "event_type": "macro_catalyst",
      "event_time": "2026-06-18T08:30:00-04:00",
      "known_at": "2026-06-01T10:00:00-04:00",
      "label": "CPI release",
      "importance": "red",
      "source": "macro_calendar",
      "scope": ["Inflation", "Rates"],
      "source_refs": ["config/macro_calendar.json"],
      "context_only": true
    }
  ]
}
```

### 5. Parameters / thresholds

No analytical threshold for scheduled events. Derived markers need explicit transition rules from their source feature. Deduplicate by stable source ID plus event time/type; if unavailable, use a deterministic content hash. Distinguish event time from `known_at` and ingestion time.

### 6. UI components needed

Reusable chart-marker component, event rail/list, type and importance filters, detail popover, timezone display, overlap clustering, and source/provenance link.

### 7. State management logic

Scheduled events are **calendar state** and update when catalyst sources refresh; they attach to runs/snapshots based on event windows. Derived state-change markers are **run-based or daily-based** according to their source feature. Marker layout/clustering is dashboard-only. Historical replay must filter by `known_at` to avoid hindsight.

### 8. Data storage requirements

Persist normalized events with stable IDs, revisions, source provenance, `event_time`, `known_at`, and ingestion time. Store derived markers as reproducible references to source states. Do not silently mutate historical event times; append revisions.

### 9. Dependencies on existing MNE modules

`mne/catalysts.py`, `mne/macro_catalysts.py`, `mne/company_catalysts.py`, `mne/catalyst_environment.py`, `mne/storage.py`, and all future transition-producing modules.

### 10. Risks / constraints

Calendars are revised, times are timezone-sensitive, and some events lack precise timestamps. Visual proximity does not establish causality. Too many markers can obscure charts; filtering and clustering must not alter underlying records.

### 11. Recommended implementation phase

**Phase 2 — shared visualization infrastructure**, before Replay and Pre/Post Event Comparison.

## 12. Pre/Post Event Comparison

### 1. Purpose

Compare narrative and contextual states before and after a selected event using fixed, transparent windows.

### 2. Problem it solves

Users cannot consistently assess what changed around a catalyst or state transition when run timing is irregular. Manual comparisons invite cherry-picking and causal overstatement.

### 3. Required inputs

- A normalized event marker with event time and `known_at`.
- Compatible run JSON and/or daily snapshots on both sides of the event.
- Narrative shares, ranks, pulse, concentration, regime, crowding, expression confirmation, and market context.
- Window definition, market-session calendar, and version compatibility metadata.

### 4. Output schema

```json
{
  "pre_post_event_comparison": {
    "event_id": "macro_cpi_2026-06-18",
    "grain": "daily",
    "window": {"pre": 3, "post": 3, "unit": "observations"},
    "pre_refs": ["snapshots/2026-06-15.json", "snapshots/2026-06-17.json"],
    "post_refs": ["snapshots/2026-06-18.json", "snapshots/2026-06-21.json"],
    "comparisons": [
      {"metric": "AI / Tech Growth.share", "pre": 0.44, "post": 0.36, "delta": -0.08, "method": "median"}
    ],
    "state_changes": [{"metric": "narrative_regime", "pre": "concentrated_leadership", "post": "rotating"}],
    "coverage": {"pre": 2, "post": 2, "complete": false},
    "reason": "Narrative share declined and the narrative regime changed across the selected observation window.",
    "causality_claimed": false,
    "context_only": true
  }
}
```

### 5. Parameters / thresholds

Default daily window: three observations before and three after, excluding the event observation unless the selected policy explicitly assigns it. Default aggregation: median for numeric metrics and deterministic mode-with-most-recent-tiebreak for categorical states. Require at least two observations per side; otherwise `insufficient_coverage`. Intraday windows must use completed runs and market-session-aware boundaries.

### 6. UI components needed

Event selector, window/grain controls, side-by-side state cards, delta table, aligned small charts, coverage warning, source-run inspector, and persistent “association, not causation” notice.

### 7. State management logic

Comparisons are derived on demand from immutable **run-based or daily-based** sources. A post window remains `incomplete` until enough observations exist and should refresh only when a new qualifying run/snapshot arrives. Selection and display options are dashboard-only. Catalyst revisions must create a new comparison version rather than silently shifting historical windows.

### 8. Data storage requirements

Derive on demand initially. Cache only with event revision, source refs/hashes, window policy, taxonomy/ruleset versions, and calculation method. Never persist a delta without its pre/post source set.

### 9. Dependencies on existing MNE modules

Future Event Markers, `mne/storage.py`, catalyst modules, narrative intelligence outputs, market-context modules, and future Narrative Replay for historical inspection.

### 10. Risks / constraints

Event overlap, holidays, sparse runs, and after-hours timing can contaminate windows. Before/after association is not attribution. Multiple comparisons can encourage selective interpretation; show the chosen policy and coverage prominently.

### 11. Recommended implementation phase

**Phase 4 — event analysis**, after Event Markers and stable daily histories; before full Narrative Replay.

## Recommended delivery sequence

1. **Phase 1 — expression foundations:** Group-Level Market Expression Maps; Market Expression Confirmation.
2. **Phase 2 — daily history and shared UI infrastructure:** Narrative Transition Map; Narrative Heatmap; Crowding Dashboard; Event Markers.
3. **Phase 3 — deterministic synthesis:** Trader Sentiment Layer; Narrative Exhaustion; Narrative Regime Engine.
4. **Phase 4 — interpretive and event analysis:** Narrative Playbook Library; Pre/Post Event Comparison.
5. **Phase 5 — historical research:** Narrative Replay.

Each phase must preserve original run JSON and snapshot inputs, add versioned schemas rather than silently redefining existing fields, and ship rule-boundary tests plus missing-data behavior before user-facing activation.
