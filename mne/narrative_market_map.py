"""Deprecated legacy narrative map retained for persisted-output compatibility.

Canonical real-instrument identity, structural narrative relevance, and market
expression evaluation live in the versioned config registries. Do not add new
consumers or mappings here; removal requires proof that no compatibility consumer remains.
"""

CONTEXT_NOTE = (
    "These assets are narrative-expression proxies and not trade recommendations."
)

MARKET_EXPRESSION_MAP_VERSION = "phase_1_static_v1"

NARRATIVE_MARKET_MAP = {
    "ai": {
        "display_theme": "AI",
        "primary": ["NVDA", "MSFT", "AVGO"],
        "secondary": ["ANET", "VRT", "DELL"],
        "offsets": ["TLT", "XLU", "XLP"],
        "description": "AI infrastructure, compute, and data center spending.",
    },
    "energy": {
        "display_theme": "Energy",
        "primary": ["XLE", "CVX", "XOM"],
        "secondary": ["SLB", "HAL", "OXY"],
        "offsets": ["XLU", "TLT"],
        "description": "Oil, gas, and energy supply narratives.",
    },
    "rates": {
        "display_theme": "Rates",
        "primary": ["TLT", "IEF"],
        "secondary": ["KRE", "XLF"],
        "offsets": ["QQQ"],
        "description": "Interest-rate and bond-market sensitivity.",
    },
    "inflation": {
        "display_theme": "Inflation",
        "primary": ["GLD", "DBC"],
        "secondary": ["XLE", "FCX"],
        "offsets": ["TLT"],
        "description": "Inflation and commodity-sensitive assets.",
    },
    "recession": {
        "display_theme": "Recession",
        "primary": ["TLT", "XLU", "XLP"],
        "secondary": ["SHY"],
        "offsets": ["XLY"],
        "description": "Defensive and slowdown-sensitive assets.",
    },
}


def normalize_theme(theme):
    if theme is None:
        return None
    return str(theme).strip().lower()


def get_market_expression(theme):
    theme_key = normalize_theme(theme)
    mapping = NARRATIVE_MARKET_MAP.get(theme_key)

    if not mapping:
        return {
            "theme": theme_key,
            "display_theme": str(theme).strip() if theme else "Unavailable",
            "mapping_version": MARKET_EXPRESSION_MAP_VERSION,
            "mapped": False,
            "context_only": True,
            "is_signal": False,
            "primary": [],
            "secondary": [],
            "offsets": [],
            "description": "No curated market expression mapping is available for this theme.",
            "note": CONTEXT_NOTE,
        }

    return {
        "theme": theme_key,
        "display_theme": mapping["display_theme"],
        "mapping_version": MARKET_EXPRESSION_MAP_VERSION,
        "mapped": True,
        "context_only": True,
        "is_signal": False,
        "primary": list(mapping["primary"]),
        "secondary": list(mapping["secondary"]),
        "offsets": list(mapping["offsets"]),
        "description": mapping["description"],
        "note": CONTEXT_NOTE,
    }
