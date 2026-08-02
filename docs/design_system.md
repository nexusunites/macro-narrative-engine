# MNE Design System

This system formalizes the existing dashboard foundation. It is a cohesion layer, not permission to change analytical behavior or rebuild working sections.

## Foundations

- **Obsidian base:** `--bg`, `--bg-soft`, `--panel`, `--panel-soft`, `--surface-0` through `--surface-3`, `--border`, `--border-strong`, `--text`, `--muted`, and `--muted-strong` are the canonical neutral palette.
- **Two-hue budget:** `--teal` aliases `--up` (`#4ade80`) and `--amber` aliases `--down` (`#f87171`). Hue is reserved for a real persisted state or measured change. Teal means confirming, strengthening, or constructive participation; amber means weakening, contradiction, pressure, or caution. Neutral, unavailable, and unchanged states use slate tokens. Hue is a small accent, never a whole-card tint or decorative terminal treatment.
- **Typography:** Inter/system UI is the reading face. `--font-serif` is an intentional, narrow display accent for prominent analytical numerals; it is not a body or navigation face.
- **Spacing:** `--space-1` through `--space-9` define the spacing rhythm. Sections remain generous and card density stays low.

## Components

Section headings establish the takeaway before supporting metrics. Story cards, market-expression role rows, evidence previews, empty states, X-Ray disclosures, and locked states reuse the shared surface, border, type, and spacing tokens. Locked states explain the boundary, preserve existing content, and point to account/plan context without implying billing exists.

X-Ray disclosures use native `details`/`summary` semantics. A short plain-language explanation precedes the control; supporting engine names and limitations remain inside it.

## Motion and responsive behavior

Hover and disclosure transitions are subtle and short. Under `prefers-reduced-motion: reduce`, animation and transition durations collapse and hover translation is removed. Layouts must remain usable at 1280px, 1024px, and 390px; controls may wrap or stack, but must not require horizontal page scrolling.

## Boundaries

The user dashboard, auth, account, and preferences surfaces share this system. Admin remains operationally separate. Presentation tokens and labels never alter engine terminology, thresholds, persistence, entitlements, or authorization.
