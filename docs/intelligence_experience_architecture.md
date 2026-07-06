# Intelligence Experience Architecture (IXA)

## A Permanent Design Philosophy for the Macro Narrative Engine

This document belongs alongside `ARCHITECTURE.md`,
`docs/source_intelligence_platform.md`, `docs/narrative_memory_system.md`,
`docs/historical_replay_engine.md`, and `docs/narrative_style_guide.md` as one
of MNE's permanent foundational references. It is a philosophy document, not a
UI specification, a dashboard design, or a frontend implementation guide. It
defines how a human being should experience MNE's intelligence, in a way meant
to remain true regardless of which specific interface eventually renders it.

## 1. Product Philosophy

MNE's Intelligence Engine - Narrative Detection, Leadership, Rotation, Pulse,
Regime Alignment, the Narrative Brief, the Source Intelligence Platform, the
Narrative Memory System, the Historical Replay Engine - exists to produce a
rigorous, deterministic, explainable understanding of what the market's
narratives are doing and why. That is a hard problem, and MNE has been built to
solve it honestly.

But solving the intelligence problem is not the same as solving the experience
problem. A perfectly correct, perfectly explainable conclusion is worthless to a
person who cannot find it, cannot understand it in the time they have, or is
scared away by a wall of detail they never asked for. The Intelligence
Experience Architecture exists to make sure that gap never opens up - that the
rigor built into MNE's intelligence layer is matched, at every turn, by an
experience layer disciplined enough to make that rigor usable by whoever is
looking at it, whatever their level of expertise, whatever their available time.

This document rests on one architectural rule above all others, elevated to its
own permanent section immediately following this one, because everything else
here is a consequence of taking that rule seriously.

## 2. The Intelligence / Experience Principle

**"The Intelligence Engine generates intelligence. The Experience Layer delivers
it."**

This is not a stylistic preference or a convenient division of labor. It is a
first-class architectural rule that governs every component MNE has ever built
or will ever build, and it is the single most important sentence in this
document.

**The Intelligence Engine is the sole authority responsible for generating
deterministic intelligence.** Every conclusion MNE holds - a theme score, a
leadership standing, a regime read, a narrative brief, a historical
reconstruction - originates in the Intelligence Engine, including its Memory and
Replay subsystems, and nowhere else. There is exactly one place in MNE's entire
architecture where intelligence is produced.

**The Experience Layer is responsible only for delivering, organizing,
explaining, comparing, teaching, visualizing, searching, and enabling exploration
of that intelligence.** It is a rich, essential, and permanently evolving layer,
but everything it does is done to intelligence that already exists, never as an
act of producing new intelligence of its own.

**No Experience component may independently generate, modify, override, or
reinterpret deterministic intelligence.** This is an absolute boundary, not a
matter of degree. An Experience component that quietly starts drawing its own
conclusions, however reasonable those conclusions might sound, has stopped being
an Experience component and has become an unaccountable second Intelligence
Engine, running without any of the determinism, evidence-traceability, or
explainability discipline the real one is held to.

Every current and future Experience component is bound by this principle without
exception:

- Dashboard
- Narrative Brief presentation
- AI Analyst
- Historical Research
- Mobile applications
- Reports
- API consumers

All of the above consume Intelligence. None of them produce it. This is true
today, with the components MNE already has, and it is true permanently, for
every Experience surface MNE will ever build. This principle does not get
renegotiated as new interfaces are added.

## 3. User Experience Philosophy

The Experience Layer's job is to never get in the way, and never leave anyone
behind. A person with five seconds and a person with an afternoon should both
leave an interaction with MNE feeling like they got exactly what they needed -
not that they were shown too little to trust it, and not that they were shown too
much to use it.

This means the experience layer is not designed around a single "target user."
It is designed around a single target relationship: however curious a person is
right now, MNE should meet them there, and should never make going one level
deeper feel like a separate, harder product. The philosophy is not "simple for
beginners, complex for experts." It is one continuous surface that reveals
itself at whatever pace curiosity demands, always delivering intelligence that
already exists, never inventing a shortcut conclusion of its own to feel more
responsive.

## 4. Progressive Intelligence

