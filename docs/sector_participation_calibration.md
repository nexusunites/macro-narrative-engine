# Sector Participation Calibration Audit

Audit date: 2026-08-04

## Observed facts

The configured real run store contained **165 persisted run files**. A read-only audit found **zero sector-keyed `market_snapshot` entries** and therefore **zero valid persisted sector observations**. There were no sector `pct_change` values or `observed_at` timestamps to distribute, validate, or use for empirical tuning. The two old files in the repository sample data directory are not the live run store and were excluded.

This result is reproducible without fetching or rewriting data:

```console
python scripts/audit_sector_observations.py "$MNE_DATA_DIR/results"
```

The audit counts every JSON run file, recognizes only registry-owned sector keys, and counts an observation as valid only when it has a parseable timestamp and a finite numeric percentage change. Malformed files and observations remain visible in the file/entry counts but are excluded from valid observations.

No live or historical data was fetched to manufacture a calibration sample. A current smoke fetch, if run for pipeline verification, is not calibration data.

## Unchanged provisional thresholds

There is no empirical basis for changing numeric rules. The following shipped values remain provisional and unchanged:

| Rule | Value | Status |
|---|---:|---|
| Strong movement | `STRONG_MOVE_PCT = 1.0` | Provisional; unchanged |
| Meaningful movement and contradiction | `MEANINGFUL_MOVE_PCT = 0.25` | Provisional; unchanged |
| Near-zero detached movement | `DETACHED_MOVE_EPSILON = 0.01` | Provisional; unchanged |
| Post-close pipeline grace | `STALE_GRACE_WINDOW = 8 hours` | Provisional engineering allowance |

Participation breadth also remains unchanged and provisional. Any fresh contradiction produces `CONTRADICTED`; three or more confirming sectors produce `BROAD`; two produce `MODERATE`; one produces `CONCENTRATED`; an emerging-only result produces `LIMITED`; otherwise breadth is `UNAVAILABLE`. Partial coverage can only support the state justified by fresh, classifiable rows.

## Structural role and observed participation

The former runtime cap on structurally `EMERGING` sectors was removed. Structural maturity describes the curated durability of a narrative-sector connection; participation describes a fresh observed ETF response. Neither dimension mutates or limits the other.

“Structural maturity does not limit the strength of observed market participation. MNE displays both dimensions separately so an early-stage connection can still show a strong current response.”

Accordingly, an `EMERGING` structural role may display `STRONG`, `PARTICIPATING`, `EMERGING`, `DETACHED`, `CONTRADICTING`, or `UNAVAILABLE`. The stored structural role remains unchanged.

## Contradiction rules

`CONTRADICTING` requires all of the following: a structurally mapped sector, a curated explicit `expected_expression`, a finite percentage move from fresh valid ETF data, movement opposite the expected direction, and absolute movement of at least 0.25%. Structural role is not a runtime gate. A structurally detached sector has no curated expected direction and therefore fails closed to `UNAVAILABLE`; an ETF move alone cannot make it contradicting. A near-zero move remains `DETACHED` because the epsilon rule precedes contradiction.

## Exchange-session freshness

Freshness uses the NYSE calendar supplied by the explicitly declared `pandas_market_calendars` dependency. All comparisons accept an injected `as_of` and use timezone-aware UTC instants.

1. Missing or malformed `observed_at` is `UNAVAILABLE`.
2. A timestamp later than `as_of` is incoherent and fails closed to `UNAVAILABLE`; it is never fresh.
3. Count NYSE session closes strictly after the observation and at or before `as_of`.
4. Zero completed session closes means `FRESH`. Friday-close data therefore remains valid through the weekend, and the most recent completed-session observation remains valid through an exchange holiday.
5. After exactly one subsequent session close, data remains `FRESH` through an inclusive eight-hour grace window so the daily pipeline can persist the new close.
6. After that grace window, or once two or more sessions have closed, the observation is `STALE`.
7. A ten-calendar-day absolute stale backstop is a defensive guard against unexpected calendar gaps, not the primary freshness rule.

The price source supplies daily closes, not genuine intraday observations. “Current” therefore means current relative to the latest available completed daily session; it does not imply sub-day price precision.

### Conservative fallback limitations

No manually maintained broad holiday table is used. If the calendar dependency is missing, raises an error, or cannot produce the expected close column, freshness resolves to `UNAVAILABLE` rather than silently guessing that uncertain data is fresh. This conservative fallback cannot preserve weekend, holiday, or early-close freshness by itself; normal operation requires the declared and verified calendar dependency. `pandas_market_calendars` supplies exchange holidays and scheduled early closes.

## Compatibility and boundaries

The existing flat `market_snapshot` format is unchanged. Old snapshots without sector keys or timestamps continue to render participation as unavailable, with no migration or historical rewrite. Freshness and participation operate only on persisted input; they do not fetch during classification or page rendering. The dashboard injection boundary remains unchanged, and `mne/sector_isolation.py` still imports no market-context, calendar, or provider module. This work changes no scoring, taxonomy, Narrative Memory, Historical Replay, persistence schema, or market-data provider.

## Future recalibration criteria

Recalibrate the movement thresholds, 3/2/1 breadth breakpoints, and eight-hour grace window only after **at least 20 trading days** of real persisted observations exist—approximately **220 valid sector observations** across the 11 configured sectors. At that point, analyze actual distributions, state frequencies, sector coverage, and pipeline timing. Until the trigger is met, the thresholds remain provisional and should not be tuned against assumptions or isolated smoke-fetch values.
