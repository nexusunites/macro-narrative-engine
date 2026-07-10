# The Macro Narrative Engine
## Product Backlog

*This is the master implementation backlog for MNE, effective as of Platform Foundation v1.0. It is not the Product Vision, not an architecture document, and not a roadmap with dates — it is the single source of truth for what should be built next, organized by Epic, with every item scoped to reflect concrete user or platform value. Every future sprint handoff should originate from an item in this document.*

*This document is intentionally living. It should be updated whenever implementation meaningfully changes the state of the product. Status should always reflect verified implementation rather than planned work.*

*Status reflects what is confirmed operational in production as of this writing, based on direct inspection of live run output (`platform_observability`, `source_intelligence`, `narrative_brief`, `event_lifecycle`, and related blocks) and confirmed Codex implementation reports — not merely what has an architecture document.*

---

## Completed Foundations

The following major platform capabilities are considered complete as part of **Platform Foundation v1.0**. Future contributors should treat these as foundational — generally to be extended, not redesigned:

- **Source Intelligence Platform (SIP)** — Evidence Objects with deterministic IDs, the Source Registry (`config/source_registry.json`), Feed Health, and Freshness Validation, all operational in production.
- **Source Confidence Model** — deterministic evidence-collection confidence persisted under `source_intelligence.source_confidence`, with Admin visibility.
- **Source Trust Layer** — ENI Phase 1 source expansion, ENI Phase 2 network health measurement, Source Confidence, and Source Reliability / Quarantine Tracking are implemented; reliability tracking is recommendation-only with no automatic source status changes.
- **Coverage Intelligence (EQE)** — per-narrative evidence breadth, diversity, and concentration measurement, first layer of the Evidence Quality Engine.
- **Evidence Network Initiative foundations** — ENI Phase 1 source coverage repair/expansion and ENI Phase 2 network health measurement, including provider/category rollups, provider concentration, overall network status, persisted `source_intelligence.network_health`, and the Admin Evidence Network section.
- **Narrative Intelligence** — theme/group scoring, taxonomy, Narrative Leadership, Rotation, Pulse, Dynamics, Crowding, Change Summary, Regime Alignment, Breadth Confirmation, and related market/catalyst context engines.
- **Narrative Brief Engine** — deterministic, template-composed, evidence-traceable daily briefs with graceful fallback behavior.
- **Event Lifecycle Engine** — deterministic catalyst phase awareness.
- **Platform Observability (POL)** — per-stage pipeline telemetry, run metadata, and engine version reporting.
- **Configuration Portability** — environment-driven, cross-platform data directory resolution with no import-time filesystem side effects.
- **Evidence Diagnostics** — accepted-evidence persistence (capped at 500 entries with an explicit truncation flag), the evidence funnel summary, the zero-match warning, and the healthy-but-severely-stale source flag.
- **Operations Center MVP** — render-time, admin-only operational summary using existing persisted signals, with component summaries for Configuration, Pipeline / Platform Observability, Evidence Network, Source Confidence, Source Reliability, Coverage Intelligence, and Freshness / Feed Health.
- **Dashboard Data Quality Banner / Trust Summary** — compact user-facing evidence-quality summary in the dashboard, built from existing persisted signals only, without exposing admin diagnostics or changing scoring, sources, persistence, or admin behavior.
- **Research Workspace MVP + UX Polish + Evidence Reader Panel** — `/research` selector, narrative investigation page, dashboard entry-point wiring, admin-gated observability reference, paced investigation zones, readable evidence display, neutral coverage explanation, calm event lifecycle empty state, selectable Supporting Evidence cards, headline-level Evidence Reader side panel, original article access when available, calm unavailable state for missing URLs, and admin boundary are implemented.
- **Historical Replay Foundation + Admin Console** — replay request creation, historical evidence selection with publication and knowledge-boundary cutoffs, ineligible evidence exclusion, accepted eligible evidence inclusion, deterministic theme/group replay wrapper, isolated replay persistence under configured replay storage, replay metadata, config portability, no-live-fetch replay behavior, determinism tests, cross-validation against known live run scores from the same accepted evidence, and the admin-only `/admin` replay trigger/summary console are implemented and verified.

This is a summary for orientation only — each system's canonical reference is its own architecture document in this repository.

---

## How to Read This Backlog

**Status is tracked at the Epic level**, in each Epic's "Current status" line — it describes what is verifiably built today, per the verification standard stated above. Status is deliberately not tracked per item: most unbuilt items would simply repeat "not started," and Epic-level status plus each item's Dependencies column together tell the full readiness story without that noise.

