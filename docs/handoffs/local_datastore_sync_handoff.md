# Local Datastore + Drive Sync — Codex Implementation Handoff

## Problem and measured evidence

`MNE_DATA_DIR` currently points at a Google Drive CloudStorage directory on macOS. Measured on the live system: reading the results directory (158 JSON files, ~6–9 MB) takes **~19.6 s** through Drive streaming (with intermittent `Operation timed out` failures) versus **~0.056 s** from local SSD — a ~350x penalty on every page render and engine run, and the dominant cause of the remaining dashboard latency after the render-cache and context-split fixes.

Fix: the active datastore becomes a plain local directory; Google Drive becomes an optional, non-destructive backup/cross-device sync target, addressed by explicit `pull`/`push` commands and an optional run wrapper. No always-on sync, no daemons.

Read `AGENTS.md` before starting. All standing rules apply. Verified context: `config.py` resolves `MNE_DATA_DIR` (env override, else `~/.mne/data`) with `data_dir_source()` visibility; `mne/storage.py` derives all subdirectories from `DATA_DIR`; `scripts/` already hosts standalone operational scripts (`backfill.py`, `repair_snapshot_support_scores.py`) — follow that pattern; `run_mne.bat` exists for Windows direct execution and must keep working unchanged.

## Scope

1. **`MNE_DATA_DIR` behavior is untouched.** No changes to `config.py` resolution, defaults, or any consumer. The user simply points it at a local path.
2. **New optional `MNE_SYNC_DIR`** environment variable: the secondary (Drive) directory. Read only by the new sync tooling — the engine, dashboard, and `config.py` never consult it.
3. **New thin CLI — `scripts/sync_data.py`** with subcommands `status`, `pull`, `push`, backed by a reusable module (`mne/data_sync.py`) so logic is testable without subprocess invocation.
4. **New run wrapper — `scripts/run_mne.py`**: optional pull → run engine → push only on success.
5. Documentation updates (see below).

No shell configuration is modified by any code — `~/.zshrc` etc. are the user's to edit; the docs explain how.

## Command interface

- `python scripts/sync_data.py status` — prints both resolved paths, whether each exists, file/byte counts per top-level subdirectory, and counts of files that `pull`/`push` would copy or update. Read-only.
- `python scripts/sync_data.py pull` — copy `MNE_SYNC_DIR` → `MNE_DATA_DIR` per the sync semantics below.
- `python scripts/sync_data.py push` — copy `MNE_DATA_DIR` → `MNE_SYNC_DIR`.
- `python scripts/run_mne.py [--pull] [engine args…]` — optionally pull first; invoke `main.py` via `sys.executable` with pass-through args; propagate the engine's exit code exactly; push only after exit code 0; never push after a failed run. `python main.py` direct execution remains unchanged in behavior.

## Path resolution and validation

- Both variables resolve via `Path(value).expanduser().resolve()`.
- Missing `MNE_DATA_DIR` falls back to the existing `config.py` default (reuse `config.get_data_dir()`; do not reimplement resolution).
- Missing `MNE_SYNC_DIR`: sync commands exit with a clear one-line diagnostic ("MNE_SYNC_DIR is not set — set it to your shared backup directory to enable sync") and a non-zero exit code; the wrapper without `--pull` runs normally and simply skips the post-run push with an informational line.
- Same resolved path for source and destination: refuse with a diagnostic, non-zero exit. Also refuse if one path is inside the other.
- Source directory missing on `pull`/`push`: calm diagnostic, non-zero exit, no partial work.

## Sync semantics (non-destructive, standard library only)

- Recursive walk (`os.walk`/`pathlib`), `shutil.copy2` for copies; no `rsync`, no external dependencies.
- Copy files absent at the destination; update files whose source `(size, mtime_ns)` differs — copy when in doubt; **never delete or move destination files**; destination-only files are always preserved.
- Recreate nested directory structure as encountered.
- Skip transient artifacts: hidden files (`.DS_Store`, `.tmp*`) excluded by a small fixed skip-list.
- Per-file failures (e.g., a CloudStorage timeout) are caught, reported with the file path and reason, counted, and do not abort the remaining copy; the command exits non-zero if any file failed, after completing what it could.
- Conflict behavior: last-writer-wins per direction by design. This version is explicitly single-writer — the docs state the safe workflow (pull → work → push) and that concurrent editing on two machines between syncs is unsupported.

