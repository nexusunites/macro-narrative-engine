# Dashboard Visual Rework v2 — Implementation Handoff

## Purpose

The user dashboard (`/`, rendered by `dashboard.py:2321` → `templates/dashboard.html` + one
hand-written stylesheet `static/styles.css`, ~4985 lines, no build step) already carries the
plain-language layer and the answer-first architecture from the prior rework
(`docs/dashboard_rework_handoff.md`). What it lacks is a single, ratified *visual* target. This
sprint set brings the live dashboard to visual parity with an approved, self-contained mockup.

**The approved visual contract is `docs/mockups/dashboard_concept_v1.html`** — a pure-ASCII,
self-contained HTML file (~54KB) checked into the repo alongside this handoff. Open it in a browser
next to the live app at `/` while working; it is the source of truth for palette, spacing, motion,
and layout. Where this document and the mockup disagree, the mockup wins for pixels; this document
wins for scope and data honesty. Design rules are formalized in `docs/design_system.md` (v2, being
updated in parallel — reference it for token names and the two-hue budget rule).

**Scope is presentation-layer only** for Sprints A–D. No engine, scoring, threshold, taxonomy, or
persistence change. Admin stays operationally separate. Sprint E is a separately-tracked backend
prerequisite, scoped here but not designed here.

**Status: not implemented — ready to hand to Codex.** This is a Codex-ready brief; do not implement
directly from it, and do not stage, commit, or push.

---

## Approved palette (from the mockup — the retoken target)

| Token role | Approved value | Current `:root` value (`static/styles.css`) |
|---|---|---|
| App background | `#0B0E11` | `--bg: #090b0f` (L3) |
| Panel | `#12171D` | `--panel: #11161d` (L4) |
| Panel raised | `#171D25` | `--panel-soft: #171d26` (L5) |
| Teal (up/constructive) | `#2DD4BF` | `--up: #4ade80` (L15), aliased `--teal` (L62) |
| Teal bright | `#5EEAD4` | (none — new) |
| Amber (caution) | `#F0A64B` | `--warn: #d7b36a` (L14) |
| Red (down/pressure) | `#F16A5F` | `--down: #f87171` (L16), aliased `--amber` (L63) |
| Bright-slate steady text | `#C9D2DC` on `rgba(201,210,220,0.12)` | ad hoc `--muted`/`--status-*` |

Card recipe from the mockup: radius **16px**, padding **24px**, hover `translateY(-2px)` over
**150ms**. These become the unified card system (Sprint A).

---

## Data reality (read before Sprint C — this bounds what ships honestly)

The engine exposes only **3 populated narrative groups** (AI / Tech Growth, Macro Pressure,
Energy / Commodities; `Geopolitical Risk` is a fourth `NARRATIVE_GROUPS` key but is unmapped across
every curated layer today) over **5 scored themes** (`ai`, `rates`, `inflation`, `energy`,
`recession` in `config/theme_taxonomy.json`). There is **no sub-narrative / per-story extraction**
today. The mockup's attention cloud shows **15 named story chips** sized by weight — that content
does not exist in the engine yet. Sprint C therefore ships the *cloud mechanism* against a
view-model, populated at theme/group granularity via `mne/presentation_language.py` display names,
and the full 15-story experience is gated on Sprint E. Do not fabricate stories to fill the cloud.

---

## Sprint A — Foundation (retoken + unified card system)

**Files:** `static/styles.css` (`:root` L1–77 and the enumerated usage sites below), `docs/design_system.md` (token names must match).

**Tasks:**
1. Retoken `:root` to the approved palette above. Keep `--up`/`--down` as the canonical directional
   pair; repoint their hues to `#2DD4BF` / `#F16A5F`; add `--teal-bright: #5EEAD4`; move amber onto
   `#F0A64B`. Do **not** delete legacy tokens outright (Admin/Research still consume them) — retire
   them only from user-dashboard *scopes*.
2. Retire `--status-*`, `--accent` (and its `--brand-accent` alias), and `--warn` from every
   user-dashboard component, replacing them with the neutral base + the two-hue directional pair, or
   the bright-slate steady treatment. Enumerated usage (grep evidence, §Grep Evidence) is the work
   list.
