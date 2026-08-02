# MNE User Dashboard Rework — Codex Implementation Handoff

## Purpose

Full rework of the user dashboard (`/`, `templates/dashboard.html` + `static/styles.css`) around two goals:

1. **Comprehension without a guide.** A first-time viewer must understand every element without explanation. Internal vocabulary (Regime Alignment, Pulse, Crowding, Pre-Catalyst Chop) is engine language, not user language.
2. **Robinhood-grade UI.** The current dashboard is a long scroll of uniform cards and raw tables. The rework adopts the Robinhood pattern: one hero number with an interactive chart, a small set of large answer-first cards, progressive disclosure, and directional color.

Scope is presentation-layer only. No engine, signal, threshold, or persistence changes. Admin dashboard untouched. All engine terminology remains canonical internally — this rework adds a translation layer on top, preserving terminology discipline.

---

## Part 1 — Plain-Language Layer

### 1.1 Principle

Every user-facing element leads with a plain-English answer to a question a normal person would ask. The internal metric name appears only as a small secondary caption (for continuity with Admin/Research), never as the primary label. Every state string passes this test: *would a non-finance friend understand it with zero context?*

### 1.2 Implementation shape

Create `mne/presentation_language.py`: a deterministic, dictionary-based translation module (no logic, no inference — pure lookup with an explicit fallback that passes the raw string through and flags it). The dashboard view-builder in `dashboard.py` calls it; templates render only translated fields. Unknown states must never crash — render the raw value with a subtle "untranslated" style so gaps are visible in review.

Each translation entry has three fields:

- `label` — the plain-English state (2–5 words)
- `meaning` — one sentence, plain English, shown as supporting text or in the "Why?" expander
- `tone` — one of `good | neutral | caution` for color mapping (see 2.4)

### 1.3 Copy dictionary (canonical — implement exactly, extend by pattern)

**Metric names → user-facing questions/labels:**

| Internal | User-facing label | Supporting question shown as caption |
|---|---|---|
| Regime Alignment | Market Support | "How supportive is the market backdrop right now?" |
| Dominant Narrative | Today's Top Story | "What is the market talking about most?" |
| Narrative Leadership | The Stories Driving Markets | "Which stories lead, and who's gaining or fading?" |
| Narrative Pulse | Strength | — |
| Acceleration | Momentum | — |
| Crowding | Attention | — |
| Market Environment | Market Mood | — |
| Catalyst Environment | Upcoming Events | — |
| Positioning | Trader Behavior | — |
| Change Summary | What Changed | "Since the last update" |
| Market Snapshot | Markets Right Now | — |
| Example Headlines / Top Theme Evidence | What We Read | "The headlines behind today's read" |
| Regime Alignment History | Support Over Time | — |
| Data Quality (trust summary) | Data Quality | — |

**State strings (examples across each vocabulary — complete the pattern for every state in `mne/environment.py`, `mne/positioning_environment.py`, `mne/operating_modes.py`, `mne/breadth.py`, pulse/acceleration/crowding, rotation states):**

| Internal state | `label` | `meaning` | `tone` |
|---|---|---|---|
| Clean Risk-On | Markets are confident | Investors are buying broadly with little hedging. | good |
| Fragile Risk-On | Confident, but on edge | Markets are rising, but the gains are narrow and easily shaken. | caution |
| Risk-Off | Markets are defensive | Investors are pulling back toward safety. | caution |
| Macro Stress | Economic worry is driving markets | Big-picture concerns (rates, inflation, growth) are in control. | caution |
| Nasdaq Pre-Catalyst Chop | Drifting before a big event | Markets are moving sideways while waiting on an upcoming event. | neutral |
| Active Catalyst Positioning | Traders are positioning for an event | An imminent event is visibly shaping trading behavior. | neutral |
| Pre-Catalyst Positioning | Getting set ahead of an event | An upcoming event is starting to influence positioning. | neutral |
| Normal Positioning Environment | Nothing unusual | No event is meaningfully distorting trading behavior. | neutral |
| Pulse: Dormant | Quiet | This story is barely present in the news. | neutral |
| Pulse: Emerging | Starting to build | This story is beginning to show up consistently. | neutral |
| Pulse: Building | Gaining traction | Coverage is growing steadily. | good |
| Pulse: Strong | A major story | This story commands a large share of coverage. | good |
| Pulse: Dominant | The story everyone's telling | This story dominates the news cycle. | good |
| Acceleration: Rising | Heating up | — | good |
| Acceleration: Stable | Holding steady | — | neutral |
| Acceleration: Cooling | Cooling off | — | caution |
| Crowding: Low | Room to grow | Attention isn't concentrated here yet. | neutral |
| Crowding: Moderate | Getting noticed | A meaningful share of coverage is converging here. | neutral |
| Crowding: High | Everyone's watching | Attention is heavily concentrated — crowded stories can reverse fast. | caution |
| Rotation: Holding Leadership | Holding the lead | — | good |
| Rotation: Challenging | Closing in | — | neutral |
| Rotation: Losing Influence | Fading | — | caution |

