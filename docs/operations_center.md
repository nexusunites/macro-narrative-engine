# MNE — Operations Center
## A Permanent Operational Philosophy for the Macro Narrative Engine

*This document belongs alongside the Source Intelligence Platform, the Intelligence Experience Architecture, and the Platform Observability Layer as one of MNE's permanent foundational references. It is a philosophy and architecture document, not an implementation handoff, not a UI mockup, and not an admin page redesign — it defines, permanently, how every operational engine in MNE communicates its health to the humans responsible for running it.*

---

## 1. Vision

MNE already contains a growing family of independent engines — the Source Intelligence Platform, Coverage Intelligence, Platform Observability, Narrative Intelligence, the Narrative Brief Engine, the Event Lifecycle Engine — and its architecture anticipates many more: Historical Replay, Narrative Memory, the AI Experience, the Evidence Network Initiative, and engines not yet named. Each of these, correctly, has produced its own diagnostics as it was built. But diagnostics that accumulate engine by engine, section by section, eventually stop being clarity and start being homework: a wall of per-engine detail an administrator has to mentally assemble into an answer that should have been handed to them.

The Operations Center is MNE's permanent answer to that. It is the single place where the platform explains its own operational health to a human — plainly, consistently, and in seconds — with every raw detail still reachable underneath, but never as the price of a first answer. It is, in a real sense, the Intelligence Experience Architecture applied inward: the same discipline MNE uses to make market intelligence approachable, applied to MNE's understanding of itself.

---

## 2. Why Operations Matter

MNE's entire value rests on trust in its output — and trust in output requires trust in operation. A platform whose data quality silently degrades, whose sources quietly go stale, or whose pipeline stages fail invisibly will eventually produce a confidently-presented conclusion built on bad ground. MNE's architecture has been unusually disciplined about preventing *silent* failure — Feed Health, Freshness Validation, the evidence funnel, the zero-match warning, and per-stage telemetry all exist specifically so that nothing degrades invisibly.

But visibility is not the same as understandability. The recent zero-match investigation proved this concretely: every fact needed to diagnose the problem was already persisted — health states, freshness statuses, rejection reasons, funnel counts — yet the diagnosis still required a manual, multi-file, cross-referencing investigation, because no single surface assembled those facts into an answer. The platform *knew* what was wrong. It just couldn't *say* it. The Operations Center exists so that gap never has to be closed by hand again.

---

## 3. Operational Clarity Principle

Every operational component in MNE — every engine, every subsystem that can be healthy or unhealthy — exposes exactly four things, in this order:

- **Status** — a single standardized state (§6) describing how this component is doing right now.
- **Confidence** — how sure the platform is of that status (§7).
- **Reason** — the specific, plain-language facts behind the status.
- **Recommendation** — what, if anything, a human should do about it.

A worked example of the standard:

> **Evidence Network**
> **Status:** GOOD
> **Confidence:** HIGH
> **Reason:** 23 healthy sources contributed. CNBC is blocked. WSJ is stale.
> **Recommendation:** Investigate CNBC authentication. Review WSJ endpoint.

Notice what this example does: it does not hide the problems (CNBC, WSJ) behind the overall GOOD status, and it does not let two degraded sources panic the overall status into something alarmist when twenty-three others are working. Status summarizes honestly; Reason names specifics honestly; Recommendation converts specifics into action. All four fields are derived deterministically from data the engines already compute — the Operations Center introduces no new judgment of its own, only translation, exactly consistent with the observational disciplines already established by the Evidence Quality Engine ("qualifies without modifying") and the Platform Observability Layer ("observes, never modifies").

---

## 4. Operations Center Philosophy

The Operations Center answers four questions, in order, within seconds of an administrator arriving:

1. **What is working?**
2. **What is not working?**
3. **Why?**
4. **What should I do next?**

Everything about its design flows from these four questions and their ordering. An administrator arriving after an alert, before a market open, or during an incident does not have time to read tables first and derive meaning second — meaning comes first, always, with detail one deliberate step beneath it.

The governing design principles, stated permanently:

- **Readable before detailed.** Plain language before field names.
- **Summaries before tables.** The rollup before the rows.
- **Meaning before metrics.** "Two sources are degraded" before "entries_parsed: 0."
- **Recommendations before implementation.** What to do before how the detection works.
- **Expandable diagnostics.** Every raw detail remains reachable — deferred, never withheld, exactly as the Intelligence Experience Architecture already requires for user-facing intelligence.
- **Consistent language across every engine.** A status of DEGRADED means the same thing whether it describes a feed, a replay, or a memory store. An administrator who learns to read one engine's health has learned to read all of them.

