# Sub-Narrative Story Extraction (Sprint E) — Implementation Handoff

**Status: not implemented — ready to hand to Codex. Do not implement from this document in this
session.** This is the backend brief that fulfills the Sprint E contract stated in
`docs/handoffs/dashboard_visual_rework_v2_handoff.md` (L155–166). It turns the interim group-level
attention cloud into a real per-story cloud, without changing any engine scoring.

## Purpose

The attention cloud on `/` currently renders **group-level** chips (≤3 populated
`NARRATIVE_GROUPS`) as an honest interim, because "there is no sub-narrative / per-story extraction
today" (visual-rework handoff, L50–54). Sprint E adds a **curated story registry + deterministic
extraction** so the same cloud can render named sub-narratives (e.g. "Oil Supply Shock", "AI
Chips") sourced from persisted run inputs. The Sprint C 9-field chip contract and the
`templates/_partials/narrative_constellation.html` template are **unchanged**; only the data source
behind `dashboard.py:build_attention_cloud` (L1297) swaps when the new field is present.

## Charter constraints (AGENTS.md — non-negotiable)

AGENTS.md L9 states the core philosophy: *"explainability (every signal hand-derivable from
persisted inputs), deterministic logic over probabilistic scoring, honest degradation (gaps and
nulls are truthful; never fabricate values), and narrative-first design."*

This bounds the design absolutely:

