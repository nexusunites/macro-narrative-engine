# The Macro Narrative Engine
## Security & Intellectual Property Model

*This document belongs alongside the Product Vision, the Source Intelligence Platform, the Historical Replay Engine, the Narrative Memory System, the Intelligence Experience Architecture, the Platform Observability Layer, and the Research Workspace Architecture as a permanent reference. It defines what must be protected, why, and how — at a strategic and architectural level, not a technical or legal one. This document is not legal advice, not a licensing decision, and not an implementation guide; it should remain valid regardless of which specific tools, hosts, or legal instruments MNE eventually uses to carry it out.*

---

## 1. Purpose

MNE's value does not live in any single file, any single feature, or any single day's output. It lives in the combination of a deterministic architecture, a coherent methodology, an accumulating body of historical understanding, and a product philosophy that took real effort to arrive at. None of that protects itself automatically. This document exists to name, plainly and permanently, what MNE actually needs to protect, why it matters, and what principles should guide every future decision that touches security, access, data, or intellectual property — so that as MNE grows, and as the people and tools involved in building it change, the thing being protected doesn't quietly erode along the way.

---

## 2. Security Philosophy

Security, for MNE, is not primarily a defense against attackers — though ordinary technical hygiene matters and is assumed throughout this document. Security here means something broader: **the deliberate preservation of everything that makes MNE valuable**, against carelessness, against premature or unintentional disclosure, against the quiet erosion that happens when access is granted too loosely or too permanently, and against losing track of what actually needs protecting as the platform grows more complex.

MNE's long-term value comes from the combination of its deterministic intelligence, its architecture, its methodology, its accumulated historical data, its product vision, and the experience it delivers to the people who use it. Security exists to preserve that combination — not any one piece of it in isolation, but the whole, coherent thing those pieces add up to.

---

## 3. Intellectual Property Philosophy

MNE's intellectual property is not any single line of code. It is the accumulated result of deliberate architectural decisions, a specific methodology for turning evidence into narrative intelligence, a product philosophy arrived at through real iteration, and — over time — a body of historical understanding that cannot be recreated simply by rewriting the software that produced it.

This reframes what "protecting IP" actually means for MNE. Code can be rewritten. Architecture, methodology, and years of faithfully preserved historical narrative understanding cannot be rebuilt quickly, and in the case of historical data, cannot be rebuilt at all — once a day passes without being properly captured, that day's understanding is gone permanently. Protecting MNE's intellectual property means protecting the things that are actually hard, or impossible, to reconstruct — not reflexively guarding everything with equal intensity regardless of how replaceable it is.

---

## 4. Assets That Require Protection

The following are the assets this document exists to protect, roughly in order of how difficult or impossible each would be to reconstruct if lost or prematurely disclosed:

- **Historical datasets and accumulated Narrative Memory** — irreplaceable; once a day's understanding is lost, it cannot be regenerated.
- **The Evidence Object model and narrative taxonomy** — the conceptual backbone that every other system depends on; disclosure of these doesn't just reveal a detail, it reveals the shape of the entire platform.
- **Architecture documents** — the Source Intelligence Platform, the Historical Replay Engine, the Narrative Memory System, the Intelligence Experience Architecture, the Platform Observability Layer, the Research Workspace Architecture, and every document like them represent significant, hard-won design thinking, not incidental notes.
- **Product Vision and methodology** — the reasoning behind *why* MNE is built the way it is, which is at least as valuable as the code that implements it.
- **User research** — real, gathered understanding of who MNE serves and how, which took genuine effort to obtain.
- **MNE-data broadly** — the running accumulation of everything the platform has ingested, processed, and concluded.
- **AI prompts and instructions that define platform behavior** — these are, functionally, part of MNE's architecture, and deserve the same protection as any other architectural asset, not the casual treatment "just a prompt" might otherwise suggest.
- **Future proprietary datasets** — anything MNE eventually builds that doesn't exist yet but will carry the same irreplaceability as today's historical data once it does.
- **Future trained models**, should MNE ever develop any of its own — a category reserved deliberately, even though none exist yet, precisely so this document doesn't need to be rewritten the day one does.
- **Source code** — real and worth protecting, but, consistent with §3, the most reconstructable asset on this list; its protection matters, but it is not where MNE's deepest, least-replaceable value actually resides.

