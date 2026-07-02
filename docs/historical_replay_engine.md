# MNE - Historical Replay Engine (HRE)

## Canonical Implementation Reference

Author role: Chief Systems Architect / Technical Director / Product Architect

Position: First operational subsystem of the Narrative Memory System (NMS)

Consumer: ChatGPT (schema/parameter refinement) -> Codex (implementation)

Status: Permanent architecture specification - no code included.

## 1. Product Philosophy

The Narrative Memory System defines why MNE should remember. The Historical
Replay Engine (HRE) is the first system that makes that remembering operational.
It exists to answer one, precisely bounded question:

**"What would MNE have concluded if it had existed on this date?"**

This is deterministic historical reconstruction, not prediction, and the
distinction is architectural, not rhetorical. HRE does not simulate an alternate
past or estimate what "probably" happened. It re-runs MNE's actual, existing,
deterministic intelligence pipeline against evidence that actually existed as of
the replay date, and nothing else. The output is not a guess about history; it is
the same kind of rigorous, explainable conclusion MNE produces every day,
computed for a day that has already passed.

HRE inherits every governing principle already established for Narrative Memory
(determinism, explainability, source-agnosticism, non-prediction, no ML/LLM
dependency) and for the Source Intelligence Platform (evidence as the
standardized unit of input). It adds exactly one new discipline of its own, which
is the philosophical core of this entire document: **temporal integrity** - the
guarantee that a replay of March 3rd can never, under any circumstance, be
influenced by anything MNE learned on March 4th or later.

## 2. Purpose

HRE reconstructs MNE's historical intelligence outputs for any past date by
re-executing the same deterministic Narrative Intelligence pipeline used in live
operation, constrained to only the Evidence Objects that existed at or before
that date. It is the mechanism that gives the rest of the Narrative Memory
System (Memory Timeline, Narrative Evolution, Event Memory, Narrative
Accountability, and everything downstream of them) something real to be built
from: a faithful, reproducible record of what MNE actually would have concluded,
day by day, throughout history.

HRE does not itself build timelines, accountability chains, or knowledge
products. It produces the raw historical intelligence runs those future systems
will consume. Its job ends at "produce a trustworthy historical run"; everything
past that is future, separately scoped work.

## 3. Architectural Overview

HRE sits inside Narrative Memory, downstream of the Source Intelligence Platform,
and reuses, rather than reimplements, the existing Narrative Intelligence
pipeline:

```text
Source Intelligence Platform (SIP)
        |  (standardized Evidence Objects, live + historical connectors)
        v
Historical Evidence Pipeline
        |  (evidence filtered to the replay date's knowledge boundary)
        v
Historical Replay Engine
        |  (orchestrates a replay run against the existing pipeline)
        v
Narrative Intelligence  (Theme/Group Scores, Leadership, Rotation, Pulse,
        |                Dynamics, Crowding, Change Summary, Event Lifecycle,
        |                Market Environment, Breadth, Narrative/Market
        |                Relationship, Regime Alignment - unchanged logic)
        v
Narrative Brief Engine (unchanged logic)
        v
Historical Run Object -> Replay Persistence (isolated from live storage)
        v
Replay Report -> Dashboard / Admin / Historical Research Interface
```

Central design commitment: HRE does not fork or duplicate Narrative Intelligence
or Narrative Brief logic. It orchestrates the same deterministic modules live MNE
uses, supplying them with historically bounded evidence instead of live evidence.
This is what guarantees a replayed date and a live date are computed with
identical rigor. The only thing that differs is which Evidence Objects are
visible to the run.

## 4. Relationship to Narrative Memory

HRE is the first operational subsystem of Narrative Memory, and it exists
specifically to fulfill Narrative Memory's Historical Replay concept, as defined
in the NMS vision document, with a concrete, buildable mechanism. Where the NMS
vision document describes Historical Replay philosophically - "what did the
world look like on this date" - this document defines exactly how that question
gets answered.

