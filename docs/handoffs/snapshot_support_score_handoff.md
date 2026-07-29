# Daily Snapshot Support Score — Codex Implementation Handoff

## Purpose

The reworked dashboard hero chart reads Market Support (Regime Alignment) scores exclusively from daily snapshots, but snapshots do not persist that score. Result: the hero chart shows the insufficient-history state on real data. This handoff adds the score to snapshot persistence going forward and repairs existing snapshots from persisted run results. Small, surgical change — no signal logic, threshold, or dashboard changes.

## Facts (verified in code)

- `main.py` sets `run["regime_alignment"]` and includes it in the saved results dict. Older results files (e.g., May 2026) predate this and lack the key — that is valid, not a defect.
- `mne/storage.py` → `write_daily_snapshot` builds `raw_runs` entries containing only `run_id`, `timestamp`, `narratives`, `event_lifecycle`; `_aggregate_raw_runs` produces the snapshot. No regime data survives.
- `dashboard.py` → `_snapshot_support_score` already looks up, in order: `regime_alignment.score` (nested), `market_support.score`, `market_support_score`, `support_score`. Persist to match the **first** form.

## Changes

### 1. Forward persistence (`mne/storage.py`)

- Add `regime_alignment` to each `raw_runs` entry in `write_daily_snapshot` and `build_daily_snapshot_preview`: `{"score": <int|None>, "state": <str|None>}`, taken from `run_data.get("regime_alignment")`. Absent → `None` values, never omit the key going forward.
- In `_aggregate_raw_runs`, add top-level `regime_alignment: {"score", "state", "source_run_id"}` to the snapshot, selected by the representative rule: **the latest raw run of the day that has a non-null score**. If no run that day has one, persist `{"score": null, "state": null, "source_run_id": null}`. Deterministic, hand-derivable: latest qualifying timestamp wins.

### 2. Snapshot repair backfill (`mne/storage.py` + admin surface if trivial)

`backfill_daily_snapshots` skips existing snapshots, so add a separate idempotent pass, e.g. `repair_snapshot_support_scores() -> int`:

- For each existing snapshot file lacking a `regime_alignment` key (or with score null), load that date's results files from `RESULTS_DIR`, apply the same representative rule, and write the score/state/source_run_id into the snapshot. Touch nothing else in the file.
- Returns count of snapshots repaired. Zero repaired because no results contain the key is valid, not a failure (established principle).
- Expose via the existing script/CLI pattern used for other backfills; no new UI required.

### 3. Chart behavior (verify only, no changes expected)

Days with null scores must be skipped by the chart data builder (gaps, not zeros). Confirm `dashboard.py`'s snapshot chart builder already does this; fix only if it plots nulls as values.

## Ratified Decisions (Daniel, 2026-07-29)

1. **Representative rule = latest run of the day with a score.** Ratified.
2. **Null-score days persist an explicit null** (never omit the key, never fabricate a value). The chart renders these as gaps. Remediation of null days is explicitly deferred: recovering historical scores is a future Historical Replay Foundation use case, not part of this handoff. Optional cheap addition if trivial: an admin-side count of snapshot days with null support scores, so gaps are visible rather than silent.

## Verification

- Unit tests: raw-run enrichment, representative selection (multiple runs, none-with-score, single), repair idempotency (second run repairs 0).
- Run repair against real data; report count repaired.
- Load `/`: hero chart renders real snapshot scores where history exists; insufficient-history state still renders correctly when it does not.
- Full test suite passes; `/admin` and `/research` return 200.

Implement to a verified local state and stop — do not stage, commit, or push.
