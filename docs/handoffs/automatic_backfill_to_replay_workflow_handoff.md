# Codex Implementation Handoff — Automatic Backfill-to-Replay Workflow

Status: **Handoff only. No code written.** This document is the implementation
spec Codex should build against. It is grounded in direct inspection of the
current codebase (file:line references below), not assumption.

---

## 1. Objective

Admins currently run each source backfill manually, wait, then hand-select the
resulting `backfill_id`s into the separate replay form. This adds one
admin-only guided workflow — **"Build Historical Replay"** — that runs
selected backfills sequentially, shows every outcome honestly (including
empty/failed sources), and only launches one combined replay on an explicit
second confirmation. Backfill and replay remain two distinct persisted
artifacts, called through their existing public entry points, unchanged.

This item is already named in `docs/product_backlog.md:141,377` as future work
("Automatic backfill-to-replay flow ... Medium ... Future") — this sprint
implements it.

---

## 2. Ground truth from the current codebase (do not re-derive — verified)

**`mne/historical_backfill.py`**
- `SUPPORTED_SOURCES` (line 13-14) is a **tuple**, not an enum/dict:
  `("fed_fomc", "bls_cpi", "bea_gdp_pce", "eia_energy")`.
- `run_and_persist_historical_backfill(source, start, end, fetch=None, data_dir=None)`
  (line 375) → returns `(path: Path, result: dict)`. `start`/`end` are
  **required positional params**, not optional — there is no "date-only, no
  range" call shape at this layer.
- Raises `ValueError` for bad source/date/range (via `build_backfill_request`,
  line 127, and `_parse_date`, line 473); other exceptions (connector/IO)
  propagate uncaught — nothing in this module catches them.
- Manifest (`build_backfill_manifest`, line 294-310) fields: `backfill_id`,
  `requested_start_date`, `requested_end_date`, `generated_at`, `source_id`,
  `provider`, `category`, `records_found`, `evidence_count`,
  `date_range_covered`, `storage_tier`, `warnings`, **`replay_ready` (bool)**,
  `limitations`, `status` (`"COMPLETE"` if `replay_ready` else `"PARTIAL"`).
  **There is no `EMPTY` or `FAILED` status string anywhere in this module.**
  Zero evidence still persists as `status="PARTIAL"` with a warning appended.
- Persisted at `{MNE_DATA_DIR}/historical_evidence/{backfill_id}/manifest.json`
  and `.../evidence.json` (line 321-348, root resolved line 411-413) — **not**
  `historical_backfills/`.

**`mne/historical_backfill_admin.py`**
- `is_valid_backfill_id(value)` (line 16-17) — regex format check, no I/O.
- `load_backfill_summary_by_id(backfill_id, data_dir=None)` (line 72-83) —
  path-containment guarded, loads manifest safely for display.
- `build_backfill_error_context(error)` (line 86-91) — logs + returns
  `{"status": "failed", "message": "..."}` for the generic-exception path.

**`mne/historical_replay.py`**
- `run_and_persist_historical_replay(replay_date, mode=SUPPORTED_MODE, evidence_cutoff=None, backfill_id=None, backfill_ids=None, include_backfilled_evidence=False)`
  (line 485-503) → `(path: Path, output: dict)`.
- `ReplayRequest.__post_init__` (line 51-66) merges singular/plural backfill id
  inputs, dedupes by first occurrence, **preserves order**.
- `_load_backfill_evidence_for_replay` (line 275-334): for **≥2** ids, any
  invalid/missing/unreadable id raises `HistoricalReplayError` before
  persisting anything. **For exactly 1 id, an invalid id is silently resolved
  to an empty evidence list — it does not raise.** This asymmetry matters (see
  §5.3) — do not rely on the engine's own leniency for validation; always
  revalidate through the admin validator first regardless of selection count.
- Cutoff (`select_backfilled_evidence`, line 235-272): strict
  `published_at <= cutoff`, cutoff defaults to end-of-day UTC on `replay_date`
  (line 82-86). No changes needed or permitted here.
- Persisted as a **flat file** `{MNE_DATA_DIR}/replays/{replay_id}.json` (line
  474-482, root line 104-108) — not a directory-per-id like backfills.
