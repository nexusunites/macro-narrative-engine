# MNE Design System v2

This is the visual contract for the user dashboard. Every future UI change — by a
human, Claude, or Codex — must conform to it. It supersedes the v1 cohesion notes
below; where v1 still holds (obsidian base, low density, honest translation, reduced-
motion), that intent is carried forward with concrete tokens and component specs.

## 1. Purpose and canonical reference

The approved look is the "high-end consumer tech meets institutional alpha" direction —
Robinhood energy, not Bloomberg density, not cyberpunk glow. When in doubt, match the
mockup pixel for pixel.

- **Canonical reference:** `docs/mockups/dashboard_concept_v1.html` — the single source of
  truth for layout, tokens, and copy.
- **Approved artifact:** https://claude.ai/code/artifact/fef2bc5c-3612-4cb0-9ae1-169fef306a68
- This document is the written contract; the mockup is the visual contract. If they ever
  disagree, the mockup wins and this doc is corrected.

## 2. Information philosophy

- **Story before statistics.** Lead with the plain-English market story; numbers support
  it, they never open the section. Every heading states the takeaway first.
- **Engine language never leaks.** All user-facing copy passes through
  `mne/presentation_language.py` (see `METRICS`, `MARKET_EXPRESSION_COPY`). Raw engine
  vocabulary (`persistence_score`, `narrative_pulse`, `concentration_gap`, role codes) is
  never rendered in primary copy. Labels follow `docs/ui_naming_framework.md`.
- **Progressive disclosure.** Surface the answer; put the evidence and limitations one
  layer down (story detail panel, X-Ray `details`/`summary`, connected stories).
