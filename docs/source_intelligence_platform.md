# MNE - Source Intelligence Platform (SIP)

## Permanent Architecture Specification

**Author role:** Technical Director / Systems Architect / Data Platform Architect  
**Consumer:** ChatGPT (schema/parameter refinement) -> Codex (implementation)  
**Status:** Foundational architecture spec - no code included - intended as a permanent reference document, not a one-off feature spec

## 1. Product Philosophy

MNE's intelligence layer is now mature; the constraint has shifted from "can we build smarter narrative logic" to "can we trust what we fed it." The Source Intelligence Platform (SIP) exists to make MNE aware of the quality of its own inputs, without changing what MNE does with those inputs once accepted.

SIP is built around a foundational abstraction: evidence, not headlines. Headlines are simply the first and most common form of evidence MNE ingests, but SEC filings, earnings transcripts, Federal Reserve publications, economic releases, and future data types are all, structurally, the same thing: a piece of evidence with a timestamp, a source, a quality state, and a relationship to narrative categories. Designing SIP around headlines specifically would mean re-architecting it the first time a non-headline source type is added. Designing it around a standardized Evidence Object from the outset means every ingestion type, present or future, enters MNE through the same deterministic, explainable pipeline.

This document defines that permanent architecture in full, but Phase 1 implementation deliberately proves it against MNE's existing headline pipeline alone before any additional connector type is built. The architecture is designed for many evidence types; the first implementation is scoped to prove it with one.

Governing principles:

- **Deterministic.** Every health state, freshness classification, coverage rating, and confidence score is the output of explicit rules against measurable facts (timestamps, HTTP status, parse results, counts), never inferred, never modeled, and this holds regardless of which evidence type produced the underlying fact. Even identity itself is deterministic: Evidence Objects are identified by a reproducible hash, not an arbitrarily generated ID.
- **Explainable.** Every inclusion or exclusion decision must be traceable to a specific reason, not a silent drop, and traceable to a specific Evidence Object, not a specific source format. Excluded evidence is never discarded; it is persisted with its rejection reason.
- **Narrative-first.** SIP describes evidence quality in service of narrative intelligence. Its outputs (confidence, coverage) exist to contextualize the Narrative Brief and other modules, not to become a competing intelligence product.
- **Transparent.** Nothing about source or evidence handling should be a black box, even to a technical admin looking at raw diagnostics.
- **Modular.** SIP is a layer that sits underneath the existing intelligence modules, feeding them normalized evidence plus provenance and quality signals. It does not sit inside them.
- **Auditable.** Every run's evidence decisions must be reconstructable after the fact from persisted Evidence Objects, not just observable live.
- **Source-agnostic.** No downstream intelligence module should ever need to know whether a given fact came from RSS, an API, a filing, or a future ingestion type. That knowledge is confined to the connector and normalization layers.
- **Resilient by separation.** Source-side failure and narrative-generation failure are distinct concerns with distinct persistence guarantees. SIP must never lose its own diagnostics just because the narrative pipeline it feeds could not complete.

Critical boundary: SIP measures, normalizes, and reports on evidence quality. It does not decide how narrative scoring uses that evidence. Any change in how a module weights evidence based on tier/confidence/type is a decision made inside that module, consuming SIP's output. SIP itself introduces no new scoring math. This document's refinements must not, and do not, change narrative scoring, theme taxonomy, narrative groups, Regime Alignment, Narrative Brief logic, or any other existing downstream intelligence module.

## 2. Current Architecture

- RSS ingestion exists but is largely undifferentiated: feeds are pulled and parsed with limited failure visibility, and downstream modules consume RSS-shaped headline data directly. There is no abstraction between "how we fetched this" and "what narrative logic reads."
- Broken feeds fail silently. There is no persisted record that a feed did not return data on a given run.
- No freshness concept exists. A feed returning six-day-old headlines is treated identically to one updated minutes ago.
- No persisted feed health exists. Health, if evaluated at all, exists only transiently in logs, not in run JSON or snapshots.
- No source metadata exists in run JSON. Downstream review cannot answer "what did MNE actually read today."
- All source types (Tier-1 macro wires vs. general business blogs, for example) are treated with equal structural standing.
- Historical backfill logic and live ingestion logic are not architecturally separated, creating risk of cross-contamination between "what happened today" and "what we're reconstructing about the past."
- There is no concept of evidence beyond headlines. The architecture has no standardized way to represent a SEC filing, an earnings transcript, or a Fed publication alongside a headline.
- Current failure behavior aborts execution when zero headlines are collected. A total source outage today means MNE produces no run output at all, including no diagnostic record of what went wrong. This is a specific, known limitation that SIP's persistence model is designed to correct.
- Rejected/filtered headlines are discarded, not retained. There is no record today of what was excluded or why.

## 3. Desired Future Architecture

SIP introduces an Evidence Normalization Layer as a permanent architectural boundary, plus five cooperating engines that operate on normalized Evidence Objects rather than raw source-specific data. All are deterministic and independently testable, sitting between raw ingestion and the existing intelligence layer:

```text
[Raw Source] -> [Connector] -> [Evidence Normalizer] -> [Standardized Evidence Object]
               (Phase 1: RSS only)      (deterministic hash-based evidence_id)
                                                                |
                                                                v
                                                      [Source Registry-driven
                                                       Feed Health Engine]
                                                                |
                                                                v
                                                      [Freshness Validation Engine]
                                                    (object-level + source-level)
                                                                |
                              +---------------------------------+--------------------+
                              v                                                      v
                 [Evidence Contribution Tracking]                    [accepted Evidence Objects ->
                 (all objects persisted, incl.                        Backward-Compatibility Adapter ->
                  rejected, with rejection metadata)                  existing headline-list interface ->
                              |                                        Narrative Detection / Taxonomy,
                              v                                        unchanged]
                 [Coverage Intelligence] -> [Source Confidence Model]
                 (thresholds/rules sourced from                    |
                  config/source_registry.json)                     v
                                                    (exposed to Narrative Brief Engine,
                                                     dashboards, run JSON, snapshots)
```

