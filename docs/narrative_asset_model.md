# Narrative Asset Model

Asset Exploration separates two deterministic concerns:

- `config/asset_registry.json` defines the bounded, versioned universe of 19 instruments that MNE currently fetches and persists.
- `config/narrative_asset_map.json` curates structural narrative relationships for supported assets only.
- `mne/asset_exploration.py` validates and presents structural relevance without reading market data.
- `mne/asset_participation.py` classifies current participation from each asset's own persisted market snapshot record, using the shared session-aware freshness function and sector-calibrated thresholds.
- `dashboard.py` is the integration boundary and passes participation into the structural context as a plain dictionary.

Sector ETFs enter a sector-scoped page through the existing Sector Isolation row. Their participation state is reused rather than recomputed. Unmapped, unfetched, stale, and malformed observations fail closed to unavailable; no proxy movement or recommendation is inferred.
