# The Macro Narrative Engine
## Product Backlog

*This is the master implementation backlog for MNE, effective as of Platform Foundation v1.0. It is not the Product Vision, not an architecture document, and not a roadmap with dates — it is the single source of truth for what should be built next, organized by Epic, with every item scoped to reflect concrete user or platform value. Every future sprint handoff should originate from an item in this document.*

*This document is intentionally living. It should be updated whenever implementation meaningfully changes the state of the product. Status should always reflect verified implementation rather than planned work.*

*Status reflects what is confirmed operational in production as of this writing, based on direct inspection of live run output (`platform_observability`, `source_intelligence`, `narrative_brief`, `event_lifecycle`, and related blocks) and confirmed Codex implementation reports — not merely what has an architecture document.*

---

## Completed Foundations

The following major platform capabilities are considered complete as part of **Platform Foundation v1.0**. Future contributors should treat these as foundational — generally to be extended, not redesigned:

- **Source Intelligence Platform (SIP)** — Evidence Objects with deterministic IDs, the Source Registry (`config/source_registry.json`), Feed Health, and Freshness Validation, all operational in production.
- **Coverage Intelligence (EQE)** — per-narrative evidence breadth, diversity, and concentration measurement, first layer of the Evidence Quality Engine.
- **Narrative Intelligence** — theme/group scoring, taxonomy, Narrative Leadership, Rotation, Pulse, Dynamics, Crowding, Change Summary, Regime Alignment, Breadth Confirmation, and related market/catalyst context engines.
- **Narrative Brief Engine** — deterministic, template-composed, evidence-traceable daily briefs with graceful fallback behavior.
- **Event Lifecycle Engine** — deterministic catalyst phase awareness.
- **Platform Observability (POL)** — per-stage pipeline telemetry, run metadata, and engine version reporting.
- **Configuration Portability** — environment-driven, cross-platform data directory resolution with no import-time filesystem side effects.
- **Evidence Diagnostics** — accepted-evidence persistence (capped at 500 entries with an explicit truncation flag), the evidence funnel summary, the zero-match warning, and the healthy-but-severely-stale source flag.

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

**Current status:** Architecture (RWA) is complete. Two Codex-ready MVP handoffs (engineering data-contract layer and UX/journey layer) already exist and have not yet been confirmed implemented. The dashboard already carries a `/research` navigation link with no confirmed destination behind it.

**Dependencies:** None remaining. Every engine this Epic consumes (SIP, Narrative Intelligence, EQE, Event Lifecycle, Narrative Brief) is already implemented and confirmed live.

**Epic priority:** **Critical**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Narrative Investigation MVP | Build the single-narrative investigation page per the two existing MVP handoffs (Narrative Overview, Brief, Evidence, Coverage, Source Summary, Catalyst context) | First real place to answer "why" and "what evidence supports it" | None | Medium | Critical |
| Dashboard entry-point wiring | The single click-through affordance connecting a dashboard narrative card to its Investigation page | Makes the MVP reachable at all | Narrative Investigation MVP | Low | Critical |
| Admin-gated Observability reference | Surface the existing POL reference link inside the workspace, admin-only | Faster admin diagnosis without leaving the investigation | Narrative Investigation MVP, POL (done) | Low | Medium |
| Narrative Comparison mode | Side-by-side investigation of two narratives, periods, or regimes | Supports "how does this compare" questions | Narrative Investigation MVP | Medium | Future |
| Company Analysis mode | Company-centric narrative investigation | Supports "which companies benefit" questions | Company Memory (not built) | High | Future |
| Catalyst Analysis standalone mode | Dedicated catalyst/event investigation surface | Deeper event-specific research | Narrative Investigation MVP | Medium | Future |
| Research Session persistence | Concrete session mechanics (currently only conceptually specified) | Continuity across an investigation, foundation for saved work | Narrative Investigation MVP | Medium | Future |
| Saved investigations, watchlists, annotations, shared workspaces, trade journals | Reserved-compatibility extensions named in the RWA architecture | Long-term personalization and collaboration | Research Session persistence | High | Future |

---

## Epic 2 — Historical Replay

**Goal:** Let MNE reconstruct what it would have concluded on any past date, using only evidence that existed at the time.

**Why it matters:** This is the foundation everything in Narrative Memory depends on, and it's what eventually lets the Research Workspace answer "how did we get here," not just "what's happening now."

**Current status:** Architecture (HRE) is complete and detailed, including determinism, temporal-integrity, and persistence-isolation rules. Zero implementation has begun.

**Dependencies:** The Evidence Object schema and deterministic `evidence_id` scheme (SIP, done) are the direct technical foundation. Historical evidence connectors (archival ingestion) are a separate, not-yet-built SIP-adjacent capability this Epic depends on for anything beyond the current live data window.