HRE produces the material every other Narrative Memory concept depends on:
Memory Timeline entries, Narrative Evolution analysis, Event Memory, Company
Memory, and eventually Narrative Accountability all require a faithful
historical run to draw from. HRE is that faithful historical run, produced on
demand for any requested date. It does not implement any of those downstream
Memory Objects itself. It provides their foundation.

## 5. Relationship to Source Intelligence Platform

HRE consumes only standardized Evidence Objects, as defined by SIP, and depends
on SIP's architectural guarantee that live ingestion and historical
reconstruction share the same Evidence Normalization Layer and the same
deterministic `evidence_id` scheme.

HRE does not read RSS or any other raw source format directly, and it does not
depend on live ingestion being active or available at replay time. Historical
evidence reaching HRE has already been normalized through SIP's pipeline. Whether
that evidence was originally captured live and archived, or reconstructed by a
SIP historical connector built in a future phase, HRE treats it identically,
because both paths converge on the same Evidence Object shape before HRE ever
sees it.

Explicit dependency boundary: HRE's own scope does not include building
historical evidence connectors, such as archival ingestion for dates before
MNE's live capture began. That is SIP's responsibility, scoped separately. HRE
assumes historical Evidence Objects are available to query; it does not produce
them.

## 6. Historical Evidence Pipeline

The Historical Evidence Pipeline is the step that enforces temporal integrity
before any Evidence Object is allowed to reach the replay engine.

Process:

1. Query. For a given replay date `D`, retrieve every persisted Evidence Object,
   live-captured or SIP-historical, whose `timestamp` field is at or before the
   applicable knowledge boundary for `D`.
2. Knowledge boundary definition. The knowledge boundary is the precise cutoff
   instant defining "what MNE could have known" - by default, end-of-day, or a
   configurable specific time, on date `D` itself, in a fixed reference timezone
   consistent with the timezone discipline already established for the Event
   Lifecycle Engine. This boundary is a required, explicit parameter of every
   replay request, not an implicit assumption.
3. Strict filtering. Any Evidence Object with a `timestamp` after the knowledge
   boundary is excluded absolutely. There is no soft inclusion, no partial
   credit, no relevance-based override. This filtering step is the single most
   important gate in this entire architecture.
4. Freshness/health reapplication. SIP's Feed Health and Freshness Validation
   states, as they were recorded on the original object or reconstructed for
   archival evidence, are preserved and consumed by replay exactly as they would
   have been consumed live. A historically stale object is treated as stale in
   replay, exactly as it would have been treated as stale had MNE run live on
   that date.
5. Output. A bounded, immutable Evidence Object set - the exact evidence universe
   visible to the replay run - is handed to the Historical Replay Engine.

This pipeline is deliberately isolated as its own step, separate from the replay
engine itself, so that "what evidence was visible" is independently inspectable
and independently testable from "what conclusions were drawn from it."

## 7. Replay Engine

The Replay Engine is the orchestration layer that takes a bounded Evidence
Object set and a replay date, and drives it through the existing, unmodified
Narrative Intelligence pipeline exactly as a live run would be driven,
substituting only the evidence source.

Responsibilities:

- Accept a replay request specifying the target date and knowledge boundary.
- Invoke the Historical Evidence Pipeline to obtain the bounded evidence set.
- Invoke each existing Narrative Intelligence module in the same sequence and
  with the same interfaces a live run uses, supplying the bounded evidence set in
  place of live evidence.
- Collect each module's output into a Historical Run Object.
- Hand the completed run to Replay Persistence - never to live run storage.

What the Replay Engine explicitly does not do: it does not contain narrative
scoring logic, taxonomy logic, or any independent judgment about the evidence. It
is a pure orchestrator. Every actual conclusion is produced by the same modules
that produce live conclusions. This is what guarantees a replay and a live run
are computed with identical logic, differing only in evidence visibility.

## 8. Replay Inputs

A replay request requires:

- `replay_date` - the historical date being reconstructed.
- `knowledge_boundary` - the explicit cutoff instant, defaulting to end-of-day
  on `replay_date` in the fixed reference timezone if not otherwise specified.