---

## 5. Repository Security

MNE's codebase should live in **private repositories** by default, permanently, unless a specific, deliberate decision is made to release a specific, bounded piece of it (§11). Access should follow the **principle of least privilege**: a collaborator receives exactly the access their current contribution requires, not broad access granted for convenience or in anticipation of future need. Access should be revisited and revoked as roles and contributions change, not left to accumulate indefinitely.

Meaningful changes should pass through **code review** before merging — not as bureaucratic overhead, but as a second set of eyes on anything that touches architecture, taxonomy, or the deterministic core described in §3. **Branch protection** should prevent direct, unreviewed changes to the lines of the codebase that matter most. **Release discipline** — clear, deliberate boundaries around what constitutes a released, stable state of MNE versus in-progress work — protects against half-finished or experimental work being mistaken for, or exposed as, the platform's actual current state.

---

## 6. Secret Management

Credentials, API keys, and any other secret required to operate MNE should never be committed to the codebase, in any form, at any point in its history — a secret that has ever touched version control should be treated as compromised and rotated, not merely removed going forward. Secrets belong in environment-level configuration (`.env` files and equivalent mechanisms), kept out of the repository entirely, and rotated periodically as a matter of routine discipline rather than only in response to a suspected incident.

This document deliberately does not specify which tools or services should manage secrets — that is an implementation detail properly left to whoever is building at the time, and specifying it here would tie a permanent document to technology that may not exist in a few years. What's permanent is the principle: secrets are never code, and are never treated as permanent once issued.

---

## 7. Data Protection

MNE's data — historical narrative data, user-generated research, Company Memory, Narrative Memory broadly, and everything else accumulating within MNE-data — deserves protection proportional to its irreplaceability (§3, §4). Historical data in particular should be backed up with real discipline: not as an afterthought, but as an explicit recognition that a single loss of properly-captured historical understanding is permanent in a way that losing code or configuration simply is not.

Cloud synchronization, wherever it is used to store or move MNE's data, should be treated as a convenience for access, never as a substitute for a deliberate backup and protection strategy. Convenience and protection are different problems, and solving the first should never be mistaken for having solved the second.

---

## 8. Architecture Protection

MNE's architecture documents — the Source Intelligence Platform, the Historical Replay Engine, the Narrative Memory System, the Intelligence Experience Architecture, the Platform Observability Layer, the Research Workspace Architecture, and every future document like them — represent proprietary intellectual property in their own right, independent of the code that implements them. They should remain private by default, exactly as the codebase does, and should be released publicly only through the same kind of intentional, deliberate decision described in §11 — never by casual sharing, incidental exposure, or the assumption that "it's just documentation."

The architectural thinking captured in these documents is, in many cases, harder to reproduce than the code built from it — protecting the documents is protecting the thinking, not merely the paperwork describing it.

---

## 9. AI Usage Policy

AI may assist MNE's development — in writing code, in reasoning through architecture, in accelerating work of many kinds. **AI does not own MNE**, does not hold any stake in what MNE becomes, and every contribution AI makes remains exactly that: a contribution, not a decision.

**AI-generated code becomes part of MNE only after human review and deliberate acceptance.** Nothing produced by an AI system is treated as final or authoritative simply because it was generated efficiently or plausibly. **Deterministic platform decisions — what MNE concludes, how it reasons, what its architecture requires — remain owned by MNE and by the humans directing its development, never by any AI tool used along the way.** This mirrors, at the level of development practice, the same principle the Intelligence Experience Architecture already establishes for MNE's product itself: AI assists; it does not decide, and it does not own what results from its assistance.

---

## 10. Collaboration Policy

Future collaborators — whoever they turn out to be — should receive only the minimum access their contribution genuinely requires, following the same least-privilege discipline already established for repository access (§5). Every contributor carries a responsibility to protect the assets described in §4, not only whichever narrow piece of the system they happen to be working on directly.