**Epic priority:** **High** (foundational, but sequenced deliberately after Research Workspace has a working live-data experience to extend)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Historical Evidence Pipeline | Knowledge-boundary filtering enforcing "no future evidence" | The core integrity guarantee everything else depends on | SIP evidence model (done) | High | High |
| Replay Engine orchestration | Re-runs existing Narrative Intelligence pipeline against bounded historical evidence | Produces trustworthy historical reconstructions | Historical Evidence Pipeline | High | High |
| Historical Run Object persistence | Namespaced, versioned storage isolated from live runs | Auditable, reproducible historical records | Replay Engine orchestration | Medium | High |
| Replay determinism verification suite | Automated proof that identical requests produce identical results | Trust in reconstructed history | Historical Run Object persistence | Medium | High |
| Historical/evidence confidence split | `source_confidence` vs. `evidence_confidence` per historical run | Honest signal about reconstruction completeness | Replay Engine orchestration | Medium | Medium |
| Admin replay console | Manual trigger/inspection tooling for a given date | Debugging and backfill support | Replay Engine orchestration | Medium | Medium |
| Historical Context integration into Research Workspace | Date selection and reconstructed views inside the workspace | Turns replay into something users actually touch | Research Workspace MVP (Epic 1), Historical Run Object persistence | Medium | Medium |
| Historical Research Interface | Open-ended querying across accumulated historical runs | Deep, self-directed historical research | Narrative Memory (Epic 3) | High | Future |

---

## Epic 3 — Narrative Memory

**Goal:** Preserve MNE's daily understanding faithfully across time, so history remains re-examinable exactly as it was understood in the moment.

**Why it matters:** Without this, MNE's intelligence resets every day. This is what turns individual runs into an actual accumulated history.

**Current status:** Vision and architecture (NMS) complete. Zero implementation. **This Epic must not begin until Historical Replay's core pipeline (Epic 2, items 1–4) is implemented and verified** — Memory preserves Intelligence outputs across time, and Historical Replay is what makes those outputs for past dates trustworthy in the first place.

**Dependencies:** Historical Replay Engine (hard blocker, per above).

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

**Current status:** Zero implementation. Fully governed by the Intelligence Experience Architecture's AI boundary, already established as permanent doctrine. **Should not begin until the Research Workspace has real, stable, deterministic output for AI to operate on** — this is an explicit sequencing decision already made in the RWA architecture's own build order, not a new constraint introduced here.

**Dependencies:** Research Workspace MVP (Epic 1), for something worth explaining; Historical Replay/Memory, for anything beyond current-day explanation.

**Epic priority:** **Deferred — intentionally sequenced later**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Explanation/summarization layer | AI restates existing Narrative Brief content in plainer or deeper language | Faster, more natural understanding | Research Workspace MVP | Medium | Future |
| Comparison assistant | AI helps contrast narratives, dates, or regimes using existing outputs | Easier cross-narrative reasoning | Research Workspace MVP, Historical Replay (for cross-date) | Medium | Future |
| Conversational Q&A | Answers questions using existing intelligence and memory | Natural-language access to MNE's understanding | Research Workspace MVP | Medium | Future |
| AI-organized investigation assistant | Suggests next steps through an investigation | Guided research | Research Workspace MVP | High | Future — requires deliberate scrutiny per the risk already flagged in the RWA architecture (organization suggestions can imply conclusions through ordering alone) |
| Voice interface | Level 1–2 conversational access | Hands-free, glanceable access | AI Experience core capabilities above | Medium | Future |

---

## Epic 5 — Intelligence Platform

**Goal:** The deterministic core that turns evidence into narrative understanding — themes, groups, leadership, regime, and everything the rest of MNE is built on.

**Why it matters:** This is MNE's actual product. Nearly all of it is already built and running.

**Current status:** **Substantially Implemented.** Confirmed live in production: theme/group scoring, taxonomy (v1.1), Narrative Leadership, Leadership Rotation, Narrative Pulse, Narrative Dynamics/Crowding, Change Summary, Regime Alignment, Breadth Confirmation, Narrative/Market Relationship, Catalyst Environment, Positioning Environment, Market Expression, Event Lifecycle Engine, and the Narrative Brief Engine.

**Dependencies:** None for current capability. Remaining items depend on SIP's future evidence-type expansion.

