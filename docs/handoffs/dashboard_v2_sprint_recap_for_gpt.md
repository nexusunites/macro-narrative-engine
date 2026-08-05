# Dashboard V2 — Sprint Recap (context update for GPT)

Hey — this is a catch-up so we can start our next conversation at "what's next"
instead of "what happened." You and I shaped the vision together:
Robinhood-not-Bloomberg, the obsidian / teal / amber palette, the rule that the
dashboard must never leak engine language, the translation-layer idea, and the
three-tier ingestion roadmap (headlines first, then social sentiment, then
institutional data). You know the vision. You have not seen a single thing that
got built. This document closes that gap.

Short version: the redesign is done and live on real data. The dashboard now
matches the approved mockup end to end. Below is how it happened, in order, then
the open horizons I want to think through with you.

---

## Phase 1 — We mocked it before we built it

This is the part I think you'll like most. Instead of jumping into another build
sprint, we built a full-fidelity, clickable HTML mockup of the entire redesigned
dashboard and iterated it with you over four review rounds — before one line of
production code changed. Getting the argument settled in a throwaway file was far
cheaper than settling it in the app.

- Published mockup: https://claude.ai/code/artifact/fef2bc5c-3612-4cb0-9ae1-169fef306a68
- Canonical copy in the repo: `docs/mockups/dashboard_concept_v1.html`

The four rounds landed like this:

1. Colors approved — but the steady / neutral states were too muted. New rule
   that stuck: steady must read at FULL visual weight in bright slate. "A muted
   grey that disappears is a defect, not restraint." Steady is a real state, not
   the absence of one.
2. Research navigation restored, and a watchlist was added.
3. The watchlist stopped being an overlay and became a real layout column on wide
   screens.
4. That column was aligned flush with the top of the Market Support card and
   slimmed to 260px — it expands into free margin before it ever shrinks content.

Worth noting: the mockup loop caught a real bug of its own — a watchlist that
overlapped neighboring content by roughly 97px. We fixed it in the mockup, not in
production.

---

## Phase 2 — We wrote down the contract

Before building, the design language got promoted from "vibe we agree on" to an
enforceable contract (commit `1ca1c90`):

- `docs/design_system.md` was rewritten as Design System v2. The load-bearing
  rules: hue means state, never decoration; roughly 85% of the screen stays
  neutral; story before statistics; engine language never leaks (everything user-
  facing routes through `mne/presentation_language.py`); one uniform card system,
  not per-section snowflakes; and when two readings conflict, the mockup wins.
- `docs/handoffs/dashboard_visual_rework_v2_handoff.md` split the build into
  discrete sprints.

The point of writing it down: every sprint below could be judged against a fixed
spec instead of re-litigated.

---

## Phase 3 — The build sprints

Working model: Codex implemented each sprint; then it was audited in a real
browser, with actual measurements, before anything got committed. That loop
earned its keep — it caught a summary-swap bug where cards were contradicting
their own pills, on top of the 97px overlap from the mockup phase.

- Sprint A (`8414fc9`) — The v2 palette became the DEFAULT. The legacy palette got
  scoped down to Research and Admin only. One unified card recipe. Steady states
  in bright slate, per the Phase 1 rule.
- Sprint B (`c8d35d3`) — The "what changed" strip became a real NYSE-style
  auto-scrolling ticker (pauses on hover, static fallback for reduced-motion). The
  hero was restyled to a plain-language headline plus a Market Support panel with
  the teal glow.