**Status vocabulary (Epic level):**
- **Implemented / Substantially Implemented** — confirmed operational in production output or by an explicit Codex implementation report.
- **In Progress** — implementation has begun or was partially confirmed.
- **Architecture complete, not started** — a canonical architecture document exists; no implementation has begun.
- **Not started** — neither implementation nor (in some cases) detailed architecture exists yet.

**Priority is tracked at both levels.** Each Epic carries an epic-level Priority describing how urgently the Epic as a whole deserves attention right now; each Backlog Item additionally carries its own Priority (`Critical` / `High` / `Medium` / `Low` / `Future`), since a single Epic can contain both work that's ready today and work that's correctly deferred.

**One clarification on how Priority relates to sequencing:** item-level Priority describes the *importance/severity* of the item itself; the Recommended Implementation Order at the end of this document describes *sequencing*, which weighs importance against value-per-effort. These are different axes — an item can be genuinely Critical in severity (e.g., a degraded data source) while still being correctly sequenced behind work that unlocks more user value per unit of effort. When the two appear to disagree, the Implementation Order governs what gets built next; item Priority governs how seriously the item is treated when its turn comes.

---

## Epic 1 — Research Workspace

**Goal:** Give users an actual place to investigate a narrative in depth, using intelligence MNE already produces.

**Why it matters:** This is currently MNE's single biggest gap between backend capability and user-visible value. SIP, the Evidence Quality Engine, the Event Lifecycle Engine, and the Narrative Brief Engine are all fully operational — but none of that reaches a user beyond the flat dashboard. A working Research Workspace converts already-built intelligence into a usable product for the first time.

**Current status:** **Implemented.** Research Workspace MVP, UX polish, and Evidence Reader Panel are confirmed implemented. The `/research` selector is purpose-led and card-based; the investigation page is organized into four paced zones (Snapshot, Explanation, Evidence, Research Entry Points); Supporting Evidence is more readable and selectable; selected evidence opens in a side panel with deterministic, field-bound headline-level explanation; original article access remains available when a URL exists; missing URLs show a calm unavailable state; coverage explanation uses neutral breadth-not-quality language; Event Lifecycle empty state is calm; dashboard links use investigation-oriented wording; and admin-only diagnostics remain gated. Full article ingestion and full article summarization are not implemented.

**Dependencies:** None remaining. Every engine this Epic consumes (SIP, Narrative Intelligence, EQE, Event Lifecycle, Narrative Brief) is already implemented and confirmed live.

**Epic priority:** **Critical**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Narrative Investigation MVP | **Implemented.** Single-narrative investigation page with Snapshot, Explanation, Evidence, and Research Entry Points zones. | First real place to answer "why" and "what evidence supports it" | Done | Medium | Complete |
| Dashboard entry-point wiring | **Implemented.** Dashboard narrative links now route users into the investigation experience with investigation-oriented wording. | Makes the MVP reachable at all | Done | Low | Complete |
| Admin-gated Observability reference | **Implemented.** Admin-only diagnostics and observability references remain gated from the user-facing research experience. | Faster admin diagnosis without leaving the investigation | Done | Low | Complete |
| Research Workspace UX polish | **Implemented.** Purpose-led card selector, paced investigation zones, readable Supporting Evidence, neutral coverage language, calm Event Lifecycle empty state, and verified admin boundary. | Makes the research experience legible, calm, and trust-preserving | Done | Medium | Complete |
| Evidence Reader Panel | **Implemented.** Supporting Evidence cards are selectable and open a side panel with deterministic headline-level explanation from persisted evidence fields only; original article links remain available when URLs exist, missing URLs show a calm unavailable state, full article text limitations are stated, and standard user view does not expose raw `evidence_id`, `source_id`, or admin diagnostics. No article fetching, scraping, paywall bypassing, LLM calls, or AI-generated article summaries were added. | Lets users inspect why an evidence item matters without implying full article access or AI summarization | Done | Medium | Complete |
| Narrative Comparison mode | Side-by-side investigation of two narratives, periods, or regimes | Supports "how does this compare" questions | Narrative Investigation MVP | Medium | Future |
| Company Analysis mode | Company-centric narrative investigation | Supports "which companies benefit" questions | Company Memory (not built) | High | Future |
| Catalyst Analysis standalone mode | Dedicated catalyst/event investigation surface | Deeper event-specific research | Narrative Investigation MVP | Medium | Future |
| Full article ingestion | Future, not implemented. Store and process full article text only if a deliberately scoped ingestion strategy is approved later. | Could support deeper article-level research while preserving source and rights boundaries | SIP non-headline/full-text ingestion design | High | Future |
| Research Session persistence | Concrete session mechanics (currently only conceptually specified) | Continuity across an investigation, foundation for saved work | Narrative Investigation MVP | Medium | Future |
| Saved investigations, watchlists, annotations, shared workspaces, trade journals | Reserved-compatibility extensions named in the RWA architecture | Long-term personalization and collaboration | Research Session persistence | High | Future |