This is the primary design principle underlying everything else in this
document: **every intelligence component should support progressively deeper
levels of understanding, and no user should ever be forced into a level of depth
they did not ask for, nor blocked from going as deep as they want.**

Four levels apply universally, across every intelligence object MNE produces:

**Level 1 - Snapshot.** Roughly five seconds. The question being answered is
simply "what is happening?" - a headline, a state, a single clear signal. No
justification, no caveats, no supporting detail. Just the fact, stated plainly.

**Level 2 - Explanation.** Roughly thirty seconds. The question is "why?" - a
short, plain-language account of what is driving the Level 1 fact, in the same
restrained, template-composed style already established for the Narrative Brief
Engine. Enough to satisfy genuine curiosity without requiring study.

**Level 3 - Intelligence.** Several minutes. The question is "show me the
evidence." This is where a user meets the actual supporting intelligence modules
- theme/group scores, leadership standings, rotation status, coverage and
confidence ratings - with enough structure to actually verify the Level 2
explanation rather than just take it on faith.

**Level 4 - Research.** Unlimited. The question is "show me everything."
Historical Replay, Narrative Memory, the full Evidence Explorer, Source
Explorer, and every research tool MNE offers become available here, without
ceiling.

No intelligence object is exempt from supporting all four levels, even if some
levels are thin for a given object on a given day. A quiet narrative's Level 2
explanation might simply be "no significant change today" - thinness is an
honest answer, not a missing feature. At every one of these four levels, without
exception, what a user is shown is intelligence the Intelligence Engine already
produced. Depth changes how much of it is surfaced, never whether what is
surfaced was actually concluded by the Engine.

## 5. User Types

The Intelligence Experience Architecture is designed around four primary
audiences, all of whom use the same Intelligence Engine. Only the depth of
interaction changes, never the substance of what is shown.

**Casual Investor.** Goal: understand today's market in seconds. Lives almost
entirely at Level 1, occasionally dipping into Level 2.

**Active Investor.** Goal: understand why the market is behaving this way. Lives
primarily at Level 2, moving into Level 3 when something does not sit right or
warrants a closer look.

**Trader.** Goal: understand the supporting intelligence and evidence directly.
Lives primarily at Level 3, using Level 2 as an entry point and occasionally
reaching into Level 4 for specific verification.

**Researcher / Institution.** Goal: deep exploration using historical memory,
replay, evidence, and research tools. Lives natively at Level 4, treating Levels
1-3 as a starting orientation rather than a destination.

These are not four different products, four different data sources, or four
different truths. They are four different entry depths into one continuous,
honest body of intelligence. A Casual Investor who suddenly gets curious should
be able to fall straight down to Level 4 without hitting a wall, an upsell, or a
mode switch, and a Researcher glancing at their phone for ten seconds should get
exactly as clean a Level 1 read as anyone else.

## 6. Information Hierarchy

Information density should increase only as user intent increases - never as a
default, and never automatically imposed by MNE's own eagerness to display
everything it knows.

Landing surfaces stay extremely simple: a small number of Level 1 facts, clearly
stated, with an obvious and inviting path deeper for anyone who wants it. Each
additional interaction - a tap, a hover, a click into a card - should reveal
meaningfully deeper intelligence, never a flat repetition of what was already
shown. Users should never be forced into an "expert mode" to get a straight
answer, and expert users should never be forced to leave a simple surface just
to reach the depth they are after. Depth should be reachable from the simple
surface, not hidden behind a separate one.

## 7. Universal Intelligence Card Model

Every intelligence component in MNE - a narrative theme, a group, a leadership
standing, an event, a company, a regime read - is presented through the same
conceptual card structure, so that learning to read one part of MNE teaches a
user how to read all of it:

- **What?** - the Level 1 snapshot fact.
- **Why?** - the Level 2 explanation.
- **Evidence** - the Level 3 supporting intelligence and underlying evidence.
- **History** - how this specific object has behaved over time, drawing on
  Narrative Memory and, where relevant, Historical Replay.
- **Research** - the Level 4 doorway into full research tooling scoped to this
  specific object.

Cards expand naturally, in place, rather than overwhelming the user with a new
destination for every additional layer of curiosity. The card model is the
concrete embodiment of Progressive Intelligence, and every field in it is a
delivery of existing intelligence. The card format organizes and reveals; it
never fills a gap with a component-generated inference.

