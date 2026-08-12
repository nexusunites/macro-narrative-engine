# Color Re-Saturation — Make the Later Pages Lead With Color

**Author:** Claude (orchestrator) · **Implements:** Codex, from this doc only · **Audit:** Claude, in-browser color census, before each commit.

## Why this exists

Per Product Blueprint v3 and Daniel's 2026-08-12 direction: *"colors should lead more — some pages are really bland — but like how they were in the mockup."* An in-browser color census (identical scan on each page at 1280px, cache-busted) pinpointed exactly which pages drifted:

| Surface | teal text runs | teal fills | teal glows | verdict |
|---|---:|---:|---:|---|
| Dashboard **mockup** (target) | 28 | 5 | — | reference |
| Live **Overview** (`/`) | 51 | 4 | 3 | **already good — leave** |
| Live **Research finder** (`/research`) | 6 | 1 | 0 | **bland — fix** |
| Live **Studio** landing (`/studio`) | 0 | 0 | 0 | **flat — fix** |
| **Investigation** (`/research/{key}`) | not censused (anon-gated) | — | — | **same tier — fix, verify during impl** |

**Overview is NOT in scope — it meets the mockup.** The problem is confined to the research tier (finder, investigation, Studio), which was built later under a "~85% neutral, one-glow-per-section" restraint that muted the mockup's color leading.

## Ratified color model (apply consistently)

- **Teal** — strengthening / positive / constructive.
- **Amber** — weakening / cooling / caution (narrative losing force).
- **Red** — **downside PRICE / decline only** (price axis, Robinhood-style). NOT for narrative/market state. Keep the existing red→amber state treatment; red returns only where a price is falling (candles, price deltas). *(Red is not expected to appear on the finder/Studio; it belongs on asset/price surfaces.)*
- **Slate** — neutral, but **BRIGHT slate** (`--muted-strong`), not muted grey. Steady/neutral states must read as bright pills/text, not near-invisible grey.

## The standard to match: what Overview does that the finder doesn't

The live Overview leads with color via (all present in the mockup too):
1. **Colored direction text** on state elements (51 teal runs) — strengthening reads teal, fading reads amber, at a glance.
2. **Per-section teal glow** (`glow-teal` box-shadow) giving each panel a live edge (Overview has 3; finder/Studio have 0).
3. **Filled accent pills** — small vivid teal/amber tags (e.g. "Today's focus", "Cooling") rather than grey outlines.
4. **Colored sector stripes** and bright-slate steady pills.

## Task — bring the research tier up to that standard

Do NOT invent new visual language; **port the Overview/mockup treatment** onto the later pages. Reference `docs/mockups/dashboard_concept_v1.html` and `docs/mockups/research_studio_concept_v1.html` (view `#view-research`, `#view-studio`).

**Research finder (`templates/research_selector.html`, `static/styles.css`):**
- Narrative/story cards must carry a **colored direction indicator** — teal (strengthening) / amber (fading) fill or bright accent, not grey. This is the single biggest lever (finder has 6 teal runs vs Overview's 51).
- The 5 theme filter chips (ai/rates/inflation/energy/recession) should be **vivid/legible**, and the active chip clearly teal-filled — not grey-on-grey.
- Add the **per-section teal glow** to the primary finder panel(s) to match Overview.
- Steady/neutral metadata → **bright slate**, not muted grey.
- Stars/save affordances → visible teal accent on active.

**Investigation (`templates/narrative_investigation.html`):** apply the same — direction text teal/amber on the snapshot/memory/sector/story modules, bright-slate steady, ensure the existing sparkline/sector stripes read vividly. Census it during implementation and match Overview's density.

**Studio (`templates/studio.html`, `_partials/studio_compare.html`):** the anon landing is fully colorless — give it at least the teal brand/CTA accent and a glow so it doesn't read dead. Populated rail direction marks (teal/amber/slate) and Compare direction rows should already be colored; verify they're vivid, not muted.

**Palette base:** keep the ratified tokens (`--teal #2dd4bf` / `--teal-bright #5eead4` / `--amber #f0a64b` / `--down` red for price / bright `--muted-strong` slate). This is a **usage** change (fills/glows/direction-color density), not a token redefinition — do not alter `:root` token values or the scoped page token blocks.

## Verification (per AGENTS.md) — census-based

For each changed page, run the **color census** cache-busted at 1280px and show the before/after counts. Target: the research tier's teal-lead and glow counts should move **materially toward Overview's** (it need not match exactly, but "6 teal runs / 0 glows" → single digits with 0 glows is a fail; expect a clear jump + at least the per-section glow present).
- No red anywhere on finder/Studio (red is price-only; its presence there is a defect).
- Steady states are bright slate, not grey.
- Full suite passing (**baseline 874, 2 known `test_authorization` failures**); `/`, `/admin`, `/research` return 200.
- 1280 / 1024 / 390 widths; JS-disabled render intact; no filename leak; no horizontal scroll.
- **Overview (`/`) unchanged** — confirm its census didn't regress (this pass must not touch it).
- Cache-bust CSS before reading computed styles; `pkill -f uvicorn` before starting the audit server.
- `git diff --check` clean; nothing staged/committed/pushed (Daniel commits).

## Out of scope

Overview/dashboard (already correct), token redefinitions, historical/admin pages, Studio Sprint Q artboard, engine logic.