---

## Epic 2 — Historical Replay

**Goal:** Let MNE reconstruct what it would have concluded on any past date, using only evidence that existed at the time.

**Why it matters:** This is the foundation everything in Narrative Memory depends on, and it's what eventually lets the Research Workspace answer "how did we get here," not just "what's happening now."

**Current status:** **Historical Replay Foundation implemented and verified; Historical Replay Admin Console implemented.** Core replay request creation, evidence cutoff using publication and knowledge-boundary rules, rejected/stale/duplicate/unknown evidence exclusion, accepted eligible evidence inclusion, isolated replay persistence under configured replay storage, replay metadata (`cutoff`, evidence selection rule, and `future_evidence_excluded`), determinism verification, no-live-RSS-fetch replay behavior, config portability for replay storage, and cross-validation against known live run scores from the same accepted evidence are implemented. Admin can trigger deterministic replays from `/admin`, inspect compact replay summaries, view warnings, artifact filename/path, and recent replay history; replay artifacts remain isolated from live results and route handling does not expose arbitrary paths. User-facing replay UI is not implemented. Research Workspace historical mode is not implemented. Historical evidence connectors / archival backfill are not implemented.

**Dependencies:** The Evidence Object schema and deterministic `evidence_id` scheme (SIP, done) are the direct technical foundation. Historical evidence connectors (archival ingestion) are a separate, not-yet-built SIP-adjacent capability this Epic depends on for anything beyond the current live data window.

**Epic priority:** **High** (foundational, but sequenced deliberately after Research Workspace has a working live-data experience to extend)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Replay request model / core foundation | **Implemented.** `mne/historical_replay.py` provides replay request creation and the callable replay foundation. | Establishes the callable foundation for date-bound replay | Done | Medium | Complete |
| Historical Evidence Pipeline | **Foundation implemented.** Replay request/cutoff/evidence selection enforces publication and knowledge-boundary cutoff rules; excludes rejected, stale, duplicate, and unknown evidence; includes accepted eligible persisted evidence; and avoids live RSS fetching during replay. Historical evidence connectors and archival backfill are not implemented. | The core integrity guarantee everything else depends on | SIP evidence model (done) | High | Complete |
| Replay Engine orchestration | **Foundation implemented.** Replay wraps the existing deterministic theme/group analysis against bounded historical evidence and is cross-validated against known live run scores from the same accepted evidence. Full historical taxonomy replay remains future. | Produces trustworthy historical reconstructions | Historical Evidence Pipeline | High | Complete |
| Historical Run Object persistence | **Foundation implemented.** Replay output persists under configured replay storage, isolated from live results, with replay metadata including cutoff, evidence selection rule, and `future_evidence_excluded`. Config portability for replay storage is implemented. Versioned replay retention remains future. | Auditable, reproducible historical records | Replay Engine orchestration | Medium | Complete |
| Replay determinism verification suite | **Foundation implemented.** Determinism tests are covered in `tests/test_historical_replay.py`, alongside no-live-fetch behavior and live-score cross-validation coverage. | Trust in reconstructed history | Historical Run Object persistence | Medium | Complete |
| Historical/evidence confidence split | Future, not implemented. `source_confidence` vs. `evidence_confidence` per historical run | Honest signal about reconstruction completeness | Replay Engine orchestration | Medium | Future |
| Admin replay console | **Implemented.** `/admin` includes an admin-only Historical Replay section where admins can enter `replay_date`, trigger deterministic replay using persisted evidence only, and inspect result summary, warnings, artifact filename/path, and recent replay list. Replay-id handling is safe and does not expose arbitrary paths; user dashboard and Research Workspace do not expose replay controls. | Debugging and backfill support | Done | Medium | Complete |
| Historical Replay UI | Future, not implemented. Full user-facing replay UI and date picker outside admin tooling | Makes replay accessible outside CLI/helper paths | Historical Replay foundation and admin console (done) | Medium | Future |
| Historical Context integration into Research Workspace | Future, not implemented. Date selection and reconstructed views inside the workspace | Turns replay into something users actually touch | Research Workspace MVP (Epic 1), Historical Run Object persistence | Medium | Future |
| Historical evidence connectors | Future, not implemented. Archival ingestion and historical web/data fetching needed for dates before the available evidence window | Extends replay beyond locally available persisted evidence | Historical Replay foundation (done), SIP connector expansion | High | Future |
| Historical taxonomy replay | Future, not implemented. Reconstruct analysis using taxonomy definitions appropriate to the replay date/version | Improves fidelity for older replays as taxonomy evolves | Taxonomy versioning/expansion tooling | Medium | Future |
| Versioned replay retention | Future, not implemented. Retention/versioning policy for replay outputs across engine and taxonomy versions | Supports long-run auditability and comparison | Historical Run Object persistence foundation (done) | Medium | Future |
| Historical Research Interface | Open-ended querying across accumulated historical runs | Deep, self-directed historical research | Narrative Memory (Epic 3) | High | Future |

