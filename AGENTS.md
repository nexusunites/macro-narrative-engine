# AGENTS.md — Working Agreement for AI Contributors

This file orients any AI agent (Codex, Claude, GPT, or other) before working in this repository. Read it fully before making changes.

## What this project is

Macro Narrative Engine (MNE): a deterministic, evidence-driven macro narrative intelligence platform. It detects dominant market narratives from news, measures their strength and evolution, and presents them in a dashboard. It is an analysis engine, **not** a trading signal generator, forecaster, or black-box ML system.

Core philosophy (non-negotiable): explainability (every signal hand-derivable from persisted inputs), deterministic logic over probabilistic scoring, honest degradation (gaps and nulls are truthful; never fabricate values), and narrative-first design.

## Where current state lives

- `docs/project_status.md` — canonical current project state. Read this first.
- `docs/product_backlog.md` — epics, priorities, and what's complete ("Completed Foundations" = extend, don't redesign).
- `docs/handoffs/` and `docs/dashboard_rework_handoff.md` — implementation specifications. Each implemented feature's spec is its reference.
- `ARCHITECTURE.md` — how the engine works.

## Division of labor

- **Claude** — architecture, strategic direction, handoff authoring, post-implementation verification.
- **Codex** — primary implementation, from written handoff documents only.
- **GPT** — UI/UX advisory and schema/parameter definition before handoffs are written.

Implementation work follows written handoffs in `docs/handoffs/`. If a task has no handoff document, ask for one rather than inferring scope.

## Standing rules (all agents)

1. **Never stage, commit, or push.** Implement to a verified local state and stop. Committing is Daniel's step.
2. **Judgment calls are pre-ratified in handoff documents.** Do not re-ask ratified decisions; do not make unratified architectural decisions silently — flag them.
3. **Terminology discipline.** Engine-level names (Regime Alignment, Narrative Pulse, Crowding, Source Confidence, Network Health, etc.) are canonical and consistent across code and docs. User-facing plain language lives exclusively in `mne/presentation_language.py` — a deterministic dictionary, translated at the presentation boundary. Never rename engine concepts; never hardcode user-facing copy in templates.
4. **Presentation/engine boundary.** Dashboard work must not change engine logic, signal semantics, thresholds, or persistence formats unless the handoff explicitly says so. Admin and Research surfaces are separate from the user dashboard.
5. **Data philosophy.** Long-term trends read daily snapshots (one representative point per day), never per-run history — this prevents repeated-run inflation. Run-level data serves only immediate comparisons (Change Summary).
6. **User dashboard color budget.** Neutral black/white base plus exactly two hues: `--up` green (also the brand accent, via the scoped `--brand-accent` repoint) and `--down` red-orange (strictly directional). States convey meaning through typography, never color. Any other hue on `/` is a defect.
7. **Registry-owned configuration.** Thresholds live in `config/source_registry.json`; runs persist `thresholds_used`.
8. **Honest empty states.** Zero matches, zero backfilled, or missing history can be correct outcomes, not bugs. Verify before "fixing."
9. **Verify before negative claims.** Before asserting that a feature does not exist, check `docs/project_status.md`, `docs/product_backlog.md`, handoffs/specs, routes, templates/static assets, models/migrations, tests, and recent git history. Treat "not implemented by this document" as a scoped historical statement, not a repository-wide current-state fact; when sources conflict, report the conflict and prefer verified code plus newer approved handoffs. Never conclude "not implemented" from an architecture document alone.

## Verification standard

Every implementation ends with: full test suite passing; `/`, `/admin`, `/research` returning 200; rendering checked against both the latest real run and a populated synthetic run; empty/degraded states rendered; `git diff --check` clean; nothing staged, committed, or pushed. UI work additionally checks 1280/1024/390 widths, JS-disabled rendering, and the color budget.

## Environment notes

- Python / FastAPI / Jinja2; tests via pytest. No frontend framework, no build step — vanilla JS only (`static/chart.js` pattern).
- Runtime data lives outside the repo at the configured `MNE_DATA_DIR`; never write runtime outputs into the repository.
- `.vscode/settings.json` contains a CSS linter false-positive workaround; check there before chasing linter errors.