**Epic priority:** **Medium** (maintain and extend; the core is done)

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Source Confidence Model | The designed-but-unbuilt SIP synthesis layer combining health, freshness, and coverage into one trust signal about the *quality of collected evidence* — was today's evidence collected cleanly. (Distinct from the Network Confidence Model, Epic 7, which assesses the resilience and adequacy of the evidence network itself.) | Honest answer to "was today's evidence collected cleanly" | Feed Health, Freshness Validation, Coverage Intelligence (all done) | Medium | High |
| Taxonomy versioning/expansion tooling | Formalized tracking of taxonomy changes across versions | Prevents confusion like the recent zero-match investigation, where taxonomy version had to be manually cross-checked | None | Medium | Medium |
| Positive-match explainability | Extend the recent zero-match diagnostics to also explain *why* a headline matched a theme | Faster trust-building and debugging | Evidence Diagnostics & Persistence Fix (done) | Low–Medium | Medium |
| Multi-evidence-type Narrative Detection | Scoring against SEC filings, transcripts, and other future evidence types | Richer, more corroborated narrative detection | SIP non-headline connectors (Epic 7) | High | Future |

---

## Epic 6 — Dashboard Experience

**Goal:** A fast, glanceable operational overview — distinct from, not a smaller version of, the Research Workspace.

**Why it matters:** The current dashboard works and degrades honestly, but a recent design review surfaced real, fixable issues — some cosmetic, one a genuine trust risk.

**Current status:** **Implemented**, with known UX debt. Confirmed issues: a template composition bug in the hero sentence, a raw-filename run selector, inconsistent navigation (anchor links mixed with real routes), an unverified trend-label claim on the regime history chart, and all Level 3/4 content (historical charts, score tables) currently flattened into the same page as Level 1/2 content.

**Dependencies:** None blocking the quick fixes. Moving Level 3/4 content out depends on the Research Workspace existing as a destination.

**Epic priority:** **High**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Fix hero sentence composition bug | Correct the malformed "market context is market confirmation is unclear..." string | Removes a visible, credibility-damaging bug | None | Low | Critical |
| Human-readable run selector | Replace raw filenames with formatted dates/times | Basic usability | None | Low | High |
| Verify/fix regime trend label logic | Confirm the "improving/worsening" claim actually reflects the chart's volatility | Prevents a misleading claim on a platform built around honest reads | None | Low–Medium | High |
| Consolidated degraded-run banner | One clear explanation instead of several scattered "not found" messages | Prevents a low-data day from looking broken | Source Confidence Model (Epic 5) for full context, but a partial version is buildable now | Medium | High |
| Navigation consistency | Replace anchor-link/route mix with a single consistent model | Removes user confusion about what's a real page | Research Workspace (for where /research should actually point) | Medium | High |
| Move Level 3/4 content into Research Workspace | Relocate regime history chart, leadership history table, raw score tables | Restores the dashboard's speed and focus | Research Workspace MVP (Epic 1) | Medium | Medium |

---

## Epic 7 — Data Quality & Source Intelligence

**Goal:** Make sure MNE knows the quality of its own inputs, and acts on that knowledge honestly.

**Why it matters:** This is the foundation every other Epic's trustworthiness rests on — and it's mostly done.

**Current status:** **Substantially Implemented.** Confirmed live: Evidence Objects, deterministic `evidence_id`, the Source Registry (`registry_version` 1.0.0), Feed Health, Freshness Validation, Coverage Intelligence, and the Evidence Diagnostics & Persistence Fix (accepted-evidence persistence, evidence funnel, zero-match warning, healthy-but-severely-stale flag).

**Dependencies:** Feed remediation items need direct investigation, not more architecture, before they can be closed.

**Epic priority:** **High**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| WSJ feed remediation | Confirm and fix the suspected silent-redirect/stale-mirror issue on `wsj-markets` | Restores a currently-degraded source | None (investigation-first) | Low–Medium | Critical |
| CNBC 403 remediation | Resolve the blocked `cnbc-top-news` source | Restores a fully-lost source | None | Low–Medium | High |
| Source Quarantine automation | Auto-exclude sources exceeding their expiration threshold across runs | Prevents a quietly-degraded source from going unnoticed indefinitely | Feed Health, Freshness Validation (done) | Medium | High |
| Source Confidence Model | (Cross-listed with Epic 5) | See Epic 5 | — | Medium | High |
| Network Confidence Model | Design and implement the deterministic model evaluating whether the Evidence Network is currently capable of supporting reliable macro understanding — per the ENI architecture. Distinct from Source Confidence: Source Confidence measures the *quality of collected evidence* (health, freshness, ingestion mechanics); Network Confidence measures the *resilience and adequacy of the evidence network itself* (diversity, provider concentration, dependency risk). A day can score high on one and low on the other. | Catches the failure mode per-evidence validation cannot: clean collection from a dangerously thinned network | Evidence Network Initiative (architecture accepted), Operations Center, Coverage Intelligence (done) | Medium | High |
| Non-headline connectors (Phase 2) | SEC filings, transcripts, government publications, and other evidence types | Richer, more diverse evidence base | Evidence Normalization Layer (done, proven with headlines only) | High | Future |
| Historical evidence connectors | Archival ingestion needed for dates before live capture | Enables Historical Replay beyond the current live window | Historical Replay core (Epic 2); becomes High priority once Epic 2 begins | High | Future |
| Full Source Registry admin editing UI | In-app registry editing, replacing config-file-only edits | Faster source management | Source Registry (done) | Medium | Medium |