- `taxonomy_version` - optional, defaults to the taxonomy version that was active
  as of `replay_date`, if known and versioned; otherwise the earliest available
  version.
- `replay_version` - the version identifier of the HRE orchestration logic
  itself performing the replay, distinct from taxonomy version.

Replay Inputs are deliberately minimal and explicit. No implicit "current
settings" leak into a replay request. Anything that could affect the outcome of
a replay must be an explicit, recorded parameter of that replay, because those
parameters are exactly what makes a replay reproducible and auditable.

## 9. Replay Outputs

A completed replay produces deterministic historical versions of the same output
set live MNE produces for a given day:

- Theme Scores
- Group Scores
- Narrative Leadership
- Leadership Rotation
- Narrative Pulse
- Narrative Dynamics
- Narrative Crowding
- Change Summary
- Event Lifecycle
- Market Environment
- Breadth Confirmation
- Narrative / Market Relationship
- Regime Alignment
- Narrative Brief

Structural fidelity requirement: each of these outputs should match the
schema/shape of its live-run counterpart wherever practical, so that any tooling
built to read live run JSON, including dashboards, admin diagnostics, and future
Memory consumers, can read a Historical Run Object with minimal or no adaptation.
Where a live output depends on something structurally unavailable in a historical
context, for example Change Summary's normal "since last run" comparison, that
dependency must be explicitly and honestly represented in the output rather than
silently omitted or fabricated.

## 10. Replay Persistence

Hard rule: Historical Replay must never overwrite, merge with, or be stored
alongside live run history. This is a direct extension of the Historical
Compatibility boundary already established in the SIP architecture, applied
specifically to replay outputs.

Persistence model:

- Historical Run Objects are persisted in a storage namespace/path structurally
  and physically separate from the live daily run/snapshot path - never the same
  directory, never the same file naming convention, never reachable by any
  live-run reader without an explicit, deliberate namespace switch.
- Each Historical Run Object is content-addressed or otherwise uniquely keyed by
  the combination of `replay_date` + `knowledge_boundary` + `replay_version` +
  `taxonomy_version`, so that re-running an identical replay request resolves to
  the same stored object rather than silently duplicating it.
- Multiple replay runs for the same `replay_date` under different parameters,
  such as a different `knowledge_boundary`, or a re-run under a newer
  `replay_version` after HRE itself has been improved, are persisted as distinct
  Historical Run Objects, not overwrites of one another. This preserves the
  ability to compare how replay fidelity itself has evolved, without ever
  destroying an earlier replay's record.
- No live run's daily snapshot mechanism is modified, extended, or touched by
  this persistence model in any way.

## 11. Historical Run Objects

The Historical Run Object is the persisted unit produced by a completed replay -
conceptually the historical analogue of a live daily run/snapshot, but explicitly
namespaced as historical.

Required metadata carried by every Historical Run Object:

- `replay_date` - the date being reconstructed.
- `evidence_range` - the actual span of Evidence Object timestamps that were
  available and used. This may be narrower than expected if historical evidence
  is incomplete.
- `taxonomy_version` - which version of MNE's theme taxonomy was used for this
  replay.
- `replay_version` - which version of the HRE orchestration logic performed this
  replay.
- `source_confidence` - the SIP-defined confidence rating computed against the
  historically bounded evidence set, describing how much trust to place in the
  ingestion quality of the evidence used.
- `evidence_confidence` - a distinct rating describing how complete the
  historical evidence record itself is for this date. A date reconstructed from a
  rich, well-archived evidence set rates differently than a sparsely archived
  early date. This must not be conflated with `source_confidence`, which
  describes health/freshness/coverage mechanics rather than archival
  completeness.
- `reconstruction_completeness` - an explicit, honest statement of how complete
  this replay is believed to be relative to what a live run on that date would
  have captured, such as "Full," "Partial - evidence gaps detected," or
  "Minimal - sparse archive," with supporting detail.

Body: the full set of Replay Outputs, structured to mirror live run output shape
wherever practical.

Every Historical Run Object is a complete, self-contained, honestly labeled
record. A future reader must never need to guess how trustworthy or complete a
given historical reconstruction is; that information is always attached directly
to the object.

