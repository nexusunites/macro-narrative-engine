# MNE - Historical Evidence Backfill Architecture

## Canonical Implementation Reference

Author role: Technical Director / Systems Architect / Data Architect / Source
Intelligence Architect

Position: Source Intelligence Platform (SIP)-side companion to the Historical
Replay Engine (HRE) - supplies the historical Evidence Objects HRE's own
architecture explicitly declines to produce.

Status: Architecture specification only. No code included, no connectors
implemented, no data fetched.

---

## 1. Purpose

`docs/historical_replay_engine.md` (HRE) already draws its own scope boundary
precisely: HRE "does not itself build historical evidence connectors, such as
archival ingestion for dates before MNE's live capture began... HRE assumes
historical Evidence Objects are available to query; it does not produce them"
(HRE Section 5), and lists "No historical evidence connectors" as an explicit
Non-Goal (HRE Section 19). This document is that named, deferred scope. It
defines the architecture for **Historical Evidence Backfill**: the mechanism by
which SIP reconstructs historical Evidence Objects, on demand, for dates MNE
did not capture live, so that HRE has something real to replay against for
those dates.

This document answers one question:

**"How can MNE reconstruct historical evidence for a requested date or range
without storing every article from all history upfront?"**

It is architecture only. No connector is implemented, no historical data is
fetched, and no code in `mne/historical_replay.py`, `mne/source_registry.py`,
or anywhere else changes as part of this document.

---

## 2. Product Requirement

A marketable historical comparison feature cannot be limited to the narrow set
of dates on which MNE happened to already be running and persisting live
runs. Today, confirmed by direct reading of `mne/historical_replay.py`,
`load_historical_run_records()` reads only already-persisted live run JSON
files from the results directory, and `select_historical_evidence()` filters
each run's already-accepted evidence by publish/ingestion cutoff. There is no
path today by which evidence for a date MNE did not run on can enter a replay.
Historical Replay is real and correct for the dates it has data for; it simply
has no data for any other date.

Historical Evidence Backfill closes that gap **without** requiring MNE to
store or fetch the entire historical internet up front. It supplies evidence
lazily, one requested date/range at a time, from a deliberately small set of
approved, structured historical sources - reusing the exact same Evidence
Object shape, the exact same Historical Evidence Pipeline cutoff discipline,
and the exact same Historical Replay Engine that already exist.

---

## 3. Backfill vs. Stored MNE History

Two different things must not be conflated, and this document treats them as
architecturally distinct at every layer:

| | **Stored MNE History** | **Historical Evidence Backfill** |
|---|---|---|
| Source | MNE's own live daily runs, captured as they happened | Approved historical sources, reconstructed after the fact |
| Path today | `RESULTS_DIR` (live run snapshots), read by `load_historical_run_records()` | New, separate on-demand reconstruction path (this document) |
| Coverage | Only dates MNE was actually running | Any date within a supported historical source's date range |
| Trust character | "Evidence MNE actually observed live" | "Evidence a historical source now reports as having existed then" - honestly labeled as reconstructed, never presented as identical in kind to live capture |
| Storage discipline | Whatever MNE already persists per live run | Deliberately minimal, on-demand, reused across requests (Section 8) |

Backfilled evidence, once normalized, converges on the **same Evidence Object
shape** used by live capture (Section 7) - this is the same convergence
guarantee HRE Section 5 already describes for "a SIP historical connector
built in a future phase." Once that convergence happens, Historical Replay
treats backfilled evidence identically to live-captured evidence. What is
different, and must stay visibly different, is the *provenance* attached to
that evidence (`evidence_origin`, Section 7) and the *honesty* of what is
claimed about coverage (Section 12). Backfill does not, and must not, attempt
to make historical evidence indistinguishable from live evidence in its
metadata - only structurally interchangeable in shape.

Explicit non-goal restated: this document does not propose storing MNE's
entire addressable historical range up front. Coverage is built lazily,
request by request, and cached for reuse (Section 9).

---

## 4. Supported Historical Source Model

Historical sources are registered separately from (but structurally parallel
to) the live Source Registry (`config/source_registry.json`, confirmed schema:
`source_id`, `display_name`, `provider`, `category`, `priority`,
`ingestion_type`, `supported_evidence_types`, `url`, `status`,
`freshness_threshold_minutes`, `expected_update_frequency_minutes`,
`supported_narratives`). Historical sources need several fields the live
registry has no reason to carry (an RSS feed has no "date range supported" -
it only has "now"), so this document proposes a distinct
**Historical Source Registry** model rather than overloading the live schema:

```
source_id                    - stable identifier, same discipline as live source_id
provider                     - publisher/institution name
category                     - same category vocabulary as the live registry
                                (e.g. "Central Bank Communications", "Market Structure")
date_range_supported         - { "earliest": <ISO date>, "latest": <ISO date | "present"> }
access_method                - e.g. "public archive HTTP", "public API", "licensed feed"
storage_permissions          - what MNE is allowed to retain: NONE / METADATA_ONLY /
                                NORMALIZED_EVIDENCE / FULL_TEXT (maps to Section 8 tiers)
evidence_fields_available    - which of the connector contract's fields (Section 5)
                                this source can actually populate
rate_limits                  - requests per unit time, concurrency ceiling
reliability_notes            - known gaps, format-change history, archive completeness caveats
legal_storage_notes           - licensing terms, attribution requirements, retention limits
status                       - APPROVED / UNDER_REVIEW / DISABLED (same status discipline
                                as the live registry's ENABLED/DISABLED convention)
```

A historical source only becomes usable by a backfill job once it is
`APPROVED` in this registry - mirroring the live registry's existing
discipline of an explicit, inspectable source list rather than ad hoc fetching.
This registry is itself a config artifact (conceptually
`config/historical_source_registry.json`), not code; defining its shape here
does not create the file.

---

## 5. Backfill Request Model

```
backfill_id            - stable identifier, e.g. "backfill_{date}_{mode}_{sources_hash}"
requested_date         - single date, OR:
requested_range        - { "start": <ISO date>, "end": <ISO date> }  (optional, mutually
                          exclusive with requested_date at the request level)
narrative_mode         - "macro" only for now, matching HRE's SUPPORTED_MODE constant
                          in mne/historical_replay.py (no expansion of replay modes here)
source_categories      - optional filter; defaults to all APPROVED historical sources
evidence_cutoff        - same semantics as HRE's knowledge_boundary: the latest instant
                          of evidence eligible for this date, defaulting to end-of-day
                          on the requested date in the same fixed reference timezone
                          HRE already uses
status                 - PENDING / RUNNING / COMPLETE / PARTIAL / FAILED
```

A backfill request is a request to *populate the evidence store* for a
date/range - it is explicitly not itself a replay request. It produces
replay-eligible evidence; it does not run Historical Replay (Section 10 keeps
these two steps decoupled, matching HRE's own separation of the Historical
Evidence Pipeline from the Replay Engine).

---

## 6. Historical Source Connector Contract

A connector is anything that turns one approved historical source's raw
records into the normalized shape below. This document defines the contract;
it does not implement any connector.

Normalized record (connector output, pre-evidence-normalization):

```
title / headline
source                 - historical source_id from the Historical Source Registry
provider
published_at           - the record's original publication timestamp, not retrieval time
url / reference         - permanent reference, may be a citation rather than a live URL
snippet / summary       - only if legally available under that source's storage_permissions
category
source_type             - e.g. "central_bank_communication", "government_publication"
raw_id / reference_id   - the connector's own stable identifier for this record, distinct
                          from MNE's evidence_id (needed for idempotent re-runs, Section 9)
retrieval_timestamp     - when MNE's backfill job actually fetched this record
usage_storage_rights    - flag echoing the source's storage_permissions, carried per-record
                          so downstream normalization never has to re-derive it
```

A connector must never return full copyrighted article bodies unless the
source's `storage_permissions` in the Historical Source Registry explicitly
allows it (Section 8, Tier 3). A connector must not attempt to bypass a
paywall or access restriction to obtain a record.

---

## 7. Evidence Normalization

Backfilled normalized records become MNE `EvidenceObject`s using the exact
same dataclass already defined in `mne/evidence.py` - no schema change to
`EvidenceObject` is proposed or required:

```python
evidence_id, source_id, source_name, evidence_type, timestamp, title, summary,
url, metadata: dict, accepted, rejection_reason, freshness_state,
freshness_age_minutes, freshness_checked_at
```

Mapping from the connector contract (Section 6):

- `timestamp` <- connector's `published_at` (publication time is preserved
  exactly; never overwritten with `retrieval_timestamp`).
- `source_id`, `source_name`, `url`, `title` <- direct mapping.
- `evidence_type` <- derived from the connector's `source_type`/`category`,
  consistent with the live registry's `supported_evidence_types` vocabulary.