- `replay_metadata` (line 216-232) already includes `backfill_ids_requested`,
  `backfill_ids_used`, `backfilled_evidence_counts_by_id`,
  `live_evidence_count`, `backfilled_evidence_count`, `total_evidence_count`,
  `evidence_sources_used`. Coverage Intelligence is attached at line 413-416
  under `source_intelligence.coverage_intelligence` — already source-agnostic,
  nothing to change.

**`mne/historical_replay_admin.py`**
- `is_valid_replay_id(value)` (line 14-15).
- `validate_replay_backfill_ids(backfill_ids, data_dir=None) -> (valid_ids, invalid_ids)`
  (line 18-51) — dedupes preserving order, checks format + loadable summary.
  **This is the exact re-validation function to reuse at confirmation time.**

**`dashboard.py`**
- `GET /admin` (line 1494) renders `templates/admin.html`, a single ~1667-line
  template with anchored `<section id="historical-replay">` (line 64) and
  `<section id="historical-backfill">` (line 311).
- `POST /admin/historical-backfill` (line 1555-1574) and
  `POST /admin/historical-replay` (line 1533-1552) both follow strict
  **POST/Redirect/GET**: 303 redirect to `/admin?backfill=<id>` /
  `?backfill_error=<code>` or `/admin?replay=<id>` / `?replay_error=<code>`.
- `execute_admin_backfill_form(source, start_date, end_date)` (line 351-391)
  and `execute_admin_replay_form(...)` (line 430-464) are the thin
  validate-then-call-then-summarize wrappers this workflow should mirror, not
  import (they live in `dashboard.py`; `mne/historical_workflow.py` must not
  import from `dashboard.py` — that would invert the existing `dashboard.py
  → mne/*` dependency direction).
- **No auth exists anywhere.** Admin gating is purely the `/admin*` path
  prefix convention (confirmed by grep — no middleware, no session/token
  check). New routes must follow the same convention and nothing more (matches
  Non-Goal: "add authentication in this sprint").
- Public isolation is already tested:
  `tests/test_historical_backfill_admin.py:157-169`
  (`test_user_dashboard_does_not_expose_backfill_ui`) asserts
  `assertNotIn("Historical Backfill", html)` and
  `assertNotIn('action="/admin/historical-backfill', html)` against
  `dashboard.html`/`research_selector.html`. New workflow tests must add the
  equivalent assertion for the new workflow controls.
- **Test convention** (both `test_historical_backfill_admin.py` and
  `test_historical_replay_admin.py`): no FastAPI `TestClient`. Tests use a
  `temporary_mne_data_dir()` context manager that creates an isolated temp
  dir, patches `os.environ["MNE_DATA_DIR"]`, reloads `config`, swaps
  `dashboard.RESULTS_DIR`; they call `execute_admin_*_form`-style functions
  directly and render templates via
  `dashboard.templates.env.get_template(...).render(...)`; connectors are
  faked via `unittest.mock.patch`. `tests/test_historical_workflow.py` must
  follow this exact pattern — no new test infrastructure.

---

## 3. Two design decisions this handoff makes explicit (the original ask under-specified these)

### 3.1 Status model — workflow-level mapping only, no schema change

`historical_backfill.py` has no `EMPTY`/`FAILED` manifest status. Do **not**
add one there (that would be changing connector/persistence logic, forbidden).
Instead, `mne/historical_workflow.py` derives a **display-only** three-state
outcome per source, from data the backfill module already produces:

| Workflow outcome | Derived from |
|---|---|
| `FAILED` | `run_and_persist_historical_backfill` raised (any exception) — no `backfill_id` produced. Capture the message via the same path `historical_backfill_admin.build_backfill_error_context(error)` already uses, for consistent wording. |
| `EMPTY` | Call succeeded, manifest persisted, but `manifest["replay_ready"] is False`. |
| `COMPLETE` | Call succeeded, `manifest["replay_ready"] is True`. |

Only `COMPLETE` entries are replay-selectable. This is pure orchestration
reading an existing boolean — zero duplication of connector logic.

### 3.2 Carrying Step 1 results across the PRG redirect — small workflow manifest, not query-string encoding

Stuffing 1-4 sources' worth of warnings/error text/evidence counts into a
redirect query string is fragile (escaping, length, honesty of display). Use
the task's Option B: a small persisted workflow manifest.

```
{MNE_DATA_DIR}/historical_workflows/{workflow_id}/manifest.json
```

`workflow_id` format: `workflow_{replay_date}_{shortuuid}` — validate with the
same discipline as `is_valid_backfill_id`/`is_valid_replay_id` (regex format
check + path-containment check before any file read, mirroring
`historical_backfill_admin.load_backfill_summary_by_id`'s existing guard at
line 72-83).