- **NO clustering, NO ML, NO LLM.** Stories are a **hand-curated registry**; extraction is
  keyword matching with fixed integer weights. Every chip must be hand-derivable from the run JSON
  plus the checked-in registry. The visual-rework Sprint E note ("cluster headlines within a
  theme", L159) is a *placeholder verb*; the orchestrator has ratified deterministic matching
  instead — do not build a clusterer.
- **Honest empty states** (AGENTS.md L35). Stories with zero keyword matches are **omitted**. The
  cloud renders however many matched — no padding to 15, no minimum count. Zero matches is a
  correct outcome, not a bug.
- **Never fabricate.** `why` / `watch_for` / `tape` / `trend` copy is derived only from matched
  headlines, persisted share deltas, and curated registry text — never invented movement.
- **Daily-snapshot vs run-level discipline** (AGENTS.md L32). Extraction reads the **current run's**
  accepted headlines only (a run-level immediate comparison, like Change Summary), never per-run
  history. Direction compares against exactly the **one** prior run.

## Architecture overview

```
config/story_registry.json   (curated, semver, cross-validated)
        │  load + validate (fail-closed)
        ▼
mne/story_registry.py        StoryRegistryError / validate_story_registry / load_story_registry
        │  frozen dataclasses
        ▼
mne/story_extraction.py      extract_stories(headlines, theme_attribution, registry) -> dict
        │  reuse theme_analysis matching helpers; sum matched keyword weights
        ▼
run["story_extraction"]      persisted at main.py assembly (mirrors change_summary prior-run point)
        │  run.get + isinstance guard
        ▼
dashboard.py build_attention_cloud   story-sourced entries when present, group-level fallback else
```

## 1. Config schema — `config/story_registry.json`

Top level: `{"version": "1.0.0", "stories": {<slug>: {...}}}`. `version` must match the
`_SEMVER` pattern reused from `narrative_relationships.py` (L21). Each story is keyed by a stable
lowercase slug and carries:

| field | type | validation rule |
|---|---|---|
| `display_name` | non-empty str | user-facing; the ONLY string that appears in cloud copy — never the slug |
| `group` | str | must be a key of `NARRATIVE_GROUPS` (`mne/narrative_signals.py` L1–6) |
| `themes` | list[str] | non-empty; each theme must be in `NARRATIVE_GROUPS[group]` **and** in the taxonomy (`config/theme_taxonomy.json` themes) |
| `keywords` | `{strong,medium,weak}` | each a list[str]; ≥1 keyword total; weights 3/2/1 via `theme_analysis.WEIGHTS` (L6) |
| `driving_sectors` | list[str] | each must be a sector key present in `config/narrative_sector_map.json`; display via `sector_isolation.SECTOR_KEYS` (L15) |
| `catalyst_names` | list[str] | optional (may be `[]`); matched case-insensitively by name against the catalysts feed |
| `connected` | list[str] | each must be another story slug in the registry; no self-links; deduped |

**Theme-space caveat (judgment call, ratified here).** `NARRATIVE_GROUPS` themes and the taxonomy
themes only partially intersect: only `ai` is both an AI-group theme and a real taxonomy theme;
Energy resolves to `energy`; Macro Pressure to `rates/inflation/recession`; **Geopolitical Risk has
no taxonomy theme and therefore no eligible stories** (mirroring its unmapped state noted in the
visual-rework handoff L47–48). The `themes` validation deliberately requires membership in *both*
sets so a story can never claim a theme the engine cannot score.

## 2. Module `mne/story_registry.py` (mirror `narrative_relationships.py` exactly)

Copy the shape of `narrative_relationships.py` — same imports, same fail-closed idiom:

- `class StoryRegistryError(ValueError)` — analog of `NarrativeRelationshipError` (L24).
- `DEFAULT_STORY_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "story_registry.json"`
  (analog of L16).
- `_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")` (reuse the L21 pattern).
- Frozen dataclasses: `Story` (`slug, display_name, group, themes: tuple, keywords: <frozen tiers>,
  driving_sectors: tuple, catalyst_names: tuple, connected: tuple`) and `StoryRegistry`
  (`version, stories: tuple[Story, ...]`). Frozen, like `NarrativeRelationship` (L28) /
  `NarrativeRelationshipConfig` (L41).
- `validate_story_registry(data) -> StoryRegistry`: object check → version semver check → `stories`
  must be a dict; for each `(slug, item)` run every table rule above, raising `StoryRegistryError`
  with a `stories[<slug>].<field>` message on the first violation (mirror `_required_text`, L47).
  `connected` cross-references are validated in a **second pass** after all slugs are known (a slug
  can only be validated to exist once the whole keyset is read).
- Deterministic order: sort stories by `(group, slug)` and each tuple field by natural order, so the
  loaded registry is byte-stable regardless of JSON key order (mirror the `sorted(..., key=_sort_key)`
  at L98).
- `load_story_registry(path=DEFAULT_STORY_REGISTRY_PATH)`: wrap `Path(path).open` + `json.load` in
  `except (OSError, json.JSONDecodeError)` → raise `StoryRegistryError` (verbatim mirror of L101–107).

The whole module is a validated read model; it holds no scoring logic.

## 3. Module `mne/story_extraction.py`

`extract_stories(headlines, theme_attribution, registry, accepted_evidence=None) -> dict`.

- **Reuse, do not reimplement**, `theme_analysis.find_theme_keyword_candidates` (L28) +
  `select_non_overlapping_matches` (L47) — the same word-boundary, longest-match-wins,
  non-overlapping machinery that scores themes. A story's per-headline score is the sum of matched
  tier weights; a story's **raw score** is the sum over accepted headlines.
- **Dedupe honesty:** iterate the exact accepted-headline set analyze_themes saw (drawn from
  `theme_attribution` headlines / `accepted_evidence` titles) so a headline counts once per story,
  identical to theme scoring — no double counting, no per-run inflation.
- **Zero-match omission:** a story with raw score 0 (no matched headline) is **absent** from the
  output dict. No placeholder entry.
- **Output** (per matched story):
  ```
  {
    "slug": str,
    "score": int,                     # sum of matched tier weights
    "matched_count": int,             # number of accepted headlines that matched ≥1 keyword
    "examples": [                      # up to 3, first-seen order (deterministic)
      {"title": str, "source": str, "timestamp": str}
    ]
  }
  ```
  `examples` are drawn from `accepted_evidence` records (keys confirmed present:
  `title`, `provider`/`source_name`, `published_at`/`timestamp`) using the same
  `record.get("provider") or record.get("source_name")` / `record.get("published_at") or
  record.get("timestamp")` fallback that `build_dashboard_evidence` already uses (dashboard.py
  L1281–1286). Titles with no matching accepted record still count toward score but yield no example.
- **Determinism:** stories emitted sorted by `(-score, slug)`; examples in first-seen order; no
  randomness, no timestamps-of-now. Identical `(headlines, registry)` input must produce
  byte-identical output.

## 4. Persistence & backward compatibility

Write `run["story_extraction"]` at the `main.py` assembly point. Extraction depends only on
`theme_attribution` + `accepted_evidence` (both available after the NARRATIVE_INTELLIGENCE stage,
main.py L337–366) and the prior run for direction — so compute it **alongside `change_summary`**,
which already loads the single prior run at L677–679:

```python
prior_runs = get_recent_runs(RESULTS_DIR, 1)        # existing, L677
prior_run = prior_runs[-1] if prior_runs else None  # existing, L678
run["change_summary"] = build_change_summary(run, prior_run)   # existing, L679
run["story_extraction"] = build_story_extraction(               # NEW, same prior-run point
    headlines, theme_attribution,
    source_intelligence.get("accepted_evidence", []),
    load_story_registry(), prior_run,
)
```

Shape: `run["story_extraction"] = {"registry_version": "<semver>", "stories": {slug: {...}}}`.

**Backward compatibility:** older runs have no `story_extraction` key. Every consumer uses the
established `run.get("story_extraction")` + `isinstance(..., dict)` guard idiom (identical to how
`build_attention_cloud` guards `group_scores` / `theme_scores` at dashboard.py L1306, L1328). A run
without the field falls back to the group-level cloud with no error.

## 5. Direction & weight semantics (run-over-run)

- **Direction** comes from the **share-of-total-story-score delta** vs the prior run's
  `story_extraction`, routed through the existing `attention_direction_from_share_delta`
  (`presentation_language.py` L139) — the same helper the group cloud already uses (dashboard.py
  L1336). For each story: `share = score / total_story_score`; `share_delta = share − prior_share`
  (prior share 0 if the story was absent last run). `> 0 → up`, `< 0 → down`, `== 0 → steady`.
- **First run after deploy** has no prior `story_extraction`, so **every story reports `steady`**.
  State this plainly in the PR: **all-steady on the first run is correct, not a bug** (AGENTS.md L35
  honest empty states). Prior-run location matches Change Summary exactly.
- **Weight** is the 1–5 bucket `max(1, min(5, ceil((score / max_score) * 5)))` — byte-identical to
  the group cloud's weight formula (dashboard.py L1376). `max_score` is the top matched story's
  score in this run.

## 6. Cloud builder swap & fallback (`dashboard.py:build_attention_cloud`, L1297)

`build_attention_cloud` gains a story-sourced path guarded at the top:

- If `run.get("story_extraction")` is a dict with a non-empty `stories` map → build entries from it.
- Else → the current group-level path (L1306–1385) runs unchanged (the interim honest fallback).

Story-sourced entries keep the **exact 9-field contract** the template consumes
(`{name, weight, direction, why, driving, watch_for, connected, tape, trend}`, dashboard.py
L1374–1384). No template edit. Field mapping:

- `name` → `registry.display_name` (never the slug).
- `weight` → §5 bucket.
- `direction` → §5 share-delta direction.
- `why` → `attention_cloud_why(display_name, direction_label, share)` (L162), share in percent.
- `driving` → curated `driving_sectors` mapped through `sector_isolation.SECTOR_KEYS` display names.
- `watch_for` → up to 2 entries; use `catalyst_names` that resolve against this run's catalysts feed
  first (honest "watch for a scheduled event"), else `attention_cloud_watch_for(display_name)` (L167).
- `connected` → registry `connected` slugs → their `display_name`, **filtered to stories that also
  matched in this run** (mirror the group cloud's `visible_groups` filter, L1327/L1356).
- `tape` → first `examples[*].title` passed through `attention_cloud_evidence` (L175).
- `trend` → `attention_cloud_trend(direction_label)` (L171).

All copy routes through `presentation_language.py`; no engine keys or slugs leak into visible copy
(Sprint C acceptance, visual-rework L124–128).

## 7. Copy / display-name additions

- Sector display names already exist as `sector_isolation.SECTOR_KEYS` (L15) — reuse; do not add a
  parallel map. If a thin `presentation_language` wrapper is preferred for boundary discipline, add
  one that reads `SECTOR_KEYS` and nothing else.
- The existing `attention_cloud_*` helpers (L116–177) already produce every string the story path
  needs; extend their fixed dicts only if a story-specific phrasing is required. Add no
  free-floating hardcoded copy in `dashboard.py` or templates (AGENTS.md L30).
- Story `display_name` values live in the registry (data), not in `presentation_language` — they are
  curated labels, not engine-concept translations.

## 8. Test plan

- **`tests/test_story_registry.py`** — mirror `tests/test_narrative_relationships.py` (122 lines):
  checked-in registry loads as immutable frozen records (`FrozenInstanceError` on mutate); schema
  fails closed on bad version, non-dict stories, unknown group, theme outside group∩taxonomy,
  invalid sector key, self-link, missing connected slug, empty keyword set; `load_story_registry`
  wraps `OSError`/`JSONDecodeError` into `StoryRegistryError`; deterministic sort is stable.
- **`tests/test_story_extraction.py`** — deterministic extraction from a fixed fixture headline set:
  correct scores/`matched_count`, zero-match stories omitted, ≤3 examples in first-seen order,
  direction derived from a supplied prior run (steady when prior absent), and **byte-stability**
  (same input → identical serialized output across two calls).
- **View-model tests** — extend the existing cloud/constellation test to assert: (a) the
  story-sourced cloud keeps all 9 fields with `display_name` names and no slugs; (b) a run **without**
  `story_extraction` still yields the group-level fallback unchanged.

## 9. Acceptance criteria (each verifiable against the real engine + dashboard)

1. `python -m json.tool config/story_registry.json` passes; `load_story_registry()` returns frozen
   records; the full test suite passes.
2. Run `main.py` against live RSS (or a fixture headline file) and inspect the persisted run JSON:
   `run["story_extraction"]["stories"]` contains **only** stories with ≥1 keyword match, scores are
   the hand-summable tier-weight totals, and omitted stories are genuinely absent.
3. Load `/` against that run: story chips render with honest `why`/`driving`/`watch_for`/`connected`/
   `tape`/`trend`, sized by weight; no slug or engine key appears in visible copy; the ticker and
   Market Support cards remain consistent with the same run.
4. Load `/` against an **older** run lacking the field: the group-level cloud renders unchanged; no
   error, no console noise. `/`, `/admin`, `/research` all return 200.
5. First-run-after-deploy check: with no prior `story_extraction`, every chip reads `steady`; confirm
   this is reported as correct, not patched around.

## 10. Out of scope

- No engine scoring, threshold, taxonomy, or group-definition changes. Story extraction is a
  **read-side** derivation from existing accepted evidence + theme attribution.
- No new UI sections and no template edits — the Sprint C attention-cloud template/JS are the
  delivery surface.
- No clustering, ML, or LLM of any kind. No new persistence outside the single `story_extraction`
  key. No Geopolitical Risk stories until that group is mapped across the curated layers.

## Appendix — seed `config/story_registry.json`

Seeded with 15 stories grounded in the live taxonomy keyword space. **Verified** (see handoff PR
notes): valid JSON; every `group`/`theme`/`driving_sector`/`connected` reference resolves against
`NARRATIVE_GROUPS`, `config/theme_taxonomy.json`, and `config/narrative_sector_map.json` (0 errors);
and 10 of the 15 stories match the newest real headline file, so the first real run yields a
non-trivial cloud. The other 5 (`disinflation_hopes`, `consumer_stress`, `recession_watch`,
`opec_policy`, `rate_cut_bets`) are legitimate honest omissions on that run.

```json
{
  "version": "1.0.0",
  "stories": {
    "oil_supply_shock": {
      "display_name": "Oil Supply Shock",
      "group": "Energy / Commodities",
      "themes": ["energy"],
      "keywords": {"strong": ["crude oil", "opec", "brent", "wti"], "medium": ["oil prices", "oil"], "weak": ["crude"]},
      "driving_sectors": ["energy", "materials"],
      "catalyst_names": [],
      "connected": ["natural_gas", "opec_policy", "commodity_spikes"]
    },
    "natural_gas": {
      "display_name": "Natural Gas",
      "group": "Energy / Commodities",
      "themes": ["energy"],
      "keywords": {"strong": ["natural gas", "lng"], "medium": ["nat-gas", "gas prices"], "weak": ["gas"]},
      "driving_sectors": ["energy", "utilities"],
      "catalyst_names": [],
      "connected": ["oil_supply_shock", "data_center_power"]
    },
    "ai_chips": {
      "display_name": "AI Chips",
      "group": "AI / Tech Growth",
      "themes": ["ai"],
      "keywords": {"strong": ["nvidia", "ai chip", "ai chips", "micron"], "medium": ["semiconductor", "ai server", "chips"], "weak": ["chip"]},
      "driving_sectors": ["technology"],
      "catalyst_names": ["NVDA Earnings"],
      "connected": ["data_center_power", "cloud_spending"]
    },
    "data_center_power": {
      "display_name": "Data Center Power",
      "group": "AI / Tech Growth",
      "themes": ["ai"],
      "keywords": {"strong": ["data center", "data centre", "data centers"], "medium": ["ai server", "server demand"], "weak": ["power demand"]},
      "driving_sectors": ["technology", "utilities", "industrials"],
      "catalyst_names": [],
      "connected": ["ai_chips", "cloud_spending", "natural_gas"]
    },
    "cloud_spending": {
      "display_name": "Cloud Spending",
      "group": "AI / Tech Growth",
      "themes": ["ai"],
      "keywords": {"strong": ["cloud backlog", "ai capex", "ai spending"], "medium": ["cloud", "capex"], "weak": ["spending boom"]},
      "driving_sectors": ["technology", "communication_services"],
      "catalyst_names": [],
      "connected": ["ai_chips", "data_center_power"]
    },
    "fed_rate_path": {
      "display_name": "Fed Rate Path",
      "group": "Macro Pressure",
      "themes": ["rates"],
      "keywords": {"strong": ["fed rate cut", "fomc", "powell"], "medium": ["the fed", "fed funds"], "weak": ["fed", "hiking"]},
      "driving_sectors": ["financials"],
      "catalyst_names": ["FOMC"],
      "connected": ["treasury_yields", "rate_cut_bets", "inflation_fears"]
    },
    "treasury_yields": {
      "display_name": "Treasury Yields",
      "group": "Macro Pressure",
      "themes": ["rates"],
      "keywords": {"strong": ["treasury yield", "treasury yields", "interest rates"], "medium": ["bond yields", "borrowing estimate", "borrowing costs"], "weak": ["yields", "treasury"]},
      "driving_sectors": ["financials", "real_estate"],
      "catalyst_names": ["FOMC"],
      "connected": ["fed_rate_path", "rate_cut_bets"]
    },
    "inflation_fears": {
      "display_name": "Inflation Fears",
      "group": "Macro Pressure",
      "themes": ["inflation"],
      "keywords": {"strong": ["inflation", "cpi", "pce", "sticky inflation"], "medium": ["price pressures", "cost of living"], "weak": ["prices rise"]},
      "driving_sectors": ["consumer_discretionary", "financials"],
      "catalyst_names": ["CPI", "PPI"],
      "connected": ["fed_rate_path", "disinflation_hopes", "commodity_spikes"]
    },
    "disinflation_hopes": {
      "display_name": "Disinflation Hopes",
      "group": "Macro Pressure",
      "themes": ["inflation"],
      "keywords": {"strong": ["disinflation"], "medium": ["cooling inflation", "softer inflation"], "weak": ["prices ease"]},
      "driving_sectors": ["consumer_discretionary"],
      "catalyst_names": ["CPI"],
      "connected": ["inflation_fears", "rate_cut_bets"]
    },
    "consumer_stress": {
      "display_name": "Consumer Stress",
      "group": "Macro Pressure",
      "themes": ["recession"],
      "keywords": {"strong": ["consumer confidence"], "medium": ["retail sales", "consumer spending"], "weak": ["spending slump"]},
      "driving_sectors": ["consumer_discretionary", "real_estate"],
      "catalyst_names": ["Retail Sales", "Consumer Confidence"],
      "connected": ["labor_market", "recession_watch"]
    },
    "labor_market": {
      "display_name": "Labor Market",
      "group": "Macro Pressure",
      "themes": ["recession"],
      "keywords": {"strong": ["unemployment", "layoffs", "payroll"], "medium": ["jobless", "job losses", "nonfarm payroll"], "weak": ["hiring"]},
      "driving_sectors": ["consumer_discretionary", "financials"],
      "catalyst_names": ["Nonfarm Payrolls"],
      "connected": ["recession_watch", "consumer_stress"]
    },
    "recession_watch": {
      "display_name": "Recession Watch",
      "group": "Macro Pressure",
      "themes": ["recession"],
      "keywords": {"strong": ["recession", "hard landing", "economic weakness"], "medium": ["downturn", "slowdown", "contraction"], "weak": ["soft landing"]},
      "driving_sectors": ["financials", "consumer_discretionary"],
      "catalyst_names": ["Nonfarm Payrolls"],
      "connected": ["labor_market", "consumer_stress"]
    },
    "commodity_spikes": {
      "display_name": "Commodity Spikes",
      "group": "Energy / Commodities",
      "themes": ["energy"],
      "keywords": {"strong": ["gold", "commodity prices"], "medium": ["wheat", "soybean", "corn", "copper"], "weak": ["metals"]},
      "driving_sectors": ["materials", "energy"],
      "catalyst_names": [],
      "connected": ["oil_supply_shock", "inflation_fears"]
    },
    "opec_policy": {
      "display_name": "OPEC Policy",
      "group": "Energy / Commodities",
      "themes": ["energy"],
      "keywords": {"strong": ["opec", "opec+"], "medium": ["production cut", "output cut", "supply cut"], "weak": ["barrels"]},
      "driving_sectors": ["energy"],
      "catalyst_names": [],
      "connected": ["oil_supply_shock"]
    },
    "rate_cut_bets": {
      "display_name": "Rate Cut Bets",
      "group": "Macro Pressure",
      "themes": ["rates"],
      "keywords": {"strong": ["rate cut", "rate cuts"], "medium": ["fed funds", "dovish"], "weak": ["easing"]},
      "driving_sectors": ["financials", "real_estate"],
      "catalyst_names": ["FOMC"],
      "connected": ["fed_rate_path", "treasury_yields", "disinflation_hopes"]
    }
  }
}
```
