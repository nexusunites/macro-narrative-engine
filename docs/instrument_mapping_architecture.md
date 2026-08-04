# Instrument Mapping Architecture

MNE keeps five instrument concerns separate so every identifier has one clear owner.

1. **Asset Registry** (`config/asset_registry.json`) owns real instrument identity, metadata, fetched availability, and display eligibility. `fetched` and `display_enabled` are distinct; an unfetched instrument cannot be presented as current live coverage.
2. **Narrative Asset Map** (`config/narrative_asset_map.json`) owns curated structural narrative-to-real-asset relevance, including role, expected direction, rationale, and display state. Every mapped asset must be fetched and registered.
3. **Market Expression Map** (`config/market_expression_map.json`) owns narrative-expression evaluation. Its identifiers must resolve through either the real asset registry or the synthetic concept registry; it does not own identity.
4. **Synthetic Concept Registry** (`config/synthetic_market_concepts.json`) owns non-tradable conceptual aggregates. These concepts never enter Asset Exploration and never render as assets or tickers.
5. **Legacy Narrative Market Map** (`mne/narrative_market_map.py`) is deprecated compatibility output. It remains until repo-wide proof shows that scripts, reports, exports, runtime consumers, and persisted-output readers no longer depend on it.

Sector ETFs persist under sector slugs and remain visible in Asset Exploration through Sector Isolation row reuse. Asset participation also supports a deterministic sector-slug fallback for any future direct sector-ETF mapping. XLE is not duplicated in the Narrative Asset Map.

The live universe uses the existing `get_market_snapshot` path only. Page rendering never fetches data, structural relevance is never inferred from price movement, and missing or old observations remain explicitly unavailable.