---

## Epic 3 — Narrative Memory

**Goal:** Preserve MNE's daily understanding faithfully across time, so history remains re-examinable exactly as it was understood in the moment.

**Why it matters:** Without this, MNE's intelligence resets every day. This is what turns individual runs into an actual accumulated history.

**Current status:** Vision and architecture (NMS) complete. Zero implementation. **This Epic should not begin until Historical Replay is more mature and/or integrated as needed** — Memory preserves Intelligence outputs across time, and the implemented Historical Replay foundation is only the first step toward trustworthy, product-integrated historical reconstruction.

**Dependencies:** Historical Replay maturity and/or Research Workspace historical integration, as needed for the specific memory work.

**Epic priority:** **Deferred — hard-blocked** (correctly blocked by Epic 2, not a scoping choice)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Memory Object persistence model | Concrete schemas for Narrative/Company/Event/Economic/Technology/AI/Policy/Competitive Memory | Foundation for every timeline and history view | Historical Replay Engine core | High | Future |
| Memory Timeline read API | Sequenced access to a narrative's state over time | Powers "how has this narrative evolved" | Memory Object persistence model | Medium | Future |
| Narrative Evolution views | Emergence, dominance, displacement narrative arcs | Long-run narrative storytelling | Memory Timeline read API | Medium | Future |
| Company Memory | Company-to-narrative association history | Powers Company Analysis mode | Memory Object persistence model | High | Future |
| AI Memory / AI Benchmark History | Specialized tracking of AI-related narrative and benchmark evidence | Fast-moving AI narrative context over time | Memory Object persistence model | Medium | Future |
| Narrative Accountability chain | Promise → Expectation → Outcome → Evidence → Reality, deterministic only | Historical understanding without grading companies | Memory Object persistence model | High | Future |

---

## Epic 4 — AI Experience

**Goal:** Let AI make MNE's existing intelligence more accessible — explaining, comparing, teaching, organizing — without ever generating or altering a conclusion.

**Why it matters:** This is where MNE starts to feel conversational, but only once there's real, stable deterministic output worth explaining.

**Current status:** Zero AI implementation. Fully governed by the Intelligence Experience Architecture's AI boundary, already established as permanent doctrine. The implemented Evidence Reader Panel is deterministic/template-based and field-bound; it is not AI-generated and does not provide AI article summaries. **AI Experience should not begin until the Research Workspace has real, stable, deterministic output for AI to operate on** — this is an explicit sequencing decision already made in the RWA architecture's own build order, not a new constraint introduced here.

**Dependencies:** Research Workspace MVP (Epic 1), for something worth explaining; Historical Replay/Memory, for anything beyond current-day explanation.

**Epic priority:** **Deferred — intentionally sequenced later**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Explanation/summarization layer | AI restates existing Narrative Brief content in plainer or deeper language | Faster, more natural understanding | Research Workspace MVP | Medium | Future |
| AI article summaries | Future, not implemented. AI-generated summaries of full articles are outside the current Evidence Reader Panel, which is deterministic/template-based and limited to persisted headline-level evidence fields. | Could make article-level reading easier only if full article ingestion and AI governance are deliberately added later | Full article ingestion, AI governance | High | Future |
| Comparison assistant | AI helps contrast narratives, dates, or regimes using existing outputs | Easier cross-narrative reasoning | Research Workspace MVP, Historical Replay (for cross-date) | Medium | Future |
| Conversational Q&A | Answers questions using existing intelligence and memory | Natural-language access to MNE's understanding | Research Workspace MVP | Medium | Future |
| AI-organized investigation assistant | Suggests next steps through an investigation | Guided research | Research Workspace MVP | High | Future — requires deliberate scrutiny per the risk already flagged in the RWA architecture (organization suggestions can imply conclusions through ordering alone) |
| Voice interface | Level 1–2 conversational access | Hands-free, glanceable access | AI Experience core capabilities above | Medium | Future |

