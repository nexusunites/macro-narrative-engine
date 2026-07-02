# Narrative Memory System (NMS)

## A Permanent Architecture and Vision Document for the Macro Narrative Engine

This document belongs alongside `ARCHITECTURE.md`, `docs/roadmap.md`,
`docs/project_status.md`, `docs/future_concepts.md`,
`docs/narrative_style_guide.md`, and `docs/source_intelligence_platform.md` as
one of MNE's permanent foundational references. It is a philosophy and
architecture document, not an implementation handoff. It defines why Narrative
Memory exists and what it must always remain true to, so that whoever eventually
builds it, in whatever year that happens, builds the same thing this document
describes.

## 1. Vision

MNE was built to answer a question that changes every day: what story is the
market telling right now? Every system described in this document's companion
documents - Narrative Detection, Leadership, Rotation, Pulse, Regime Alignment,
the Narrative Brief, the Source Intelligence Platform - exists to answer that
question well, for today.

But a platform that can only ever answer "what is true right now" has a hidden
limitation: it cannot tell you how today came to be true, and it cannot help you
recognize a pattern it has already lived through once before. The Narrative
Memory System exists to remove that limitation. It is the layer of MNE that
remembers - not so MNE can predict the future, but so MNE, and the people who use
it, can understand the present with the full weight of everything that came
before it.

Narrative Memory is not a new intelligence system. It is what happens to
intelligence after the day it was generated.

## 2. Why Narrative Memory Exists

Every run of MNE's intelligence layer produces a rich, deterministic,
well-reasoned understanding of a single moment. Without memory, that
understanding has a shelf life of one day - tomorrow's run supersedes it, and
yesterday's reasoning, however sound, becomes inaccessible except as a buried log
entry.

This is a strange asymmetry for a platform whose entire value proposition is
narrative - because narratives are, definitionally, things that unfold over time.
A narrative's leadership on a single day is a data point. A narrative's
leadership over six months, and the specific moments it strengthened, weakened,
or was replaced, is a story. MNE cannot tell that story without remembering each
chapter as it was actually understood at the time it happened.

Narrative Memory exists so that MNE's daily intelligence accumulates into
something greater than the sum of its days: a continuous, faithful record of how
market narratives actually evolved, preserved exactly as MNE understood them in
the moment, available for query at any point in the future.

## 3. Why Memory Is Different From Prediction

It would be easy to conflate "remembering the past" with "forecasting the
future" - both deal with time, and both are tempting to build once a platform has
rich historical data sitting in front of it. The Narrative Memory System is built
on a firm rejection of that conflation.

Prediction asks: what will happen next? It requires modeling, probability, and
inference beyond what has been directly observed. Memory asks: what actually
happened, and how do we understand it now? It requires only fidelity - an
accurate, complete, and honest record of what MNE's deterministic intelligence
actually concluded, when it concluded it, and on what evidence.

This distinction is not a minor implementation detail; it is the philosophical
spine of this entire document. Memory is retrospective and factual. It can
support human judgment about the future - a person looking at how AI narrative
leadership behaved during the last three Fed cycles is better equipped to reason
about the next one - but the system itself never crosses the line into making
that inference on the person's behalf. Narrative Memory's job ends at accurate,
explainable recollection. Everything past that point is left to the human doing
the reasoning.

## 4. Architectural Philosophy

Narrative Memory occupies a specific, permanent position in MNE's architecture -
not above Intelligence, not below Evidence, but as the layer that sits between
the two and turns momentary understanding into durable understanding:

```text
Evidence
   |
Narrative Intelligence
   |
Narrative Memory
   |
Knowledge
   |
User Experience
```

Evidence, via the Source Intelligence Platform, is the raw material: headlines,
filings, transcripts, publications, whatever form it eventually takes. Narrative
Intelligence is where MNE reasons about that evidence deterministically, today,
to produce leadership, rotation, pulse, regime alignment, and every other daily
read. Narrative Memory is where that reasoning, once produced, is preserved
faithfully across time rather than allowed to expire. Knowledge is what gets
built on top of an accumulated memory: the timelines, the accountability records,
the competitive histories. User Experience is where all of it finally becomes
something a person can look at and understand.