- `summary` <- connector's `snippet/summary`, only when `usage_storage_rights`
  permits retention beyond metadata (Section 8).
- `metadata` (already a free-form dict on `EvidenceObject` - **this is the
  exact, no-schema-change extension point this document relies on**) carries:
  ```
  evidence_origin: "HISTORICAL_BACKFILL"
  backfill_id
  connector_source_id       (the historical source_id, Section 4)
  raw_id                    (connector's reference_id, for idempotency)
  retrieval_timestamp
  usage_storage_rights
  ```

Hard requirements, all directly testable once implementation begins:

- Publication timestamp, source/provider, and URL/reference are always
  preserved - never fabricated, never left blank when the connector supplied
  them.
- `evidence_origin = "HISTORICAL_BACKFILL"` and `backfill_id` are always
  present in `metadata` - this is what lets any downstream reader (HRE, Admin,
  a future Historical Comparison View) distinguish backfilled evidence from
  live-captured evidence without guessing, and is exactly the kind of honest
  provenance HRE Section 11's `evidence_confidence` field is designed to
  consume.
- Backfilled evidence must never claim or imply it was collected live by
  MNE's own RSS ingestion (no `HISTORICAL_BACKFILL` record is ever mixed into
  `RESULTS_DIR` or presented as a live run's own accepted evidence).
- Enough metadata survives normalization that a later temporal-integrity audit
  (HRE Section 16) can verify a piece of backfilled evidence the same way it
  verifies live evidence: by inspecting `timestamp` against the replay
  knowledge boundary, nothing more privileged.

---

## 8. Storage Model

Three tiers, matching the product brief's requested structure:

- **Tier 1 - Replay output only.** No normalized evidence retained; only the
  eventual Historical Run Object (already covered by HRE's own persistence
  model, isolated under `MNE_DATA_DIR/replays/`). Cheapest, but every re-replay
  requires re-fetching from the historical source, and no other consumer can
  inspect the underlying evidence.
- **Tier 2 - Normalized evidence objects + replay output (default).**
  Normalized `EvidenceObject`s (Section 7) are persisted in a new, dedicated
  namespace - proposed `MNE_DATA_DIR/historical_evidence/{backfill_id}/` -
  physically and structurally separate from both `RESULTS_DIR` (live) and
  `MNE_DATA_DIR/replays/` (replay output), matching HRE's existing discipline
  of never mixing storage namespaces across concerns. This is what makes
  reconstructed dates reusable without re-fetching, and what a future
  Historical Comparison View or Historical Research Interface would actually
  query.
- **Tier 3 - Full content, only when legally allowed/licensed.** Full article
  bodies retained only for sources whose Historical Source Registry entry
  explicitly grants `FULL_TEXT` storage permission. This tier is opt-in per
  source, never a default, and never applies to sources without an explicit,
  recorded legal basis.

**Default is Tier 2.** MNE does not store full copyrighted article bodies
unless a specific source's registry entry allows it. Tier 2 is sufficient for
every currently-scoped consumer (Historical Replay, Admin inspection, a future
comparison view) because Historical Replay itself only ever needed
normalized `EvidenceObject`s, never full article text, even for live runs.

---

## 9. Backfill Cache / Manifest

Before running a new backfill job, MNE must be able to answer "has this
date/range already been reconstructed?" without re-fetching. A **backfill
manifest** answers this, one per `backfill_id`, stored alongside the Tier 2
evidence namespace (`MNE_DATA_DIR/historical_evidence/{backfill_id}/manifest.json`):

```
backfill_id
requested_date / requested_range
source_coverage           - which Historical Source Registry sources actually
                            contributed records for this backfill, and which
                            approved sources returned nothing
date_range_reconstructed  - the actual span of evidence obtained, which may be
                            narrower than requested (mirrors HRE's own
                            evidence_range honesty discipline, Section 11 of
                            the HRE doc)
evidence_count
replay_artifact_link      - populated once Historical Replay has actually been
                            run against this backfill's evidence (Section 10);
                            null if backfill has occurred but replay has not
warnings                  - sparse coverage, connector failures, partial dates
generated_at
source_limitations        - carried forward from each contributing source's
                            reliability_notes/legal_storage_notes (Section 4)
```

A new backfill request for a date/range that already has a manifest with
adequate `source_coverage` should be served from the existing manifest and
Tier 2 evidence rather than re-running connectors - this is the "cache" the
product brief asks for. Re-fetching should be an explicit, deliberate action
(e.g. a registry version change, a new approved source, or an explicit
refresh request), never an implicit side effect of asking for the same date
twice.