Manifest content (written once, immediately after Step 1 completes; the only
field mutated afterward is `replay_id`, see §3.3):

```json
{
  "workflow_id": "...",
  "generated_at": "...",
  "requested_replay_date": "...",
  "requested_start_date": "...",
  "requested_end_date": "...",
  "mode": "macro",
  "requested_sources": ["fed_fomc", "bls_cpi"],
  "source_outcomes": [
    {
      "source": "fed_fomc",
      "status": "COMPLETE",
      "backfill_id": "backfill_...",
      "evidence_count": 12,
      "replay_ready": true,
      "warnings": [],
      "limitations": [...],
      "error_message": null
    }
  ],
  "replay_id": null
}
```

This is a **third, distinct artifact type** — not the backfill manifest, not
the replay artifact — so it cannot violate "existing backfill/replay
artifacts are not mutated." It is the workflow's own audit record, isolated
under its own namespace, exactly as the task's storage guidance requires.

### 3.3 Idempotency mechanics

- `GET /admin/historical-workflow` — form. No side effects.
- `POST /admin/historical-workflow/run-backfills` — the **only** trigger for
  running backfills. Runs sequentially, writes the workflow manifest once,
  redirects (303) to `GET /admin/historical-workflow/confirm?workflow_id=...`.
  A user refreshing the confirmation page re-issues the GET, not the POST —
  backfills are never rerun on refresh (matches existing PRG behavior already
  proven for backfill/replay forms).
- `GET /admin/historical-workflow/confirm?workflow_id=...` — loads the
  manifest, re-displays all outcomes (COMPLETE/EMPTY/FAILED) honestly, shows
  the proposed replay id list (COMPLETE entries only), offers two explicit
  actions.