Memory should not replace Intelligence. Memory should preserve Intelligence
across time. This single sentence is the most important architectural constraint
in this document, and every other principle in this document exists to protect
it. Narrative Memory does not re-derive what Leadership or Regime Alignment
believed on a given day. It stores what those systems actually concluded, so that
belief remains inspectable forever, immune to future changes in how those systems
compute their conclusions.

## 5. Relationship to Evidence

Narrative Memory's relationship to evidence is one of consumption, never
dependency on mechanism. It consumes standardized Evidence Objects, as defined by
the Source Intelligence Platform, and it does so identically whether that
evidence arrived through live ingestion this morning or was reconstructed
through historical replay for a date years in the past.

This is a deliberate architectural choice, not a convenience: Narrative Memory
must never depend directly on RSS feeds, specific APIs, or any particular
ingestion mechanism. Ingestion mechanisms change - feeds go offline, providers
change formats, entirely new evidence types get added. If Narrative Memory
depended on any of that directly, every ingestion change would become a
memory-layer migration. Because it depends only on the standardized Evidence
Object interface, it remains stable across ingestion changes that are, from
memory's point of view, simply implementation detail happening one layer below
it.

The practical consequence is powerful: because live intelligence and historical
replay both produce the same Evidence Object shape, Narrative Memory treats a
Tuesday reconstructed from an archive with exactly the same rigor, and exactly
the same code path, as a Tuesday captured live. Memory does not know or care
which one it is looking at.

## 6. Relationship to Intelligence

Narrative Memory preserves what MNE's intelligence systems concluded -
Leadership, Rotation, Pulse, Regime Alignment, Market Environment, Event
Lifecycle, the Narrative Brief, and every future intelligence module - without
ever recalculating them.

This preservation-not-recalculation boundary matters enormously over long time
horizons. Intelligence systems evolve: scoring gets refined, taxonomy gets
expanded, new signals get incorporated. If Narrative Memory recalculated history
using today's version of Leadership logic, then "what MNE believed about AI
narrative leadership in March" would silently change every time Leadership's
algorithm was updated - and the historical record would no longer be a record of
what MNE actually believed at the time, but a record of what MNE's current logic
retroactively believes it should have believed. That is not memory. That is
revisionism, however well-intentioned.

Narrative Memory instead preserves intelligence outputs as they were generated,
timestamped and attributed to the specific run and, implicitly, the specific
version of the intelligence logic that produced them. A future reader asking
"what did MNE think was happening on this date" always gets the answer MNE
actually gave on that date - not a modern re-interpretation of it.

## 7. Relationship to Knowledge

Knowledge is what memory becomes once it accumulates enough history to reveal
patterns, trajectories, and structure that no single day's intelligence could
show on its own.

Company Promise Tracking, Narrative Accountability, Competitive Intelligence, AI
Benchmark History, Narrative Timelines, Historical Regime Analysis, and
Structural Market Shift analysis are all, in this architecture, Knowledge - and
Knowledge is explicitly built from accumulated Memory, not from raw Evidence.
This ordering matters: it means every future knowledge system inherits Memory's
guarantees of determinism, fidelity, and non-recalculation for free, rather than
needing to re-derive them independently. A Narrative Timeline is not a new
analytical engine reading old headlines - it is a presentation layer over what
Memory already faithfully recorded.

This is what makes Knowledge trustworthy in this architecture: it is never more
than an organized view onto Memory, and Memory is never more than a faithful
record of what Intelligence, in its moment, actually concluded from real
Evidence.

## 8. Relationship to Future Research

Narrative Memory is also the foundation for research MNE cannot yet name.
Historical Narrative Engines, structural regime studies, long-run
narrative-to-outcome comparisons, and forms of analysis not yet conceived will
all, eventually, want to ask questions of MNE's accumulated history. Narrative
Memory's job is to make sure that when those future systems arrive, the
historical record they need already exists, in a faithful and queryable form -
not that Narrative Memory anticipates what those systems will want to ask. It
provides the archive; it does not need to predict the questions.