---

## Epic 5 — Intelligence Platform

**Goal:** The deterministic core that turns evidence into narrative understanding — themes, groups, leadership, regime, and everything the rest of MNE is built on.

**Why it matters:** This is MNE's actual product. Nearly all of it is already built and running.

**Current status:** **Substantially Implemented.** Confirmed live in production: theme/group scoring, taxonomy (v1.1), Narrative Leadership, Leadership Rotation, Narrative Pulse, Narrative Dynamics/Crowding, Change Summary, Regime Alignment, Breadth Confirmation, Narrative/Market Relationship, Catalyst Environment, Positioning Environment, Market Expression, Event Lifecycle Engine, the Narrative Brief Engine, and the Source Confidence Model.

**Dependencies:** None for current capability. Remaining items depend on SIP's future evidence-type expansion.

**Epic priority:** **Medium** (maintain and extend; the core is done)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Source Confidence Model | **Implemented.** SIP synthesis layer answering "Was today's evidence collected cleanly?" by combining source health, freshness, and coverage into an evidence-collection confidence state. Distinct from Network Health and from the future Network Confidence Model: Source Confidence evaluates the quality of collected evidence for the run, while Network Confidence will evaluate the resilience and adequacy of the evidence network itself. | Honest answer to "was today's evidence collected cleanly" | Done | Medium | Complete |
| Taxonomy versioning/expansion tooling | Formalized tracking of taxonomy changes across versions | Prevents confusion like the recent zero-match investigation, where taxonomy version had to be manually cross-checked | None | Medium | Medium |
| Positive-match explainability | Extend the recent zero-match diagnostics to also explain *why* a headline matched a theme | Faster trust-building and debugging | Evidence Diagnostics & Persistence Fix (done) | Low–Medium | Medium |
| Multi-evidence-type Narrative Detection | Scoring against SEC filings, transcripts, and other future evidence types | Richer, more corroborated narrative detection | SIP non-headline connectors (Epic 7) | High | Future |

---

## Epic 6 — Dashboard Experience

**Goal:** A fast, glanceable operational overview — distinct from, not a smaller version of, the Research Workspace.

**Why it matters:** The current dashboard works and degrades honestly, but a recent design review surfaced real, fixable issues — some cosmetic, one a genuine trust risk.

**Current status:** **Implemented**, with known UX debt. Dashboard Data Quality Banner / Trust Summary is implemented: the dashboard now has a calm, user-facing evidence-quality summary built from existing persisted signals, and it does not expose admin diagnostics. Remaining known UX debt includes the hero sentence composition bug, raw-filename run selector, unverified trend-label claim on the regime history chart, and historical content migration / Level 3/4 content separation.

**Dependencies:** None blocking the quick fixes. Moving Level 3/4 content out depends on the Research Workspace existing as a destination.

**Epic priority:** **High**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Fix hero sentence composition bug | Correct the malformed "market context is market confirmation is unclear..." string | Removes a visible, credibility-damaging bug | None | Low | Critical |
| Human-readable run selector | Replace raw filenames with formatted dates/times | Basic usability | None | Low | High |
| Verify/fix regime trend label logic | Confirm the "improving/worsening" claim actually reflects the chart's volatility | Prevents a misleading claim on a platform built around honest reads | None | Low–Medium | High |
| Consolidated degraded-run / data-quality banner | **Implemented.** Dashboard trust summary provides one compact, user-facing evidence-quality explanation from existing persisted signals only, without exposing admin diagnostics. | Prevents a low-data day from looking broken | Done | Medium | Complete |
| Navigation consistency | **Partially implemented.** Dashboard links into Research Workspace now use investigation-oriented wording and route to the implemented investigation experience. Broader dashboard navigation cleanup may still remain. | Removes user confusion about what's a real page | Research Workspace MVP (done) | Medium | Medium |
| Dashboard trust summary | **Implemented.** `mne/dashboard_trust_summary.py` renders the dashboard's compact trust summary without changing scoring, sources, persistence, or admin behavior. | Gives users a calm read on evidence quality without exposing internal diagnostics | Done | Low | Complete |
| Move Level 3/4 content into Research Workspace | Relocate regime history chart, leadership history table, raw score tables | Restores the dashboard's speed and focus | Research Workspace MVP (Epic 1) | Medium | Medium |

---

## Epic 7 — Data Quality & Source Intelligence

**Goal:** Make sure MNE knows the quality of its own inputs, and acts on that knowledge honestly.

