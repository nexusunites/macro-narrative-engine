# MNE Explanation Layer — Codex Implementation Handoff

## Objective

Make every major user-facing surface lead with a natural-language explanation of market behavior, supported by charts and numbers — instead of leading with internal measurements (score, share, rank, deltas, run counts, state enums) that users must interpret themselves. Deterministic, template-based, persisted-fields-only. No LLMs, no predictions, no trade language.

**Product principle:** MNE is an explanation product supported by statistics, not a statistics product that expects users to explain the numbers. Every major section follows: (1) plain-English takeaway → (2) what changed → (3) supporting evidence → (4) technical details only when useful.

Read `AGENTS.md` before starting. All standing rules apply. This sprint is presentation-only: no changes to scoring, taxonomy, Narrative Memory classification, lifecycle logic, replay, comparison calculations, or Coverage Intelligence.

## Architecture (decided)

**New `mne/explanation_layer.py`, composing on top of `mne/presentation_language.py` — not merged into it.** The split: `presentation_language` owns *vocabulary* (word/state-level dictionary translation); `explanation_layer` owns *composition* (multi-field sentence and paragraph assembly from persisted context). The explanation layer is **pure**: functions take already-loaded context dicts and return explanation dicts — no file I/O, no imports of storage or network modules (this is what makes test 25 provable and output byte-identical). It uses `presentation_language` for every translated word.

Helpers (as drafted): `explain_narrative_snapshot`, `explain_narrative_change`, `explain_lifecycle_state`, `explain_history_pattern`, `explain_dominance_change`, `explain_evidence_breadth`, `explain_historical_comparison`, `explain_confidence_state`, `build_supporting_detail_labels`, `build_explanation_limitations`.

**Schema** (surfaces use the fields they need):

```
{
  "headline": str,              # the takeaway
  "what_changed": str | None,
  "why_it_matters": str | None,
  "supporting_points": [str],   # max 3 in primary view
  "limitations": [str],
  "technical_details": [str],   # raw metrics, engine terms — secondary disclosure only
}
```

## Language rules (enforced by tests)

Primary copy never contains: `run`, `runs`, `meaningful run`, `score delta`, `rank delta`, `share delta`, `configured window`, `persistence threshold`, `concentration gap`, raw state enums (`RE_ACCELERATING`, `BROAD`, …), evidence-origin enums, raw theme/group keys, or the forbidden market words (`bullish`, `bearish`, `forecast`, `prediction`, `buy`, `sell`, `winner`, `loser`). Internal metrics remain available in `technical_details` / Why-expanders.

Canonical translation examples (implement as the pattern for all cases):

| Internal | Primary copy |
|---|---|
| "Energy appeared in 8 of the last 10 meaningful runs." | "Energy has remained consistently present in the market conversation." |
| "Rates were absent for four runs and then reappeared." | "Interest-rate concerns had faded into the background but have recently returned." |
| "AI rank increased from 3 to 1." | "AI moved to the center of the market conversation." |
| "Share declined by 12 percentage points." | "AI still matters, but it no longer commands as much attention as it recently did." |
| "Memory state: RE_ACCELERATING." | "Attention is beginning to build again after a quieter period." |

**Deterministic state rules** (fixed templates, display names only):

- Dominant + declining share → "{name} remains the leading narrative, but its influence has eased from its recent peak."
- Recurring → "{name} has returned to the market conversation after a quieter period."
- Emerging → "{name} is beginning to attract more attention, though its history is still limited."
- Persistent → "{name} has remained a consistent part of the market conversation."
- Fading → "Attention around {name} has been declining."
- Re-accelerating → "Attention around {name} is beginning to build again."
- Absent → "{name} was not meaningfully present in this snapshot."

Cover every persisted lifecycle/memory state; unknown states fall back through the existing untranslated-marker pattern (visible in review, never crashing).

**Time language:** natural phrases only ("recently", "after a quieter stretch", "compared with its recent peak", "across the available history", "during the selected historical period"). Never imply continuous calendar coverage. Required integrity line (in `limitations`, surfaced via the existing disclosure patterns): "Recent behavior reflects available MNE snapshots and may not represent every calendar day."

**Coverage/confidence translation:** BROAD → "The reconstruction draws from several distinct historical source categories." · LIMITED → "The reconstruction is based on a narrower set of historical evidence." · UNKNOWN → "There is not enough information to describe the breadth of the evidence." Never implying truth, predictive quality, conviction, or certainty.

## Surface integrations

