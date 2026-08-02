# MNE Design System & Dashboard Experience Foundation — Implementation Handoff

## Purpose

Unify the product visually and structurally around the approved MNE identity ("a visual narrative
intelligence platform that makes global market stories understandable, explorable, and actionable")
and the Story → Spread → Market Expression → Price Response journey. This sprint is presentation and
structure only — no engine, scoring, taxonomy, or entitlement-logic changes. It extends
`docs/dashboard_rework_handoff.md` and `docs/handoffs/dashboard_sprint_d_handoff.md`, which already
did most of the hard work (dark neutral base, ratified 2-hue color budget, `<details>`-based
progressive disclosure, admin/user context split). This handoff's job is to name that work correctly,
close the gaps where newer surfaces (auth, personalization, entitlements) fell outside the system, and
reserve structural space for future sprints — not to rebuild what already works.

**Status: ratified by Daniel on 2026-08-02.** All open judgment calls below are resolved. This is a
gap-fill and naming pass, not a dashboard rebuild. Refine the established foundation, fill genuine
design-system gaps, and reserve future product terms until real data supports them.

Do not implement code from this document directly. This is the Codex-ready brief.

---

## 1. Objective Summary

Formalize the existing dark, low-chroma dashboard into a documented design system (`docs/design_system.md`),
apply the approved dual-label naming framework only where a real analytical field already backs the
label (`docs/ui_naming_framework.md`), reconcile the ratified "≤2 non-neutral colors" budget with the
new spec's broader teal/amber semantic ask (Judgment Call, see below), formalize the existing
`<details>`/`.why-expander` pattern into a reusable "X-Ray" component, close the token-system gap on
auth/preferences pages, add a real locked/entitlement UI component (today there is none), and reorder
nothing that doesn't need reordering — the current `dashboard.html` section order already matches the
spec's A/B/E/F/G targets closely; only C (Narrative Discovery Preview) is net-new and D (Market
Expression Preview) needs a content check, not a rebuild.

## 2. Files Changed

**Modify:**
- `static/styles.css` — add semantic token aliases (`--teal`, `--amber` per Judgment Call 1), add
  `@media (prefers-reduced-motion: reduce)` rules (currently absent — grepped, zero hits), migrate the
  hardcoded auth/preferences colors at lines 4858–4883 (`#d8d8d8`, `#aaa`, the dangling
  `var(--border-color, #d8d8d8)` fallback where `--border-color` is never defined) onto the real token
  set, add `.xray-disclosure`, `.locked-state`, `.narrative-discovery-preview` component classes.
- `templates/dashboard.html` — insert the reserved Narrative Discovery Preview section (C) between
  "Stories" (`#stories`, line 163) and "My Narratives" (`#my-narratives`, line 235); verify/adjust the
  "Markets Right Now" section (`#markets`, lines 262–287) content against the Market Expression Preview
  spec (primary/secondary/offset roles, not a dense ticker table — confirm current content matches
  before touching); no other section needs to move.
- `templates/_partials/ai_analyst.html` — no structural move needed (it already sits second-to-last,
  below all primary content); confirm no CSS gives it more visual weight than a narrative card.
- `templates/login.html`, `signup.html`, `reset_password.html`, `account.html`, `preferences.html` —
  replace ad-hoc inline/hardcoded colors with the shared token set so auth/account surfaces stop
  looking like a bolted-on feature.
- `mne/presentation_language.py` — additive only. Add public-label entries only for the approved Keep
  terms that have a confirmed engine-field mapping (see §4 table): X-Ray View, Market Reaction,
  Narrative Gravity, the literal Narrative Pulse metric, and the new composite "Narrative Direction" /
  "Recent Movement" label (built from existing Pulse + Acceleration/rotation values — see Ratified
  Decision 2). Do not rename or redefine the internal `"Narrative Pulse"` engine metric key — it stays
  exactly as-is, already translated to `"Strength"`. Do **not** add entries for Attention Velocity,
  Primary-Source Support, or Daily Launch Line this sprint (Ratified Decision 3) — those are documented
  in `docs/ui_naming_framework.md` only, as reserved terms with no implementation.
- `dashboard.py` — presentation-context wiring only: pass whatever existing `narrative_leadership` /
  `view.presentation` data the reserved Narrative Discovery Preview needs; replace the raw
  `EntitlementDenied` exception handler string (lines 161–167) with a render of the new
  `locked-state` template partial, same status code and message, styled instead of bare HTML.
  Optional unrelated cleanup while in this file: remove the unreachable second `return None` in
  `build_personalization_context` (line 257, after the real `return context` at 256).