- `POST /admin/historical-workflow/confirm` with `action=run_replay` — the
  **only** trigger for replay. Steps:
  1. Reload the workflow manifest by `workflow_id`.
  2. **If `manifest["replay_id"]` is already set, do not rerun** — redirect
     straight to the existing `/admin?replay=<replay_id>` view. This is what
     makes a resubmitted/duplicated confirm POST idempotent (test #17).
  3. Otherwise, re-extract the `COMPLETE` backfill ids from the manifest (not
     from client-submitted form fields — the manifest is the trusted source)
     and re-validate them via
     `historical_replay_admin.validate_replay_backfill_ids` (test #13). Any
     now-invalid id aborts with a calm error; do not proceed.
  4. Call `historical_replay.run_and_persist_historical_replay(replay_date=manifest["requested_replay_date"], mode="macro", backfill_ids=<validated ids in manifest order>)`.
  5. Write `replay_id` into the workflow manifest (the only post-hoc mutation,
     and only to the workflow's own artifact).
  6. Redirect (303) to the existing `/admin?replay=<replay_id>` result view —
     reuse it entirely, no new replay-result template.
- `action=cancel` — redirect to `/admin/historical-workflow` (or `/admin`),
  no state change.

---

## 4. Scope

### 4.1 New module: `mne/historical_workflow.py`

Public functions (exact names Codex should implement; signatures are a
starting point, adjust only for correctness, not for scope):

```python
def run_workflow_backfills(sources, start_date, end_date, data_dir=None) -> list[dict]:
    """Run historical_backfill.run_and_persist_historical_backfill for each
    source in the fixed order given by historical_backfill.SUPPORTED_SOURCES
    (filtered to `sources`), sequentially, never concurrently. Returns one
    outcome dict per source per §3.1's status mapping. Never raises for a
    single source's failure — captures it as a FAILED outcome and continues
    to the next source."""

def build_workflow_manifest(replay_date, start_date, end_date, mode, requested_sources, source_outcomes) -> dict: ...

def write_workflow_manifest(manifest, data_dir=None) -> Path: ...

def load_workflow_manifest(workflow_id, data_dir=None) -> dict | None:
    """Format-validate workflow_id and path-containment-check before reading,
    mirroring historical_backfill_admin.load_backfill_summary_by_id."""

def mark_workflow_replay(workflow_id, replay_id, data_dir=None) -> None:
    """The one permitted post-hoc mutation: set manifest['replay_id']."""

def is_valid_workflow_id(value) -> bool: ...
```

**Deterministic order**: iterate `historical_backfill.SUPPORTED_SOURCES` in
its declared tuple order, filtered to the requested set — do not depend on
client-submitted/checkbox order (test #6).

**Only selected connectors are called**: reject the whole request (no
connector calls at all) if any submitted source is not in `SUPPORTED_SOURCES`,
or if the source list is empty, or if `replay_date`/`start_date`/`end_date`
fail validation — validate all of these *before* the sequential backfill loop
begins (test #3, #4, #5, #7, #21). Reuse whatever validation
`run_and_persist_historical_backfill`/`build_backfill_request` already does by
attempting the call and catching `ValueError`, exactly as
`execute_admin_backfill_form` does today — do not reimplement date parsing.
If a shared `replay_date`/range is invalid in a way that would otherwise cause
every source to fail identically, validate it once up front (Codex should
inspect whether `build_backfill_request` validates before or after any
network/connector access, and hoist a shared pre-check only if needed to
avoid N redundant connector attempts on a single bad date).

Default `start_date`/`end_date` to `replay_date` when the admin supplies only
a single date (goal item 1: "date or date range") — `run_and_persist_historical_backfill`
has no optional-range call shape, so the workflow must always resolve concrete
start/end strings before calling it.

### 4.2 Routes in `dashboard.py`

Add, following the exact PRG pattern of the existing backfill/replay routes:

- `GET /admin/historical-workflow` — form.
- `POST /admin/historical-workflow/run-backfills` — Step 1.
- `GET /admin/historical-workflow/confirm` — Step 2 display.
- `POST /admin/historical-workflow/confirm` — Step 3 (`action=run_replay` or `action=cancel`).

Each handler is a thin wrapper (parse form via `parse_qs`, matching the
existing routes' style, call into `mne/historical_workflow.py` and
`mne/historical_replay.py`/`historical_replay_admin.py`, redirect). Do not put
orchestration logic in `dashboard.py` beyond this thin layer, and never in
templates.

### 4.3 Templates

Add `templates/historical_workflow.html` (dedicated page, both the intake form
and the confirmation state as two render branches or two blocks) rather than
growing the already-1667-line `admin.html` further. Add only a small entry
link/section to `admin.html` pointing at `/admin/historical-workflow` — do not
duplicate the backfill or replay sections' markup there.

Reuse existing safe-display helpers
(`historical_backfill_admin.build_backfill_admin_summary`,
`historical_replay_admin.build_replay_admin_summary`,
`normalize_backfill_display_path`/`normalize_replay_display_path`) for
rendering individual backfill/replay fields inside the new template — do not
write new ad hoc formatting.

### 4.4 Safety boundaries (unchanged from the original ask, now grounded)

- No new file-path input from the client — `workflow_id` is format+containment
  validated exactly like existing `backfill_id`/`replay_id` (§3.2).
- Only `historical_backfill.SUPPORTED_SOURCES` values are ever passed to a
  connector call.
- No RSS/live fetch — the workflow never touches `RESULTS_DIR` or live
  ingestion code paths at all.
- Workflow manifest lives in its own namespace
  (`historical_workflows/`), never inside `historical_evidence/` or `replays/`.
- No controls added to `dashboard.html` or `templates/research_selector.html`/
  `research.html` — verify by grepping those templates for the new route
  strings, same technique the existing isolation test uses.

---

## 5. Tests required (`tests/test_historical_workflow.py`, following the existing `temporary_mne_data_dir()` + direct-call + template-render convention — no `TestClient`)

Map 1:1 to the original 27 test requirements; grouped by what they actually exercise given the design above:

1. Form renders (`GET /admin/historical-workflow`), sources listed come from `historical_backfill.SUPPORTED_SOURCES`.
2. Unsupported source in POST body → rejected, no manifest written, no connector called (patch/mock each connector and assert zero calls).
3. Empty source list → rejected calmly, same zero-call assertion.
4. Invalid `replay_date`/range → rejected, zero connector calls.
5. Sources run in `SUPPORTED_SOURCES` order regardless of submitted order (assert call order on the mock).
6. `COMPLETE`, `EMPTY` (mock a connector returning zero records), and `FAILED` (mock a connector raising) outcomes each appear correctly in the written workflow manifest and in the confirmation page's rendered HTML — three separate cases.
7. Partial failure (mix of the three outcomes) does not write a `replay_id` into the manifest and does not call `run_and_persist_historical_replay` (mock it, assert not called).
8. Confirmation POST (`action=run_replay`) re-validates ids via `historical_replay_admin.validate_replay_backfill_ids` even when the manifest already lists them as `COMPLETE` — simulate a backfill artifact deleted between Step 1 and confirm, assert the replay is rejected, not silently run with fewer ids.
9. Confirmation POST calls `run_and_persist_historical_replay` with exactly the `COMPLETE`-outcome ids, in manifest order.
10. A second confirmation POST after `replay_id` is already set redirects to the existing replay result without calling `run_and_persist_historical_replay` again (mock, assert call count == 1 across two POSTs).
11. `GET` on the confirm page never triggers backfill or replay execution (assert both mocked functions uncalled after N gets).
12. Workflow writes nothing under `RESULTS_DIR`.
13. Existing backfill manifest/evidence files for ids used are untouched (hash/mtime comparison before and after the workflow runs) — asserts no mutation of `historical_evidence/{backfill_id}/*`.
14. Existing replay artifact files are untouched beyond the one new replay written by this workflow run.
15. No RSS/live-fetch code path invoked (same technique existing backfill/replay admin tests use to guarantee this).
16. `dashboard()` (public `/`) and `research_selector()` HTML contain no reference to `/admin/historical-workflow` (mirrors `test_user_dashboard_does_not_expose_backfill_ui`).
17. Resulting replay's `source_intelligence.coverage_intelligence` is present and non-empty when at least one `COMPLETE` backfill was used (asserts the workflow didn't bypass or fork replay's existing coverage computation).
18. No scoring/taxonomy field differs between a replay run directly via `execute_admin_replay_form` and the same replay run via this workflow, given identical inputs (byte-for-byte compare the two output dicts minus `replay_id`/timestamps) — direct regression guard against any accidental logic fork.

Also required: confirm `tests/test_historical_backfill_admin.py`,
`tests/test_historical_replay_admin.py`, `tests/test_historical_backfill.py`,
and `tests/test_historical_replay.py` still pass unmodified (this workflow
must not touch those modules' behavior).

---

## 6. Verification Codex must run before reporting this done

```bash
python -m unittest tests.test_historical_workflow -v
python -m unittest tests.test_historical_backfill_admin -v
python -m unittest tests.test_historical_replay_admin -v
python -m unittest tests.test_historical_backfill -v
python -m unittest tests.test_historical_replay -v
python -m unittest discover -s tests
python -m compileall dashboard.py main.py mne tests
git diff --check
```

Manual walkthrough (small range only — e.g. a single week):
1. Open `/admin`, follow the new "Build Historical Replay" link.
2. Select two sources (e.g. `fed_fomc`, `bls_cpi`) and a small date range.
3. Submit — confirm redirect to the confirmation page, not directly to a replay result.
4. Confirm each source's outcome (COMPLETE/EMPTY/FAILED) is visible and honest.
5. Confirm no replay was created yet (check `{MNE_DATA_DIR}/replays/` before clicking confirm).
6. Click "Run combined replay" — confirm redirect to the existing `/admin?replay=<id>` view.
7. Confirm the replay's `replay_metadata.backfill_ids_used` matches what was shown at confirmation.
8. Open the result via Historical Research; confirm it loads.
9. Refresh the confirmation page and the replay result page — confirm neither backfills nor replay reruns.
10. Confirm `/` and `/research` show no workflow controls.

---

## 7. Non-goals (unchanged, restated for the executor)

No public UI, no auto-selected sources, no auto-launched replay, no
background jobs/concurrency, no scheduled backfills, no new connectors, no
scoring/taxonomy changes, no Source/Network Confidence changes, no Operations
Center/Dashboard Trust Summary/Narrative Memory changes, no LLMs, no
authentication.

---

## 8. Known open question for Codex to resolve during implementation, not before

Whether `build_backfill_request`/`run_and_persist_historical_backfill`
validates dates strictly before attempting any connector I/O (needed to
decide whether a single shared pre-check is worth hoisting above the
per-source loop, or whether per-source `ValueError` catching alone already
prevents any connector call on bad input). Read `historical_backfill.py`
directly at implementation time to confirm; do not guess.

---

## 9. Marking this implemented

This document is a handoff, not a report. **Automatic Backfill-to-Replay
Workflow cannot be marked implemented until** Codex builds against this spec
and the verification in §6 is actually run and its output inspected — not
assumed to pass.