Documentation standards matter here precisely because MNE's architecture is itself an asset (§8): a contributor working without a clear understanding of existing architecture is more likely to erode it by accident, through inconsistency, than through any deliberate act. Architectural consistency should be treated as a collaboration requirement, not a nice-to-have — new contributions should extend MNE's existing architecture deliberately, in the way every document in this repository already models, not introduce quiet, undocumented departures from it.

---

## 11. Open Source Policy

**MNE is proprietary by default.** This is the permanent starting position for every part of the platform, and nothing in this document should be read as an eventual expectation of broad open-sourcing.

That said, individual, narrowly-scoped utilities may be open-sourced in the future, if — and only if — doing so does not expose proprietary architecture, methodology, or competitive advantage as described in §3 and §4. The test for any such decision is not "would this be useful to others" but "does this reveal anything that makes MNE's deepest, least-replaceable value easier to reconstruct or compete with." A genuinely generic, standalone utility with no meaningful connection to MNE's narrative intelligence, taxonomy, or accumulated data can reasonably be considered; anything closer to the core described in §3 should not be, regardless of how tempting the goodwill or visibility might seem.

---

## 12. Future Commercialization

Whatever commercial form MNE eventually takes — software, data products, research workflows, an API, an enterprise offering, or something not yet imagined — the same underlying assets from §4 remain what's actually being protected and, eventually, offered. Commercialization should be understood as a way of making MNE's accumulated value available to others under deliberate terms, never as a reason to loosen the protections this document establishes in the meantime.

Branding, methodology, research workflows, and the accumulated data and intelligence MNE produces are all part of what a future commercial offering would actually rest on — protecting them well before commercialization is what makes commercialization possible at all, rather than something to begin thinking about only once a commercial moment arrives.

---

## 13. Operational Security Principles

- **Assume every credential will eventually need rotation**, and design habits accordingly rather than treating rotation as an exceptional, reactive event.
- **Treat access as something to be actively maintained, not just granted** — review who has access to what, periodically, rather than only when someone joins.
- **Treat every architecture document and every dataset as an asset with a specific owner and a specific protection level**, not as ambient, ownerless information that happens to exist in the repository.
- **Prefer explicit, deliberate decisions over convenient defaults** wherever those defaults would loosen protection — convenience is a reasonable tiebreaker only after protection requirements are already satisfied, never before.
- **Assume disclosure is permanent.** Something shared, even briefly or accidentally, should be treated as though it can never fully be un-shared — this should inform caution before sharing, not just remediation after.

---

## 14. Long-Term Stewardship

MNE will outlive any single contributor, any single tool, and quite possibly any single technology choice made along the way. Long-term stewardship means making decisions, at every stage, as though whoever inherits MNE next — a future collaborator, a future version of the founder's own team, or simply a future point in time — will need to understand and continue protecting exactly what this document describes, without having been present for the reasoning behind it.

This is why this document itself exists in the form it does: technology-independent, implementation-agnostic, and deliberately written to remain true regardless of what changes underneath it. Stewardship is the discipline of protecting MNE not just for today's team, but for whoever continues building it.

---

## 15. Guiding Principles

- **Protect understanding, not secrecy.** The goal is preserving what makes MNE valuable, not reflexively hiding everything with equal intensity.
- **Share intentionally.** Disclosure, when it happens, is always a deliberate decision, never a default or an accident.
- **Own deterministic intelligence.** What MNE concludes, and how it concludes it, belongs to MNE — never to any tool or collaborator involved in building it.
- **Keep evidence traceable.** Traceability is a form of protection as much as it is a form of rigor — it is what makes MNE's conclusions defensible and its history auditable.
- **Protect long-term intellectual property, not just short-term secrets.** The hardest-to-reconstruct assets — architecture, methodology, historical data — deserve the most deliberate protection, precisely because they cannot be quickly rebuilt if lost.
- **Architecture is an asset.** Design documents are not incidental paperwork; they represent real, hard-won thinking, and should be protected as carefully as the code built from them.
- **Least privilege, always.** Access is granted to what's needed, for as long as it's needed — never more, never indefinitely by default.
- **AI assists; it does not own.** Every contribution AI makes to MNE's development remains subject to human review and human ownership.
