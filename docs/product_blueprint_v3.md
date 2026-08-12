# MNE Product Blueprint v3

## Current Intelligence → Understanding → Thesis Building

### Purpose

This document defines the current product blueprint for the Macro Narrative Engine (MNE). It should guide future UI, product, research, and workflow decisions.

MNE should remain a **current-condition market intelligence platform** first. Research and history exist to deepen understanding of the present, not to turn the product into a historical archive.

---

# Core Product Model

MNE should guide users through three stages:

**Overview → Research → Studio**

Each stage has a distinct purpose.

## Overview

**Primary question:**
What do I need to know right now?

Overview is the current-market briefing layer.

It should prioritize:

* current dominant narratives
* what changed
* why it matters
* market confirmation or divergence
* upcoming catalysts
* the engine's highest-priority observations

The engine should guide attention rather than simply display information.

The desired outcome is:

> In a few minutes, the user understands today's market.

---

## Research

**Primary question:**
Why is this happening?

Research is an investigation layer focused on explaining the current market.

It may include:

* narrative drivers
* supporting headlines and evidence
* related narratives
* source context
* market relationships
* catalysts
* AI explanation
* a concise historical snapshot

Historical information belongs here only when it helps explain the current situation.

Research should not become a historical archive or a page dominated by old data.

The intended flow is:

**Current narrative → explanation → evidence → relationships → historical context**

---

## Studio

**Primary question:**
What do I think?

Studio is the user's thesis-building workspace.

The user leads here.

Users should be able to:

* drag and drop headlines
* drag narratives, catalysts, sectors, assets, and other relevant objects
* create their own connections
* organize evidence
* compare narratives or ideas
* build hypotheses
* develop market theses
* save investigations
* revisit previous thinking

Studio is not another dashboard and not another Research page.

It is where the user moves from consuming MNE's interpretation to constructing their own.

Every object placed on the Studio artboard should eventually be able to carry intelligence behind it, such as:

* related narratives
* sources
* catalysts
* sectors
* assets
* confidence
* suggested connections
* opposing evidence

The value of Studio is not merely the canvas. It is the intelligence attached to the objects and relationships on that canvas.

---

# AI Role by Surface

The AI should behave differently depending on the page.

### Overview AI

**Role:** Guide

It should answer:

* What matters?
* What changed?
* Why should I care?
* What should I watch next?

### Research AI

**Role:** Explainer

It should answer:

* Why is this happening?
* What evidence supports it?
* What relationships matter?
* What historical context is actually relevant?

### Studio AI

**Role:** Collaborator

It should help the user think.

Examples:

* suggest possible connections
* point out missing evidence
* identify contradictions
* surface opposing explanations
* challenge a thesis
* suggest additional objects worth adding to the artboard

The AI should not force agreement with the engine.

Studio should support **human thesis + machine assistance**, not machine conclusion only.

---

# History Philosophy

History is a capability, not the identity of the product.

MNE does not need to preserve every raw headline indefinitely.

Instead, it should retain enough historical knowledge to explain how today's market developed.

Prefer storing:

* narrative snapshots
* representative evidence
* major catalysts
* market reactions
* meaningful relationship changes
* outcome summaries
* important narrative transitions

The goal is to preserve **meaning**, not maximum raw volume.

A useful mental model is:

**Hot data:** rich current information
**Compressed memory:** summarized recent history
**Historical knowledge:** important long-term narrative context

This should keep storage manageable without removing the engine's ability to understand narrative evolution.

---

# Current Information Is the Front Door

All major product flows should begin with the present.

The preferred hierarchy is:

**Current state → understanding → exploration → historical context**

Not:

**Current state → historical archive → more history**

Historical information should appear when it helps answer a current question.

---

# Engine Intention

MNE should not behave like a passive database.

The engine should have intention.

It should guide the user toward the most important information.

That does not mean hiding uncertainty or forcing one interpretation.

It means answering:

* What deserves attention?
* What changed meaningfully?
* What is strengthening?
* What is weakening?
* What conflicts with the dominant interpretation?
* What catalyst could change the situation next?

The engine should help the user know where to look.

---

# Translation Layer

Raw engine terminology should not leak into the consumer interface.

Examples:

Internal:

`macro_pressure`

User-facing:

**Higher-rate pressure**

Internal:

`dominant_share`

User-facing:

**This is currently the market's primary focus.**

Internal:

`persistence_score`

User-facing:

**This narrative has remained important for several weeks.**

Internal metrics remain available where useful, but they should not become the primary language of the interface.

---

# Narrative Discovery

Narrative Discovery should show actual market stories and events, not mostly engine statistics.

Good examples:

* AI Infrastructure
* Data Center Power Demand
* Treasury Yields
* Tariffs
* Labor Market Weakness
* China Stimulus
* Oil Supply Risk
* Semiconductor Demand
* Inflation Pressure

The word cloud or discovery surface should answer:

> What is the market talking about right now?

It should not primarily answer:

> How many engine runs contained this category?

Persistence, streaks, acceleration, and concentration can remain available as supporting metadata.

---

# Visual Direction

MNE should retain the original **Robinhood-inspired consumer-fintech direction**.

It should not drift toward a Bloomberg-terminal aesthetic.

The experience should feel:

* spatial
* clean
* current
* premium
* alive
* approachable
* information-rich without appearing dense

### Palette

Primary background:

`#0B0E11` deep obsidian

Semantic accents:

* teal for positive / strengthening / constructive states
* amber for negative / weakening / caution states
* slate for neutral information

These accents should actually be visible in the product.

The interface should not remain uniformly gray.

Color should guide attention and communicate state, not merely decorate the interface.

### Motion

Use subtle, high-performance motion where it improves comprehension:

* crisp hover states
* card transitions
* responsive controls
* smooth artboard interactions
* restrained state-change animation

Avoid unnecessary visual noise or a cyberpunk appearance.

---

# Overview, Research, and Studio Must Stay Distinct

A feature should have a clear owner.

### Overview owns:

Current awareness.

### Research owns:

Current understanding.

### Studio owns:

User exploration, comparison, and thesis construction.

If a feature could live equally well on two pages, reconsider its purpose or presentation.

---

# Product North Star

A user should leave MNE with three increasingly valuable outcomes:

### Awareness

I know what matters today.

### Understanding

I understand why it matters.

### Conviction

I have developed my own informed view.

MNE should guide the user through that progression without requiring them to understand how the engine works internally.

---

# Final Product Rule

**Overview tells the current market story.**

**Research explains the current market story.**

**Studio lets the user explore, compare, and build their own market story.**

History supports all three where useful, but history should not become the product's center of gravity.

---

# Addendum — Direction ratified after this blueprint was shared (2026-08-12)

The blueprint above is the north star as Daniel authored it. The following decisions were ratified in the working session that reviewed it, and refine the "Visual Direction" section without changing its intent.

## Ratified semantic color model

The palette is obsidian base + three semantic accents, plus a fourth reserved axis:

- **Teal** (`--teal #2dd4bf`, `--teal-bright #5eead4`) — strengthening / positive / constructive.
- **Amber** (`--amber #f0a64b`) — weakening / cooling / caution (a narrative losing force). Amber owns narrative-state decline; the earlier red→amber state migration stays correct.
- **Slate** — neutral, rendered as **bright slate** (`--muted-strong`), not muted grey. Steady/neutral states must read as bright pills/text, never near-invisible grey.
- **Red** (`--down`) — **downside PRICE / decline only** (the price axis, Robinhood-style down = red). Red is **not** used for narrative or market state. Its presence on non-price surfaces (finder, Studio) is a defect.

This resolves the "bring red back" call: red returns as a real, visible accent, but scoped strictly to price direction.

## Color must lead — calibrated to the mockup

"Accents should actually be visible" is a hard requirement, not a preference. The build had drifted greyer than the approved mockups under a "~85% neutral, one-glow-per-section" restraint. Direction: restore the mockups' colored fills, brighter slate steady, and per-section color presence.

Verification is a **color census** (in-browser count of colored text runs / fills / glows, cache-busted at 1280px), measured against the approved mockup and the Overview surface as the internal benchmark. The research tier (finder, investigation, Studio) was re-saturated to that standard; Overview already met it and was left untouched.

## Historical reconstruction posture

History stays alive but is **efficiency-gated**, not backburnered. The go/no-go is the efficiency question itself: if requests can be normalized to a canonical period grid (compute-once-per-period + meter only cache-misses) cheaply, the tier is promoted as a real consumer feature; if that dedup turns messy or expensive, it holds at the current basic version. Decision-gated, not shelved.

## Roadmap gaps this blueprint exposes

The blueprint ratifies most of what is built (nav spine, v2 palette, story registry, translation layer). The open gaps it names as future work:

1. **Overview prioritization** — Overview currently displays; it does not yet rank/editorialize "the single most important thing right now."
2. **Surface-differentiated AI** — one Explainer mode exists; the Guide (Overview) and Collaborator (Studio) roles do not.
3. **Studio artboard (Sprint Q)** — the drag-drop canvas where objects carry intelligence is the largest unbuilt piece; needs a mockup-first design round.
4. **3-tier memory** — hot / compressed / historical is a new backend direction, not yet built.
