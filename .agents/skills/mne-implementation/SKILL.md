---
name: mne-implementation
description: Implement approved Macro Narrative Engine handoffs with strict scope control, baseline verification, architecture preservation, testing, and browser validation.
---

# MNE Implementation

Use this workflow only when implementing a user-identified, approved Macro Narrative Engine handoff.

## Prepare

1. Read the repository-root `AGENTS.md` and the user-identified implementation handoff in full before editing. Treat the handoff as the task contract; follow `AGENTS.md` wherever it is stricter.
2. Inspect the affected source files and existing tests before deciding how to implement the change.
3. Run `git status --short` before editing. Record all existing working-tree changes and preserve pre-existing user work.
4. Establish a test baseline by running the relevant targeted tests before editing. Record existing failures so they can be distinguished from regressions introduced by the implementation.

## Control scope

- Implement only the scope approved by the handoff and user instructions. Prefer the smallest complete implementation that satisfies every acceptance criterion.
- Modify only authorized files. If another file is technically required, explain why before expanding scope.
- Do not perform unrelated cleanup, roadmap expansion, architecture redesign, dependency additions, schema changes, migrations, or persistence changes unless explicitly authorized.
- Preserve engine, presentation, persistence, authentication, and authorization boundaries.
- Never reset or discard changes, stage, commit, push, create branches, or switch branches unless explicitly instructed.

## Implement and test

- Add realistic regression tests for the normal path, relevant empty or failure states, and the user-visible path where practical.
- Never weaken existing tests merely to make them pass.
- Run relevant targeted tests after editing, then the full test suite when feasible.
- Run `compileall` for every changed Python source file and Python test file.
- Run `git diff --check`.
- Run route checks for every affected web surface.
- For user-facing UI changes, use the project `playwright-cli` skill when the environment permits. Inspect the rendered application for route status, expected content, interactions, console errors, static asset failures, responsive behavior, and all visible acceptance criteria.
- If browser automation is unavailable, report the substitute verification actually used.
- Never claim a verification step passed unless it was actually run.

## Final review

Review the final diff and repository state. Confirm that:

- only authorized files, or files whose necessity was explained before editing, changed;
- all pre-existing user work remains intact;
- no secrets, generated junk, or debugging output were added;
- no unrelated formatting churn occurred; and
- any baseline failures are clearly separated from new regressions.

Return a concise completion report with these sections:

### Implemented

Summarize the approved behavior implemented and the files changed.

### Verification

List only checks actually run, their outcomes, any pre-existing failures, and any verification that could not be performed.

### Repository State

Summarize `git status --short`, distinguish pre-existing work from task changes, and confirm that nothing was staged, committed, or pushed.