- Sprint C (`3cd5843`) — The old SVG constellation node graph was replaced by the
  attention cloud: clickable story chips sized by how much attention each is
  drawing, with a detail panel (why it matters / what's driving it / what to watch
  for / what it's connected to / a real tape quote). Honest interim state: it only
  showed the engine's real three groups — no invented stories to fill space.
- Sprint D (`ff471b6`) — The watchlist shipped for real: a docked star tab that
  becomes a sticky column on desktop, and a floating button plus overlay on
  mobile. It's wired into the personalization system, and direction now comes from
  a single source so cards, chips, and panels can't disagree with each other.
- Sprint F (`7dec584`) — Full mockup parity. I made the call that on the dashboard
  only, the left app rail is replaced by the mockup's slim top bar (other pages
  keep the rail — this also resolved a nav-hiding tradeoff we'd been stuck on). Big
  Picture cards were rebuilt to the mockup anatomy (Rank 01, status pills,
  STRENGTH / MOMENTUM / ATTENTION tiles, share meters). Sector tiles got
  driving / steady / detached stripes and a legend. Evidence was rebuilt as calm
  per-narrative columns with real sources and timestamps. The attention cloud
  moved above the Big Picture cards, matching the mockup's reading order.
- Sprint E (`9094112`, brief `3f283d6`) — The backend that makes the cloud REAL,
  and the one place I made a design decision I want to flag to you.

### Sprint E — your "cluster the headlines" idea, adapted to the charter

You proposed clustering headlines into named stories. I implemented the intent but
not the mechanism: it's a CURATED STORY REGISTRY plus deterministic keyword
extraction — no ML, no clustering model, no LLM. The reason is the engine's
charter (`AGENTS.md`): every signal has to be deterministic, hand-derivable, and
never fabricated. A black-box clusterer would have broken that promise.

- `config/story_registry.json` defines 15 named stories — "Oil Supply Shock,"
  "AI Chips," "Fed Rate Path," and so on — each with tiered keywords (strong /
  medium / weak), curated driving sectors, catalysts, and links to connected
  stories. It's data, not code: you or I can edit the newsroom without a deploy.
- Every engine run persists exactly which stories matched.
- Recent real runs render 8 to 9 story chips out of the 15 defined (the two most
  recent runs rendered 8 and 9). Stories that match nothing are honestly omitted —
  we never pad the cloud up to 15.
- The audit re-summed one story's score by hand straight from the raw headlines
  and it matched the persisted value exactly — so "hand-derivable" is real, not
  aspirational.
- One honesty note: the first run of a session shows all-steady directions,
  because there's no prior run to compare against. Directions go live from the
  second run on. We chose "steady" over inventing a direction.

---

## Where things stand now

- The dashboard visually and structurally matches the approved mockup, end to end,
  on real data.
- 852 tests pass. Two fail, both pre-existing authorization tests unrelated to
  this work (`test_authorization`).
- Every sprint above is committed.

---

## Open horizons — for us to think through next

These are questions, not plans. This is the part I actually want your head on.

1. Story-registry curation as an ongoing editorial job. What's the cadence? What
   are the criteria for adding a story vs. retiring one? And should clicking a
   chip open a per-story detail view?
2. The asset execution view. This is the vision's Tier-3 charting — the HTF bounded
   candles, the "Daily Launch Line," the narrative countdown timers. An asset
   exploration page already exists, but it predates the design system and doesn't
   speak the new visual language yet.
3. Tier 2 of your ingestion roadmap: social sentiment / "Retail Velocity." The hard
   question is how it coexists with the deterministic charter — sentiment is
   inherently fuzzier than a keyword match.
4. Geopolitical Risk is a defined narrative group (its keywords are war / China /
   tariffs) with no story or theme mapped to it in the registry. Do we map it into
   the curated layers, or is it deliberately a different kind of signal?
5. Watchlist alerts and persistence. The in-page watchlist could feed the existing
   alert machinery — worth deciding if and how.
6. The word-cloud's growth path. As the registry grows past ~15 stories, does the
   cloud need attention thresholds, grouping, or paging so it stays legible?

That's the whole update. The vision held up — the main thing that changed is that
"the dashboard leaks engine language" is now a rule with a single enforcement
point, and the attention cloud is backed by real, hand-checkable data instead of a
placeholder. Ready when you are to pick a horizon.