---

## 5. Information Hierarchy

The Operations Center is organized in strictly descending altitude:

**Level 1 — Platform Summary.** One glance: the overall platform status, and which engines (if any) are not at their best. This alone answers "what is working / what is not" for an administrator with ten seconds.

**Level 2 — Engine Summaries.** One standardized component (§8) per engine — Status, Confidence, Reason, Recommendation — answering "why" and "what should I do" for each engine that deserves a look.

**Level 3 — Diagnostics.** The existing per-engine diagnostic detail MNE already produces: health tables, freshness records, funnel counts, coverage tables, stage timings. Everything already built by SIP, EQE, and POL lives here — organized under this hierarchy rather than replaced by it.

**Level 4 — Raw Data.** The persisted run JSON, evidence objects, telemetry records — the ground truth everything above is derived from, available for the administrator who needs to verify rather than trust.

Density increases only with deliberate descent. Nothing at Level 1 or 2 requires reading a table; nothing at Level 3 or 4 is more than a step or two away.

---

## 6. Status Vocabulary

Seven standardized operational states, used identically by every engine, present and future. These describe **operational condition**, and each has an exact meaning:

| Status | When it is used |
|---|---|
| **EXCELLENT** | Everything this engine is responsible for is functioning fully, with no degraded elements at all. Reserved for genuinely clean states — not the default label for "probably fine." |
| **GOOD** | The engine is functioning well overall; minor degraded elements may exist but do not meaningfully impair the engine's output (e.g., most sources healthy, one or two degraded). |
| **LIMITED** | The engine is functioning, but its output is materially narrower or thinner than normal (e.g., enough sources lost that evidence diversity is genuinely reduced). Not broken — constrained. |
| **DEGRADED** | The engine is producing output, but that output is compromised in a way a consumer of it should know about before relying on it. |
| **WARNING** | A specific condition exists that is not yet impairing output but predictably will if unaddressed (e.g., a source trending toward quarantine, a stage's duration creeping upward). Forward-looking by definition. |
| **CRITICAL** | The engine's core function is failing or has failed for this run; its output for the affected scope should not be relied upon. |
| **OFFLINE** | The engine did not run, could not run, or is unreachable. Distinct from CRITICAL: OFFLINE means absence, CRITICAL means broken presence. |

Rules of use, permanently:

- Every engine's status is derived **deterministically** from facts that engine already computes — rule tables, not judgment, exactly as every classification in MNE already works.
- Statuses are **honest, not diplomatic**. An engine that is LIMITED is labeled LIMITED, even on a demo day. The platform's credibility depends on its self-reporting being as trustworthy as its market reporting.
- Statuses describe **operational condition, never market meaning**. A quiet news day that produces few narrative matches is not a DEGRADED platform — it may be an EXCELLENT platform honestly reporting a quiet day. The zero-match episode is the canonical example: the pipeline was working perfectly; only the *legibility* of that fact was missing.

---

## 7. Confidence Vocabulary

Four standardized confidence levels, describing how sure the platform is of the status it just reported:

| Confidence | Meaning |
|---|---|
| **HIGH** | The status is derived from complete, current, directly-observed data. Nothing needed to compute it was missing or inferred. |
| **MODERATE** | The status is derived from substantially complete data, but some contributing signal was missing, defaulted, or degraded — the status is probably right, and the gap is nameable. |
| **LOW** | Enough contributing data was missing or unreliable that the status is a best available reading, not a firm one. The Reason field must say why. |
| **UNKNOWN** | The platform cannot meaningfully assess this component's condition right now (e.g., the engine never ran, or its inputs never arrived). UNKNOWN is an honest answer, never a gap papered over with a guessed status. |

Confidence here is the operational sibling of concepts MNE already has — the Narrative Brief's "Data Completeness," SIP's Source Confidence, Historical Replay's evidence confidence. It describes **completeness of the data behind the status**, never a probability that things will stay fine. And critically: confidence never softens status. A CRITICAL status at LOW confidence is still presented as CRITICAL — the confidence tells the administrator how firmly to hold it, not whether to see it.

---

## 8. Standard Component Layout

Every engine exposes its operational state through the same conceptual component, permanently:

- **Title** — the engine's human name (e.g., "Evidence Network," "Coverage Intelligence").
- **Overall Status** — one value from §6.
- **Confidence** — one value from §7.
- **Reason** — the specific facts behind the status, in plain language. Specific means specific: named sources, named stages, real counts — never "some issues detected."
- **Recommendation** — the action a human should consider, or an explicit "No action needed." Recommendations are drawn from fixed, deterministic mappings (the same discipline as Feed Health's existing `recommended_action` lookup), never generated freehand.
- **Expandable Details** — the doorway down to Level 3 diagnostics and Level 4 raw data for this engine.

This layout is not a suggestion — it is the contract. An engine whose operational state cannot be expressed through this component is an engine whose self-reporting is incomplete, and the fix is to complete the engine's self-reporting, never to give that engine a bespoke, nonstandard presentation.

---

## 9. Engine Applications

How the standard applies across MNE's engines, current and planned:

**Evidence Network Initiative (source ingestion, health, freshness).** Status rolls up from existing Feed Health states and source freshness statuses (e.g., all sources healthy and fresh → EXCELLENT; a minority blocked/stale → GOOD or LIMITED depending on diversity impact; majority failing → DEGRADED or CRITICAL). Reason names the specific sources and their specific conditions. Recommendation draws on the existing per-state recommended actions. The §3 worked example is exactly this engine.

**Coverage Intelligence.** Status reflects whether coverage measurement itself operated correctly — not whether coverage was broad. A run where every narrative measured MINIMAL coverage can still be an EXCELLENT Coverage Intelligence engine, honestly measuring thin evidence. Reason summarizes the measurement outcome ("4 narratives measured; broadest at MODERATE"); the coverage values themselves remain descriptive facts, never operational alarm.

**Platform Observability.** Status rolls up from existing per-stage telemetry (all stages SUCCESS → EXCELLENT; PARTIAL stages present → GOOD/LIMITED; FAILED stages → DEGRADED/CRITICAL; run never completed → OFFLINE). Reason names the specific stages and durations. Recommendation points at the specific stage worth investigating.

**Configuration.** Status reflects whether configuration resolved and loaded cleanly — registry loaded and valid at its expected version, data directory resolved and writable, no fail-loud validation errors. A malformed registry or an uncreatable data directory is exactly the kind of condition this engine's CRITICAL exists for, with a Recommendation naming the file and the fix.

**Historical Replay** *(once implemented)*. Status describes replay operation — did requested replays complete, deterministically, within temporal-integrity guarantees. Reason and Confidence naturally incorporate the reconstruction-completeness and evidence-confidence concepts that engine's architecture already defines.

**Narrative Memory** *(once implemented)*. Status describes preservation health — are runs being faithfully persisted into memory, is the historical record continuous, are there gaps. A missed day of memory capture is a WARNING or DEGRADED condition worth surfacing immediately, because that loss is permanent.

**AI Experience** *(once implemented)*. Status describes the assistant's operational availability and its boundary compliance instrumentation — never the quality of its explanations. The AI layer's health is "is it up, is it responding, is it operating within its permanent constraints" — an operational question with a deterministic answer, like every other engine's.

**Future engines.** Any engine not yet imagined adopts this identically (§12).

---

## 10. Dashboard vs. Operations Center

The user dashboard answers *"what is the market's story today?"* The Operations Center answers *"is the platform that told you that story healthy?"* These are different questions, for different audiences, at different moments — and mixing them damages both.

Operational diagnostics on the user dashboard would clutter a surface whose entire value is speed and focus, and would expose users to internal conditions they can neither act on nor correctly interpret. Conversely, a user-facing surface is the wrong home for the density and honesty operational work requires. The one legitimate crossing point is already established: the dashboard may carry a single, calm, high-level data-quality signal (Source Confidence / Data Completeness, as MNE's existing architecture already provides for) — a *summary of consequence* for the user, never the operational detail behind it. Everything deeper belongs here.

This division is the operational mirror of the Dashboard/Research Workspace split the Intelligence Experience Architecture already established: same platform, different products, serving different moments. The Operations Center is a third such product — the one serving the person responsible for keeping the other two trustworthy.

---

## 11. Progressive Disclosure

An administrator moves through the Operations Center in exactly the descending sequence of §5:

```
Platform Summary        — what's working, what isn't, in one glance
        ↓
Engine Summary          — Status / Confidence / Reason / Recommendation per engine
        ↓
Diagnostics             — the existing per-engine detail: tables, records, timings
        ↓
Raw Data                — persisted JSON, evidence objects, telemetry ground truth
```

Each step down is one deliberate choice, never forced and never blocked — the same Progressive Disclosure discipline the Intelligence Experience Architecture established for users, applied to administrators. An administrator who trusts the summary never has to descend; an administrator who needs to verify a single number can reach ground truth in a few deliberate steps; and no one is ever handed Level 4 density as the price of a Level 1 question.

---

## 12. Future Compatibility

New engines adopt this standard automatically, not by convention but by construction: an engine joins the Operations Center by exposing the Standard Component contract (§8) — Title, Status from §6, Confidence from §7, Reason, Recommendation, and a path to its own diagnostics. That is the entire integration surface. The Operations Center does not need to know what a new engine *does* to display its health; it needs only the contract.

Two permanent rules protect this:

- **The vocabularies are closed.** New engines do not invent new status or confidence values. If a future engine's condition genuinely cannot be expressed in the existing vocabulary, that is a deliberate, platform-wide vocabulary amendment to this document — never a one-engine exception.
- **The Operations Center computes nothing.** Every Status, Confidence, Reason, and Recommendation is derived by the engine itself (or a thin deterministic rollup over the engine's own persisted output). The Operations Center translates and presents; it never becomes a second place where operational judgment lives — the same boundary discipline as every presentation layer in MNE.

---

## 13. Verification Standards

Any future implementation claiming to realize this document should be judged against these standards:

1. **The four questions test.** An administrator with no prior context can answer "what is working, what is not, why, and what should I do" within seconds of arriving — verified by walking the actual surface, not by inspecting the data behind it.
2. **The vocabulary test.** Every displayed status and confidence value comes from §6/§7, spelled and meant identically across every engine — no synonyms, no per-engine variants.
3. **The contract test.** Every engine present exposes all six Standard Component fields (§8); no engine has a bespoke layout, and no field is missing or freehand.
4. **The honesty test.** Degraded conditions produce degraded statuses. A fixture with known problems (a blocked source, a failed stage) must surface those problems truthfully at Level 1 and 2 — never absorbed silently into a GOOD rollup.
5. **The determinism test.** The same persisted run data always produces the same statuses, confidences, reasons, and recommendations — byte-for-byte, on every evaluation.
6. **The no-new-judgment test.** Nothing displayed is computed by the Operations Center itself beyond deterministic rollup of engine-provided facts — confirmed by inspection, consistent with §12's second rule.
7. **The reachability test.** From any Level 2 engine summary, its Level 3 diagnostics and Level 4 raw data are reachable in a small number of deliberate steps — deferred, never withheld.
8. **The zero-match test, specifically.** The canonical historical failure of legibility — accepted evidence, zero taxonomy matches, healthy pipeline — must be immediately understandable from the Operations Center alone: correct status (not falsely alarmed), honest reason, and no manual file investigation required. This document exists, in large part, because that scenario once required one.

---

## Appendix A — Future Operational KPIs

This appendix is intentionally informational rather than normative.

The Operations Center architecture defines how engines communicate operational health.

This appendix captures the types of operational metrics that future implementations should summarize for administrators.

These metrics may evolve as MNE grows without requiring changes to the core operational philosophy.

### Evidence Network Initiative

Summarize metrics such as:

- Overall Network Health
- Healthy Sources
- Degraded Sources
- Blocked Sources
- Disabled Sources
- New Sources Added
- Evidence Collected
- Evidence Accepted
- Evidence Rejected
- Duplicate Rate
- Freshness Rejection Rate
- Provider Diversity
- Evidence Density
- Narrative Coverage Quality
- Single Source Dependency Risk
- Top Contributing Sources
- Recently Failing Sources

### Coverage Intelligence

Summarize:

- Coverage Quality by Narrative
- AI
- Energy
- Rates
- Inflation
- Recession
- Provider Diversity
- Evidence Concentration
- Coverage Trend
- Lowest Coverage Areas
- Highest Coverage Areas

### Platform Observability

Summarize:

- Pipeline Status
- Overall Runtime
- Pipeline Success Rate
- Failed Stages
- Warning Stages
- Skipped Stages
- Slowest Stage
- Historical Runtime Trend

### Configuration

Summarize:

- Configuration Status
- Registry Version
- Data Directory
- Environment Source
- Configuration Validation
- Missing Files

### Historical Replay

Future metrics:

- Replay Success Rate
- Replay Runtime
- Temporal Integrity
- Historical Coverage
- Historical Confidence

### Narrative Memory

Future metrics:

- Memory Health
- Days Stored
- Missing Days
- Memory Growth
- Synchronization Status

### AI Experience

Future metrics:

- Availability
- Response Time
- Boundary Compliance
- Successful Requests
- Failed Requests

### Presentation Principle

Operational metrics should never be shown as raw implementation details first.

Every metric should first contribute to a plain-language operational summary.

Administrators should understand platform health before inspecting measurements.

Measurements support the summary.

They do not replace it.