## 8. Navigation Principles

Navigation should follow user intent, not implementation structure. A person
using MNE should never need to know, or care, which internal module produced what
they are looking at. They think in terms of market understanding, not system
architecture.

Representative navigation concepts, organized around what a user is trying to
understand rather than what MNE happens to call the underlying subsystem:

- **Today's Market** - the immediate, Level 1/2 read.
- **Narratives** - the living state of theme and group intelligence.
- **Market Environment** - the broader backdrop: breadth, regime, positioning.
- **Historical Replay** - reconstructing any past date.
- **Research** - the full Level 4 surface.
- **Companies** - company-centric narrative and memory views.
- **AI Intelligence** - the conversational/explanatory layer.
- **Settings.**

This list is illustrative, not exhaustive or fixed. The underlying principle,
organize by what a user wants to understand, never by which module computed it,
is what is permanent here, not any specific menu structure.

## 9. Dashboard Philosophy

The Dashboard is an operational surface, and its character should be shaped
entirely by that purpose: it is current, concise, fast, and glanceable. Its job,
above everything else, is to answer three questions immediately, without
requiring a single additional interaction:

1. What is happening?
2. Why is it happening?
3. How confident is MNE?

Everything else on the dashboard is supporting intelligence, reachable but not
competing for the same first glance. This is deliberately narrow - a dashboard
that tries to answer everything answers nothing quickly, and speed of
orientation is precisely what most users come to a dashboard for. If a dashboard
surface is tempted to add a fourth thing to that first glance, that is a signal
the fourth thing belongs one level deeper, or belongs in Research entirely - not
that the first glance should get busier.

## 10. Research Philosophy

Research is a fundamentally different product from the Dashboard, not a denser
version of it. Where the Dashboard is operational, current, concise, fast, and
glanceable, Research is exploratory, historical, comparative, evidence-rich,
unhurried, and investigative. These are opposing design postures, and Research
should be built to feel like a deliberately different kind of space - one where
a user has chosen to slow down and dig, not one where the Dashboard simply grew
more panels.

Research is Progressive Intelligence's Level 4 in full, exposing:

- Historical Replay
- Narrative Memory
- Evidence Explorer
- Source Explorer
- Company Memory
- AI Memory
- Competitive Intelligence
- Narrative Accountability

Research users should have virtually unlimited depth, bounded only by what MNE's
intelligence and memory layers actually contain - never by an artificial ceiling
imposed at the experience layer. Both Research and the Dashboard are legitimate,
permanent modes of using MNE, built on the same Intelligence and Memory layers
underneath - but **Research must never be built, designed, or thought of as
"Dashboard with more panels."** It is its own Experience surface, with its own
pacing, its own posture, and its own reason for existing, sharing only the
underlying intelligence and the architectural principles in this document with
the Dashboard it stands apart from.

## 11. AI Experience

MNE's AI layer exists entirely inside the Experience Layer. It is a consumer of
MNE's intelligence, never a producer of it - the single clearest, highest-stakes
application of the principle in Section 2 anywhere in this architecture, and for
that reason its boundary is stated here as explicitly as possible.

**AI may:**

- Explain
- Teach
- Summarize
- Compare
- Organize
- Personalize presentation
- Retrieve historical context
- Answer questions using existing Intelligence

**AI may never:**

- Generate new intelligence
- Modify narrative scores
- Override deterministic conclusions
- Produce competing interpretations
- Invent historical context
- Predict markets
- Replace the Intelligence Engine

Every item in the first list is an act of translation, retrieval, or
organization applied to intelligence that already exists. Every item in the
second list is an act of independent authorship, however plausible-sounding or
well-intentioned, and is therefore categorically excluded, with no exceptions
carved out for convenience, user request, or apparent helpfulness. **The
Intelligence Engine always remains the sole source of truth.** If a future AI
capability would require concluding something the Intelligence Engine has not
already concluded, that capability does not belong to the AI Experience layer.
It belongs, if anywhere, back in the Intelligence Engine itself, subject to that
engine's full determinism and evidence-traceability discipline before it could
ever be considered.

## 12. Clarifying "Personalization"

Because the word "personalize" can be read too broadly, it is defined narrowly
and permanently here: **personalization refers only to presentation. It never
refers to the underlying intelligence itself.**