1. **Research Workspace (Narrative Investigation).** Page leads with: takeaway headline, what changed recently, lifecycle interpretation, why notable now. Raw score/share/rank/streak move into a supporting-details disclosure. Charts, Recent Memory card, Evidence Reader, and historical views untouched in function.
2. **Narrative History page.** Natural pattern summary above the charts via `explain_history_pattern` (e.g., "AI built steadily, became dominant, then cooled from its recent peak."). Composed from the persisted series shape (emergence, peaks, dominance spans, gaps, recurrence) by explicit deterministic rules documented in the module. No "runs" in primary copy.
3. **Dashboard.** Review-and-tighten only — the rework already leads with composed sentences. Ensure the hero subtitle and narrative-card sentences answer: dominant story, strengthening/fading/stable, competing narratives emerging, evidence base broad or limited. Where the explanation layer produces a cleaner sentence than the existing composer, swap the source; do not redesign layout or lengthen the page.
4. **Historical Research (user).** Investigation leads with: what defined the period, most influential narratives, what evidence supported the reconstruction, coverage limitations. No replay/backfill terminology in primary copy (already enforced; now also natural-language-first).
5. **Historical Comparison (user).** Leads with a concise change summary via `explain_historical_comparison` (e.g., "The market conversation shifted from AI-led growth toward energy and inflation concerns." / "The dominant narrative remained unchanged, but its influence weakened."). When coverage differs materially between periods, append: "Part of the difference may reflect broader source coverage in the later reconstruction." Score/rank tables remain as supporting evidence.

**Progressive disclosure everywhere:** primary = headline + concise explanation + ≤3 supporting points; secondary (existing details/summary patterns) = scores, shares, ranks, streaks, counts, deltas, state labels, engine terms.

## Non-Goals

As drafted: no logic changes anywhere, no LLMs, no predictions or trade language, no removal of supporting metrics, no dashboard redesign, no personalization, no alerts.

## Likely files

New `mne/explanation_layer.py`; `mne/presentation_language.py` (vocabulary additions only); `mne/research_workspace.py`, `mne/narrative_history.py`, `mne/historical_research_view.py`, `mne/historical_comparison_view.py` (context wiring); `dashboard.py` (wiring only if required); templates for investigation, narrative history (as named in the implemented history sprint), dashboard, historical investigation, historical comparison; `static/styles.css`; `tests/test_explanation_layer.py` plus focused updates to existing user-facing tests.

## Ratified Decisions (Daniel, 2026-07-29)

1. **Separate `explanation_layer.py` module** composing on top of `presentation_language.py`, with the pure-function/no-I/O constraint. Ratified.
2. **Dashboard treatment is swap-in-place, not addition.** Ratified.
3. **Supporting-points cap of 3** in primary views. Ratified provisionally — the cap is a single constant; adjust later if primary views feel thin.

## Tests required

The 30 tests as drafted: state-rule rendering for dominant/persistent/emerging/fading/recurring/re-accelerating/absent and declining-dominant (1–8); display-name conversion (9); forbidden-terminology absence in primary copy — runs, enums, delta terms, predictive, trade (10–14); raw metrics available in secondary sections (15); explanation-before-metrics ordering on Research Workspace, Narrative History, dashboard, Historical Research, Historical Comparison (16–20); coverage translation (21); missing-data calm and thin-history cautious wording (22–23); byte-identical output for identical input (24); no LLM/network path — assert the module imports no I/O modules (25); no scoring/taxonomy regression (26); Evidence Reader, charts, admin diagnostics intact (27–29); no leakage of JSON/paths/telemetry/IDs (30). Add: every persisted lifecycle/memory state has an explanation rule (dictionary-completeness test); supporting-points cap enforced.

## Verification

- `python -m unittest tests.test_explanation_layer -v`
- `python -m unittest tests.test_research_workspace -v`
- `python -m unittest tests.test_narrative_history -v`
- `python -m unittest tests.test_historical_research_user -v`
- `python -m unittest tests.test_historical_comparison_user -v`
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne tests`
- `git diff --check`

Manual: dashboard; a dominant investigation; a fading or recurring investigation; Narrative History; Historical Research; Historical Comparison — each explains meaning before metrics; grep rendered primary copy for `run`, enum tokens, delta terms, and forbidden market words; charts and technical details remain accessible; admin unchanged; 1280/1024/390. No source fetching.

## Output required

Report: objective summary; files changed; module/helper summary; schema example; per-surface behavior (Research Workspace, Narrative History, dashboard, Historical Research, Historical Comparison); progressive-disclosure behavior; language and safety verification; verification performed; known remaining gaps; whether the MNE Explanation Layer can be marked implemented.

Implement to a verified local state and stop — do not stage, commit, or push.
