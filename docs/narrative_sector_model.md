# Narrative Sector Model

Version 1.0.0 is a curated, deterministic map from canonical narrative groups to canonical sectors. Each stored record contains a sector key, one structural role (`PRIMARY`, `SECONDARY`, `EMERGING`, `OFFSET`, or `DETACHED`), a rationale, and a display flag. Omitted sectors have no curated relationship; omission does not mean detached.

The read model adds `participation_state`, `evidence_count`, `instruments`, explanation text, availability, and a route link. Structural role describes a durable connection in MNE's narrative model. Participation describes current sector-level market behavior. They are separate fields and separate visual signals.

Participation supports the forward-compatible states `STRONG`, `PARTICIPATING`, `EMERGING`, `MIXED`, `DETACHED`, `CONTRADICTING`, and `UNAVAILABLE`. This sprint always returns `UNAVAILABLE`: MNE does not yet fetch or persist real sector-level market data. Broad-market instruments, narrative-level Market Expression, and evidence concentration are not sector proxies. Evidence counts remain zero and instrument lists remain empty.

Structural breadth counts curated sector connections and their role mix. It does not describe current market participation. The later **Sector Market Data Plumbing and Participation States** sprint is explicitly deferred; it will add real sector ETF coverage, persisted sector snapshots, freshness rules, and genuine participation classification while preserving this structural map as a separate layer.