## 12. Replay Determinism

Two identical replay requests must always produce identical results. Given the
same `replay_date`, `knowledge_boundary`, `taxonomy_version`, and
`replay_version`, HRE must produce byte-for-byte identical Historical Run Objects
(timestamps of the replay execution itself aside), regardless of when the replay
is actually run, or how many times.

This requires three specific disciplines:

1. Evidence set stability. The Historical Evidence Pipeline's query must be
   reproducible. Querying for the same date/boundary must return the same
   Evidence Object set every time, which in turn requires that persisted Evidence
   Objects are themselves immutable once stored, a guarantee inherited from SIP's
   architecture, and that the deterministic `evidence_id` hashing scheme prevents
   any ambiguity about which objects belong to which query result.
2. Pipeline logic stability within a `replay_version`. As long as
   `replay_version` and `taxonomy_version` are held constant, the Narrative
   Intelligence modules invoked by the Replay Engine must behave identically
   across executions. This is already guaranteed by those modules' own existing
   determinism requirements; HRE does not need to re-guarantee it, only avoid
   breaking it.
3. No hidden environmental inputs. The Replay Engine must not allow any implicit
   "current state," such as today's date, today's registry version, or today's
   taxonomy, to leak into a replay run. Every input that could affect the outcome
   is an explicit, recorded Replay Input.

Versioning, not overwriting, is how determinism coexists with improvement. When
HRE's own logic or the underlying taxonomy legitimately improves over time,
replaying the same historical date under the new `replay_version` or
`taxonomy_version` produces a new, separately persisted Historical Run Object
rather than silently changing the meaning of the old one. Determinism is scoped
to "same parameters, same result." It is not a claim that history can never be
reconstructed better in the future, only that any such improvement is itself a
new, honestly versioned record.

## 13. Historical Confidence

Historical Confidence extends SIP's Source Confidence concept into the replay
context, and is deliberately split into the two distinct metadata fields already
introduced in section 11, because they answer different questions:

- `source_confidence` answers: given the evidence we have for this date, how
  healthy, fresh, and well-covered was it, mechanically speaking? This is the
  same kind of question SIP already answers for live runs, applied to the
  historically bounded set.
- `evidence_confidence` answers a question that has no live-run equivalent: how
  complete is our archival record of this date at all? A date reconstructed
  shortly after MNE began systematically archiving evidence will typically rate
  higher than a date reconstructed from sparse, retroactively gathered sources.

Both ratings use the same deterministic, rule-based, registry-configurable
approach already established for Source Confidence in SIP: no machine learning,
no subjective judgment, and every rating accompanied by a specific, inspectable
reason.

Why this distinction matters: a future consumer of a Historical Run Object, such
as a Narrative Timeline or Accountability chain, needs to know not just "was the
evidence for this date good evidence" but "do we actually have enough evidence
for this date to trust the reconstruction at all." Conflating these two
questions into one score would hide exactly the information a careful historical
researcher needs most.

## 14. Replay Verification

Verification procedures ensuring replay accuracy and fidelity to the
architecture's guarantees:

| # | Test | Verifies |
|---|---|---|
| 1 | Replay a recent historical date for which a live run already exists; compare outputs | Replay output structurally and substantively matches the original live run's output, allowing only for legitimate, versioned improvements made to Narrative Intelligence since. Differences must be explainable by version, not by defect. |
| 2 | Run the identical replay request, using the same four key parameters, twice | Byte-for-byte identical Historical Run Objects produced - direct test of replay determinism. |
| 3 | Inject an Evidence Object timestamped one minute after the knowledge boundary into the archive, then replay | The injected object is absolutely excluded from the resulting Historical Run Object and from all computed outputs - direct test of temporal integrity. |
| 4 | Replay a date for which the archived evidence is deliberately sparse/incomplete | `evidence_confidence` and `reconstruction_completeness` honestly reflect the gap; outputs are still produced, consistent with SIP's "continue operating on partial data" philosophy, but clearly labeled as less complete. |
| 5 | Replay two different dates and confirm persisted Historical Run Objects never collide or overwrite each other, and confirm neither touches live run storage | Direct test of persistence isolation. |
| 6 | Re-run a previously replayed date under a new `replay_version` after a legitimate HRE logic change | A new, separate Historical Run Object is created; the original replay's record remains unchanged and independently retrievable. |
| 7 | Attempt to replay a date using a `knowledge_boundary` earlier than any available evidence exists | HRE produces a well-formed Historical Run Object with `reconstruction_completeness = "Minimal"` or equivalent and an empty or near-empty evidence set, rather than failing silently or fabricating output. |