- Every Connector (RSS only in Phase 1; APIs, filings, transcripts, government publications, and future types in later phases) is responsible only for translating its native format into a standardized Evidence Object. Nothing downstream of the normalizer is aware of the original format.
- The Source Registry, persisted at `config/source_registry.json`, replaces hardcoded source lists and is now the single authoritative definition of sources, evidence types, categories, coverage thresholds, and confidence rules for the entire platform.
- The Feed Health Engine and Freshness Validation Engine evaluate at the Evidence Object level. `health_state` and object-level `freshness_state` are fields on the Evidence Object, not side-channel data tied to a specific ingestion mechanism, while a separate, explicitly distinct source freshness status describes the provider as a whole.
- Evidence Contribution Tracking records, per run, exactly what each source contributed as Evidence Objects, both accepted and rejected, and what happened to each one downstream.
- Coverage Intelligence aggregates contribution plus health plus freshness into per-narrative/per-group coverage ratings, using thresholds sourced from the registry, computed identically regardless of evidence type mix.
- The Source Confidence Model synthesizes all of the above into a single, explainable "how much should MNE trust today's evidence" signal, using rules sourced from the registry, consumable by the Narrative Brief Engine and dashboards.
- A thin Backward-Compatibility Adapter sits immediately after acceptance filtering, converting the accepted Evidence Object set into the existing headline-list shape that current downstream modules already expect. This allows SIP to be introduced with zero changes to Narrative Detection, Taxonomy, or any scoring module.

No existing intelligence module changes its internal logic. They continue to receive the same shape of accepted-evidence input they do today (headline-shaped, via the adapter). The normalizer plus adapter guarantee that shape regardless of what enters the pipeline upstream, which is what makes future evidence types addable without downstream modification once later phases begin.

## 4. Source Registry

A centralized, structured registry replacing all hardcoded source lists. This is the single authoritative source definition for the entire Source Intelligence Platform.

Canonical location: `config/source_registry.json`

This file is the single point of configuration for what MNE ingests, how it is categorized, how evidence is typed, and the deterministic thresholds/rules that Coverage Intelligence and Source Confidence apply. It is version-controlled configuration, not application code, and not embedded per-run. Runs reference it by `registry_version`.

Minimum required top-level structure:

```json
{
  "registry_version": "string",
  "sources": ["...array of Source Metadata Model objects..."],
  "evidence_types": ["...registered evidence type definitions..."],
  "categories": ["...registered Source Category definitions..."],
  "coverage_thresholds": { "...rating threshold configuration consumed by Coverage Intelligence...": true },
  "confidence_rules": { "...ordered rule table consumed by the Source Confidence Model...": true }
}
```

Registry responsibilities:

- Enumerate every source MNE is permitted to ingest from, regardless of ingestion type or evidence type.
- Define per-source ingestion parameters (connector type, URL/endpoint, cadence expectations).
- Declare which Evidence Type(s) each source's connector is expected to produce. A source is not assumed to produce headlines by default; it explicitly declares its evidence output.
- Define per-source narrative/group relevance, used by Coverage Intelligence, independent of evidence type.
- Support enabling/disabling a source without code changes (data-level toggle, not a deploy).
- Serve as the join key for every downstream health, freshness, contribution, and confidence record. Every diagnostic record references a `source_id` from this registry, and every Evidence Object references the `source_id` that produced it.
- Own the coverage rating thresholds and confidence band rules as first-class registry sections (`coverage_thresholds`, `confidence_rules`). These are configuration data, editable without code changes, not values hardcoded inside the Coverage Intelligence or Source Confidence engines.

Registry is data, not code. Adding a new source, including a source of a brand-new evidence type in a later phase, is a `config/source_registry.json` edit plus a new connector, not a change to Feed Health, Freshness Validation, Coverage Intelligence, Evidence Contribution Tracking, Source Confidence, or any narrative module.

## 5. Source Metadata Model

Each entry in the registry's `sources` array:

```json
{
  "source_id": "string",
  "display_name": "string",
  "provider": "string",
  "category": "string (one of Source Categories)",
  "priority": "TIER_1 | TIER_2 | TIER_3",
  "ingestion_type": "RSS | API | MANUAL | OTHER",
  "supported_evidence_types": ["string (one or more Evidence Types; Phase 1: 'Headline' only)"],
  "url": "string",
  "enabled": "boolean",
  "freshness_threshold_minutes": "integer",
  "expected_update_frequency_minutes": "integer",
  "weighting": "number (0.0-1.0, structural weight)",
  "supported_narratives": ["string", "..."],
  "supported_groups": ["string", "..."],
  "notes": "string | null",
  "registered_at": "ISO 8601 date",
  "last_modified_at": "ISO 8601 date"
}
```

Field notes:

- `supported_evidence_types` is the field that generalizes the registry beyond headlines. In Phase 1, every source declares `["Headline"]` only. The field exists and is populated correctly from day one so later phases require no schema migration, only new values.
- `ingestion_type` describes the mechanical fetch method; `supported_evidence_types` describes the content produced. These are intentionally separate axes.
- `weighting` is a structural value (how much this source is expected to matter within its tier), not a live scoring multiplier applied opaquely.
- `supported_narratives` / `supported_groups` are explicit tags used only by Coverage Intelligence to compute per-narrative coverage.
- `freshness_threshold_minutes` and `expected_update_frequency_minutes` are distinct: the former is the age cutoff for a single Evidence Object; the latter is how often the source itself is expected to publish anything at all. This second value drives source-level freshness status, not object-level freshness.