**Create:**
- `templates/_partials/xray_disclosure.html` — Jinja macro wrapping a `<details class="xray-disclosure">`
  element, parameterized by summary label, plain-language explanation, and a block of supporting
  content, so Narrative/Sector/Market X-Ray all render through one component instead of bespoke markup.
- `templates/_partials/locked_state.html` — reusable entitlement/locked card + full-page variant,
  driven by `mne.entitlements.ENTITLEMENT_COPY` / `usage_summary()`, replacing the current bare
  `HTMLResponse(f"<h1>Access unavailable</h1>...")` fallback in `dashboard.py`.
- `docs/design_system.md` — the ratified token/typography/spacing/motion reference, including the
  teal/amber/slate usage rule from Ratified Decision 1.
- `docs/ui_naming_framework.md` — the Keep/Avoid label table with engine-field mappings, plus an
  explicit "Reserved — not implemented" section listing Attention Velocity, Primary-Source Support,
  and Daily Launch Line so the terms aren't lost, only deferred.

**Update (docs hygiene, not scope creep — both are already stale against the live app):**
- `docs/dashboard_rework_handoff.md` §2.1 — its section list predates "My Narratives" and the AI
  Analyst panel; add them so the doc matches the live 10-section `dashboard.html`.
- `docs/product_backlog.md` lines ~148–150 — still say entitlement enforcement is "Future, not
  implemented"; it shipped in `ef3ee20`. Not this sprint's core job, but touch it if the naming pass
  already has the file open.

**Tests (new or extended, mapped to the 22 requirements in §12 of the original spec):**
- `tests/test_dashboard_trust_summary.py` / `test_dashboard_trust_fixes.py` — extend for the new
  section order and the reserved Narrative Discovery Preview placeholder.
- `tests/test_presentation_language.py` — extend `test_canonical_copy_is_exact` deliberately for any
  new label; do not let it break by accident.
- new `tests/test_design_system_structure.py` (or similar) — asserts hierarchy order, that a
  plain-English takeaway renders before any metric, that 3–5 narrative cards render, that admin
  sections never leak (reuse the existing pattern from
  `test_user_dashboard_does_not_render_source_confidence_admin_section`), that the locked-state
  component renders for a denied entitlement instead of the raw exception string, and that no
  prediction/trading/scoring language appears.

## 3. Design-System Summary

The dark neutral base the new spec calls "deep obsidian" already exists — `--bg: #090b0f` — it has
just never been named that in docs. `docs/design_system.md` should document the existing token set as
canonical rather than reinvent it:

- **Base:** `--bg`, `--bg-soft`, `--panel`, `--panel-soft`, `--surface-0/1/2/3`, `--border(-strong)`,
  `--text`, `--muted`, `--muted-strong` (`static/styles.css:1–76`).
- **Two-hue budget (ratified `dashboard_rework_handoff.md` §2.4, amended once already in
  `dashboard_sprint_d_handoff.md` Part 2 to let green double as brand accent, amended again by this
  handoff per Ratified Decision 1):** `--up`/`--teal: #4ade80`, `--down`/`--amber: #f87171` — same two
  hex values, no third hue introduced. Usage is now broader than price deltas but still governed by
  the same rule: **"tone is primarily communicated through typography, hierarchy, icons, and wording;
  hue is reserved for meaningful state or change."** Teal/amber may appear only when backed by a real
  data-driven state (confirming/strengthening → teal; weakening/contradiction/pressure → amber;
  neutral/unavailable/unchanged → slate/`--muted`), and only as a small accent (icon, dot, thin border,
  or arrow) — never a full card tint, never a background fill, never applied decoratively or to a value
  that hasn't actually changed. The dashboard must not read as a red/green trading terminal.
- **Typography:** Inter + system-ui stack (`styles.css:90`) already matches "modern geometric
  sans-serif" — no change. `--font-serif` is defined (`styles.css:61`) but only used in a handful of
  `.support-score`-style display numbers — decide in this sprint whether that's an intentional accent
  treatment worth documenting or dead weight worth removing (small, not blocking).
