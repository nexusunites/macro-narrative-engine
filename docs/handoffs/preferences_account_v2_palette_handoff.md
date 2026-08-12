# Preferences & Account — v2 Palette Pass (Handoff)

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser (logged-in), before commit.

## Why this exists

`preferences.html` and `account.html` were migrated to the shared top bar in an earlier sprint but were never fully brought onto the v2 palette. They still carry a **vestigial `user-historical-page` body class** whose CSS rule was renamed away in Sprint R2 (`7e5163d`), so they now reference a selector that no longer exists. This surfaced during the R2 audit.

## Root cause (confirmed by cascade analysis)

- The legacy scope `body:not(.user-dashboard)` (`static/styles.css:107`, specificity `(0,1,1)`) sets **legacy tokens**: `--accent: #68d391` (green), `--brand-accent: var(--accent)` (green), `--warn: #d7b36a`.
- Every v2 top-bar page (`research-*`, `studio-*`, `historical-v2-page`) avoids green either by (a) referencing `var(--teal)` / `var(--teal-bright)` **directly** in component CSS, and/or (b) adding a **scoped token block** that redefines `--accent`/`--brand-accent`/`--warn` to v2 values (see `body.historical-v2-page` at `styles.css:~3069`, the pattern to mirror).
- `preferences.html` / `account.html` do **neither**. They set `class="user-historical-page app-topbar-page"`, and since `.user-historical-page` no longer has a rule, any body content that uses `var(--accent)` / `var(--brand-accent)` resolves to **legacy green**, and `--warn` to legacy gold.
- The top bar itself is fine everywhere — its active underline uses `var(--teal)` (`styles.css` `.dashboard-primary-nav a.active::after`), which the legacy scope never overrides.

So the visible defect is confined to the **page bodies** of these two pages wherever they lean on `--accent`/`--brand-accent`/`--warn`.

## Scope

**Only** `templates/preferences.html`, `templates/account.html`, and `static/styles.css` (token scope). Do not touch other pages, engine logic, or the historical/admin surfaces.

## Task

1. **Remove the vestigial class.** In both templates, change `class="user-historical-page app-topbar-page"` → `class="app-topbar-page preferences-account-v2-page"` (or reuse an existing v2 class — your call, but give them a hook for the token block below). Keep `app-topbar-page`.

2. **Give them a v2 token scope.** Add a scoped block (mirror `body.historical-v2-page`) that sets, for these pages: `--accent: var(--teal-bright); --brand-accent: var(--teal-bright); --warn: var(--amber);` plus any obsidian/panel tokens they need. This guarantees v2 resolution regardless of the legacy scope.
   - **Preferred alternative (your judgment):** if it's clean and low-risk, instead of another per-page block, add a single **base normalization on `.app-topbar-page`** that sets these three tokens to v2 values — this would make *every* top-bar page consistent and remove the need for per-page token blocks. Only do this if you verify (in browser) it does not regress `research`, `studio`, or the `historical-v2-page` pages. If there's any doubt, use the scoped per-page block and note the consolidation as a future option.

3. **Restyle any green/red-for-state in the two bodies to v2.** Audit their rendered output for legacy green accents, red-for-state, or gold warnings, and convert to teal / amber / bright-slate per the design system (red is downside price only — neither of these pages should have red). Copy stays in `mne/presentation_language.py`.

4. **Background:** confirm the background is intentional after losing the old `.user-historical-page` gradient — either plain `var(--bg)` or a subtle teal radial matching `historical-v2-page` (`radial-gradient(circle at 14% 8%, rgba(45,212,191,.08), transparent 32rem), var(--bg)`). Match the other v2 pages.

## Verification (per AGENTS.md)

These pages are **auth-gated** (`/preferences`, `/account` 303→login for anon), so you must verify **logged in** — create a QA session as you did for the R2 request-form audit. Then, with CSS cache-busted:
- Computed `--accent`, `--brand-accent`, `--warn` on `<body>` resolve to v2 (teal-bright / amber), and a full computed-style scan shows **no legacy green (`#68d391`)** and **no red-for-state**.
- Top-bar active state (Preferences highlighted on `/preferences`) is teal; account nav correct.
- No horizontal scroll at 1280 / 1024 / 390; JS-disabled render intact.
- No raw filename/path/id leak.
- Full suite passing (**baseline 873, 2 known pre-existing `test_authorization` failures**: `test_csrf_and_deterministic_helpers`, `test_user_forbidden_admin_admin_allowed`); `/`, `/admin`, `/research` return 200.
- **Add/extend a structure test** asserting neither template references `user-historical-page` and both keep `app-topbar-page` (guards the regression from recurring).
- `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

**Recurring gotcha:** cache-bust CSS in the browser (`link.href = link.href.split('?')[0] + '?bust=' + Date.now()`) before reading computed styles, and `pkill -f uvicorn` before starting the audit server.

## Out of scope

Historical tier (done), admin pages (legacy rail by decision), the historical-request hardening (separate parked note), Studio Sprint Q.