## 6. Evidence Object Model

The standardized unit that every connector must produce and every downstream intelligence module consumes indirectly via the Backward-Compatibility Adapter in Phase 1.

```json
{
  "evidence_id": "string (deterministic hash)",
  "source_id": "string",
  "source_type": "string (mirrors ingestion_type from the registry: RSS | API | MANUAL | OTHER)",
  "evidence_type": "string (one of Evidence Types; Phase 1: 'Headline' only)",
  "timestamp": "ISO 8601 datetime",
  "title": "string",
  "summary": "string | null",
  "content": "string | null",
  "url": "string | null",
  "entities": [],
  "categories": [],
  "importance": "string",
  "freshness_state": "FRESH | STALE | UNKNOWN",
  "health_state": "string (from Feed Health Engine, inherited from the fetch that produced this object)",
  "acceptance_status": "ACCEPTED | REJECTED",
  "rejection": {
    "reason": "string | null (e.g., 'duplicate', 'stale', 'malformed', 'unsupported', 'quarantine', 'failed_validation')",
    "detail": "string | null"
  },
  "metadata": {}
}
```

Evidence ID - deterministic identity:

`evidence_id` must be a deterministic hash, not a randomly generated or auto-incrementing value, so that re-ingesting or re-normalizing the same underlying evidence always produces the same identifier. Recommended construction:

```text
evidence_id = sha256(
    source_id +
    evidence_type +
    timestamp +
    normalized_title +
    url_or_link (if available)
)
```

`normalized_title` refers to a consistent normalization (case, whitespace) applied before hashing, so trivial formatting differences in a re-fetch of the same item do not produce a different ID. This determinism enables stable deduplication, deterministic replay, and historical consistency.

Design rules:

- Flexibility over completeness. Not every evidence type populates every field. `metadata` is the extension point for evidence-type-specific fields that do not warrant a top-level schema field.
- `health_state` and `freshness_state` live on the object, not beside it. This is what makes health/freshness engines evidence-type-agnostic.
- `acceptance_status` and `rejection` are first-class, permanent fields, not a separate side-table. Every Evidence Object the normalizer produces, whether ultimately accepted or rejected, is a complete, valid, persistable object. Rejection is a status on the object, not a reason the object never existed.
- One Evidence Object exists per discrete unit of evidence.
- Backward-compatible with existing headline data. A headline ingested under the current architecture maps cleanly onto this schema (`evidence_type = "Headline"`, `content` typically null, `summary` populated).

## 7. Evidence Types

A registrable, extensible enumeration, defined in the registry's `evidence_types` array, not a fixed compiled list.

Phase 1 scope: only `Headline` is implemented and connected. The remaining types below are registered as known future types in the architecture but have no active connector in Phase 1.

| Evidence Type | Description | Phase |
|---|---|---|
| Headline | Standard news headline (current RSS ingestion) | Phase 1 - active |
| Press Release | Company or institutional press release | Deferred |
| SEC Filing | Regulatory filings (10-K, 10-Q, 8-K, etc.) | Deferred |
| Earnings Transcript | Full or partial earnings call transcripts | Deferred |
| Conference Call | Non-earnings corporate or institutional calls | Deferred |
| Economic Release | Scheduled economic data releases (CPI, NFP, etc.) | Deferred |
| Government Publication | Fed, Treasury, or other government agency publications | Deferred |
| Research Paper | Academic or institutional research | Deferred |
| AI Benchmark Result | Structured AI model benchmark data | Deferred |
| Corporate Guidance | Forward guidance statements from companies | Deferred |
| Regulatory Announcement | Non-filing regulatory actions/announcements | Deferred |
| Historical Archive Entry | Reconstructed evidence from Historical Intelligence replay | Deferred |
| Alternative Dataset | Non-traditional structured data sources | Deferred |

Extensibility rule: this table is registry-level configuration. Adding a new evidence type in a future phase requires: registering the type name in `config/source_registry.json`, building a connector that normalizes into the standard Evidence Object shape for that type, and optionally defining type-specific `metadata` conventions for admin display. It requires zero changes to Feed Health, Freshness Validation, Coverage Intelligence, Evidence Contribution Tracking, Source Confidence, or any narrative intelligence module. This capability is architected in Phase 1 but intentionally not exercised until a later phase.

## 8. Evidence Normalization Layer

The permanent architectural boundary between raw ingestion and narrative analysis.

Position in the pipeline:

```text
Raw Source -> Connector -> Evidence Normalizer -> Standardized Evidence Object (incl. deterministic evidence_id)
           -> Backward-Compatibility Adapter -> existing headline-list interface
           -> Narrative Intelligence -> Narrative Brief -> Dashboard
```

Responsibilities:

- Each Connector (RSS only in Phase 1) is source-format-aware but produces only raw, connector-native structures. It does not decide health, freshness, or narrative relevance.
- The Evidence Normalizer is the single choke point that transforms any connector's raw output into a valid Evidence Object, computing the deterministic `evidence_id`, and stamping `source_id`, `source_type`, `evidence_type`, and initial `metadata`. It does not yet know `health_state`, object-level `freshness_state`, or `acceptance_status`. Those are stamped by the Feed Health Engine, Freshness Validation Engine, and acceptance filtering immediately downstream, still before the object reaches narrative logic.
- The Backward-Compatibility Adapter is a thin, explicit translation step immediately after acceptance filtering: it takes the set of `ACCEPTED` Evidence Objects for the run and converts them into the exact headline-list shape existing downstream modules already consume. This adapter is what allows SIP to ship in Phase 1 with zero modification to any existing intelligence module. `REJECTED` Evidence Objects never reach the adapter or narrative logic; they remain visible only in persisted diagnostics.
- No downstream intelligence module may depend on RSS-specific or any other source-specific field. In Phase 1 this is enforced structurally by the adapter boundary; in later phases, as modules migrate to consume Evidence Objects directly, the same rule holds.
- New connectors never require normalizer rewrites for existing types. A new connector for an existing evidence type reuses the existing normalization path for that type. A connector for a genuinely new evidence type requires a new, additive normalization mapping, not a change to existing mappings.