**Why it matters:** This is the foundation every other Epic's trustworthiness rests on — and it's mostly done.

**Current status:** **Substantially Implemented.** Confirmed live: Evidence Objects, deterministic `evidence_id`, the Source Registry, Feed Health, Freshness Validation, Coverage Intelligence, the Source Confidence Model, Source Reliability / Quarantine Tracking, and the Evidence Diagnostics & Persistence Fix (accepted-evidence persistence, evidence funnel, zero-match warning, healthy-but-severely-stale flag). Source Confidence is persisted under `source_intelligence.source_confidence` every run and is displayed in Admin. Source Reliability / Quarantine Tracking evaluates repeated source weakness across recent persisted runs, persists `source_intelligence.source_reliability` every run, and is displayed in the Admin Source Reliability / Quarantine Tracking section. It is recommendation-only: it does not automatically disable, quarantine, enable, or otherwise change any source status. ENI Phase 1 source coverage expansion is implemented: the source registry was expanded, CNBC was restored with legitimate public-feed User-Agent behavior, WSJ was investigated and disabled after serving stale January 2025 content, Reuters and Bloomberg remain disabled, accepted evidence improved materially, provider/category diversity improved, and the registry version was updated. ENI Phase 2 network health measurement is implemented: `source_intelligence.network_health` persists provider rollups, category rollups, provider concentration, and overall `network_status` every run, with an Admin Evidence Network section available for inspection.

**Dependencies:** Remaining unbuilt items depend on existing SIP foundations, the implemented ENI network-health measurement block, or future admin/operations surfaces as noted below. Feed remediation investigation for WSJ and CNBC is complete.

**Epic priority:** **High**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| WSJ feed remediation | **Implemented as investigation completed.** `wsj-markets` was confirmed to serve stale January 2025 content and was disabled rather than treated as a healthy source. | Prevents stale evidence from silently entering the network | Done | Low–Medium | Complete |
| CNBC 403 remediation | **Implemented.** `cnbc-top-news` was restored using legitimate public-feed User-Agent behavior. | Restores a previously lost source | Done | Low–Medium | Complete |
| Provider/category network health measurement | **Implemented.** Persist provider rollups, category rollups, provider concentration, and overall `network_status` in `source_intelligence.network_health`, with admin visibility in the Evidence Network section. | Gives admins a direct read on evidence-network diversity and concentration risk | Done | Medium | Complete |
| Source Reliability / Quarantine Tracking | **Implemented.** `mne/source_reliability.py` evaluates repeated source weakness across recent persisted runs using `source_reliability_thresholds`, persists `source_intelligence.source_reliability` every run, and exposes recommendations in the Admin Source Reliability / Quarantine Tracking section. Recommendation-only: source status changes remain manual. | Gives admins a direct read on persistent source weakness without silently changing the evidence network | Done | Medium | Complete |
| Source Quarantine automation | Future, not implemented. Automatically changing source status based on reliability findings remains out of scope; source disable/quarantine/enable decisions are still manual. | Prevents a quietly-degraded source from going unnoticed indefinitely once operational controls are deliberately enabled | Source Reliability / Quarantine Tracking (done), source-status governance, Operations Center MVP (done) | Medium | Future |
| Source Confidence Model | **Implemented.** Cross-listed with Epic 5. Answers "Was today's evidence collected cleanly?" and persists under `source_intelligence.source_confidence`, with Admin visibility. Distinct from Network Health and from future Network Confidence. | Honest run-level read on evidence-collection quality | Done | Medium | Complete |
| Network Confidence Model | Future, not implemented. Design and implement the deterministic model evaluating whether the Evidence Network is currently capable of supporting reliable macro understanding — per the ENI architecture. Distinct from Source Confidence and from the implemented network-health measurement block: Source Confidence measures the *quality of collected evidence* (health, freshness, ingestion mechanics); Network Confidence will synthesize the *resilience and adequacy of the evidence network itself* into a confidence model. A day can score high on one and low on the other. | Catches the failure mode per-evidence validation cannot: clean collection from a dangerously thinned network | Evidence Network Health Measurement (done), Operations Center MVP (done), Coverage Intelligence (done) | Medium | High |
| Non-headline connectors (Phase 2) | SEC filings, transcripts, government publications, and other evidence types | Richer, more diverse evidence base | Evidence Normalization Layer (done, proven with headlines only) | High | Future |
| Historical evidence connectors | Future, not implemented. Archival ingestion needed for dates before live capture | Enables Historical Replay beyond the current live window | Historical Replay foundation (Epic 2, done); fuller replay product maturity | High | Future |
| Full Source Registry admin editing UI | In-app registry editing, replacing config-file-only edits | Faster source management | Source Registry (done) | Medium | Medium |
| Operations Center refinements | Future. The first Operations Center summary layer is implemented, but fuller operational workflows for reviewing source reliability recommendations, deciding manual source status changes, and coordinating Network Confidence follow-on work remain future scope. | Gives operators a more mature place to act on diagnostics without automatic status changes | Operations Center MVP (done), Source Reliability / Quarantine Tracking (done), Network Confidence Model (not built) | Medium | Future |