**Numbers and units:**

- "55 / 100" → keep the number as hero, but the state word carries the meaning ("55 — Mixed support"). Score bands map to plain words: 0–39 "Unsupportive", 40–59 "Mixed", 60–79 "Supportive", 80–100 "Strongly supportive". *(Bands are presentation-only; do not alter engine scoring. Use existing regime state string if it already encodes this — prefer engine truth over new bands where available.)*
- "mentions" → "N stories" (e.g., "23 stories today").
- "concentration gap" / "Gap" → "lead over #2".
- "share_delta +3 pts" → "+3 pts of coverage share" with an up/down arrow.
- "X-day streak" stays — it's already plain.
- Confidence lines ("Confidence: Medium") → "Based on partial data" (Low), "Based on solid data" (Medium/High). Keep exact mapping in the dictionary.

**Narrative group names** stay as-is (AI / Tech Growth, Macro Pressure, Energy / Commodities) — they're already legible.

### 1.4 Explainability preserved

Every card gets a "Why?" affordance (expander or tooltip) revealing the engine's `reason` string plus the internal metric name and raw state — e.g., "Engine signal: Regime Alignment · Fragile Risk-On". This keeps the hand-derivable standard intact while removing jargon from the primary surface.

---

## Part 2 — Visual Rework (Robinhood-inspired)

### 2.1 Page architecture (top to bottom, replacing current order)

1. **Hero — the one number.** Market Support score, rendered huge (`--text-size-display`), with plain state word beside it, delta chip vs. previous run ("+7 since yesterday"), and the interactive history chart directly beneath. This is the Robinhood "portfolio value + chart" moment. The current mode-context sentence ("Drifting before a big event") becomes the one-line subtitle under the number.
2. **What Changed** — compact horizontal strip of change chips (not a four-column grid). Empty state: single quiet line "No major changes since the last update."
3. **The Stories Driving Markets** — the three narrative cards, redesigned (2.3).
4. **Markets Right Now** — Robinhood-style instrument list rows (2.3).
5. **Upcoming Events** — event lifecycle list, translated labels, countdown chips.
6. **What We Read** — headline evidence, grouped by story.

**Removed from the user dashboard** (moved to Admin or dropped): Narrative Scores table, Narrative Group Scores table, the duplicate environment card-grid at `#catalysts` (its content merges into the hero subtitle, Upcoming Events, and the Why-expanders), the Daily Leadership table (replaced by rotation chips on the narrative cards; full table remains available in Research/Admin). The trust-summary banner shrinks to a small Data Quality pill in the header that expands on click — a banner-sized warning is an enterprise pattern.

### 2.2 Header and navigation

- Keep the app rail. Replace in-page anchor subnav with real hierarchy later (existing backlog item); for now the subnav anchors may remain but restyle as quiet text links.
- Run selector: replace raw filenames with formatted labels ("Today 2:45 PM", "May 21") — resolves the known raw-filename debt item. Keep the filename as the option `value`.

### 2.3 Card system