## 9. Implementation Scope - Phase 1 Boundaries

Phase 1 supports only the current headline-based ingestion pipeline (RSS). The complete Evidence Object architecture, registry, normalizer, deterministic IDs, health engine, freshness model, contribution tracking, coverage intelligence, confidence model, adapter, persistence, and dashboards are built and fully proven using the existing headline sources only.

Explicitly deferred to future phases:

- SEC filings
- Earnings transcripts
- Federal Reserve publications
- Government releases
- Historical datasets / Historical Intelligence connectors
- Alternative data
- AI benchmark ingestion

Rationale: the objective of Phase 1 is to prove the complete Evidence Object architecture end-to-end against a single, well-understood evidence type before expanding connector types. Every engine in this document is designed to be evidence-type-agnostic, but that design is only trustworthy once it has been exercised against real production data. Phase 1 is that proof. Expanding to additional evidence types is real, valuable, and anticipated work, but it is out of scope for this handoff and belongs to a separately scoped future implementation pass.

Every schema field that references evidence types (`evidence_type`, `supported_evidence_types`, `evidence_types` registry array, `by_evidence_type` breakdowns) is fully specified and implemented in Phase 1, populated correctly with the single value `Headline`: the architecture is complete; the connector roster is intentionally minimal.

## 10. Source Categories

Fixed, extensible enumeration, registered in the registry's `categories` array, independent of evidence type.

| Category | Responsibility |
|---|---|
| Macro | Broad macroeconomic conditions and commentary |
| Federal Reserve | Fed communications, speeches, policy signals |
| Treasury | Treasury issuance, yields, department commentary |
| Economic Data | Scheduled data releases and their reporting (CPI, NFP, PPI, etc.) |
| Inflation | Inflation-specific commentary and analysis |
| Rates | Interest rate markets and commentary |
| Energy | Energy markets, supply/demand, policy |
| Commodities | Broad commodity markets |
| AI | AI industry, product, and research narrative |
| Technology | Broader tech sector narrative |
| Companies | Company-specific news |
| Earnings | Earnings reports and reactions |
| SEC | Regulatory filings and enforcement |
| Geopolitics | Geopolitical events with market relevance |
| Market Structure | Exchange, clearing, market-mechanics news |
| ETFs | ETF flows, launches, structural news |
| Volatility | Vol markets and vol-specific commentary |
| Credit | Credit markets, spreads, corporate debt |
| General Business | Broad business news not captured by the above |

Extensibility rule: new categories are added via `config/source_registry.json` edits; no downstream module hardcodes the category list. Coverage Intelligence and dashboards must read the live category set from the registry.

## 11. Source Priority Tiers

| Tier | Definition | Role |
|---|---|---|
| Tier 1 | Core narrative sources: primary, high-reliability, high-relevance evidence producers expected to be central to daily narrative detection | Primary evidence for dominant/leading narratives; absence of Tier 1 coverage on a topic is itself a meaningful, surfaced signal |
| Tier 2 | Specialist sources: narrower scope, high relevance within their category, but not broad enough to anchor a dominant narrative alone | Supporting/corroborating evidence; strengthens coverage ratings within their category |
| Tier 3 | Context sources: general business/background sources providing breadth and secondary confirmation | Contextual texture only; contributes to coverage diversity metrics, not narrative anchoring |

Constraint on use: tier must influence narrative scoring only through explainable, inspectable mechanisms already surfaced by SIP, never an invisible multiplier baked into scoring math without a corresponding, human-readable diagnostic explaining its effect.

## 12. Feed Health Engine

A deterministic state machine evaluated per source, per ingestion attempt, and stamped onto every Evidence Object that fetch produces via the `health_state` field.

| State | Meaning |
|---|---|
| Healthy | Fetched successfully, content within expected cadence, no anomalies |
| Fresh | Fetched successfully, new content since last successful fetch, within freshness threshold |
| Partial | Fetched successfully but with partial/incomplete content |
| Stale | Fetched successfully but returned content is older than `freshness_threshold_minutes` |
| Offline | Fetch failed: no response / connection failure |
| Redirected | Fetch resulted in an unexpected redirect (possible URL/endpoint drift, needs registry review) |
| Parse Error | Fetch succeeded but content could not be normalized into a valid Evidence Object |
| Rate Limited | Fetch rejected due to rate limiting by the source |
| Blocked | Fetch rejected due to access denial (e.g., 403, geo-block, auth failure) |
| Empty | Fetch succeeded but returned zero Evidence Objects |
| Unknown | State could not be determined by any defined rule; explicit "we don't know" state, never silently defaulted to Healthy |

Every state carries:

```json
{
  "state": "string (one of the above)",
  "reason": "string (specific, e.g., 'HTTP 429 received')",
  "severity": "INFO | WARNING | CRITICAL",
  "recommended_action": "string"
}
```

Severity mapping: `INFO` = Healthy, Fresh. `WARNING` = Partial, Stale, Redirected, Empty. `CRITICAL` = Offline, Parse Error, Rate Limited, Blocked, Unknown.

Rule: health state is computed independently of freshness validation at the fetch/normalization level. This is distinct from, and must never be conflated with, source-level freshness status. Health describes whether the fetch and normalization mechanics worked; freshness, both object-level and source-level, describes recency.