---

## Epic 8 — Administration & Diagnostics

**Goal:** Give admins a coherent way to understand platform health and behavior, not just scattered per-engine diagnostics.

**Why it matters:** Every SIP/EQE/POL sprint added its own admin section correctly and additively. The Operations Center MVP now adds the first unified top-level readout, and Historical Replay now has an admin-only operational console under `/admin`; fuller operational workflows and deeper historical diagnostics remain future work.

**Current status:** **Operations Center MVP implemented; Historical Replay Admin Console implemented.** Admin now renders a top-level Operations Center Summary above the existing detailed diagnostics. The summary reports overall operational status, confidence, reason, recommendation, what is working, and what needs attention, with component summaries for Configuration, Pipeline / Platform Observability, Evidence Network, Source Confidence, Source Reliability, Coverage Intelligence, and Freshness / Feed Health. Existing admin diagnostics remain available below the summary. Operations Center is render-time/admin-only and uses existing persisted signals only; it does not change persistence, scoring, sources, taxonomy, or engine logic. `/admin` also includes an operational, admin-only Historical Replay console for triggering persisted-evidence replays and inspecting compact replay summaries without exposing replay controls in the user dashboard or Research Workspace.

**Dependencies:** None blocking.

**Epic priority:** **Medium**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Unified Admin Diagnostics Hub / Operations Center MVP | **Implemented at MVP level.** `mne/operations_center.py` builds a render-time/admin-only operational summary from existing persisted signals, and `/admin` displays it above the existing detailed diagnostics. Future refinements may still improve navigation and operational workflows, but the first Operations Center layer is complete. | Faster diagnosis, less hunting across bolted-on sections | Done | Medium | Complete |
| Historical Replay Admin Console | **Implemented.** `/admin` includes an admin-only Historical Replay section for entering `replay_date`, triggering deterministic replay from persisted evidence only, and inspecting compact result summaries, warnings, artifact filename/path, and recent replay history. | Operational replay debugging and validation without exposing replay controls to users | Done | Medium | Complete |
| Historical/skipped-run browser | Future. Admin view of total-failure or skipped-run days remains unbuilt. | Visibility into days MNE couldn't complete a full run | Platform Observability (done) | Low | Medium |
| Version comparison view | Future. Compare replayed vs. live runs across engine versions; remains unbuilt. | Debugging and trust-building for Historical Replay | Historical Replay Engine (Epic 2) | Medium | Future |
| Temporal integrity audit tooling | Future. Explicit, one-click confirmation that no future evidence leaked into a replay remains unbuilt. | Direct proof of Historical Replay's core guarantee | Historical Replay Engine (Epic 2) | Medium | Future |

---

## Epic 9 — Performance & Scalability

**Goal:** Keep MNE fast and reliable as evidence volume, source count, and evidence types grow.

**Why it matters:** Not yet a bottleneck — current run durations (observed ~13.5 seconds end to end) are fast — but the foundation for noticing when that changes already exists.

**Current status:** **Foundational telemetry implemented** (Platform Observability Layer — per-stage timing, run duration, engine versions). No analysis or optimization work has begun, because none is yet needed.

**Dependencies:** Platform Observability (done); further work benefits from more accumulated telemetry history over time.

**Epic priority:** **Low** (deliberately, not neglectfully — this is correctly not urgent yet)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Performance Analytics dashboard | Trend view over accumulated POL telemetry | Early warning before performance becomes a real problem | POL (done), more accumulated history | Medium | Low |
| Reliability Reporting | Uptime/failure-rate trends from POL and SIP data | Long-run platform health visibility | POL, SIP (done) | Medium | Low |
| Run duration budget/alerting | Simple thresholds flagging an unusually slow run | Early anomaly detection | POL (done) | Low | Low |
| Ingestion scaling review | Revisit fetch/normalize performance as source count and evidence types grow | Keeps ingestion fast at scale | Non-headline connectors (Epic 7) | High | Future |

---

## Epic 10 — Future Platform Opportunities

**Goal:** Name the long-term surface area MNE's architecture already anticipates, without committing to any of it yet.