- **Spacing:** `--space-1..9` (4px→96px), `--rail-width: 208px` — already generous, matches the "no
  dense terminal layout" goal. No change needed.
- **Motion:** existing hover states (translateY + `--shadow-soft`, 150ms) are already subtle. The one
  real gap: **no `@media (prefers-reduced-motion: reduce)` block exists anywhere in `styles.css`**
  (confirmed via grep — zero hits). Add one that disables the chart-scrub transition, card hover
  translate, and any `<details>` open/close transition.

## 4. Naming-Framework Summary

`mne/presentation_language.py` (807 lines) is already a mature dual-label system (`METRICS`, `STATES`,
`_entry(label, meaning, tone)`), not a blank slate. New terms should follow that exact shape. Mapping
status for each approved Keep term:

| Public label | Meaning | Engine mapping | Status |
|---|---|---|---|
| X-Ray View | Reveal deeper structure/evidence | The existing `<details class="why-expander">` pattern, used pervasively today | **Ready** — formalize, don't invent |
| Market Reaction | Price/sector expression | Existing `market_expression*` context keys + `MARKET_EXPRESSION_COPY` | **Ready** — mostly a relabel of what's shown in "Markets Right Now" |
| Narrative Gravity | Concentration of attention around the leading narrative | Existing narrative-leadership rotation states (Dominant/Holding/Challenged/…) | **Ready**, verify against the leadership-rotation engine's exact concentration metric before wiring the label |
| Narrative Pulse (literal) | The existing persisted Pulse lifecycle metric only (Dormant→Emerging→Building→Strong→Dominant) | Existing internal `"Narrative Pulse"` metric, already translated to `"Strength"` | **Ready.** Use the label "Narrative Pulse" **only** where the displayed value maps directly to this metric — never as a broader composite. |
| Narrative Direction / Recent Movement (new composite label) | Broader strengthening, fading, or stability context | Composed from existing Pulse + Acceleration/rotation values, not a new field | **Ready.** This is the correct label for the broader composite the spec originally called "Narrative Pulse" — implement as its own entry, do not reuse the Pulse name for it (Ratified Decision 2). |
| Attention Velocity | Rate of growth of public discussion | Candidate: `Crowding` (already translated to `"Attention"`), but Crowding reads as a snapshot level, not a rate/derivative over time | **Deferred by decision, not just unverified.** Do not display, implement, or fabricate a placeholder for this label this sprint. Document as reserved in `docs/ui_naming_framework.md` only. |
| Primary-Source Support | Support from official releases, filings, transcripts, direct statements | One `source_type` field exists at `mne/historical_backfill.py:265` on raw backfill records — no evidence found of a general primary/secondary classification surfaced through `source_intelligence`/`evidence_quality` | **Deferred by decision.** Do not display, implement, or fabricate a placeholder for this label this sprint. Document as reserved only. |
| Daily Launch Line | Daily open reference | No "daily open" concept found anywhere in the codebase (`grep -ri` clean) | **Deferred by decision.** Explicit non-goal per §10 of the original spec ("Daily Launch Line chart behavior") — document as reserved only, no wiring, no placeholder chart or gauge. |

**Avoid list** — confirmed via grep that none of these terms exist in the codebase today
("Smart Money Reality," automatic "Fact Check," "Hype Meter" as a primary label). This section of the
doc is a guardrail against introducing them later, not a removal task.

## 5. Dashboard Hierarchy

The live `templates/dashboard.html` (371 lines) already renders in almost the requested order — this
is a gap-fill, not a rebuild:

| Spec section | Current state | Action |
|---|---|---|
| A. Market Orientation / Hero | `#overview .support-hero` (lines 73–140) — plain-English takeaway, strengthening/fading state, market-expression sentence, historical-context sentence, Why-expander, scrub chart | No structural change |
| B. Dominant Narrative Cards | `#stories .story-grid` (163–233) | No structural change; apply naming-framework labels where mapped (§4) |
| C. Narrative Discovery Preview | **Does not exist** | **Net new** — reserve visual space and a component boundary only; a compact ranked list using existing `narrative_leadership` data is acceptable, no interactive constellation |
| D. Market Expression Preview | `#markets .dashboard-section` (262–287), "Markets Right Now" | Verify content matches "primary/secondary/offset roles, no dense ticker table" before assuming it's done — not independently confirmed in this pass |
| E. My Narratives / Alerts | `#my-narratives .personalization-section` (235–260) | Already visually integrated between Stories and Markets, not appended at the bottom — likely satisfies the spec already; confirm visual weight matches surrounding cards |
| F. Historical Entry Points | `.dashboard-next-section` (361–367), "Explore historical narratives →" | Present but minimal (one link only, no compare/request entry points on the dashboard itself — those live on `/history`); confirm whether the spec wants more than one link here or whether routing through `/history` is sufficient |
| G. AI Analyst | `_partials/ai_analyst.html` include (line 360) | Already positioned last-but-one, already styled with no special "featured" weight — likely already satisfies "position as explanation tool, not primary intelligence" |