- **Narrative cards:** rank number small, story name as the headline, then one plain sentence composed from translated states ("A major story, heating up, and everyone's watching it."), then three quiet stat chips (Strength / Momentum / Attention) with translated values, rotation chip with arrow + delta, thin share meter, "Why?" expander, and the investigate link styled as a quiet arrow-link. Sentence composition is deterministic template-fill from the three translated labels — no free generation.
- **Market list:** replace the table with borderless rows — ticker symbol, friendly name, price, and a right-aligned % change chip colored directionally (2.4). This is the single most Robinhood-identifiable pattern; get it exact: tight rows, no gridlines, generous horizontal padding, hover highlight.
- General card treatment: fewer borders, more space. Increase card padding to `--space-5/6`, drop most `1px` borders in favor of surface-contrast (`--surface-1` on `--bg`), radius 16px, remove heavy shadows in favor of `--shadow-soft` on hover only.

### 2.4 Color — strict budget (ratified by Daniel)

Robinhood's cleanliness comes from a hard color budget: a black/white neutral base plus **at most two non-neutral colors per page**. The user dashboard adopts this rule exactly.

- **Base:** `--bg` blacks, `--surface-*` panels, white/grey text tiers. Everything defaults to neutral.
- **The two colors** are the directional pair:
  - `--up: #4ade80` (green, tuned for `--bg`)
  - `--down: #f87171` (red-orange)
  - Usage strictly limited to: % change chips, delta chips, rotation arrows, momentum arrows.
- **States carry meaning through words and typography only** — weight, size, and text tier (`--text-primary` vs `--text-tertiary`), never color. The `tone` field maps to typographic emphasis, not hue. Retire `--warn`, `--accent`, and the multi-hue status scale from the user dashboard (they may persist in Admin/Research; do not delete the tokens).
- Enforcement check per sprint: any non-neutral color on `/` that is not the up/down pair is a defect.

### 2.5 Hero chart (interactive)

Replace the static SVG with a hover-scrubbable line chart: crosshair follows pointer, score + date readout updates in a fixed position above the chart (Robinhood scrub pattern), subtle gradient fill under the line, no gridlines, no axis clutter (min/max labels only). Time-range pills below: `2W · 1M · 3M · All`, driven by the existing daily-snapshot history (respecting the run-vs-snapshot data philosophy — chart uses daily snapshots only). Vanilla JS in a small inline `<script>` or `static/chart.js`; no framework, no build step, no external dependencies.

### 2.6 Typography and motion

- Numerals: tabular figures (`font-variant-numeric: tabular-nums`) everywhere numbers appear.
- Hero number at `--text-size-display`, section titles at `--text-size-h3` (calmer than current h2 usage), captions at `--text-size-label` in `--text-tertiary`.
- Motion: 150–200ms ease transitions on hover states and expanders only. No entrance animations, no pulsing.

---

## Part 3 — Sprint Plan

The live dashboard hierarchy also includes the integrated **My Narratives** personalization/alerts section and the lower-priority **AI Analyst** explanation panel. Both are preserved parts of the user experience; neither changes the user/admin context split.

**Sprint A — Language layer.** `mne/presentation_language.py` + dictionary, view-builder integration, template text swap, Why-expanders, run-selector labels, confidence rewording. No layout changes. Verifiable: render latest run, confirm zero internal state strings visible on `/` outside Why-expanders.

**Sprint B — Layout and cards.** New page architecture, hero (static chart initially), narrative cards, market list rows, removals/relocations, trust pill, spacing/color/typography system including directional tokens.

**Sprint C — Chart interactivity and polish.** Scrub chart, range pills, hover/motion pass, empty states, responsive check at 1280 / 1024 / 390 widths.

Each sprint independently shippable; A before B before C.

---

## Part 4 — Ratified Decisions (Daniel, 2026-07-29)

1. **Directional red/green: approved,** under a strict color budget — black/white neutral base plus at most two non-neutral colors per page (the up/down pair). See 2.4 for the enforcement rule.
2. **Detail tables leave the user dashboard: approved as a trial.** Narrative Scores, Group Scores, and Daily Leadership tables move to Admin/Research. Reversible — if daily usage misses them, they return as collapsed sections.
3. **Internal terminology demoted to Why-expanders: approved for now.** Engine names (Regime Alignment, Pulse, Crowding) appear only inside Why-expanders, not on the primary surface.

---

## Verification

After each sprint: run the dashboard against the latest result file, load `/`, and confirm (a) no untranslated-state fallback styling visible, (b) no console errors, (c) Admin and Research routes unaffected, (d) empty-state rendering with a missing/old run file.

Implement to a verified local state and stop — do not stage, commit, or push.