3. Unify the card system: one surface/border/radius(16)/padding(24)/hover(`translateY(-2px)` 150ms)
   recipe applied across story cards (`#stories`, `templates/dashboard.html:166`), market rows
   (`#markets`, L267), sector tiles (`#sector-isolation`, L292 + `templates/_partials/sector_heatmap.html`),
   evidence (`#evidence`, L341), and events (`#events`, L297).
4. Brighten steady/neutral states to the bright-slate rule: `#C9D2DC` text on
   `rgba(201,210,220,0.12)` pills, bright-slate meter fills — replacing the muddy multi-hue
   `--status-*` chips currently used for rotation, delta, and event-lifecycle states.

**Acceptance:**
- No `var(--status-*)`, `var(--accent)`, `var(--brand-accent)`, or `var(--warn)` resolves onto any
  element rendered on `/`. (Admin/Research may still reference them.)
- Every card on `/` shares one radius/padding/hover recipe; visually diff against the mockup.
- Only the up/down directional pair appears as non-neutral hue on `/`; any third hue is a defect.
- Neutral/steady states read as bright slate, not olive/blue/violet.

## Sprint B — Hero + ticker

**Files:** `static/styles.css`, `templates/dashboard.html` (`.change-strip` L145–164; `#overview`
support-hero L76).

**Tasks:**
1. Convert `.change-strip` ("What Changed" chips) into the mockup's auto-scrolling marquee ticker:
   CSS `@keyframes` translating a **duplicated track** (`translateX(0 → -50%)`, **42s** linear infinite
   loop), pause-on-hover, and a `prefers-reduced-motion: reduce` static fallback that shows the chips
   without animation and without clipping. Keep the existing empty-state line ("No major changes
   since the last update.").
2. Restyle the `#overview` support-hero to the mockup's Market Support card layout (hero number,
   state word, delta chip, chart beneath). This is a *visual* restyle only — the existing hero
   chart/SVG and data wiring stay; no candle or chart-interaction work here (out of scope).

**Acceptance:**
- Ticker scrolls seamlessly (no visible seam at the loop point), pauses on hover, and renders as a
  static non-clipped strip under reduced-motion.
- Hero matches the mockup at 1440px; number, state word, and delta chip align per the mockup.

## Sprint C — Attention cloud (replaces the constellation node graph)

**Files:** `templates/_partials/narrative_constellation.html` (SVG node graph, included at
`templates/dashboard.html:238`), `static/narrative_constellation.js`, `static/styles.css`,
`dashboard.py` (view-model builder), `mne/presentation_language.py` (display names only).

**Tasks:**
1. Replace the SVG node graph with the mockup's story-chip **attention cloud**: chips sized by
   weight, plus the **story detail panel** (why / driving / watch-for / connected / tape-quote /
   trend) and the scroll-into-view interaction on chip activation.
2. The cloud **must consume a view-model, not engine keys** — build a `cloud` context in
   `dashboard.py` whose chips carry `{name, weight, direction, ...}` resolved through
   `presentation_language.py`, never raw theme/group keys. This keeps the template engine-language-free
   and lets Sprint E swap real stories in without a template change.
3. **Interim content caveat (state in the PR):** until Sprint E lands, the cloud renders
   theme/group-level chips (≤5 themes / 3 groups), not 15 stories. Do not pad to 15.

**Acceptance:**
- No engine-language leakage: no `ai`/`rates`/`Regime Alignment`/raw group keys in visible chip or
  panel copy (only inside any Why-expander).
- Chip activation opens the detail panel and scrolls it into view; keyboard-accessible; reduced-motion
  respected.
- View-model is the sole data source — grep the template for engine keys returns nothing.

## Sprint D — Watchlist (docked tab + sticky column)

**Files:** `templates/dashboard.html`, `static/styles.css`, wire to existing personalization
machinery (`#my-narratives`, `templates/dashboard.html:240`; `static/personalization.js`) where sensible.

**Geometry (exact — from the mockup):**
- Two-column shell with a **single centering owner**: `grid-template-columns: minmax(0, 1fr) 260px`,
  `gap: 24px`.
- When open (≥1200px), shell `max-width` expands **1200 → 1484px** so free page margin is consumed
  before content shrinks.
- The 260px right column is `position: sticky`; its top is **flush with the Market Support card** —
  `margin-top` matches the hero section's top padding (**36px** offset).
