# Research Workspace Architecture (RWA)
## A Permanent Architecture Document for the Macro Narrative Engine

*This document belongs alongside the Source Intelligence Platform, the Historical Replay Engine, the Narrative Memory System, the Intelligence Experience Architecture, and the Platform Observability Layer as one of MNE's permanent foundational references. It defines how research works inside MNE -- not how it is built, not what it looks like, and not what technology renders it. It is a philosophy and architecture document, not an implementation handoff.*

---

## 1. Purpose

MNE now has a complete deterministic foundation: evidence that is normalized, source-aware, health-aware, and freshness-aware; narrative intelligence that reasons over that evidence; a Coverage Intelligence layer that qualifies how broadly each narrative is supported; a Platform Observability Layer that records how the pipeline itself executed; and the architectural groundwork, already laid, for Historical Replay and Narrative Memory to eventually let MNE remember and reconstruct any day in its history.

None of that is, by itself, research. A person sitting down to actually investigate a question -- *why is this narrative dominant, what changed, which catalysts mattered, how broad is the evidence, what does history say* -- needs somewhere to do that investigating. Not a dashboard glance, not a single generated brief, but a structured environment for moving through a question at whatever depth it deserves. The Research Workspace exists to be that environment.

The distinction this document is built on is the same one that governs every other layer of MNE, extended one step further: **the Intelligence Engine generates intelligence. The Experience Layer delivers intelligence. The Research Workspace enables investigation.** These are three different jobs. The Research Workspace never does the first two -- it exists entirely to help a person investigate intelligence that already exists, using tools that already exist, without ever becoming a fourth way of producing conclusions of its own.

---

## 2. Guiding Philosophy

The Research Workspace is not another dashboard. It is not another report. It is not another AI chatbot. Each of those already exists elsewhere in MNE's architecture, and each does its own job well -- the dashboard orients quickly, the Narrative Brief composes a daily read, the AI layer (governed by the Intelligence Experience Architecture) explains and converses. The Research Workspace is something else: a structured environment for exploring evidence, narratives, history, catalysts, and market context, built for the person who has moved past "what's happening" and into "help me understand this properly."

Where the dashboard is fast and glanceable by design, the Research Workspace is deliberately unhurried. It is where a user goes to slow down, follow a question wherever it leads, and come back with an actual understanding rather than a quick read. This is the same Dashboard/Research distinction already established in the Intelligence Experience Architecture -- the Research Workspace is the concrete architectural realization of that document's Research Philosophy, given its own dedicated treatment here because of how much it now needs to orchestrate.

---

## 3. Architectural Principles

The Research Workspace, permanently and without exception:

- **Never generates intelligence.** Every fact a user encounters in the workspace originates in an existing intelligence system -- Narrative Intelligence, the Evidence Quality Engine, the Event Lifecycle Engine, the Narrative Brief Engine, Historical Replay, or Narrative Memory.
- **Never changes intelligence.** Investigating a narrative in the workspace has zero effect on that narrative's score, ranking, or any other conclusion.
- **Never changes narrative scoring.**
- **Never changes Evidence Quality.**
- **Never changes Event Lifecycle.**
- **Never changes Narrative Brief.**

It only **orchestrates** deterministic outputs already produced elsewhere -- arranging, sequencing, and cross-referencing them into a coherent investigative experience. Orchestration is the entire job. If the workspace ever finds itself computing something no other system has already computed, that is a signal the computation belongs in an intelligence layer, not in the workspace that investigates it.

---

## 4. User Investigation Model

Every research session begins with a question, not a destination. Representative questions the workspace should support investigating:

- *Why is AI dominant?*
- *When did Energy become dominant?*
- *What changed after the last FOMC meeting?*
- *How has this narrative evolved?*
- *Which companies benefit?*
- *Which catalysts mattered most?*
- *How broad is the supporting evidence?*
- *Which sources contributed?*