## 13. Freshness Validation Engine

Freshness is split into two independent, never-conflated concepts: what a single piece of evidence looks like, and what a provider's overall behavior looks like.

### 13.1 Evidence Object Freshness (`freshness_state`)

Describes a single Evidence Object's age at the moment it was ingested.

States: `FRESH`, `STALE`, `UNKNOWN`.

- `FRESH`: object age <= `freshness_threshold_minutes` for its source.
- `STALE`: object age > `freshness_threshold_minutes`.
- `UNKNOWN`: object timestamp could not be reliably determined (used sparingly, and always investigated; never a default).

### 13.2 Source Freshness Status

Describes the overall behavior of a provider across a run and across recent history. This is distinct from any single object's age.

States: `FRESH`, `STALE`, `QUIET`, `QUARANTINED`, `UNKNOWN`.

- `FRESH`: source has produced at least one `FRESH` Evidence Object within its `expected_update_frequency_minutes`.
- `STALE`: source is reachable and healthy but its most recent evidence exceeds the freshness threshold.
- `QUIET`: source has produced no new evidence at all (not even stale evidence) for one or more consecutive runs, but has not yet crossed the expiration threshold that triggers quarantine.
- `QUARANTINED`: source has exceeded its expiration threshold (a configurable multiple of `expected_update_frequency_minutes`, default 3x consecutive runs with no fresh evidence) and is excluded from ingestion for narrative scoring purposes until it produces fresh evidence again or is manually reviewed.
- `UNKNOWN`: source freshness could not be determined this run (e.g., the source itself was never successfully reached to establish a baseline).

Why these must never be conflated: an individual Evidence Object can be `STALE` while its source is `FRESH` overall (an old item mixed into an otherwise-current feed); conversely a source can be `QUIET` while every object it has ever produced remains individually valid. Object freshness is a property of content; source freshness is a property of provider behavior over time.

Behavior rules:

1. Reject stale evidence at the object level. Individual Evidence Objects with `freshness_state = STALE` are excluded from scoring input (`acceptance_status = REJECTED`, `rejection.reason = "stale"`), but this alone does not change the source's freshness status.
2. Quarantine at the source level only. Quarantine is a status flag, not a deletion. The source remains in the registry and resumes automatically once it produces fresh evidence, or can be manually re-enabled by an admin.
3. Continue operating on partial source failure. Loss or quarantine of any subset of sources must never halt a run.
4. Never silently score outdated evidence. Any Evidence Object used in narrative scoring must have `freshness_state = FRESH` and `acceptance_status = ACCEPTED`; rejection is always logged, never a silent drop.

## 14. Coverage Intelligence

Aggregates health plus freshness plus contribution data into a per-narrative and per-group coverage rating for the run, using threshold definitions sourced from `config/source_registry.json`'s `coverage_thresholds` section, never a hardcoded formula inside the engine itself.

Coverage rating scale: `Excellent`, `Good`, `Moderate`, `Weak`, `None`.

Computed deterministically from:

- Source diversity: count of distinct sources with `Healthy`/`Fresh` health state and `FRESH` source freshness status, tagged as relevant to the narrative/group, weighted by tier presence per the registry's `coverage_thresholds`.
- Evidence-type diversity: architected, dormant in Phase 1 since only `Headline` exists. A narrative corroborated by multiple evidence types can be rated more robustly covered once additional types are connected in a future phase; this factor has no effect while only one evidence type is active.
- Freshness: proportion of contributing `ACCEPTED` Evidence Objects with `freshness_state = FRESH`.
- Successful ingestion: proportion of tagged sources with `FRESH`/`STALE` (not `QUARANTINED`/`UNKNOWN`) source freshness status this run.
- Narrative relevance: proportion of `ACCEPTED` Evidence Objects from tagged sources actually matched to the narrative/group by existing unchanged Narrative Detection/Taxonomy logic.

Rating thresholds live in the registry, not in code, and are documented, version-controlled, and reviewable independent of code changes.

## 15. Evidence Contribution Tracking

For every run, per source, MNE records both accepted and rejected evidence. Nothing is silently discarded.

```json
{
  "source_id": "string",
  "run_timestamp_utc": "ISO 8601 datetime",
  "evidence_objects_loaded": "integer",
  "evidence_objects_accepted": "integer",
  "evidence_objects_rejected": "integer",
  "by_evidence_type": [
    { "evidence_type": "string", "loaded": "integer", "accepted": "integer", "rejected": "integer" }
  ],
  "rejection_reasons": [
    { "reason": "duplicate | stale | malformed | unsupported | quarantine | failed_validation", "count": "integer" }
  ],
  "duplicates": "integer",
  "matched_themes": ["string", "..."],
  "matched_groups": ["string", "..."],
  "contribution_to_scoring": {
    "themes_influenced": ["string", "..."],
    "groups_influenced": ["string", "..."]
  }
}
```

Accepted vs. loaded - persistence rule: SIP normalizes and persists every Evidence Object that is successfully produced by the normalizer, whether ultimately accepted or rejected. `evidence_objects_loaded` = total normalized this run. `evidence_objects_accepted` + `evidence_objects_rejected` = `evidence_objects_loaded` exactly. A discrepancy is itself a diagnosable error. Rejected objects are not deleted or omitted from persistence. They remain in the run's persisted `evidence_objects` array with `acceptance_status = REJECTED` and a populated `rejection` field. Rejection reasons are drawn from the fixed set: `duplicate`, `stale`, `malformed`, `unsupported`, `quarantine`, `failed_validation`.

Downstream consumption rule: Narrative Intelligence consumes only `ACCEPTED` Evidence Objects, delivered via the Backward-Compatibility Adapter in Phase 1. Rejected objects exist purely for diagnostic/audit purposes and never enter the adapter or any scoring path.