## 15. Dashboard Integration

Users should eventually be able to request a historical replay directly from the
dashboard, conceptually as follows: a user selects a past date, bounded by the
earliest date for which archived evidence exists, optionally reviews or accepts
the default knowledge boundary, and requests a replay. Once complete, the
resulting Historical Run Object renders using the same visual components already
built for live runs - Narrative Brief, Leadership, Rotation, Pulse, Regime
Alignment, and event markers - with a clear, persistent visual indicator, such as
a banner or badge, that the view is a historical reconstruction, not a live read,
alongside its `reconstruction_completeness` and confidence ratings surfaced
plainly.

This reuse of live-run visual components is only possible because of the
structural fidelity requirement established in section 9. HRE's output shape
mirrors live output shape specifically so this integration requires minimal
bespoke UI work. Full dashboard replay-request UX, including queueing, progress
indication for longer replays, and historical date-range browsing, is
implementation detail deferred to the future phase that actually builds this
integration. This section establishes the intended user experience, not its build
spec.

## 16. Admin Interface

Admin-facing replay tooling should expose:

- Replay request console - ability to trigger a replay for any
  date/knowledge-boundary/version combination, primarily for testing, backfill,
  and verification purposes.
- Historical Evidence Pipeline inspection - for a given replay, the exact
  bounded Evidence Object set that was visible to the run, independently
  viewable from the resulting conclusions.
- Historical Run Object browser - full metadata and full output inspection for
  any persisted replay, filterable by date, `replay_version`, and confidence
  ratings.
- Version comparison view - for a date replayed under multiple
  `replay_version`/`taxonomy_version` combinations, a side-by-side comparison of
  how the reconstruction changed across versions, directly surfacing the
  "versioning, not overwriting" principle.
- Temporal integrity audit tooling - a way to explicitly confirm, for any given
  replay, that no Evidence Object used exceeded the knowledge boundary; this
  should be a first-class, easily run check, not something requiring manual JSON
  inspection.

## 17. Historical Research Interface

Distinct from the admin interface, which is oriented toward operating and
verifying HRE itself, a Historical Research Interface is the future-facing
surface through which a researcher, human or a future MNE Knowledge system,
queries accumulated Historical Run Objects to ask open-ended historical
questions, such as "show me every date AI narrative leadership exceeded X" or
"compare regime alignment across the last five CPI releases."

This document establishes that such an interface is a natural, anticipated
consumer of HRE's persisted output, and that HRE's persistence model is
deliberately structured, with stable keys, complete metadata, and structurally
consistent output shape, to make that future interface straightforward to build.
Building the Historical Research Interface itself is explicitly out of scope for
this document. It is named here only to establish that HRE's design has already
accounted for it.

## 18. Architectural Boundaries

The Historical Replay Engine must never:

- Predict markets. HRE reconstructs the past; it does not project or infer the
  future in any form.
- Rewrite history. Once a Historical Run Object is persisted, it is never edited
  in place. Corrections or improvements produce a new, separately versioned
  object, never a silent overwrite.
- Infer unseen information. If evidence for a given date is incomplete, HRE
  represents that incompleteness honestly rather than filling gaps with plausible
  sounding inference.
- Use future evidence. This is the single most important boundary in this
  document: no Evidence Object timestamped after the knowledge boundary may,
  under any circumstance, influence a replay's output. This is enforced
  structurally at the Historical Evidence Pipeline, not merely as a policy. The
  pipeline's filtering step is the sole gate through which evidence reaches the
  replay engine, and it admits nothing past the boundary.