What unites these questions is that none of them has a single-number answer -- each one is really a request to move through several existing intelligence outputs in sequence: a narrative's current state, its history, the events around it, the evidence behind it, the companies attached to it. The Research Workspace's job is to make that movement natural. A user should be able to start anywhere in this list and be led, through the workspace's own structure, to whatever adjacent information the question actually requires -- without needing to already know which underlying engine holds the answer to each part of it.

---

## 5. Workspace Responsibilities

The Research Workspace is responsible for:

- Presenting a coherent, navigable environment for investigating narratives, evidence, history, catalysts, and companies.
- Sequencing and cross-referencing outputs from multiple intelligence systems into a single investigative flow, rather than leaving a user to visit each system independently and reassemble the picture themselves.
- Preserving full traceability at every step -- a user should always be able to see which underlying system produced any given fact they're looking at, consistent with MNE's platform-wide explainability standards.
- Supporting investigation at whatever depth a question actually requires, without artificially truncating it (a direct extension of the Intelligence Experience Architecture's Progressive Intelligence principle, applied specifically to the deep, Level 4 end of that spectrum).
- Providing the structural home for future research capabilities (Section 16) without requiring architectural rework as they're added.

---

## 6. Workspace Boundaries

Precisely because the Research Workspace touches nearly every intelligence system MNE has, its boundaries deserve restating as plainly as its responsibilities:

- It does not decide what a narrative's score is -- it displays what Narrative Intelligence already decided.
- It does not decide how broad a narrative's evidence is -- it displays what the Evidence Quality Engine already computed.
- It does not decide what happened on a historical date -- it displays what Historical Replay already reconstructed.
- It does not decide how the platform executed -- it displays what the Platform Observability Layer already recorded.
- It does not decide what a narrative meant over time -- it displays what the Narrative Memory System already preserved.

In every one of these cases, the verb is "displays," never "decides." The Research Workspace is a place where a user meets intelligence, not a place where intelligence is made.

---

## 7. Workspace Modes

Workspace Modes are **conceptual orientations for an investigation, not UI tabs, screens, or navigation items** -- a user's question determines which mode (or combination of modes) is relevant, not a menu they must first choose from. Representative modes:

- **Current Market** -- investigating today's narrative state directly.
- **Historical Investigation** -- using Historical Replay and Narrative Memory to understand a past date or period.
- **Narrative Comparison** -- placing two or more narratives, periods, or regimes side by side.
- **Catalyst Analysis** -- investigating a specific scheduled or unscheduled event and its narrative effects, drawing on the Event Lifecycle Engine and Event Memory.
- **Company Analysis** -- investigating a specific company's narrative footprint, drawing on Company Memory.
- **Evidence Review** -- investigating the underlying evidence and coverage behind a conclusion directly, drawing on the Evidence Quality Engine and Source Intelligence Platform.

These modes are not mutually exclusive, and a single investigation will typically move through several of them -- the mode framing exists purely to help describe the *kind* of question being asked at a given moment, so the workspace can orchestrate the right systems in response.

---

## 8. Workspace Components

Workspace Components are conceptual building blocks of an investigation -- described here by responsibility, not by implementation:

- **Narrative Overview** -- a narrative's current state: score, leadership standing, pulse, regime alignment.
- **Narrative Brief** -- the composed, template-driven daily read for a narrative, as already produced by the Narrative Brief Engine.
- **Evidence Timeline** -- the sequence of accepted Evidence Objects supporting a narrative over a chosen window.
- **Coverage Summary** -- the Evidence Quality Engine's breadth, diversity, and concentration metrics for a narrative.
- **Source Summary** -- which sources and providers contributed, and their Feed Health/Freshness standing, drawn from the Source Intelligence Platform.
- **Catalyst Timeline** -- scheduled and unscheduled events relevant to a narrative, drawing on the Event Lifecycle Engine and, historically, Event Memory.
- **Leadership Timeline** -- how a narrative's leadership and rotation standing has moved over time, drawing on Narrative Memory once that system is operational.
- **Related Companies** -- companies associated with a narrative, drawing on Company Memory.
- **Historical Context** -- a reconstructed past state for comparison, drawing on Historical Replay.
- **Memory** -- accumulated, faithfully-preserved narrative history, drawing on the Narrative Memory System broadly.
- **Observability** -- for admin/diagnostic-oriented investigation, how the platform itself executed for a given run, drawing on the Platform Observability Layer.
- **Research Notes** *(future)* -- a place for a user's own annotations and observations attached to an investigation; reserved conceptually (Section 16), not built here.

Each component's responsibility is to **display and contextualize** output from exactly one underlying system (or, for composite components like Narrative Overview, a small, clearly-attributed set of them) -- no component computes something its underlying system hasn't already computed.

---

## 9. Narrative Investigation Flow

A representative flow through which an investigation might progress -- illustrative, not a rigid, enforced sequence a user must follow step by step:

```text
Question
   ↓
Narrative Selection
   ↓
Evidence Review
   ↓
Historical Context
   ↓
Catalysts
   ↓
Coverage
   ↓
Companies
   ↓
Conclusions
```

A user begins with a question (Section 4), selects or is guided to the relevant narrative(s), reviews the evidence behind the current read, brings in historical context for comparison, checks for relevant catalysts, examines coverage breadth, looks at related companies, and arrives at their own conclusions. **The workspace organizes this research. It does not perform the research autonomously** -- at every step, the workspace is presenting deterministic platform output for the user to interpret; it never skips ahead and hands the user a conclusion it has independently drawn. The user's own reasoning, informed by everything the workspace surfaces, is what produces "Conclusions" at the end of this flow -- not the workspace itself.

---

## 10. Research Session Model

A research session is the container for a single investigation -- bounded by a user's question, and extending for as long as that investigation continues, potentially across multiple visits. The session model exists to give an investigation continuity: the narratives, time windows, and comparisons a user has brought into view should persist as a coherent working context, not reset with every navigation action.

This document does not specify how sessions are stored, how long they persist, or what technology maintains them -- those are implementation questions properly deferred to future, separately scoped work (Section 18). What matters architecturally is the *concept*: a session is a coherent, continuous investigative context, not a sequence of disconnected page views. Future capabilities like saved investigations (Section 16) are natural extensions of this concept once it exists, not separate architectures of their own.

**Status note (2026-08-15):** Studio now persists a bounded thesis artifact, while the general Research Session-persistence concept described here remains future; see `docs/project_status.md` and `docs/product_backlog.md` for current state.

---

## 11. Integration With Existing Engines

The Research Workspace consumes, without ever duplicating the logic of:

- **Narrative Intelligence** -- theme/group scores, leadership, rotation, pulse, dynamics, crowding, regime alignment.
- **Evidence Quality Engine** -- coverage, provider diversity, source concentration.
- **Event Lifecycle Engine** -- current catalyst phase and timing.
- **Narrative Brief Engine** -- the composed daily brief.
- **Historical Replay** -- reconstructed historical intelligence for any past date (Section 12).
- **Narrative Memory** -- faithfully preserved narrative history across time (Section 13).
- **Platform Observability** -- how the pipeline itself executed (Section 14).

**The workspace never duplicates their logic.** If an investigation seems to require a computation that doesn't already exist in one of these systems, the correct response is to identify which system should be extended to produce it -- not to compute it inside the workspace. This is the same discipline the Intelligence Experience Architecture already established for the Experience Layer generally (Sections 17 and 20 of that document), applied here to the specific case of a workspace that touches many systems at once rather than delivering a single one.

---

## 12. Historical Replay Integration

The Research Workspace is where Historical Replay becomes usable by a person, rather than existing only as a backend capability. **Historical Investigation** (Section 7) is the mode most directly built on Historical Replay: a user selects a past date, the workspace requests (or retrieves an already-persisted) reconstruction of that date's intelligence, and presents it through the same components (Section 8) used for current-day investigation -- Narrative Overview, Evidence Timeline, Catalyst Timeline, and so on, all populated from a Historical Run Object instead of a live run.

This reuse is only possible because Historical Replay was deliberately designed to produce output structurally consistent with live output (per the Historical Replay Engine's own architecture) -- the workspace does not need separate components for historical versus current investigation, only a clear, persistent indication (consistent with the Intelligence Experience Architecture's requirement that a historical reconstruction never be mistaken for a live read) of which one a user is currently looking at.

---

## 13. Narrative Memory Integration

Where Historical Replay answers "what would MNE have concluded on this date," Narrative Memory answers "how has MNE's understanding evolved across many dates" -- and the Research Workspace is where that accumulated memory becomes something a user can actually explore. **Leadership Timeline**, **Historical Context**, **Related Companies** (via Company Memory), and **Catalyst Timeline** (via Event Memory) are all workspace components that exist specifically to give a user access to Narrative Memory's accumulated record, without requiring them to understand Memory's internal architecture to benefit from it.

The workspace's role here is purely presentational: Narrative Memory preserves; the workspace displays what's been preserved, organized around whatever question the user is currently investigating.

---

## 14. Platform Observability Integration

Platform Observability is the one integration in this document oriented more toward admin/diagnostic investigation than toward narrative research proper -- but it belongs in the same workspace architecture because the underlying need is identical: a structured environment for investigating something, at whatever depth the question requires. A technical user investigating "why did today's run take longer than usual" or "which engine version produced this conclusion" uses the same **Observability** component (Section 8), populated from the Platform Observability Layer's persisted telemetry, following the exact same orchestration-not-computation discipline as every other integration in this document.

---

## 15. AI Integration Boundaries

The AI layer operating within the Research Workspace follows the Intelligence Experience Architecture's AI boundary without exception or modification. Within the workspace specifically, the AI:

**May:**

- Explain
- Summarize
- Compare
- Teach
- Personalize (presentation only, per the Intelligence Experience Architecture's definition)
- Answer questions
- Organize an investigation -- helping a user navigate the flow in Section 9, suggesting a relevant next component to examine, or structuring a multi-part question into its component parts

**Must never:**

- Generate intelligence
- Modify intelligence
- Override deterministic conclusions
- Change evidence
- Change coverage
- Change narratives

The Research Workspace should treat AI as an **assistant operating on deterministic platform outputs** -- a helpful guide through the investigation flow and the workspace's components, never an independent source of conclusions competing with the intelligence systems the workspace exists to present. An AI capability that "organizes investigations" (explicitly permitted above) is still bound by every constraint in this section -- organizing which existing outputs to look at, and in what order, is not the same as generating a new one.

---

## 16. Future Workspace Extensions

The following are explicitly **reserved for architectural compatibility, not implemented** by this document:

- Collaborative research
- Saved investigations
- Watchlists
- Annotations
- Portfolio overlays
- Trade journals
- Custom workspaces
- Shared workspaces

**Status note (2026-08-15):** The phrase "not implemented by this document" above describes this architecture document's scope at its authoring time; it is not a current repository-state claim. Since then, a bounded, single-user Studio thesis workspace (Sprints N–Q plus evidence types) has implemented a constrained realization of some concepts named here: a persisted thesis artifact, a story-level Saved store, a Watchlist rail, and a Compare-over-time tool. General saved-investigation and Research Session persistence and unrestricted custom workspaces remain future. Collaborative/shared workspaces, annotations/research journals, portfolio overlays, and trade journals remain unimplemented. For current state, see `docs/project_status.md` and `docs/product_backlog.md`; precedence is current status, backlog, implemented handoffs, then this historical architecture document.

Each of these is a natural extension of the concepts already established here -- a saved investigation is a persisted Research Session (Section 10); an annotation is a natural companion to the future Research Notes component (Section 8); a shared workspace extends the session model to multiple users. None require this document's architecture to be redesigned when they're eventually built -- they require only that this architecture continue to be respected as they're added: intelligence still comes from intelligence systems, the workspace still only orchestrates, and AI still only assists.

---

## 17. Risks

- **Scope pressure toward workspace-native computation.** Because the Research Workspace touches so many systems, there will be a natural temptation, over time, to add "just one small calculation" directly inside it rather than routing the need back to the appropriate intelligence system -- this is the single greatest long-term risk to this architecture's integrity, and every future workspace feature should be checked against Sections 3 and 11 before being built.
- **Historical and live investigation blending together in a user's mind.** Because the workspace deliberately reuses the same components for both (Section 12), there is a real risk that a user loses track of whether they're looking at a live read or a historical reconstruction -- the persistent, clear labeling requirement is not a minor UX nicety but a load-bearing safeguard against a genuinely confusing and potentially misleading experience.
- **AI organization creeping toward AI conclusion.** The permission for AI to "organize investigations" (Section 15) sits close to a line that would be easy to cross without noticing -- a system that always suggests the "right" next step could gradually start implying a preferred conclusion through the order and framing of its suggestions alone, even while technically never stating one outright. This deserves ongoing, deliberate attention as AI-assisted organization is actually built.
- **Session model ambiguity blocking future extensions.** Because this document deliberately leaves session persistence mechanics unspecified (Section 10), there's a risk that future extensions (saved investigations, shared workspaces) each invent their own incompatible notion of what a session is -- a future, focused architecture pass defining session mechanics concretely (without contradicting this document's conceptual model) should happen before more than one such extension is built.

---

## 18. Recommended Build Order

This document is an architecture reference, not an implementation plan -- but for orientation, the natural build sequence this architecture implies:

1. **Establish the Research Session concept concretely** (Section 10) -- even a minimal, single-user, non-persistent version -- since every other capability in this document assumes an investigation has continuity across the flow in Section 9.
2. **Build the core Workspace Components (Section 8) against systems that already exist today** -- Narrative Overview, Narrative Brief, Evidence Timeline, Coverage Summary, Source Summary, Catalyst Timeline -- since these require no new intelligence system to be built first, only orchestration of what SIP, Narrative Intelligence, EQE, and the Event Lifecycle Engine already produce.
3. **Wire the Narrative Investigation Flow (Section 9)** as the connective structure between those components, for Current Market and Evidence Review modes (Section 7) first, since those don't yet depend on Historical Replay or Narrative Memory being operational.
4. **Integrate Historical Replay (Section 12)** once that engine is implemented, adding the Historical Context component and Historical Investigation mode.
5. **Integrate Narrative Memory (Section 13)** once that system is implemented, adding Leadership Timeline, Related Companies, and the memory-dependent parts of Catalyst Timeline.
6. **Integrate Platform Observability (Section 14)** as the admin-oriented Observability component, independently of the narrative-research components above.
7. **Introduce AI assistance within the established boundaries (Section 15)**, only once the underlying components and flow are stable enough that AI has real deterministic output to explain, summarize, compare, and organize rather than being built ahead of the system it's meant to assist with.
8. **Stop.** Collaborative research, saved investigations, watchlists, annotations, portfolio overlays, trade journals, and custom/shared workspaces (Section 16) remain explicitly reserved, not built, until separately and deliberately scoped.

   **Status note (2026-08-15):** A bounded Studio thesis workspace has since been built within these boundaries; general saved investigations and unrestricted custom workspaces remain future, and the reserved collaborative/shared-workspace, annotation/research-journal, portfolio-overlay, and trade-journal capabilities remain deferred.