---

## Epic 8 — Administration & Diagnostics

**Goal:** Give admins a coherent way to understand platform health and behavior, not just scattered per-engine diagnostics.

**Why it matters:** Every SIP/EQE/POL sprint added its own admin section correctly and additively — but nothing has unified them into one coherent experience yet.

**Current status:** **Implemented incrementally**, functional but not unified — Source Registry, Feed Health, Freshness, Coverage Intelligence, Platform Observability, and the new Evidence Diagnostics sections all exist as separate additions.

**Dependencies:** None blocking.

**Epic priority:** **Medium**

| Item | Description | User value | Dependencies | Complexity | Priority |
|---|---|---|---|---|---|
| Unified Admin Diagnostics Hub | Consolidate existing sections into one coherent, navigable admin IA | Faster diagnosis, less hunting across bolted-on sections | All existing admin sections (done) | Medium | Medium |
| Historical/skipped-run browser | Admin view of total-failure or skipped-run days | Visibility into days MNE couldn't complete a full run | Platform Observability (done) | Low | Medium |
| Version comparison view | Compare replayed vs. live runs across engine versions | Debugging and trust-building for Historical Replay | Historical Replay Engine (Epic 2) | Medium | Future |
| Temporal integrity audit tooling | Explicit, one-click confirmation that no future evidence leaked into a replay | Direct proof of Historical Replay's core guarantee | Historical Replay Engine (Epic 2) | Medium | Future |

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
1. Epic 6: dashboard trust fixes — hero sentence bug, human-readable run selector, trend-label verification (all Low complexity, immediate trust wins).
2. Epic 1: Research Workspace MVP — the Narrative Investigation MVP, its dashboard entry point, and the first complete investigative user experience. This is the single largest immediate increase in user-visible value available anywhere in this backlog, because it exposes intelligence that already exists and is already proven — the smallest amount of new software for the largest value unlock.
3. Epic 7: feed remediation — the WSJ stale-feed investigation and CNBC 403 remediation. WSJ remains **Critical** in item-level severity (a silently degraded source is a real data-quality problem), but per the priority-vs-sequencing distinction in "How to Read This Backlog," severity and sequencing are different axes: these are operational platform improvements rather than the next major product capability, and are sequenced after the larger user-value unlocks above.

**Phase 2 — Near-term.** Once the Research Workspace MVP is live and the dashboard's quick fixes are in:
4. Epic 5 / Epic 7: Source Confidence Model and Source Quarantine automation — completes the Source Intelligence Platform's original synthesis story at the evidence-quality level. (The Network Confidence Model, Epic 7, extends the confidence picture to network resilience and naturally follows once Source Confidence and the Operations Center exist to build on.)
5. Epic 6: consolidated degraded-run banner and Level 3/4 content migration into the now-existing Research Workspace.
6. Epic 8: Unified Admin Diagnostics Hub.

**Phase 3 — Mid-term.** Once the Research Workspace has real usage on live data:
7. Epic 2: Historical Replay Engine core (Historical Evidence Pipeline through determinism verification).
8. Epic 1 / Epic 2: Historical Context integration into the Research Workspace.

**Phase 4 — Longer-term.** Only once Historical Replay is stable and verified:
9. Epic 3: Narrative Memory, beginning with the Memory Object persistence model and Memory Timeline.
10. Epic 4: AI Experience, beginning with explanation/summarization — only once there is enough stable, real deterministic output and enough real workspace usage for AI to meaningfully assist with.

**Phase 5 — Future, as conditions warrant.**
11. Epic 9: Performance & Scalability work, as accumulated telemetry and growing evidence volume actually call for it.
12. Epic 10: Future Platform Opportunities, each individually scoped when its Epic-level dependencies (chiefly Narrative Memory) are in place.

**Items that must not begin out of order, restated for emphasis:**
- No item in **Epic 3 (Narrative Memory)** begins before **Epic 2 (Historical Replay)**'s core pipeline is implemented and verified.
- No item in **Epic 4 (AI Experience)** begins before **Epic 1 (Research Workspace)**'s MVP is live with real, stable deterministic output.
- **Epic 7's non-headline connectors** do not begin before the current, headline-only Evidence Object architecture has been proven stable in production for a meaningful period — consistent with SIP's own original phased build discipline.
