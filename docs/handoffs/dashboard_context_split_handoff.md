# Dashboard Context Split — Codex Implementation Handoff

## Objective

Eliminate the root-page performance regression left open by the render-performance handoff. Verified cause: `dashboard.py::build_template_context` is shared between the user dashboard and admin, so `GET /` builds admin-only and no-longer-rendered context on every load — the expensive parts hit cloud-synced storage. Fix by building only what each route renders. Read-path/context-plumbing only: no engine changes, no template-content changes, rendered HTML for every route stays byte-identical.

Read `AGENTS.md` before starting.

## Verified waste on `GET /` (all built, none rendered by `templates/dashboard.html`)

1. `build_historical_replay_console(backfill_choices=historical_backfill_admin.list_recent_backfill_summaries())` — admin console + full backfill-manifest directory scan on `MNE_DATA_DIR`.
2. `build_historical_backfill_console()` — second admin console/scan.
3. `build_narrative_leadership_history()` — the Daily Leadership table was removed from the user dashboard in the rework; nothing on `/` consumes this.
4. `build_regime_history()` — assigned into context, then unconditionally overwritten by `build_daily_support_history(...)` in the `dashboard()` route. Computed and discarded on every load.

## Changes

1. **Split context building.** Refactor `build_template_context` into a lean core (run selection, recent runs, selected view — what every route needs) plus explicit admin extensions. Options: an `include_admin_consoles: bool = False` parameter, or a separate `build_admin_template_context` that composes the core — implementer's choice; prefer whichever keeps admin routes' context keys exactly as they are today.
2. **`GET /`** builds: core context + `build_daily_support_history` only. Items 1–4 above are not executed on user routes. Verify no other user-facing route (`/research`, `/history*`) executes admin console builders either; apply the same treatment if any do.
3. **Admin routes** build everything they build today — identical keys, identical values, identical rendering.
4. **Legacy `build_regime_history()`:** if after the split no route consumes it (check `/admin` and research templates before deciding), delete it and its dead assignment; if admin still renders it, keep it admin-only. Do not leave it computed-and-discarded anywhere.
5. Where directory scans remain on admin paths, routing file parses through the existing `mne/render_cache.py` is welcome but optional — admin latency is not this handoff's goal.

## Non-Goals

No template changes, no UX changes, no caching of rendered HTML, no changes to run-selection semantics, no admin latency work beyond incidental cache reuse.

## Tests required

1. `GET /` context contains no admin console keys (or contains them only if the template requires them — assert against the template's actual variable usage).
2. Admin route context keys/values unchanged (fixture comparison).
3. `build_narrative_leadership_history` and backfill-summary scans are not invoked on `GET /` (assert via mock/spy).
4. `build_regime_history` is either removed or invoked only on routes that render it.
5. Rendered HTML for `/`, `/admin`, `/research`, `/history` unchanged against saved pre-change output.
6. Full existing suite passes.

## Verification

- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`
- Timing evidence: three-run before/after timings for `GET /` (same method as the render-performance handoff). Expected outcome: `/` drops from tens of seconds to the cost of loading the current run only. Report the numbers.
- Manual: `/`, `/admin` (including replay/backfill consoles and a console action), `/research`, `/history` all render and function identically.

## Output required

Report: objective summary; files changed; context-split design; what `GET /` now executes; before/after timings; confirmation of identical rendering on user and admin routes; verification performed; whether the root-page performance regression can be marked resolved.

Implement to a verified local state and stop — do not stage, commit, or push.
