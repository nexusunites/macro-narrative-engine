# Instrument Mapping Architecture

MNE keeps five instrument concerns separate so every identifier has one clear owner.

1. **Asset Registry** (`config/asset_registry.json`) owns real instrument identity, metadata, fetched availability, and display eligibility. `fetched` and `display_enabled` are distinct; an unfetched instrument cannot be presented as current live coverage.
2. **Narrative Asset Map** (`config/narrative_asset_map.json`) owns curated structural narrative-to-real-asset relevance, including role, expected direction, rationale, and display state. Every mapped asset must be fetched and registered.
3. **Market Expression Map** (`config/market_expression_map.json`) owns narrative-expression evaluation. Its identifiers must resolve through either the real asset registry or the synthetic concept registry; it does not own identity.
4. **Synthetic Concept Registry** (`config/synthetic_market_concepts.json`) owns non-tradable conceptual aggregates. These concepts never enter Asset Exploration and never render as assets or tickers.
5. **Legacy Narrative Market Map** is retired. The former `mne/narrative_market_map.py` output and `run["market_expression"]` write path were removed after proof tests established zero active consumers (`docs/legacy_narrative_market_map_audit.md`, 2026-08-04). Old artifacts containing the field remain loadable because persisted-run readers tolerate unknown fields; artifacts without it remain the normal case.

Semantic history remains documentation-only: the legacy map assigned MSFT a primary AI role while the canonical Narrative Asset Map assigns it a secondary role, and legacy recession framing treated TLT as a flight-to-quality expression while canonical Macro Pressure uses a hawkish-rates, expected-down interpretation. The canonical roles and directions are authoritative; neither historical interpretation is active runtime logic.

Sector ETFs persist under sector slugs and remain visible in Asset Exploration through Sector Isolation row reuse. Asset participation also supports a deterministic sector-slug fallback for any future direct sector-ETF mapping. XLE is not duplicated in the Narrative Asset Map.

The live universe uses the existing `get_market_snapshot` path only. Page rendering never fetches data, structural relevance is never inferred from price movement, and missing or old observations remain explicitly unavailable.