## 9. Core Principles

Narrative Memory must remain, permanently and without exception:

- Deterministic. The same underlying run data, reviewed at any point in the
  future, produces the same memory record. Memory is never probabilistic or
  approximated.
- Explainable. Every memory record traces back to the specific intelligence
  output and evidence that produced it - nothing is remembered without a reason
  that can be shown.
- Transparent. There is no hidden memory, no undocumented retention, no silent
  aggregation the user or admin cannot inspect.
- Modular. Memory is a distinct architectural layer, addable to and queryable
  independently of Intelligence, Evidence, and Knowledge.
- Source-agnostic. Memory's fidelity does not depend on which evidence type or
  ingestion mechanism originally informed the intelligence being remembered.
- Evidence-driven. Every memory ultimately traces to real, ingested evidence -
  never inference, never assumption.
- Historically reproducible. Reconstructing a past date should be possible to do
  again, consistently, using the same historical replay mechanism, and should
  produce the same result each time.
- Auditable. A human must always be able to ask "why does MNE remember it this
  way" and receive a concrete answer.

Above all: memory must never become a prediction engine. The moment Narrative
Memory begins inferring what will happen rather than faithfully recording what
did happen, it has stopped being memory and become something else - something
explicitly out of scope for this system, permanently.

## 10. Memory Objects

Narrative Memory is organized around distinct conceptual categories of what it
preserves. These are described here as concepts, not schemas - how they are
eventually implemented is a separate, future concern.

- Narrative Memory - the evolution of a specific narrative theme or group over
  time: when it emerged, when it led, when it faded, what replaced it.
- Company Memory - how a specific company's role within narratives has evolved:
  which narratives it has been associated with, and how that association has
  shifted.
- Event Memory - the historical record of scheduled and unscheduled catalysts,
  and how narratives responded to them, building on the deterministic lifecycle
  awareness MNE already applies to events as they happen.
- Economic Memory - the accumulated history of macroeconomic data releases and
  the narrative context surrounding each one.
- Technology Memory - the evolving narrative history of specific technologies
  and technological trends as distinct from the companies that build them.
- AI Memory - a specialized lineage of Technology Memory, given AI's outsized
  and fast-moving role in MNE's current narrative landscape.
- Policy Memory - how policy narratives, monetary, fiscal, and regulatory, have
  developed and shifted over time.
- Competitive Memory - how the relative standing of companies or narratives
  within a shared category has shifted, preserved as a historical record rather
  than a live leaderboard.

These categories are not independent silos; they are different lenses onto the
same underlying preserved intelligence. A single historical moment might be
relevant to Narrative Memory, Company Memory, and Event Memory simultaneously.
The memory layer's job is to preserve the underlying fact once and make it
accessible through whichever lens a future question requires.

## 11. Memory Timeline

At its core, Narrative Memory is organized along a timeline - the same narrative,
the same company, the same event, viewed as a sequence of states rather than a
single snapshot. The Memory Timeline is what allows MNE to answer "how did this
change" rather than only "what is this now."

A timeline, in this architecture, is not a new computation - it is simply memory
read in sequence. Its value comes entirely from the fidelity of what has been
preserved beneath it: a timeline is only as trustworthy as the individual memory
records that compose it, which is why every principle in section 9 exists
upstream of this concept, not the other way around.

## 12. Historical Replay

Historical Replay is the mechanism by which MNE becomes capable of
reconstructing a historical date using archived Evidence Objects, and running its
deterministic intelligence against that archive as though the run were happening
on that day.

Historical Replay exists to answer one question: "What did the world look like
on this date?" Not as MNE understands it in hindsight, but as MNE's deterministic
logic, given the evidence actually available on that date, would have concluded.
This is a subtle but critical distinction from simply reading old headlines:
Historical Replay recreates MNE's actual reasoning process, producing the same
kind of Leadership, Rotation, Pulse, and Regime Alignment output a live run would
have produced, had MNE existed and been watching on that day.