**Allowed, presentation-only personalization:**

- Preferred dashboard layouts
- Explanation depth: how far into Progressive Intelligence's levels a user's
  default view reaches
- Beginner vs. expert language
- Research formatting
- Report formatting

**Not allowed, under any circumstance:**

- Different conclusions for different users
- Different narrative scores for different users
- Different confidence values for different users
- Any form of user-specific intelligence

**Every user receives identical deterministic intelligence.** Two users looking
at the same narrative on the same day, regardless of their preferences,
expertise level, or personalization settings, are looking at the exact same
theme scores, the exact same leadership standing, the exact same confidence
rating. Only the presentation - how much is shown, in what order, in what
language, in what format - may differ between them. Personalization is a lens,
never a filter that changes what is true underneath it.

## 13. Mobile Experience

Mobile is where Progressive Intelligence's early levels matter most, and where
the discipline of information hierarchy is tested hardest. A mobile experience
should default overwhelmingly to Level 1 and Level 2 - fast, glanceable,
confident - while still preserving an honest, unhindered path down to Level 3
and Level 4 for the user who wants it, even on a small screen. Mobile is not a
stripped-down or lesser version of MNE's intelligence. It is the same
intelligence, met at the depth mobile use typically calls for, with depth always
one deliberate tap away rather than removed entirely.

## 14. Desktop Experience

Desktop is where Level 3 and Level 4 naturally have the most room to breathe -
larger surfaces for evidence tables, coverage detail, historical comparison, and
research tooling. Desktop should take advantage of that room without treating it
as an invitation to show everything at once by default. The same
information-hierarchy discipline applies regardless of screen size. More space
is an opportunity for deeper interactions to feel spacious and legible when a
user chooses them, not a license for the landing experience itself to become
denser just because it can.

## 15. Explainability Standards

Every intelligence component, at every level, should be able to answer the same
small set of questions, consistently:

- **What?** - the fact.
- **Why?** - the reasoning.
- **How confident?** - MNE's own honest assessment of data
  quality/completeness behind the fact, drawing directly on Source Confidence
  and, where relevant, Historical/Evidence Confidence.
- **What evidence supports this?** - a traceable link to the underlying
  evidence, never an assertion floating free of its source.
- **Where can I learn more?** - an explicit, always-available path deeper,
  consistent with Progressive Intelligence.

This is the experience-layer expression of the same explainability discipline
that governs MNE's intelligence architecture itself. The Experience Layer does
not get to be vaguer or more confident than the intelligence underneath it
actually is.

## 16. Visualization Philosophy

Visualizations exist to simplify understanding. They support intelligence; they
are never the intelligence themselves. A chart is only doing its job if it makes
something that was true in the underlying data easier to grasp. A chart that
looks impressive but requires its own explanation to understand has failed at
the one thing visualization is for.

**Explain first. Visualize second.** Every visual in MNE should be introduced
by, and accompanied by, plain-language explanation. A chart is never handed to a
user as a substitute for saying what it means. This ordering is deliberate: it
keeps visualization in its proper, supporting role, and prevents MNE's
experience layer from drifting toward decoration for its own sake.

## 17. Progressive Disclosure

Progressive Disclosure is the mechanical expression of Progressive Intelligence
at the interaction level: reveal exactly one meaningful layer deeper per
interaction, never everything at once, and never so little that the interaction
feels unresponsive. A user should be able to feel, through the interface itself,
that there is always somewhere further to go, without ever being shown the
entirety of that "further" unprompted.

This principle applies uniformly whether the interface in question is a card
expanding on a dashboard, a conversational AI response offering to go deeper, or
a research tool surfacing a next logical query. The mechanism differs by
interface, but the discipline - one deliberate layer at a time, always
available, never imposed - does not.

## 18. Accessibility

MNE's intelligence is only as valuable as the range of people who can actually
receive it. Accessibility, in this architecture, is not a compliance checkbox
added after design. It is a direct extension of the same philosophy that governs
everything else in this document: intelligence should be approachable, at
whatever level of ability a person brings to it, exactly as it should be
approachable at whatever level of expertise they bring to it. Progressive
Intelligence's commitment to "never overwhelming, always reachable" applies as
fully to a screen-reader user or a user with limited dexterity as it does to a
first-time investor. The four levels, the card model, and progressive disclosure
should all be built to work cleanly across assistive technologies and varied
interaction methods, not as a parallel, secondary experience.

