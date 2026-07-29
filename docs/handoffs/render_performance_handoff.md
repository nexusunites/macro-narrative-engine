# Dashboard & Historical Render Performance — Codex Implementation Handoff

## Objective

Restore pre-rework page load speed. Two verified regressions, both repeated full-file parsing on render, amplified by `MNE_DATA_DIR` living on cloud-synced storage. Fixes are read-path only: no engine, scoring, persistence-format, template-content, or UX changes. Pages must render byte-identically before and after (except faster).

Read `AGENTS.md` before starting.

## Verified causes

1. `dashboard.py::build_daily_support_history` → `load_daily_snapshots(limit=3660)` parses every daily snapshot file, including full `raw_runs` payloads, on every dashboard render. The chart needs only `date` and the support score fields per snapshot.
2. `mne/historical_research_view.py::list_user_replays` calls `load_replay_for_historical_research` + `build_user_historical_view` — including `build_historical_evidence_context` over up to 500 evidence rows per artifact — for every artifact, on every render of `/history`, and again for the comparison selector. Card rendering needs ~7 scalar fields per artifact.

## Changes

### 1. Mtime-keyed artifact cache (shared utility)

Add a small module (e.g., `mne/render_cache.py`): an in-process dict cache keyed by `(absolute_path, mtime_ns, size)` → parsed/derived value, with a `get_or_load(path, loader)` API and a bounded size (simple FIFO/LRU cap, e.g., 512 entries). Correctness argument: replay artifacts and past-day snapshots are immutable once written; today's snapshot changes only when a run rewrites it, which changes mtime and naturally invalidates. No TTLs, no manual invalidation endpoints, no cross-process anything.

### 2. Selector card summaries

New lightweight loader in `historical_research_view.py` (e.g., `load_replay_card_summary(path)`): parses the artifact JSON once (through the cache), runs the existing validation gates (minimum snapshot fields, completed status — same exclusion behavior as today), and extracts only the card fields (`date`, dominant group/theme, evidence/source counts, breadth, summary sentence, limited flag). It must not call `build_historical_evidence_context` or `_safe_evidence`. `list_user_replays` uses it; the full `build_user_historical_view` remains unchanged for investigation pages (also routed through the cache so a card view followed by an investigation parses the file once). Comparison selector reuses the same cached summaries.

### 3. Snapshot chart loading

Either (a) route `load_daily_snapshots` file parses through the cache, or (b) add a slim `load_daily_support_points()` that extracts `(date, score, state)` per file through the cache — implementer's choice; (b) preferred if it stays simple. Chart output must be identical.

### 4. Guardrail

Do not cache rendered HTML, view dicts containing request-specific state, or anything derived from "now". Cache parsed file contents and pure per-file derivations only.

## Non-Goals

No background jobs, no external cache services, no persistence-format changes, no pagination (revisit if artifact count grows past ~200), no template changes, no changes to validation/exclusion semantics.

## Tests required

1. Cache hit avoids re-reading an unchanged file (loader called once for two accesses).
2. Modified mtime invalidates and reloads.
3. Card summaries match the fields the current implementation produces, for a populated artifact fixture.
4. Malformed artifacts are still excluded from the selector with identical behavior.
5. Zero-evidence artifacts still flagged `limited`.
6. Chart history output identical to current implementation for a snapshot fixture set.
7. Investigation page output unchanged.
8. Existing dashboard, historical research, comparison, and request test suites pass unchanged.

## Verification

- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`
- Timing evidence: measure `/`, `/history`, and `/history/compare` render time before and after (simple `time.perf_counter` around TestClient calls or curl timing, three runs each) and report the numbers.
- Manual: `/`, `/history`, `/history/compare`, one investigation page, and `/admin` render identically to before.

## Output required

Report: objective summary; files changed; cache design summary; before/after timings for the three routes; confirmation of identical rendered output; verification performed; known remaining gaps; whether the performance regression can be marked resolved.

Implement to a verified local state and stop — do not stage, commit, or push.