## Wrapper execution flow

`run_mne.py`: (1) if `--pull`, run pull; a pull failure aborts before the engine runs (exit with the pull's code). (2) Run `[sys.executable, "main.py", *args]` from the repo root. (3) If exit code is 0 and `MNE_SYNC_DIR` is set, push; a push failure is reported and yields a distinct non-zero exit even though the engine succeeded. (4) Any non-zero engine exit is propagated unchanged and no push occurs.

## Error and exit-code behavior

0 = success. Non-zero for: missing/invalid configuration, validation refusal, sync failures (with per-file detail), engine failure (propagated verbatim). All diagnostics are single-purpose, human-readable lines; no tracebacks for anticipated conditions.

## Non-Goals

No bidirectional merge, no conflict resolution beyond last-writer-wins, no deletion propagation, no databases, daemons, file watchers, locks, schedulers, or external dependencies. No changes to `main.py`, `config.py` semantics, `run_mne.bat`, or engine/dashboard behavior. Not a backup-rotation or versioning system — Drive's own version history covers that.

## Tests required (pytest, temporary directories, no real Drive access)

Missing `MNE_DATA_DIR` (falls back to default resolution); missing `MNE_SYNC_DIR` diagnostics for each command; same-resolved-path refusal; nested-path refusal; source-missing refusal; initial recursive copy including nested directories; changed-file update; unchanged-file skip; destination-only-file preservation; skip-list exclusion; per-file failure containment and non-zero exit; `status` output correctness; successful `pull`; successful `push`; wrapper: engine failure propagates exit code and suppresses push; wrapper: push occurs after success; wrapper: `--pull` failure aborts before engine; wrapper: unset `MNE_SYNC_DIR` runs engine normally and skips push informationally. Existing full suite passes unchanged.

## Documentation updates

`INSTALLATION.md` (or `README.md` where environment setup lives): `MNE_DATA_DIR` is the fast local active datastore; `MNE_SYNC_DIR` is the optional shared backup; how to set both on macOS (`export` lines the user adds to their own shell profile) and Windows (`setx` / System Environment Variables — no file edited by MNE); manual `status`/`pull`/`push` usage; wrapper usage; the safe cross-device workflow: **pull before working → run locally → push after success**; migration note for the current state (copy the Drive directory local once via `pull` with `MNE_DATA_DIR` local and `MNE_SYNC_DIR` at the Drive path).

## Acceptance criteria

All required tests pass; `python main.py` behavior byte-identical with and without the new variables set; sync is provably non-destructive (destination-only preservation test); wrapper propagates engine exit codes exactly; no repository file writes to shell configuration; no new dependencies in `requirements.txt`.

## Verification

- `python -m pytest tests/test_data_sync.py -v` (or unittest equivalent matching repo convention)
- `python -m unittest discover -s tests`
- `python -m compileall dashboard.py main.py mne scripts tests`
- `git diff --check`
- Manual: with temp directories as `MNE_DATA_DIR`/`MNE_SYNC_DIR` — `status`, `pull`, `push`, wrapper success and simulated failure (`main.py` args that produce a failing run, or a stub); confirm destination-only files survive both directions; confirm `python main.py` runs unchanged.

## Unresolved risks

- Drive CloudStorage may still time out during `push`/`pull`; per-file containment reports rather than hangs, but a fully offline Drive client can stall individual copies — the user should run sync when Drive is healthy.
- mtime fidelity on CloudStorage is imperfect; `(size, mtime_ns)` comparison may occasionally re-copy unchanged files — harmless by design.
- Single-writer assumption: simultaneous runs on two machines between syncs can silently last-writer-win; out of scope by decision, documented.

Implement to a verified local state and stop — do not stage, commit, or push.
