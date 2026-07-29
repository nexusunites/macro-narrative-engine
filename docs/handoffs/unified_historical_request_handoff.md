# Unified Historical Request Experience — Codex Implementation Handoff

## Objective

Let a user request a historical reconstruction — "Show me the market narrative for this historical period" — through a clean product flow, without understanding connectors, backfill/replay IDs, workflow manifests, cutoffs, or admin orchestration. All existing backfill, replay, cutoff, and coverage rules are preserved internally and unchanged. This sprint is the request experience and its safe workflow boundary only.

Read `AGENTS.md` before starting. All standing rules apply, plus the alignment conventions established in `docs/handoffs/user_historical_research_handoff.md` (presentation dictionary, color budget, historical tier styling, whitelist-only view shaping, deterministic composition, calm degradation).

## Execution model (decided — do not re-derive)

**Controlled synchronous reconstruction (Option B), reusing the existing admin orchestration.** Verified basis: `dashboard.py::execute_admin_workflow_backfills` already runs `historical_workflow.run_workflow_backfills` synchronously in-request with per-source containment (`COMPLETE`/`EMPTY`/`FAILED`), safe error contexts, manifest persistence, and a replay step. The user flow reuses this orchestration — same risk profile as today's admin flow — behind a user-safe boundary. Flow:

1. User submits the request form (POST).
2. Server maps product categories → supported sources, validates the date range, persists a request record (see Request state), then runs the existing workflow orchestration: sequential official-source backfills → replay generation over the replay-ready backfills.
3. On completion, PRG-redirect to a request status page, which links to the completed historical investigation.

Honest pacing copy on submit: "Reconstruction runs while you wait — this may take a minute." No fake async, no invented queue, no background jobs.

## Scope

### 1. Request form — `GET /history/request`

Inputs: a historical period (start/end date pickers; a single-date request is expressed as start = end), and coverage categories in product language with one-line descriptions:

| Product category | Internal source (server-side only) |
|---|---|
| Monetary policy | `fed_fomc` |
| Inflation | `bls_cpi` |
| Growth and consumer activity | `bea_gdp_pce` |
| Energy and commodities | `eia_energy` |