- Modify live data. No replay operation writes to, reads from for comparison
  purposes in a way that could leak back, or in any way alters live run/snapshot
  storage.
- Replace live intelligence. HRE produces historical reconstructions for past
  dates; it has no role in, and must never be invoked as part of, MNE's live daily
  intelligence pipeline.

A note on cross-boundary comparisons, Change Summary: because live Change
Summary logic normally compares "today" against "yesterday," replaying a single
isolated historical date raises the question of what it compares against. The
correct handling is that replay, when reconstructing a sequence of consecutive
historical dates, allows Change Summary to compare consecutive Historical Run
Objects to each other, never against live data. A single, isolated replay of one
date with no adjacent historical run available should honestly represent Change
Summary as unavailable/not-applicable for that run, rather than fabricating a
comparison or reaching into live data to produce one.

## 19. Non-Goals

- No prediction of any kind, anywhere in HRE.
- No historical evidence connectors. Building the actual archival ingestion
  mechanisms that supply historical Evidence Objects to SIP is explicitly SIP's
  scope, not HRE's.
- No changes to Narrative Intelligence or Narrative Brief logic. HRE
  orchestrates existing modules; it does not modify, fork, or extend their
  internal logic in any way.
- No Memory Timeline, Narrative Evolution, Company Memory, Event Memory, or
  Narrative Accountability implementation. HRE produces the raw material those
  future Narrative Memory capabilities will consume; building them is separately
  scoped, future work.
- No Historical Research Interface implementation. Its future existence is
  acknowledged, but its construction is out of scope here.
- No machine learning or LLM dependency anywhere in replay orchestration,
  evidence filtering, or confidence computation.
- No live dashboard/admin UI implementation in this phase. Sections 15 and 16
  describe intended experience and required capability, not a build spec; actual
  UI construction is a separately scoped future pass once HRE's backend is
  stable.
- No bulk/automatic backfill of all historical dates in this phase. This
  document defines the mechanism by which any single date can be replayed on
  demand; systematically replaying MNE's entire historical range is a distinct,
  much larger future initiative, not part of this handoff.

## 20. Future Evolution

Historical Replay is the foundation every other Narrative Memory capability
depends on:

- Narrative Timeline - a sequence of consecutive Historical Run Objects and, at
  the leading edge, live runs read in order becomes a timeline directly. HRE is
  what makes each point in that sequence trustworthy.
- Company Promise Tracker and Narrative Accountability - the "Outcome" and
  "Reality" stages of the Promise -> Expectation -> Outcome -> Evidence ->
  Reality chain described in the NMS vision document require exactly the kind of
  faithful, dated reconstruction HRE provides. A promise's stated expectation,
  and the later, independently replayed reality against which it is compared,
  both need to be genuine historical reconstructions, not retrospective guesses.
- AI Benchmark History - replaying dates around specific AI benchmark releases
  lets this future capability show not just the benchmark result but the
  narrative context MNE actually understood at that moment.
- Competitive Intelligence - comparing companies' relative narrative standing
  over time requires exactly the kind of consistent, versioned historical
  reconstruction HRE guarantees.
- Historical Research - the open-ended research interface is a direct, natural
  consumer of HRE's persisted, richly metadated output.
- Narrative Memory broadly - every Memory Object concept defined in the NMS
  vision document (Narrative Memory, Company Memory, Event Memory, Economic
  Memory, Technology/AI Memory, Policy Memory, Competitive Memory) becomes
  buildable specifically because HRE exists to produce the faithful historical
  runs those objects are built from.

None of these are independent systems bolted onto HRE. They are what naturally
becomes possible once a trustworthy, deterministic, temporally honest replay
mechanism exists and has been proven correct. HRE's entire value, long-term, is
in being boring, correct, and unshakeably faithful to the evidence that actually
existed on each date it reconstructs. Every future capability above inherits
that trustworthiness for free, precisely because it never has to re-establish it
independently.