- **Every element answers a market question.** If a tile, chip, or number does not answer
  a question a reader would actually ask ("What's the market talking about?", "Is this
  strengthening?", "Where is it landing?"), it does not ship.

## 3. Design tokens

Define as CSS custom properties on `:root` and style everything through them. Numeric data
uses `font-variant-numeric: tabular-nums`; tickers/timers use the mono stack.

```css
:root {
  /* Surfaces */
  --bg: #0B0E11;              /* obsidian ground */
  --panel: #12171D;           /* card surface */
  --panel-raised: #171D25;    /* raised surface: chips, stats, ticker tag */
  --line: rgba(255,255,255,0.07);
  --line-strong: rgba(255,255,255,0.14);
  /* Text */
  --text: #EDF1F5;
  --muted: #8B95A3;
  --muted-strong: #B9C2CD;
  /* State hues (state, never decoration) */
  --teal: #2DD4BF;            /* strengthening / positive */
  --teal-bright: #5EEAD4;     /* emphasis */
  --amber: #F0A64B;           /* fading / cooling */
  --red: #F16A5F;             /* downside moves only, used sparingly */
  /* System */
  --radius: 16px;             /* cards; chips use 999px */
  --shadow: 0 10px 30px rgba(0,0,0,0.45);
  --font: -apple-system, "SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, monospace;
}
```

- **Type scale:** display 44-56px (hero, weight 650, tight tracking, `text-wrap: balance`);
  section h2 ~20px; card titles ~16px; body 14-15px / 1.55; labels 11px uppercase with
  0.08em letter-spacing; big numerals with tabular-nums.
- **Spacing:** 4px base scale. Sections separated by 56-72px. Card padding 24px.
- **Radius:** 16px on cards, 999px on chips/pills. **Shadow:** `--shadow` on hover only.

## 4. Semantic color rules

- **Hue means state, never decoration.** Teal = strengthening / growing / confirming.
  Amber = fading / cooling / pressure. Slate greys = steady / neutral / unchanged.
  Red = actual downside price moves only, used sparingly.
- **~85% of the page is neutral.** Teal and amber are life in the margins — edges, glows,
  chips, deltas, meter fills — not paint. Whole cards are never tinted (the one exception:
  sector heatmap tiles may carry a 4-6% state-hue background wash).
- **Steady still reads at full weight (client-mandated).** Neutral is not invisible.
  Steady pills and meter fills use bright slate — e.g. `#C9D2DC` text on
  `rgba(201,210,220,0.12)` with a `rgba(201,210,220,0.30)` border; steady meter fills use a
  `#8B95A3 -> #B9C2CD` gradient at the same intensity as teal/amber fills; steady glyphs use
  `--muted-strong`, not `--muted`. Muted grey that disappears is a defect, not restraint.

## 5. Uniform card system

Every module — hero panel, attention cloud, story detail, group cards, sector tiles, event
rows, evidence lists, watchlist — uses one surface vocabulary so the page reads uniform.

- Surface `--panel` (or `--panel-raised` for nested/raised), border `1px solid --line`,
  radius `--radius` (16px), padding 24px.
- **Hover recipe (identical everywhere):** `transform: translateY(-2px)`, border brightens
  to `--line-strong`, `box-shadow: --shadow`, `transition: 150ms ease`.
- **Restrained teal edge glow** (`box-shadow` ring + soft outer glow) marks the single
  "today's focus" element per section — the Market Support panel, the rank-1 Energy group
  card, the soonest event. Never more than one glow per section.
- Do not invent per-module card styles. New modules compose these tokens.

## 6. Component patterns

Each matches the mockup; treat these as the spec.

- **Ticker tape ("What changed today").** Full-width marquee under the top bar; CSS
  `translateX` keyframe on a duplicated inline list (~42s, seamless -50% loop), pauses on
  hover, static scrollable row under reduced-motion. Compact chips with up/down/steady
  glyphs colored teal/amber/slate. A solid uppercase tag pins the left edge.
- **Hero + Market Support.** Two columns (stack on mobile). Left: uppercase eyebrow,
  display headline, 2-sentence plain-English subtitle, a row of stat chips. Right: Market
  Support panel with a big numeral, state label, small teal delta, inline SVG sparkline
  (area fill via low-opacity teal gradient, emphasized endpoint dot), faint teal glow.
- **Attention cloud + story detail.** Centered flex-wrap cloud of recognizable story chips
  (never engine metric names), font-size scaled by attention weight; strengthening chips
  tint teal at the largest sizes, fading amber, steady slate. Each chip is a real
  `<button>`. Clicking populates a story detail panel beneath: title, one plain "why it
  matters" line, "From the tape" source quote, driving sectors, watch-for catalysts,
  clickable connected stories, and a one-line trend. Selecting scrolls the panel into view
  (`scrollIntoView`, `auto` under reduced-motion) with a brief border highlight.
- **Narrative group cards ("The big picture").** Rank, group name, 2-line summary, three
  stat chips (Strength / Momentum / Attention), a share meter bar, "Investigate narrative"
  link. Rank-1 gets the teal glow + "Today's focus" tag; steady ranks use the bright-slate
  "Steady" pill; a cooling group uses a small amber "Cooling" chip.
- **Sector heatmap.** Grid of sector tiles; each has name, ETF ticker in muted mono, a
  participation label, and a thin state stripe on the top edge — teal (driving), slate
  (steady), amber (detached). The 4-6% state-hue background wash is allowed here only.
  Legend row: driving / steady / detached.
- **Event countdowns ("On the clock").** Event cards with live mono countdowns
  (`2d 14:22:08`) to real future datetimes, a one-line "why this matters" tied to the
  stories, soonest event gets the teal ring.
- **Evidence lists ("What we read").** Quiet columns of real headlines with a muted
  source-and-time line. Grounds story -> evidence.
- **Watchlist.** Docked slate tab (star + count) on the right edge. At >=1200px, opening
  reflows the content area into a two-column grid: main column + 24px gap + a sticky 260px
  watchlist column. The panel's unscrolled top edge aligns with the hero Market Support card
  top (offset = hero section top padding); it sticks at `top: 20px` on scroll. **Expand into
  free margin before shrinking content:** the open shell raises its max-width to
  `1200 + 24 + 260 = 1484px` so the pair grows into empty side margins first, and content
  only narrows (`minmax(0,1fr)`) when the viewport cannot fit both. Below 1200px the tab
  becomes a floating round button and the panel is a dismissible overlay. The tab/button is
  slate, not teal. Rows: colored direction glyph, name, one-word trend, click-to-select
  (scrolls detail into view), hover-revealed remove. A star toggle in the detail header adds
  or removes; state is in-page only.

## 7. Motion

- Purposeful only, 150-200ms ease. Hover lift, panel highlight, reflow, marquee. No
  decorative or looping glows beyond the single focus marker per section.
- Marquee pauses on hover.
- `prefers-reduced-motion: reduce` is always honored: disable the marquee (fall back to a
  static scrollable row), pulses, the panel highlight, and hover translation; scroll jumps
  use `behavior: auto`.

## 8. Do / Don't

**Do**
- Reuse the token set and the one card system for every new module.
- Route all copy through `mne/presentation_language.py`; keep labels honest to a backing
  field per `docs/ui_naming_framework.md`.
- Keep steady states bright (see section 4).
- Keep the page free of horizontal scroll from 390px to 1440px+.

**Don't**
- Don't add new hues or gradients beyond teal / amber / red / slate.
- Don't expose engine metrics (`persistence_score`, `narrative_pulse`, role codes, raw
  scores) in primary copy, and don't ship reserved/unimplemented labels
  (`docs/ui_naming_framework.md`: Attention Velocity, Narrative Gravity, etc.).
- Don't tint whole cards (heatmap wash excepted).
- Don't create one-off card, chip, or hover styles.
- Don't let a neutral state render as disappearing grey.

## Retirement note

The legacy multi-hue status scale in `static/styles.css` is **deprecated for the user
dashboard**: `--status-neutral`, `--status-info`, `--status-attention`, `--status-notable`,
`--status-lead`, `--status-recede`, `--status-complete`, plus `--accent`/`--accent-soft`
and `--warn`. The v1 hue values `--up: #4ade80` and `--down: #f87171` are superseded by
`--teal: #2DD4BF` and `--amber: #F0A64B`; `--red: #F16A5F` is downside-only. New dashboard
work must not reference the deprecated tokens. (Admin surfaces remain operationally separate
and are out of scope for this system.)