Backward compatibility: in Phase 1's single-evidence-type reality, `by_evidence_type` contains one entry (`Headline`). This generalization introduces no numeric or behavioral change versus a hypothetical headline-only tracking mechanism. It simply expresses the same counts in a type-aware shape ready for later phases.

## 16. Source Confidence Model

A single, explainable, per-run signal: "How much should MNE trust today's evidence?" This is a data-quality measure only, not market confidence, computed using rules sourced from `config/source_registry.json`'s `confidence_rules` section.

Output scale: `Excellent`, `High`, `Moderate`, `Low`, `Poor`.

Deterministic inputs:

- Feed health distribution across enabled sources.
- Object-level freshness proportion among accepted evidence.
- Source-level freshness status distribution (`FRESH`/`STALE`/`QUIET`/`QUARANTINED`/`UNKNOWN`). A run with many `QUIET` or `QUARANTINED` sources caps confidence.
- Coverage rating distribution across tracked narratives/groups.
- Tier 1 diversity across major categories.
- Ingestion success rate.

Computation approach: an ordered rule table, stored as `confidence_rules` in the registry, reviewable and adjustable independent of code changes. Every computed confidence value is accompanied by the specific rule/threshold that determined it.

Consumption: this is the value the Narrative Brief Engine reads when contextualizing data quality. SIP produces the signal; NBE decides how/whether to mention it, with no change to NBE's own logic required beyond consuming a new available input field.

## 17. Run JSON Extensions

Add a `source_intelligence` block to run JSON, additive only. No existing run JSON fields change shape or meaning.

```json
{
  "source_intelligence": {
    "run_timestamp_utc": "ISO 8601 datetime",
    "registry_version": "string",
    "evidence_objects": [
      { "...full Evidence Object as defined above, including health_state, freshness_state, acceptance_status, and rejection if applicable...": true }
    ],
    "sources": [
      {
        "source_id": "string",
        "health": { "state": "string", "reason": "string", "severity": "string", "recommended_action": "string" },
        "freshness": { "status": "FRESH | STALE | QUIET | QUARANTINED | UNKNOWN", "newest_item_age_minutes": "integer | null" },
        "contribution": { "...as defined in Evidence Contribution Tracking": true }
      }
    ],
    "coverage": ["...as defined in Coverage Intelligence"],
    "source_confidence": {
      "rating": "Excellent | High | Moderate | Low | Poor",
      "reason": "string",
      "contributing_factors": ["string", "..."]
    }
  }
}
```

Rules:

- `registry_version` pins which version of `config/source_registry.json` was active for this run.
- `evidence_objects` persists every normalized object for the run, accepted and rejected alike.
- The `sources[].freshness.status` field uses the full five-state source-level enumeration, while each object inside `evidence_objects[].freshness_state` uses the three-state object-level enumeration. These must never be interchanged.
- This block is populated for every run that reaches source ingestion, independent of whether a narrative run completes.

## 18. Total Source Failure & Persistence Separation

This section defines an explicit, permanent architectural distinction that did not previously exist in MNE:

> Source Intelligence persistence and Narrative Run persistence are separate concerns with separate guarantees.

Current MNE behavior: when zero headlines are collected, execution aborts entirely. No run output, diagnostic record, or persisted artifact is produced.

SIP-defined future behavior:

- Source Intelligence persistence (the `source_intelligence` block) is written whenever source ingestion is attempted, regardless of outcome, including total failure (zero sources returning usable evidence). This persistence does not depend on narrative generation succeeding, or even being attempted.
- Narrative Run persistence (the existing narrative scoring/output pipeline) proceeds only when it has sufficient accepted evidence to do meaningful work, per whatever threshold existing narrative logic already applies. If that threshold is not met, the narrative run may be skipped, but this is now a distinct, explicitly named outcome, not a silent total abort.
- When a narrative run is skipped due to total or near-total source failure, MNE must still persist the full `source_intelligence` block (all sources' health/freshness states, all Evidence Objects including whatever few were produced, and a `source_confidence.rating` of `Poor`) plus an explicit marker such as `narrative_run_status: "skipped_insufficient_evidence"`.
- This guarantees that even on a day where MNE cannot produce a narrative read at all, there is a complete, honest, persisted record of why.

Boundary with existing behavior: this section changes when and what gets persisted on total failure. It does not change the threshold logic existing narrative modules use to decide whether they have enough input to run, and it does not change narrative scoring, taxonomy, or any downstream module's internal behavior.

## 19. Historical Compatibility

SIP must support two architecturally separate ingestion concepts that share the Evidence Normalization Layer while remaining separate everywhere else:

| | Live Intelligence | Historical Intelligence |
|---|---|---|
| Purpose | Understand today's narratives | Reconstruct historical narratives |
| Phase 1 status | Active (Headline evidence type, RSS connectors) | Deferred - not built in Phase 1 |
| Data source | Live feed fetches, evaluated in real time | Backfill/replay of previously captured or archival data |
| Evidence representation | Standardized Evidence Objects via live connectors + normalizer | Standardized Evidence Objects via historical/replay connectors + the same normalizer, once built |
| Registry version awareness | Uses current `registry_version` | Must reference the `registry_version` active at the historical date, not today's registry |
| Contamination rule | N/A | Must never write into, or be scored alongside, live run/snapshot data for the current date; namespaced/stored separately |

What is architected to be shared, once Historical Intelligence is built in a future phase: the Evidence Object schema, including deterministic `evidence_id` construction; the Evidence Normalization Layer; the Feed Health state enumeration; and the general shape of Evidence Contribution Tracking.

What must never be shared: the live run pipeline's storage path, or any location that live daily snapshots read from.

This section establishes the boundary and the shared-schema design, not the implementation. Historical Intelligence connectors are explicitly out of scope for Phase 1.

## 20. Dashboard Requirements (User-Facing)

Deliberately minimal:

- A single, clean indicator near the top of the Overview page: label "Source Confidence" or "Today's Intelligence Quality", value from the five-band scale.
- Optional one-line `reason` shown on hover/tap: plain language, no field names, no counts, no source or evidence-type lists.
- If a day's narrative run was skipped due to total source failure, the dashboard must show a clear, calm, plain-language notice (e.g., "Today's narrative read could not be generated due to a data availability issue - source diagnostics are available to admins") rather than a blank or broken Overview page.
- No per-source detail, no health-state enumeration, no coverage table, no evidence-type breakdown. All of that is admin-only.

## 21. Admin Dashboard Requirements

- Source Registry view: reads directly from `config/source_registry.json`; full list of registered sources with all metadata fields, plus visibility into `evidence_types`, `categories`, `coverage_thresholds`, and `confidence_rules`.
- Evidence Object browser: searchable/filterable list of Evidence Objects for a given run, filterable by `evidence_type`, `source_id`, `health_state`, `freshness_state`, and `acceptance_status`, including the ability to view rejected objects alongside their `rejection.reason`/`rejection.detail`.
- Source Health view: current and historical health states per source.
- Freshness view: per-source source-level freshness status, newest-evidence age, and quiet/quarantine status, clearly distinguished from any individual object's freshness state.
- Coverage view: full per-narrative/per-group coverage table, referencing the active `coverage_thresholds` from the registry.
- Contribution view: full per-source contribution record, including accepted-vs-rejected breakdowns and rejection reason counts.
- Diagnostics / failure reasons: HTTP/API metadata, redirect chains, parse/normalization error details.
- Total-failure / skipped-run log: a dedicated view listing any dates where the narrative run was skipped, with the associated `source_intelligence` diagnostics for that date fully browsable despite no narrative output existing for that date.
- Duplicates and rejected evidence: browsable list, not just counts.
- Theme/group contribution drill-down.

All admin views read from the persisted `source_intelligence` run JSON block and the registry file. There is no separate live-only diagnostic path that diverges from what is persisted.

## 22. Data Persistence

- All SIP data (registry, Evidence Objects accepted and rejected, health, freshness, contribution, coverage, confidence) follows MNE's existing persistence conventions: run-level JSON in the existing external Google Drive path structure; no new storage system introduced for run data.
- The Source Registry itself lives at `config/source_registry.json`, version-controlled alongside application code (not in the external run-data path), and is referenced per-run by `registry_version`. This keeps authoritative configuration in source control while run-level facts remain in the existing external run-data location.
- Per-run `source_intelligence` blocks, including the full `evidence_objects` array (accepted and rejected), are persisted every time source ingestion is attempted. This persistence is independent of whether the narrative run itself completes.
- Historical Intelligence data, once built, is persisted in a namespace/path structurally separate from live daily runs. This is a future-phase concern, but the separation requirement is a hard architectural constraint established now.

## 23. Documentation & Permanent References

This architecture is formalized as a permanent, standalone project document:

`docs/source_intelligence_platform.md`

This document takes its place alongside MNE's other permanent architecture references:

- `ARCHITECTURE.md`
- `docs/roadmap.md`
- `docs/project_status.md`
- `docs/future_concepts.md`
- `docs/narrative_style_guide.md`

`docs/source_intelligence_platform.md` contains the durable architectural content of this handoff (Evidence Object schema, registry structure, engine responsibilities, persistence rules, phase boundaries) so that future contributors, human or AI, can understand SIP's design without needing to locate the original handoff conversation. As SIP evolves across phases, this document is the canonical place that evolution is recorded, cross-referenced from `docs/roadmap.md` and `docs/future_concepts.md`.

## 24. Verification Scenarios

| # | Scenario | Expected Behavior |
|---|---|---|
| 1 | All registered sources healthy, fresh, fully diverse across tiers/categories, Phase 1 (Headline only) | `source_confidence.rating = Excellent`; coverage ratings reflect actual diversity; `source_intelligence` block fully populated; every `evidence_objects[]` entry has `evidence_type = "Headline"` and `acceptance_status = "ACCEPTED"` |
| 2 | The same headline is fetched twice across two connector passes within one run (e.g., feed overlap) | Both normalize to the same `evidence_id` (deterministic hash); the second is marked `acceptance_status = REJECTED`, `rejection.reason = "duplicate"`, and both remain persisted in `evidence_objects[]` |
| 3 | A source returns content, but the newest item is 10 days old against a 60-minute freshness threshold | Object-level: that item's `freshness_state = STALE`, `acceptance_status = REJECTED`, `rejection.reason = "stale"`. Source-level: freshness status is independently evaluated |
| 4 | A source produces no new evidence at all for one run, but has not yet crossed the expiration threshold | Source-level freshness status = `QUIET`; source is not quarantined yet; still included in ingestion |
| 5 | A source produces no fresh evidence for 3 consecutive runs (default expiration threshold) | Source-level freshness status transitions to `QUARANTINED`; excluded from ingestion for scoring; remains visible in registry; auto-resumes if fresh evidence later detected |
| 6 | A malformed feed item fails schema validation during normalization | Evidence Object is still produced and persisted with `acceptance_status = REJECTED`, `rejection.reason = "malformed"`; not silently dropped |
| 7 | Every enabled source fails simultaneously (total outage) | `source_intelligence` block is still fully persisted (`source_confidence.rating = Poor`, all sources' health/freshness states recorded, `evidence_objects` array present even if near-empty); the narrative run is explicitly skipped with `narrative_run_status: "skipped_insufficient_evidence"` |
| 8 | Admin reviews a date where the narrative run was skipped per scenario 7 | Admin dashboard's total-failure log surfaces the date with full source diagnostics browsable, despite no narrative brief/scoring output existing for that date |
| 9 | Historical Intelligence connector work is attempted | Rejected as out of scope; confirms Phase 1 boundary is respected; no historical connector exists to test in this phase |
| 10 | Admin inspects the registry via the Source Registry view | Values shown match `config/source_registry.json` exactly, including `coverage_thresholds` and `confidence_rules` sections |
| 11 | User views the standard dashboard on a day with `source_confidence.rating = Low` | Dashboard shows only the high-level indicator plus a one-line plain-language reason; no per-source or per-evidence-type detail is exposed |

## 25. Non-Goals

- No change to narrative scoring algorithms, theme taxonomy, narrative groups, Regime Alignment, Narrative Brief logic, or any other existing downstream intelligence module. This is a hard constraint on every refinement in this document, not just a general aspiration. The Backward-Compatibility Adapter exists specifically to guarantee it structurally.
- No machine learning anywhere in normalization, health, freshness, coverage, or confidence computation.
- No opaque weighting. Tier, coverage thresholds, and confidence rules are always registry-visible configuration, never hidden in engine code.
- No LLM requirement anywhere in SIP, including within the Evidence Normalizer.
- No narrative summary generation. SIP produces structured diagnostic data, normalized Evidence Objects, and confidence ratings only.
- No live registry editing UI in this phase. Registry changes are controlled configuration updates to `config/source_registry.json`, not an in-app CRUD feature.
- No implementation of non-headline connectors in Phase 1. SEC filings, earnings transcripts, Fed publications, government releases, historical datasets, alternative data, and AI benchmark ingestion are all explicitly deferred.
- No Historical Intelligence engine implementation in Phase 1. This document defines the compatibility boundary and shared-schema design only.
- No change to the existing narrative-run-sufficiency threshold logic. Total-failure persistence changes what gets persisted and how the skip is recorded, not the criteria existing modules use to decide whether they have enough evidence to run.

## 26. Recommended Build Order

1. `config/source_registry.json` schema and initial population: establish the file, including `registry_version`, `sources` migrated from current hardcoded lists (`supported_evidence_types: ["Headline"]` for all), `evidence_types` (full table, only `Headline` active), `categories`, `coverage_thresholds`, and `confidence_rules`.
2. Evidence Object schema, including deterministic `evidence_id`: finalize and lock the schema, implement and unit-test the hashing scheme in isolation before wiring it into live ingestion.
3. Evidence Normalization Layer for the existing RSS connector: retrofit current RSS ingestion to route through a normalizer producing valid, correctly-hashed Evidence Objects.
4. Feed Health Engine: implement the state machine, stamping `health_state`.
5. Freshness Validation Engine, both axes: implement object-level `freshness_state` and source-level freshness status as genuinely independent computations.
6. Evidence Contribution Tracking with full accepted/rejected persistence: wire per-run accounting, confirming every normalized object, accepted or rejected, is retained with correct `rejection` metadata.
7. Backward-Compatibility Adapter: build the accepted-evidence-to-headline-list translation and confirm existing Narrative Detection/Taxonomy/Scoring behavior is byte-for-byte unchanged when fed adapter output versus its current direct-headline input.
8. Run JSON extension, including total-failure persistence: add the `source_intelligence` block and implement the persistence-separation logic.
9. Coverage Intelligence: build the per-narrative/per-group aggregation, consuming `coverage_thresholds` from the registry rather than hardcoded values.
10. Source Confidence Model: implement once all prior engines are stable, consuming `confidence_rules` from the registry.
11. Daily snapshot extension: persist the full block, confirming behavior matches skipped-run dates.
12. Admin dashboard: build the full diagnostic surface, including the Evidence Object browser with acceptance/rejection filtering and the total-failure/skipped-run log.
13. User dashboard indicator, including the skipped-run notice: add the minimal high-level display last among UI work.
14. `docs/source_intelligence_platform.md`: write the permanent architecture document once the implementation is stable enough that the document reflects built reality, not just plan; cross-link from `docs/roadmap.md` and `docs/future_concepts.md`.
15. Full verification suite: run all eleven verification scenarios end-to-end; confirm zero behavioral change in any existing intelligence module output.
16. Stop. Additional evidence-type connectors, Historical Intelligence, and the broader Evidence Intelligence Platform vision are explicitly deferred to future, separately scoped implementation phases.

## 27. Future Vision

The Source Intelligence Platform, as specified in this document, is the first phase of what will become a broader Evidence Intelligence Platform (EIP). This is an architectural evolution, not a rewrite: every engine and schema defined here is designed to operate identically whether MNE is ingesting one evidence type or a dozen. Phase 1 simply proves that design against a single, well-understood connector before expanding.

Future phases, each separately scoped, are expected to add: non-headline connectors (SEC filings, earnings transcripts, Fed/government publications, alternative datasets, AI benchmark results); Historical Intelligence (built on the shared normalizer and deterministic `evidence_id` scheme established here); and downstream systems such as a Historical Narrative Engine, Narrative Timeline, Narrative Accountability, Company Promise Tracker, Future Scenario Analysis, and Competitive Intelligence, all consuming standardized Evidence Objects without requiring modification to Narrative Intelligence itself.

The guarantee this document establishes for all of that future work is structural: every new capability is a new connector plus, at most, a new evidence type registered in `config/source_registry.json`, never a change to how Narrative Intelligence, the Narrative Brief Engine, or the dashboards consume evidence. `docs/source_intelligence_platform.md` is where this evolution is tracked as it happens.
