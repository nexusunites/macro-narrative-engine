# Historical Tier Cleanup — Handoff

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser, before each commit.

## Why this exists

The research tier and Studio are fully on the v2 design language (top-bar chrome, obsidian ground, teal/amber/slate palette). The **historical tier (`/history/*`) is the last user-facing surface still on the legacy left rail** (`_partials/app_rail.html`) and legacy body styling. Navigating from a v2 page into historical research visibly snaps back to the old chrome — this is the "site still feels half-updated" problem.

This handoff cleans up **only the user-facing historical pages**. Admin pages stay on the legacy rail by ratified decision (owner-only, separate chrome — same bucket as `admin.html`). It does **not** change engine logic, replay generation, or the historical request model (that hardening is a separate parked design note; see "Out of scope").

## Disposition (ratified)

| Template | Route | Auth | Verdict |
|---|---|---|---|
| `historical_comparison_user.html` | `GET /history/compare` | user | **RETIRE** — Studio Compare (Sprint P) is a functional duplicate (same `build_user_historical_comparison_context` builder). |
| `historical_selector.html` | `GET /history` | user | **KEEP + migrate + restyle** — history hub; still linked from `dashboard.html` and investigation pages. |
| `historical_request.html` | `GET /history/request` | user (`HISTORICAL_REQUEST`) | **KEEP + migrate + restyle** — request a new reconstruction; no Studio equivalent. |
| `historical_request_status.html` | `GET /history/request/{id}` | user | **KEEP + migrate + restyle** — request status. |
| `historical_investigation.html` | `GET /history/{replay_id}` | user (`HISTORICAL_RESEARCH`) | **KEEP + migrate + restyle** — single-replay deep-dive (historical analog of `narrative_investigation.html`). |
| `entitlement_denied.html` | (shared interstitial) | user | **MIGRATE + restyle** — shown at plan gates; reverts to legacy rail. |
| `historical_workflow.html` | `GET /admin/historical-workflow` | admin | **LEAVE legacy** — ratified admin chrome. |
| `historical_research.html` | `GET /admin/replay/{id}/research` | admin | **LEAVE legacy** — ratified admin chrome. |
| `historical_comparison.html` | `GET /admin/replay/compare` | admin | **LEAVE legacy** — ratified admin chrome. |

**Ratified IA decision:** the `/history` hub currently offers *request / compare / browse*. Compare now lives in Studio. The hub's compare entry **links out to `/studio/compare`** (History visibly begins folding into Studio — the intended long-term direction). Do **not** keep a separate compare surface under `/history`.

## The proven migration pattern (Sprint J)

Eight templates were already migrated in Sprint J. Follow that pattern exactly. Reference a migrated file such as `templates/narrative_history.html`:

- `<body class="app-topbar-page">` (replaces the legacy body class, e.g. `user-historical-page`).
- Immediately inside `<body>`: `{% set active_tier = "..." %}` then `{% include "_partials/app_topbar.html" %}`.
- **Delete** the standalone legacy brand header (`<header class="site-header ..."><div class="brand-row">...`). The top bar owns the brand.
- Add `<link rel="icon" href="data:,">` in `<head>` if absent (matches migrated pages).
- **History is intentionally NOT a top-bar nav item** (`app_topbar.html` is Overview·Research·Studio·Preferences). So these pages render with the top bar and **no active nav item highlighted** — that is correct and consistent with the IA (History left the nav in Sprint J). Do not add a History item to the top bar.
- Remove any `Latest meaningful run: {filename}`-style leak headers if present (none expected here, but verify — charter forbids raw run filenames in UI).

Test `tests/test_design_system_structure.py::test_sprint_j_pages_use_shared_topbar_without_filename_header` codifies this. **Extend that test's `migrated` tuple** to include the four history survivors + `entitlement_denied.html`, and **remove them from the admin/legacy assertion** where applicable. Leave `admin.html` and the three admin historical templates asserted as still using `_partials/app_rail.html`.

## Body restyle to v2 (palette + language)

Chrome swap alone is not enough — the page **bodies** must speak v2, like Sprint L/M did for the investigation view:

- Palette through tokens only. Legacy history pages use `body:not(.user-dashboard)` scope; after the Sprint K fix `--amber` is real amber (`#f0a64b`) globally, so `var(--amber)` is safe. **Direction/state colors:** strengthening = teal, fading/cooling/detached = **amber (never red)**, steady = bright slate. **Red is downside PRICE moves only.** Any green score pills / red-for-state are defects to convert.
- All user-facing copy stays in `mne/presentation_language.py` (existing `HISTORICAL_COPY` etc.) — never hardcode strings in templates.
- `historical_investigation.html` is the deepest restyle (it's the historical analog of the fully-v2 `narrative_investigation.html`). If its body restyle is large, it MAY be its own sprint/commit — do not rush it into a batch.

## Sprints

**Sprint R1 — Retire user compare + redirect.**
- Replace the `GET /history/compare` route body (`dashboard.py` ~3262) so it returns `RedirectResponse("/studio/compare?..." , status_code=307/302)` preserving `replay_a`/`replay_b` query params. (307 keeps it a GET-safe permanent-ish redirect; pick 302/307 consistent with existing redirects in the file.)
- Delete `templates/historical_comparison_user.html`.
- Repoint the three inbound links to `/studio/compare`: `historical_selector.html:22` (hub compare entry), `mne/personalization.py:246`, `mne/historical_request.py:220` (`comparison_url`). After repointing, the redirect is belt-and-suspenders for any missed link.
- Verify: `/history/compare?replay_a=X&replay_b=Y` lands on Studio Compare with the pickers pre-selected; Studio Compare still gates + meters identically (it already does — unchanged). No 500s, no orphaned template reference.

**Sprint R2 — Migrate + restyle the survivors.**
- Chrome-migrate + body-restyle: `historical_selector.html`, `historical_request.html`, `historical_request_status.html`, `entitlement_denied.html`.
- `historical_investigation.html` — chrome-migrate; body restyle to v2. Split into its own commit if the restyle is substantial.
- Extend the Sprint J structure test as described above.

## Verification standard (per AGENTS.md, every sprint)

Full suite passing (baseline: **902 tests, 2 known pre-existing `test_authorization` failures** — `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`); `/`, `/admin`, `/research` return 200; the migrated history routes return 200 (or correct redirect for `/history/compare`); rendering checked against the real run and a populated synthetic replay; empty/degraded states rendered; **1280 / 1024 / 390** widths; JS-disabled rendering; color budget (zero red-for-state, zero stray green); no horizontal scroll; no filename leak; `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

**Audit gotcha (recurring):** CSS changes require a cache-bust in the browser audit — `link.href = link.href.split('?')[0] + '?bust=' + Date.now()` before reading computed styles, or stale CSS shows false colors. Also `pkill -f uvicorn` before starting the audit server so a stale process doesn't serve fresh templates with stale Python.

## Out of scope (do NOT touch)

- **Admin historical pages** (`historical_workflow.html`, `historical_research.html`, `historical_comparison.html`) and `admin.html` — stay on the legacy rail.
- **Historical request model hardening** — the anti-spam redesign (normalize request windows to a canonical month/quarter grid so near-duplicate windows dedupe; meter only cache-miss reconstructions against the `HISTORICAL_REQUEST` quota; async queue + per-user in-flight cap). This is a separate parked design round; do not implement it here. This cleanup keeps the existing request mechanics unchanged.
- Engine logic, replay generation, thresholds, persistence formats.