Because Historical Replay shares the same Evidence Object interface as live
ingestion, and because Intelligence systems are deterministic, replaying a
historical date is not an approximation - it is a faithful reconstruction,
bounded only by the completeness of the archived evidence available for that
date. Where evidence is incomplete, that incompleteness itself becomes part of
the historical record, honestly represented rather than smoothed over.

## 13. Narrative Evolution

Narrative Evolution is the story Memory tells once enough Memory Timeline data
accumulates around a single narrative: when it first emerged as identifiable,
when it crossed into dominance, how long it held that position, what specific
pressures or catalysts accelerated or weakened it, and what eventually displaced
it.

This is where Narrative Memory begins to feel less like a database and more like
a history - not because MNE is doing anything beyond faithful recollection, but
because faithful recollection, accumulated honestly over enough time, is what a
history actually is.

## 14. Company Memory

Company Memory tracks how a specific company's relationship to MNE's narrative
landscape has developed: which narrative groups it has been associated with, how
central or peripheral that association has been at different points, and how its
narrative footprint has shifted as the company itself has changed.

Company Memory is deliberately narrative-centric, not fundamentals-centric. It
is not a financial history of the company, but a history of how the company has
featured in the stories MNE has tracked the market telling.

## 15. Event Memory

Event Memory extends the deterministic, phase-aware understanding MNE already
applies to events as they happen, via the Event Lifecycle Engine, into a
permanent historical record: not just how a single CPI release unfolded in real
time, but how the accumulated history of CPI releases, FOMC decisions, and other
recurring catalysts has shaped narrative behavior across many instances of the
same kind of event.

This is where patterns become visible that a single day's Event Lifecycle read
could never show - not through prediction, but through the simple, faithful
accumulation of many honestly recorded instances of the same event type.

## 16. AI Memory

AI Memory exists as its own named category, distinct from the broader Technology
Memory it belongs to, because of the outsized role AI narratives currently play
in MNE's landscape and the unusually fast pace at which that specific narrative
territory evolves. It preserves the evolution of AI-related narrative
leadership, the companies and technologies associated with it, and - in time -
its relationship to Narrative Accountability, where AI-specific claims and
benchmark results can be tracked against later outcomes with the same
deterministic rigor applied everywhere else in this system.

## 17. Economic Memory

Economic Memory preserves the accumulated narrative context surrounding
macroeconomic data over time - not the economic data itself, which belongs to
existing, unchanged systems, but how MNE's narrative intelligence understood and
responded to each release, release after release, building the kind of long-run
context that makes a single day's Catalyst Environment or Event Lifecycle read
richer when viewed against its own history.

## 18. Narrative Accountability

Narrative Accountability is, philosophically, the most sensitive capability
Narrative Memory enables, and it deserves particular care in how it is framed. It
follows a simple, deterministic chain:

```text
Promise
   |
Expectation
   |
Outcome
   |
Evidence
   |
Reality
```

A company, policymaker, or institution makes a promise or sets an expectation.
MNE's narrative intelligence, at the time, records how the market understood that
promise. Time passes. New evidence arrives describing what actually happened.
Narrative Accountability's role is to connect these points into a faithful,
deterministic record - not to render a verdict.

The purpose of Narrative Accountability is historical understanding, not
grading. MNE is not in the business of scoring companies as "right" or "wrong,"
assigning credibility ratings, or issuing judgments. It is in the business of
preserving, with complete fidelity, what was promised, what was expected as a
result, and what evidence later showed actually occurred - so that a human
reviewing that chain can draw their own conclusions, fully informed. This
restraint is not a limitation of the system; it is a deliberate philosophical
choice consistent with every other principle in this document: memory observes
and preserves, it does not judge.

## 19. Future Capabilities

Narrative Memory is the foundation that makes an entire generation of future MNE
capabilities possible as natural extensions rather than independent products
requiring their own architecture:

- Historical Narrative Engine - querying and reconstructing narrative states
  across any past period, powered directly by Historical Replay.
- Narrative Timeline - a user-facing view of Memory Timeline data for a chosen
  narrative, company, or event.
- Company Promise Tracker - a focused application of Narrative Accountability
  scoped to individual companies.
- Narrative Accountability, full product surface - the user-facing realization
  of section 18's philosophy.
- AI Benchmark History - a specialized application of AI Memory, tracking
  benchmark results as a form of accountable evidence over time.
- Competitive Intelligence - built from Competitive Memory, presenting relative
  narrative standing as a historical record.
- Historical Research - ad hoc, exploratory querying of the full Memory layer,
  for questions not anticipated by any specific pre-built feature.
- Long-term Narrative Evolution studies - large-scale, multi-year analyses of
  how narrative structure itself has changed, made possible only because Memory
  has been faithfully accumulating the raw material for that analysis all along.

None of these are independent products bolted onto MNE. Each is what naturally
becomes possible once faithful, deterministic memory has been accumulating long
enough - they are consequences of this architecture, not separate architectures
of their own.

## 20. Architectural Boundaries

Narrative Memory must never:

- Predict markets. Memory is retrospective by definition; forecasting belongs to
  a different, explicitly separate concern that this system does not take on.
- Generate trading signals. No memory record, timeline, or accountability chain
  should ever be framed as actionable advice.
- Invent historical events. Memory records only what evidence and intelligence
  actually produced - it never fills gaps with plausible-sounding fabrication.
- Infer unsupported causality. Memory can show that two things happened near
  each other in time; it must never assert that one caused the other without that
  causal claim being directly traceable to evidence, not to pattern-matching.
- Rewrite historical evidence. Once evidence and the intelligence derived from
  it are recorded, they are not edited to reflect later corrections or improved
  understanding. Corrections, if needed, are appended as new, separately
  timestamped memory, never silent overwrites.
- Depend on machine learning. Every memory operation - recording, timeline
  assembly, replay, accountability chaining - remains rule-based and
  deterministic.
- Depend on LLM reasoning. No generative model interprets, summarizes, or fills
  gaps in memory on MNE's behalf.
- Replace Intelligence. Memory preserves what Intelligence concludes; it never
  becomes a second, competing way of concluding things.

These boundaries exist to keep Narrative Memory trustworthy indefinitely - a
system that remembers faithfully is valuable precisely because it never quietly
becomes something else.

## 21. Non-Goals

To be explicit, separate from the architectural boundaries above, which describe
what Memory must never do, the following are simply outside this document's scope
entirely - not prohibited, just not addressed here:

- Implementation schemas, storage formats, or data models for any Memory Object.
- Specific technology choices for how historical data is stored, indexed, or
  queried.
- The build order or phasing of any Memory capability.
- UI/UX design for any Memory-powered feature.
- Integration specifics with the Source Intelligence Platform beyond the
  conceptual Evidence Object relationship described in section 5.

This document establishes why and what kind of thing Narrative Memory is. The
how belongs to future, separately scoped implementation work, produced only once
this philosophy is settled and agreed upon.

## 22. Long-Term Vision

MNE began as a way to answer a single, recurring question well: what story is the
market telling today. Narrative Memory is what allows that question to accumulate
meaning over years instead of resetting every morning. A platform that only ever
knows today is, however sophisticated, fundamentally amnesiac - it can be right
about the present and still have nothing to say about how the present came to be,
or what it resembles from the past.

The long-term vision for Narrative Memory is not a feature or a product - it is a
permanent architectural commitment that MNE's understanding, once earned, is
never thrown away. Every day's intelligence, faithfully preserved, becomes part
of a growing, deterministic, explainable history - one that future systems,
future researchers, and future versions of MNE itself can draw on without ever
needing to trust anything beyond what was actually observed and actually
concluded, at the time, from real evidence.

This is why MNE should remember: not to predict what comes next, but to make sure
that everything MNE has ever honestly understood remains available, faithfully,
for as long as MNE exists.