**Why it matters:** Every architecture document in this repository was deliberately built so these become natural extensions later, not separate products requiring redesign.

**Current status:** **Not started.** Explicitly reserved for architectural compatibility only, per the Narrative Memory System, Historical Replay Engine, and Research Workspace Architecture documents.

**Dependencies:** Almost everything here depends on Narrative Memory (Epic 3) at minimum, and several items depend on the AI Experience (Epic 4) as well.

**Epic priority:** **Deferred — dependency-gated**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Company Promise Tracker | Focused application of Narrative Accountability to individual companies | Accountable tracking of company claims vs. outcomes | Narrative Memory | High | Future |
| Competitive Intelligence | Relative narrative standing across companies over time | Comparative company research | Narrative Memory | High | Future |
| API Consumers | Structured intelligence exposed to external developers | Third-party product-building on MNE | Stable, versioned intelligence schemas (mostly done) | Medium | Future |
| Mobile Application | Level 1–2 optimized mobile experience | On-the-go access | Research Workspace, Dashboard Experience | High | Future |
| Desktop Platform | Level 3–4 optimized desktop experience | Deep research with room to work | Research Workspace | High | Future |
| Discord integration | Level 1–2 conversational surface | Quick, casual access | AI Experience core | Low–Medium | Future |
| Enterprise offering | Not yet scoped | Commercial expansion | Nearly everything above | Unscoped | Future |

---

## Recommended Implementation Order

Following the guiding philosophy — **build the smallest amount of software that creates the largest increase in user value** — and respecting every dependency called out above:

**Phase 1 — Immediate.** The highest-leverage work available right now, sequenced by the size of the user-visible value each unlocks:
1. Epic 6: remaining dashboard trust fixes — hero sentence bug, human-readable run selector, and trend-label verification (all Low complexity, immediate trust wins). The Dashboard Data Quality Banner / Trust Summary is already complete.

**Phase 2 — Near-term.** Once the dashboard's remaining quick fixes are in:
2. Epic 2 / Epic 1: User-facing Historical Replay UI and Research Workspace historical integration remain future work, to be built only where backed by the implemented replay foundation, the completed admin console, and available historical evidence.
3. Epic 6 / Epic 1: historical content migration and future Research Workspace modes only where they are backed by implemented data. Narrative Comparison, Company Analysis, Research Session persistence, saved investigations, watchlists, annotations, and shared workspaces remain future work.
4. Epic 2 / Epic 7: historical evidence connectors, historical taxonomy replay, versioned replay retention, and supporting replay diagnostics remain future work as the product surface matures.
5. Epic 7 / Epic 8: remaining source-intelligence and admin controls. Network Confidence Model, Source Quarantine automation, historical/skipped-run browsing, version comparison, and temporal integrity audit tooling remain future work. Source Confidence Model, Source Reliability / Quarantine Tracking, Operations Center MVP, and Historical Replay Admin Console are already complete.
6. Epic 7 / Epic 4: full article ingestion and AI article summaries remain future work only if deliberately desired later. The implemented Evidence Reader Panel is complete and should not be treated as future near-term work.

**Phase 3 — Mid-term.** Once the Research Workspace has real usage on live data:
7. Epic 3: Narrative Memory remains future work, beginning with the Memory Object persistence model and Memory Timeline only after Historical Replay is mature enough and/or integrated where needed.

**Phase 4 — Longer-term.** Only once Historical Replay is more product-integrated and backed by sufficient historical evidence:
8. Epic 4: AI Experience remains future work, beginning with explanation/summarization only once there is enough stable, real deterministic output and enough real workspace usage for AI to meaningfully assist with.
9. Epic 7: Network Confidence Model remains future work, sequenced after the current evidence-network health and source-confidence layers have enough operational history to justify the next model.

**Phase 5 — Future, as conditions warrant.**
10. Epic 9: Performance & Scalability work, as accumulated telemetry and growing evidence volume actually call for it.
11. Epic 10: Future Platform Opportunities, each individually scoped when its Epic-level dependencies (chiefly Narrative Memory) are in place.

**Items that must not begin out of order, restated for emphasis:**
- No item in **Epic 3 (Narrative Memory)** begins until **Epic 2 (Historical Replay)** is mature enough and/or integrated as needed for the specific memory work.
- No item in **Epic 4 (AI Experience)** begins before **Epic 1 (Research Workspace)**'s MVP is live with real, stable deterministic output.
- **Epic 7's non-headline connectors** do not begin before the current, headline-only Evidence Object architecture has been proven stable in production for a meaningful period — consistent with SIP's own original phased build discipline.