## 19. The MNE Layer Stack

The Intelligence/Experience Principle is one instance of a broader, permanent
architectural stack that this document exists at the bottom of, and must never
bypass:

```text
Evidence
   |
Source Intelligence
   |
Narrative Intelligence
   |
Narrative Memory
   |
Knowledge
   |
Experience
```

Each layer has exactly one responsibility, and no layer should bypass another:

- **Evidence** is the raw material - standardized Evidence Objects, regardless
  of origin.
- **Source Intelligence** evaluates the quality, freshness, and reliability of
  that evidence.
- **Narrative Intelligence** reasons deterministically over accepted evidence to
  produce today's understanding.
- **Narrative Memory**, including the Historical Replay Engine, preserves that
  understanding faithfully across time.
- **Knowledge** is built from accumulated Memory - timelines, accountability,
  competitive history.
- **Experience** - the subject of this entire document - delivers everything
  produced by the layers above it to a human being, without ever producing
  intelligence of its own.

This document, the Intelligence Experience Architecture, governs only the bottom
layer of this stack. It has no authority over, and must never be used to justify
shortcuts around, any layer above it. An Experience component that reaches
upward past Knowledge or Narrative Memory to fabricate its own version of what a
lower layer should have produced, even under the banner of a better user
experience, is a violation of this stack, not a clever implementation of it. The
stack exists precisely so that each layer can be trusted to have done its job
correctly, and the Experience Layer's entire value depends on never needing to
compensate for a layer it should simply be delivering.

## 20. Architectural Boundaries

The Experience Layer must never:

- **Modify intelligence.** Presentation choices - what is shown first, how it is
  phrased, how it is visualized - never change what MNE actually concluded.
- **Invent intelligence.** No experience-layer component, including the AI
  layer, produces a conclusion the Intelligence Engine did not itself produce.
- **Predict markets.** This boundary is inherited directly from every
  intelligence and memory system beneath it; the experience layer does not
  introduce forecasting through the back door of a friendlier interface.
- **Hide supporting evidence.** Depth may be deferred, through Progressive
  Intelligence, but it is never withheld. A user who wants Level 3 or Level 4
  must always be able to reach it.
- **Replace the Intelligence Engine.** The Experience Layer's entire
  responsibility is presentation and exploration of intelligence that already
  exists; it is never a second, competing way of producing intelligence.

## 21. Future Evolution

The Intelligence Experience Architecture is designed to remain valid across
interfaces MNE does not yet have, because it describes a relationship between a
person and MNE's intelligence, not a specific screen. As MNE extends to new
surfaces, each one should be understood as a new rendering of the same
structured intelligence, calibrated to that surface's natural depth and pace,
rather than a new product requiring its own philosophy:

- **Web Dashboard** - today's primary Level 1-3 surface.
- **Mobile Application** - Level 1-2 default, full depth reachable.
- **Desktop Platform** - Level 3-4 given room to breathe.
- **API Consumers** - structured intelligence exposed directly, letting
  downstream developers build their own presentation while inheriting MNE's
  underlying explainability guarantees.
- **Discord** - a naturally Level 1-2 surface, suited to quick, conversational
  glances.
- **AI Analyst** - the conversational realization of AI Experience, available
  wherever a user prefers to ask rather than browse.
- **Voice Interfaces** - an almost entirely Level 1-2 surface by necessity,
  where explanation matters even more than usual since there is no visual layer
  to lean on.
- **Future Interfaces**, not yet imagined - whatever form they take, the same
  test applies: does this surface let a user arrive at whatever depth their
  curiosity calls for, without ever forcing more or less than that, and without
  ever producing intelligence of its own?

All future interfaces consume the same structured intelligence and adapt only
the depth and pace of presentation to user intent - never the substance of what
is shown, never the rigor behind it. This is what makes the Intelligence
Experience Architecture a permanent document rather than a snapshot of current
design trends: it describes the constant relationship MNE maintains with the
people using it, regardless of which screen, device, or future medium eventually
sits between them.