Raw source IDs never render. The mapping lives server-side in `mne/historical_request.py`; the form submits product-category tokens only. Enforce a maximum request range (recommend 92 days) with a calm validation message — large ranges are an admin operation *(Judgment Call #3)*.

### 2. Pre-submission coverage explanation

Fixed copy (presentation dictionary): reconstruction uses supported official historical sources · coverage may be partial · this is not complete historical market-news coverage · evidence after the historical cutoff is excluded.

### 3. Submission boundary

The request accepts only: dates and product-category tokens. It must reject (calmly, without echoing input) anything resembling backfill IDs, replay IDs, source IDs, workflow IDs, or paths. Server-side whitelist validation of category tokens; unknown tokens are rejected, not ignored.

### 4. Request state

Persist under `MNE_DATA_DIR/historical_requests/{request_id}/request.json` with states reflecting the actual synchronous model: `REQUESTED` (written before execution) → `COMPLETE` / `PARTIAL` / `FAILED`. (`RUNNING` may be written at execution start for crash forensics, but no queue semantics exist and none are implied.) `PARTIAL` = replay generated but one or more requested sources came back `EMPTY`/`FAILED`. Record: request_id, requested period, requested product categories, per-category outcome in user-safe terms, resulting replay reference, timestamps. This record is the source for the status page — shaped through a whitelist view helper like the other user surfaces.

### 5. Request identity and idempotency

Deterministic request identity: hash of (sorted product categories, start, end). On submit, if a request with the same identity is already `COMPLETE`, redirect to its existing result instead of re-running *(Judgment Call #2)*. POST → redirect → GET (PRG) throughout; refresh of any resulting page performs no work; double-submit resolves to the same request identity.

### 6. Status / completion page — `GET /history/request/{request_id}`

Validated request ID (internal, never emphasized in copy). Shows the request in product language: period, categories, per-category outcome ("Monetary policy: reconstructed from 3 official records" / "Inflation: no records available in this period" / "Energy and commodities: could not be reconstructed"), overall state, coverage limitations. When complete or partial-with-replay: "View this reconstruction →" into the existing `/history/{replay_id}` investigation, plus the comparison entry point. Replay ID is never the product label.

### 7. Partial and failed states

Calm, specific, honest: some sources returned no evidence for the period (often correct — official releases are periodic); some sources could not be reconstructed; reconstruction unavailable when no source was replay-ready. Reuse the safe error-context pattern (`build_backfill_error_context`) — raw exceptions and connector diagnostics never render.

### 8. User/admin boundary

No arbitrary connector selection, no workflow manifests, no replay parameters, no diagnostics, no admin links. Admin workflows unchanged and remain the path for large ranges and operational inspection.

### 9. Integration

Restrained "Request a historical reconstruction →" links from `/history` (primary) and the historical selector empty state ("None exist yet — request one"). Dashboard untouched beyond its existing historical entry point.

## Non-Goals

No billing/entitlements/auth, no background queues, no concurrency, no scheduled requests, no new connectors, no changes to scoring, taxonomy, cutoff rules, Coverage Intelligence, or Research/Comparison calculations. No LLMs, predictions, or trade language.

## Likely files

`dashboard.py`, new `mne/historical_request.py` (category mapping, request identity, request persistence, orchestration wrapper reusing `historical_workflow` + replay generation), `templates/historical_request.html`, new `templates/historical_request_status.html`, small edits to `templates/historical_selector.html`, `static/styles.css`, `mne/presentation_language.py` (request vocabulary), `tests/test_historical_request_user.py`. Duplicate no connector, workflow, or replay logic.

## Ratified Decisions (Daniel, 2026-07-29)

1. **Synchronous execution (Option B) reusing admin orchestration.** Ratified.
2. **Duplicate requests reuse the existing completed reconstruction** (redirect to prior result) rather than re-running. Ratified.
3. **Maximum request range of 92 days** for the user flow; admin handles larger ranges. Ratified as an MVP bound. Removal of the bound is planned via the backlogged **Historical Request Performance** item (backfill reuse → parallel fetch → background execution), followed by **Deep History Expansion** toward the full depth of each supported official archive. Implementers should not preempt those items in this sprint.

## Tests required

The 25 tests as specified: form renders with product-language categories and no raw connector IDs (1–3); invalid date and empty category rejection (4–5); server-side mapping and rejection of arbitrary source IDs / paths / replay-backfill IDs (6–8); successful request reaches the synchronous path (9); partial and failed calm rendering (10–11); duplicate-submission idempotency and refresh-does-no-work (12–13); completion links to investigation and comparison remains available (14–15); no raw workflow/backfill/replay IDs emphasized, no raw exceptions (16–17); no admin controls on user surfaces (18); `/research` and admin workflow unchanged (19–20); no live RSS fetching (21); no scoring/taxonomy regression (22); existing historical research, comparison, and workflow tests pass (23–25). Add: max-range rejection renders calmly; same-identity resubmit redirects to the existing result; presentation-dictionary coverage for all request vocabulary.

## Verification

- `python -m unittest tests.test_historical_request_user -v`
- `python -m unittest tests.test_historical_workflow -v`
- `python -m unittest tests.test_historical_research_user -v`
- `python -m unittest tests.test_historical_comparison_user -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`

Manual: open `/history/request`; submit one small supported request (a few days, one category); confirm product language throughout; confirm the completed request opens the historical investigation; refresh every page in the flow and confirm no re-execution; resubmit the identical request and confirm redirect to the existing result; grep rendered HTML for `backfill`, `manifest`, `fed_fomc`, `MNE_DATA_DIR`; confirm admin and `/research` unchanged. Do not run large historical ranges.

## Output required

Report: objective summary; files changed; route/helper summary; request-form behavior; category-to-source mapping; execution/request-state behavior; partial/failure behavior; idempotency behavior; user/admin boundary verification; verification performed; known remaining gaps; whether Unified Historical Request Experience can be marked implemented.

Implement to a verified local state and stop — do not stage, commit, or push.