## 6. Progressive-Disclosure Behavior

Formalize what already exists rather than invent new interaction: every disclosure today is a native
`<details>`/`<summary>` (`.why-expander`, `.data-quality-pill`, `styles.css:3742–3760, 4536–4549`) — zero
JS-driven accordions exist. Build one Jinja macro, `xray_disclosure(...)`, in
`templates/_partials/xray_disclosure.html`, parameterized for the three variants:

- **Narrative X-Ray:** supporting headlines, source mix, lifecycle metrics, confidence/limitations,
  historical context — mostly data already present in `narrative_investigation.html`'s evidence zones.
- **Sector X-Ray / Market X-Ray:** relative strength, participation, exposure, offset/contradiction —
  content depth here is bounded by what `market_expression*` and `market_context` already carry; do not
  add new data sources this sprint (Sector Isolation and the full heatmap are explicit non-goals).

Each variant keeps native `<details>` semantics (free keyboard support, no ARIA reinvention needed) and
gets a short default-state explanation line before the expand affordance, matching the existing
Why-expander convention.

## 7. Component-System Summary

| Component | Plan |
|---|---|
| Page shell | Exists (`.user-dashboard` wrapper) — no change |
| Section header | Exists per-section — audit for one consistent class, consolidate if divergent |
| Narrative card | Exists (`.story-grid` cards) — apply naming labels only |
| State badge | Exists (`.tone-good/neutral/caution`, `.rotation-chip`). May gain a small teal/amber/slate accent (icon or dot, not a fill) per Ratified Decision 1, only where the state genuinely changed — typography remains the primary signal. |
| Metric supporting detail | Exists (stat chips inside cards) |
| Explanation block | Exists (`.why-expander`) — becomes the basis for `.xray-disclosure` |
| Compact evidence preview | Exists in evidence grid (`#evidence`) — reuse, don't rebuild |
| X-Ray disclosure | **New formalization** — see §6 |
| Market-expression preview | Exists (`#markets`) — verify content shape (§5, row D) |
| Empty/degraded state | Exists (e.g. "You aren't following any narratives yet…") — reuse pattern for new components |
| Locked/entitlement state | **Genuinely net-new.** Today a denied entitlement produces one unstyled `HTMLResponse` string (`dashboard.py:161–167`); `account.html` has one plain `<p>` upgrade line. No in-context locked-card pattern exists anywhere. This is real component work, not a relabel. |
| Alert item | Exists (`preferences.html` recent-alerts list, personalization card) |
| Action link/button hierarchy | Exists (`.accent-link`) — audit for consistency across new components |

## 8. Existing-Feature Preservation

Each item maps to a real guardrail already in the test suite — do not weaken these, extend them
deliberately if a label changes:

- Explanation Layer / trust summary → `tests/test_dashboard_trust_summary.py` (20 tests, includes one
  full-render end-to-end assertion).
- Admin content never leaking to `/` → `test_user_dashboard_does_not_render_source_confidence_admin_section`,
  plus `tests/test_dashboard_context_split.py` (`include_admin=False/True` split).
- Exact translated copy → `tests/test_presentation_language.py::test_canonical_copy_is_exact` — **will
  intentionally fail** if labels change; update it in the same commit as the label change, never let it
  fail silently.
- AI Analyst safety boundary → `tests/test_ai_analyst.py` (`test_sensitive_fields_never_enter_context`,
  provider-fallback tests).
- Personalization/alerts, accounts, entitlements, usage limits, authorization → their existing dedicated
  suites (`test_personalization.py`, `test_accounts.py`, `test_entitlements.py`, `test_usage_limits.py`,
  `test_authorization.py`) — none of this sprint's changes should touch their underlying logic, only how
  denial/empty states are rendered.