---

## 10. Integration with Historical Replay

Backfill and Historical Replay stay strictly decoupled, matching HRE's own
internal separation of "Historical Evidence Pipeline" from "Replay Engine":

1. Backfill's only job is to make replay-eligible `EvidenceObject`s exist
   somewhere Historical Replay can read them from - it never invokes replay
   itself, and it never modifies `mne/historical_replay.py`.
2. Backfilled evidence must obey the exact same cutoff discipline
   `select_historical_evidence()` already enforces for live-run evidence:
   `published_at` at or before the replay's `evidence_cutoff`, no future
   evidence, deduplication by `evidence_id`. No new cutoff rule is invented for
   backfilled evidence; it is the same rule, applied to a new evidence source.
3. Historical Replay remains the only replay engine. Once backfilled evidence
   exists in the Tier 2 namespace, running a replay for that date is the same
   `run_historical_replay()` call already implemented - the only change
   required (in a future implementation sprint, not this one) is that
   `load_historical_run_records()`'s evidence-gathering step needs to also be
   able to read from `MNE_DATA_DIR/historical_evidence/` in addition to
   `RESULTS_DIR`. This document does not implement that change; it only
   establishes that the integration point is additive (a second evidence
   source feeding the same selection/cutoff logic), not a fork of replay
   logic.
4. Replay output remains isolated under `MNE_DATA_DIR/replays/`, exactly as
   HRE's persistence model already requires. Backfill never writes into that
   directory; it only supplies the evidence a subsequent, separate replay run
   consumes.
5. A Historical Run Object produced from backfilled evidence should populate
   HRE's existing `evidence_confidence`/`reconstruction_completeness` fields
   (HRE Section 11) using the backfill manifest's `source_coverage` and
   `warnings` - this document does not change how those fields are computed,
   only notes that backfill is a natural, intended input to them.

---

## 11. First MVP Source: Fed / FOMC Historical Communications

Recommended first supported historical source/category: **Federal
Reserve / FOMC historical communications** (statements, minutes, press
conference transcripts).

Why this is the right first source:

- **Public.** No paywall, no licensing negotiation required to begin
  (`access_method = "public archive HTTP"`, `storage_permissions` can
  reasonably be `NORMALIZED_EVIDENCE` or better for the structured portions).
- **Macro-relevant.** Directly feeds the narratives MNE already scores highly
  on - rates, inflation, growth - with unusually strong signal density per
  document compared to general news.
- **Structured enough.** FOMC communications are published on a known,
  regular schedule with consistent formatting across years, which is exactly
  the property that makes a connector tractable without heavy per-record
  cleanup - unlike general news archives, which vary wildly by outlet and era.
- **Avoids news/paywall complexity entirely for the first implementation.**
  General news backfill (the eventual larger goal) inherits every risk in
  Section 13; Fed/FOMC communications sidestep nearly all of them, making this
  the correct low-risk first connector to validate the whole architecture
  against before extending to harder sources.

---

## 12. User-Facing Coverage Language

Historical coverage must be represented honestly, never oversold. Approved
phrasing patterns:

- "Historical reconstruction available for supported sources."
- "This date has partial historical coverage."
- "No supported historical source coverage available for this date yet."

Prohibited phrasing, anywhere in the product:

- "All market history available"
- "Complete historical news reconstruction"
- "Every article since 2000"

This mirrors HRE's own existing discipline (HRE Section 11,
`reconstruction_completeness`: "Full," "Partial - evidence gaps detected,"
"Minimal - sparse archive") - Backfill's coverage language is the pre-replay
analogue of that same honesty requirement, not a new standard invented for
this document.

---

## 13. Risks and Constraints

- **Legal/storage rights.** Every source's storage tier (Section 8) must be
  backed by an explicit legal basis recorded in its Historical Source Registry
  entry (`legal_storage_notes`); default to the most conservative tier when
  uncertain.
- **Paywalled news.** Out of scope for the MVP source and likely for any near-
  term connector; if ever pursued, requires a licensing decision, not a
  technical workaround. No paywall bypass, ever.
- **Incomplete archives.** Historical sources may have gaps; the manifest's
  `date_range_reconstructed` and `warnings` fields exist specifically to
  surface this rather than silently under-report.
- **Source bias.** A single-source backfill (e.g. Fed-only for a given date)
  produces a narrower narrative signal than live MNE's multi-provider network;
  `source_coverage` in the manifest should make this legible so downstream
  consumers do not mistake single-source depth for network breadth.