- Below 1200px: docked star tab collapses to a floating button + overlay panel (**280px**), not the
  sticky column.

**Tasks:** Build the docked star tab → sticky column at ≥1200px, the sub-1200px floating button +
overlay, and wire watchlist contents to the existing personalization/#my-narratives data where it
maps cleanly. Do not invent new persistence.

**Acceptance:**
- At ≥1200px the column top is flush with the Market Support card and content does not shrink until
  page margin is exhausted (shell reaches 1484px first).
- At <1200px the overlay panel (280px) opens/closes from the floating button; no horizontal scroll.
- Watchlist reflects the same narratives the personalization section manages.

## Sprint E — Sub-narrative story extraction (BACKEND, separate track — prerequisite for full cloud)

**Not designed in this document.** Scope only. This is the backend prerequisite that gives Sprint C
its real 15-story content. Cluster headlines *within* a theme into named stories with attention
weights, feeding the Sprint C view-model.

- **Inputs:** scored themes and their source headlines (existing engine output).
- **Outputs (per story):** `name`, `weight` (1–5), `direction`, `driving sectors`, `catalysts`,
  `connected stories`, `source headline`.
- **Boundary:** do NOT design the clustering algorithm here. State the contract, mark it as the
  gate for full cloud content, and hand it to a dedicated backend brief. Until it lands, Sprint C
  ships the interim theme/group-level cloud.

---

## Verification requirements (per sprint)

1. Run the dashboard locally against the latest result file; load `/`.
2. Compare against `docs/mockups/dashboard_concept_v1.html` open side-by-side at **1440 / 1024 / 390**
   widths. No horizontal page scroll at any width.
3. Reduced-motion check (`prefers-reduced-motion: reduce`): ticker static, no hover translate, cloud
   scroll-into-view degrades gracefully.
4. No engine-language leakage in any new copy on `/` (grep the rendered output for raw group/theme
   keys and internal metric names; they belong only in Why-expanders).
5. No console errors; Admin and Research routes visually unchanged.

---

## Out of scope

- Admin pages (operationally separate).
- Research / history pages — keep their current look; the retoken is user-dashboard-scoped, and the
  legacy tokens persist for these surfaces.
- Any chart / candle / chart-interaction work (the hero chart is restyled, not rebuilt).
- Engine, scoring, taxonomy, threshold, or persistence changes (except Sprint E's separate track).

---

## Grep Evidence (run 2026-08-04 against `static/styles.css`, 4985 lines)

Counts below are the retirement work list for Sprint A. All are `var(...)` consuming usages unless
noted; token *definitions* live in `:root` L38–44 (`--status-*`), L12 (`--accent`), L14 (`--warn`).

- **`--status-*` scale:** `grep -c -- '--status-'` = **34 matches** — 7 definitions (L38–44) + **27
  consuming usages**. Usage sites: L767, L845, L2998, L3006, the rotation/delta chip cluster
  L3548–L3559, the event-lifecycle state chips L3607–L3613, and L3679–L3721. These are all
  user-dashboard chips (rotation, delta, event state).
- **`--accent` (legacy brand green `#68d391`):** `grep -E 'var\(--accent\)'` = **18 matches** — L35
  is the `--brand-accent: var(--accent)` alias definition; the other **17 are consuming usages**
  (L1041, L1164, L1171, L1291, L1420, L1456, L1603, L1655, L1859, L1935, L1937, L2413, L2504, L2570,
  L2649, L2697, L2838). `--accent-soft` has **0** `var()` usages.
- **`--brand-accent` (aliases `--accent`):** `grep -E 'var\(--brand-accent\)'` = **24 usages** — all
  resolve to the same legacy `#68d391`. Effective legacy-green surface = 17 direct + 24 via
  `--brand-accent` = **41 usages** to retire from user-dashboard scopes.
- **`--warn` (`#d7b36a`):** `grep -E 'var\(--warn'` = **5 matches** — L40 is the
  `--status-attention: var(--warn)` definition; the other **4 are consuming usages** (L495, L2422,
  L2574, L2653).

Codex must re-run these greps before and after Sprint A; the "after" count for user-dashboard scopes
must reach zero (Admin/Research references may remain).