- Admin/user nav separation → `_partials/app_rail.html:24`'s existing `role == 'ADMIN'` gate — do not
  restructure; only re-skin.

## 9. Responsive / Accessibility Behavior

- **Reduced motion:** currently unimplemented (confirmed, zero `prefers-reduced-motion` hits in
  `styles.css`) — must be added, not just "respected" as already-true.
- **Keyboard:** native `<details>` is keyboard-accessible by default; no custom JS toggle to reinvent
  for X-Ray. If any component needs behavior `<details>` can't do (animated height, exclusive
  accordion), that's new JS territory — flag it, don't assume it's free.
- **Mobile overflow (390px):** not verified in this research pass. Audit the run-selector form, the
  "Markets Right Now" row layout, and any historical-comparison tables specifically — these are the
  most likely overflow sources given their existing density.
- There is no Playwright/browser test suite currently exercised (`.playwright/` exists but is empty) —
  all current dashboard testing is server-side HTML-string assertion. Decide explicitly whether visual
  responsive checks are manual-only this sprint (per the original spec's "Manual visual verification"
  list) or whether to introduce Playwright now — that's a tooling decision, not something to slip in
  quietly.

## 10. Safety and Language Verification

- No raw dict/enum/telemetry leakage: covered by `test_sensitive_fields_never_enter_context` and the
  existing `.untranslated` fallback convention (unknown states render literally rather than crash —
  `dashboard_rework_handoff.md` §1.2's rule, already implemented).
- No prediction/trading/scoring language: grepped the current dashboard-facing copy in
  `presentation_language.py` and `dashboard.html` — no "buy/sell/recommend/target price" language
  present today. Add an explicit grep-based test asserting this stays true as new copy is added.
- No taxonomy/scoring behavior changes: this sprint touches `dashboard.py` only for presentation
  wiring and the entitlement-denial render path — no scoring, threshold, or classification code.

## 11. Verification Performed

This handoff is the product of a read-only research pass — no code was written or executed. Verified
by direct file inspection and grep, not assumption:
`static/styles.css` (token block, hardcoded-color audit, reduced-motion absence, tone-color mapping),
`templates/dashboard.html` and all `_partials/`, `dashboard.py` (routes, context assembly, exception
handler), `mne/presentation_language.py` (full label/state inventory), `mne/personalization.py`,
`mne/alert_engine.py`, `mne/auth.py`, `mne/models.py`, `mne/account_repository.py`, `mne/security.py`,
`mne/entitlements.py`, `mne/usage_limits.py`, existing test files listed in §2/§8, and the three prior
ratified handoff docs (`dashboard_rework_handoff.md`, `dashboard_sprint_d_handoff.md`,
`product_packaging_and_monetization.md`). Codex must run the commands in the Verification section below
after implementing — nothing in this document substitutes for that.

## 12. Known Remaining Gaps

- **Color-budget scope and the Narrative Pulse naming collision are resolved** — see Ratified Decisions
  1 and 2 below. No longer open conflicts.
- Attention Velocity, Primary-Source Support, and Daily Launch Line are **deferred by decision** (§4,
  Ratified Decision 3), not merely unverified — document as reserved terms only, with no placeholder
  UI, fabricated states, or untranslated passthroughs standing in for them.
- Auth/account/preferences templates bypass the token system entirely (hardcoded `#d8d8d8`, `#aaa`, and
  a `var(--border-color, #d8d8d8)` fallback referencing a token that doesn't exist) — this is the
  clearest concrete evidence the product doesn't yet "feel like one product," and squarely in scope for
  a foundation sprint.
- Locked/entitlement UI is not a minor component tweak — it's new from nothing. Scope it accordingly.
- `docs/dashboard_rework_handoff.md` and `docs/product_backlog.md` are both stale against the current
  app state (missing sections, outdated entitlement status) — worth a documentation pass alongside this
  work so the next sprint doesn't inherit the same drift.
- Minor unrelated dead code: `build_personalization_context` has an unreachable second `return None`
  (`dashboard.py:257`).
- No visual/browser regression testing exists — all current coverage is server-rendered HTML-string
  assertion (§9).

## 13. Recommended Next UI Sprint

In priority order: (1) confirm/build the real data backing for Attention Velocity, Primary-Source
Support, and Daily Launch Line, then implement those labels once genuinely supported, (2) full Narrative
Discovery Preview → interactive constellation, (3) Sector Isolation view + sector heatmap + Sector
X-Ray, (4) Asset Exploration page + Market X-Ray, (5) Daily Launch Line chart behavior (contingent on
#1), (6) catalyst countdown timers, (7) roll the locked/entitlement component out to every gated route,
not just the dashboard's denial path.

## 14. Implementation Status

**Not implemented — ratified and ready to hand to Codex.** This document is the handoff only. All
judgment calls are resolved (see Ratified Decisions below). Mark "MNE Design System and Dashboard
Experience Foundation" implemented only after Codex completes the scoped work and all verification
commands below pass.

---

## Ratified Decisions (Daniel, 2026-08-02)

1. **Teal/amber semantic color use — ratified.** Keep the existing hex values and the two-hue budget
   (`--up`/`--teal: #4ade80`, `--down`/`--amber: #f87171`) — no third hue. Keep the rule "tone is
   primarily communicated through typography, hierarchy, icons, and wording; hue is reserved for
   meaningful state or change" as the governing principle. Teal/amber/slate may only be used when
   backed by real underlying data: teal = confirming/strengthening/constructive participation, amber =
   weakening/contradiction/pressure/caution, slate = neutral/unavailable/unchanged. No whole-card
   tinting, no decorative use, no red/green trading-terminal feel.
2. **Narrative Pulse naming conflict — ratified.** "Narrative Pulse" is used only when the displayed
   value maps directly to the existing persisted Narrative Pulse metric. The broader
   strengthening/fading/stability composite gets its own label — "Narrative Direction" or "Recent
   Movement" — built from existing Pulse + Acceleration/rotation values. The internal engine metric is
   not renamed or redefined this sprint.
3. **Labels without backing data — ratified.** Attention Velocity, Primary-Source Support, and Daily
   Launch Line are not displayed or implemented this sprint. No placeholder gauges, fabricated states,
   decorative labels, or untranslated passthroughs standing in for them. They remain documented in
   `docs/ui_naming_framework.md` as reserved product-language concepts for a later sprint once real
   supporting data and behavior exist.
4. **Net-new work — approved to proceed:** Narrative Discovery Preview, the reusable locked/entitlement
   component, reduced-motion support, replacing hardcoded auth/account/preferences colors with design
   tokens, naming-framework cleanup, and dashboard cohesion/component reuse.
5. **Boundaries — preserved, not rebuilt:** existing analytical behavior, the existing dashboard
   hierarchy where already correct, the existing two-hue color budget, existing progressive-disclosure
   patterns, the Explanation Layer, Trust Summary, Market Expression, Historical Connections, My
   Narratives, Alerts, AI Analyst, Entitlements, authentication/account navigation, and admin
   separation. None of these are rebuilt merely for visual consistency.

## Remaining Open Items (not conflicts — verification steps for Codex during implementation)

- **Market Expression Preview content check** (§5, row D): confirm "Markets Right Now" already shows
  primary/secondary/offset roles rather than a dense ticker list before treating it as a pure relabel.
- **Narrative Gravity's exact backing metric**: confirm which leadership-rotation field represents
  "concentration of attention around the leading narrative" before wiring the label.
- **`--font-serif` usage** (`styles.css:61`, used narrowly in `.support-score`-style display numbers):
  decide whether this is an intentional accent worth documenting in `docs/design_system.md` or dead
  weight to remove — low stakes, not blocking.
- **Mobile overflow at 390px** for the run-selector form and market-row layout: not verified in the
  research pass: audit during implementation, not assumed clean.

## Verification Commands (run after implementation, not before)

- Focused: `python -m unittest tests/test_dashboard_trust_summary.py tests/test_dashboard_trust_fixes.py tests/test_dashboard_context_split.py tests/test_presentation_language.py tests/test_ai_analyst.py -v`
- Full suite: `python -m unittest discover -s tests`
- Syntax: `python -m compileall dashboard.py main.py mne tests`
- Diff hygiene: `git diff --check`
- Manual visual pass at 1280px / 1024px / 390px, JS disabled, reduced-motion enabled, populated state,
  low-data/degraded state, logged-out Free user, authenticated Free user, and Pro/internal-access user —
  confirm the first view reads without financial fluency, metrics support rather than dominate the
  explanation, the path into Research is obvious, and the page reads as neither a terminal nor a game.

Implement to a verified local state and stop — do not stage, commit, or push.