- **Historical taxonomy drift.** Theme/group taxonomy has evolved and will
  keep evolving; replaying old dates against current taxonomy is already an
  HRE-level concern (HRE's `taxonomy_version` replay input), not something
  Backfill needs to solve independently - Backfill only needs to supply
  evidence, tagged with enough metadata that whichever taxonomy version
  replay uses can still process it.
- **Changing source formats.** Connectors are inherently fragile to upstream
  format changes; `reliability_notes` in the Historical Source Registry is the
  place this gets tracked, and connector failures should degrade to `PARTIAL`
  backfill status, never a silent empty result presented as complete.
- **Date/time normalization.** Historical publication timestamps may lack
  timezone information or use inconsistent formats across eras; normalization
  must resolve every timestamp to the same fixed reference timezone HRE
  already requires, and must not guess when genuinely ambiguous - honest
  omission over fabricated precision.
- **Duplicate records.** A connector re-run (e.g. cache refresh) must not
  produce duplicate `EvidenceObject`s; `raw_id`/`reference_id` (Section 6) is
  the connector-side idempotency key, and `evidence_id`'s existing
  deterministic hashing scheme is the MNE-side dedup guarantee, unchanged.
- **Cost/rate limits.** Historical Source Registry's `rate_limits` field
  exists specifically so backfill jobs respect source-imposed ceilings rather
  than discovering them via failures.
- **Evidence quality warnings.** Sparse, single-source, or partial-coverage
  backfills must produce visible warnings in the manifest - never a
  confidence-inflating result for a thin reconstruction.

---

## 14. Open Questions

- Should `backfill_id` be keyed only by date/range/mode/source-set, or should
  it also embed a Historical Source Registry version, the way HRE keys replay
  objects by `taxonomy_version`/`replay_version`? (Recommendation: yes, for
  the same reproducibility reason HRE already requires this - deferred to
  implementation sprint for final field naming.)
- Should partial backfill coverage (some approved sources return data, others
  fail) block replay entirely, or should replay proceed with a `PARTIAL`
  `reconstruction_completeness` label? (Recommendation: proceed, consistent
  with SIP's existing "continue operating on partial data" philosophy already
  established for live runs and referenced in HRE Section 14, test 4 -
  deferred to implementation sprint.)
- Where does the Historical Source Registry physically live relative to the
  live Source Registry - one file with a clearly separated section, or a
  fully separate config file? (Recommendation: separate file, since the two
  registries have materially different schemas per Section 4 and different
  approval/legal review cadences - deferred to implementation sprint.)
- What triggers a backfill refresh for a previously-reconstructed date (new
  approved source, corrected connector, expanded date range)? Not yet
  specified beyond "deliberate, never implicit" (Section 9).

---

## 15. Recommended Implementation Sequence

1. **Historical Source Registry (config + loader only).** Define the schema
   from Section 4 as a real config artifact and a read-only loader, structured
   the same way `mne/source_registry.py` already validates the live registry.
   No connectors yet.
2. **Fed/FOMC connector (single source, Tier 2 storage).** Implement exactly
   one connector against the MVP source recommended in Section 11, producing
   normalized records (Section 6) and `EvidenceObject`s (Section 7). This is
   the first sprint that touches real fetching, and should be scoped and
   authorized separately from this architecture document.
3. **Backfill request/manifest plumbing.** Implement the request model
   (Section 5) and manifest/cache (Section 9) against the Fed/FOMC connector
   only, proving the "check cache, else backfill, else serve cached" flow
   end-to-end for one source before any other connector is added.
4. **Historical Replay evidence-source integration.** Extend
   `load_historical_run_records()` (or an equivalent evidence-gathering step)
   to also read the Tier 2 `MNE_DATA_DIR/historical_evidence/` namespace,
   proving a backfilled date can be replayed through the unmodified
   `run_historical_replay()` pipeline.
5. **Admin backfill console.** Admin-only visibility into backfill status,
   manifest contents, and source coverage - mirroring the existing Historical
   Replay Admin Console pattern, not a new UI paradigm.
6. **Historical Comparison View (separately scoped, future).** Only after
   steps 1-5 are stable does a marketable, user-facing Historical Comparison
   View become sensible product scope - it depends on there being real,
   cached, honestly-labeled historical coverage to compare against, which is
   exactly what this sequence builds.

Each step above is a distinct, separately authorized implementation sprint.
This document authorizes none of them; it defines the architecture they must
conform to.
