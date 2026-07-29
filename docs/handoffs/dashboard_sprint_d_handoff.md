# Dashboard Sprint D — Data Completeness + Visual Energy

## Purpose

Post-rework review of the live dashboard surfaced two problem classes: (1) "Unavailable" values and untranslated strings leaking into the primary surface, and (2) a visually flat page — the color budget was applied so strictly that the page lost the Robinhood energy it was meant to capture. Presentation-layer only; no engine, signal, threshold, or persistence changes; Admin/Research untouched. Extends `docs/dashboard_rework_handoff.md`.

## Part 1 — Data Completeness Fixes

1. **Attention (Crowding) on non-dominant cards.** The engine computes crowding for the dominant group only (`dashboard.py` ~line 1031) — this is correct engine behavior, not missing data. Fix: omit the Attention chip entirely on non-dominant narrative cards (do not render "Unavailable" or "—"). The Why-expander on those cards notes: "Attention is measured for the leading story only."
2. **Sentence composer must skip unavailable parts.** "Gaining traction, cooling off, and unavailable." is a defect. The deterministic composer joins only available translated states with correct serial comma handling: two states → "Gaining traction and cooling off."; one state → "Gaining traction." The word "unavailable" must never appear in a composed summary sentence.
3. **Pluralization.** "1 stories behind #1" → "1 story behind #1". Apply a small deterministic pluralize helper everywhere counts render ("N stories today", gap labels).
4. **What Changed chips bypass the language layer.** Route change-summary items through `presentation_language` at the view-builder (do not modify `mne/change_summary.py` output — translate at presentation time). Rules: theme/group names title-cased via existing mapping; "->" → "→"; "Concentration gap" → "Lead over #2"; "Dominant share" → "Top story's share"; score deltas read "29 → 13 stories". Prefix each chip with a directional arrow (▲/▼) colored `--up`/`--down` — these are deltas, so directional color is in-budget.
5. **What Changed duplicate entries.** Theme-level and group-level chips can report the same movement (e.g., "Energy weakened" and "Energy / Commodities weakened"). Presentation-level dedupe: when a theme belongs to a rendered group whose chip moves the same direction in the same run, drop the theme-level chip. Deterministic, uses the existing theme→group taxonomy mapping. *(Judgment Call #2.)*
6. **Empty-chart state.** The insufficient-history message currently renders twice (corner label and center). Render once, centered, with warmer copy: "History starts today — the chart fills in as daily updates accrue." Remove the corner duplicate.
7. **Upcoming Events sparse state.** When lifecycle events are absent, the section shows a vague summary sentence plus a notice bar. Collapse to one calm line combining state and notice: e.g., "A packed event calendar — but the schedule feed was partial this run, so listings may be incomplete." Drop the boxed Calendar Notice treatment on `/` (keep the underlying message inside the Why-expander).
8. **Stray Why-expander below Markets Right Now.** Move it inside the market card footer (quiet, right-aligned), not floating in page flow.

## Part 2 — Visual Energy (amended color budget)

**Amendment to rework handoff 2.4 (Judgment Call #1):** the budget stays at two non-neutral hues, but `--up` green is promoted to double as the single brand accent — exactly the Robinhood pattern (their green is simultaneously "up" and "brand"). `--down` remains strictly directional.

Apply the accent to, and only to:

- **Hero chart line and under-fill gradient** (green line, gradient fading to transparent — the signature Robinhood element). When interactive, the scrub crosshair stays neutral.
- **Range pills:** active pill = accent text; inactive = tertiary.
- **"Investigate narrative →" buttons** and the Admin link inside the quality popover: accent text, no filled backgrounds.
- **Active rail item indicator** and the Data Quality dot (when quality is healthy; degraded quality uses `--down`).
- **Leader card treatment:** rank-01 card gets a 2px accent top border (or left edge — pick one, apply consistently) and its share meter fills accent; non-leader meters stay white at reduced opacity.

Contrast and depth (neutral fixes for flatness):

- **Primary text up, chrome down.** Card titles and key values render at full `--text` white and heavier weight; labels drop to `--text-tertiary`. The current page reads mid-grey-on-grey — widen the gap between tiers instead of adding color.
- **Hero number larger** (fill the display size; it currently under-fills its slot) and the plain-state word ("Mixed support") at `--text` white, not muted.
- **Surface separation:** stat chips inside cards sit one surface level above the card (`--surface-2` on `--surface-1`); page background stays `--bg`. Card hover: translateY(-1px) + `--shadow-soft`, 150ms.
- **What Changed chips:** pill-shaped, `--surface-2`, arrow colored directionally per Part 1.4, text white.

## Part 3 — Judgment Calls for Daniel to Ratify

1. **Green doubles as brand accent (Part 2 amendment).** Keeps two hues total but expands green beyond deltas. This is the fix for "too muted"; the alternative (staying delta-only) keeps the page flat.
2. **What Changed dedupe rule (Part 1.5).** Theme chips are suppressed when their parent group chip shows the same-direction move. Alternative: show both with distinct labels. Recommend suppression — duplicates read as a bug.
3. **Attention chip omitted on non-dominant cards (Part 1.1)** rather than shown with a placeholder. Recommend omission; a permanent "—" chip invites the "what does this mean" question the rework exists to eliminate.

## Verification

Full test suite; render `/` against latest real run and a populated synthetic run; confirm: no "Unavailable"/"unavailable" text anywhere outside Why-expanders, no untranslated change chips, no duplicate theme/group chips, correct singular/plural counts, single empty-chart message, accent applied only to the Part 2 list, `--down` never used for non-directional meaning. JS-disabled and 1280/1024/390 checks. Admin/Research unaffected.

Implement to a verified local state and stop — do not stage, commit, or push.
