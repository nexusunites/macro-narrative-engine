import json
import re
from pathlib import Path


WEIGHTS = {
    "strong": 3,
    "medium": 2,
    "weak": 1,
}


DEFAULT_TAXONOMY_FILE = Path("config/theme_taxonomy.json")
DEFAULT_TAXONOMY_VERSION = "unknown"
ENGINE_VERSION = "1.0.0"


def keyword_match_span(text: str, keyword: str):
    pattern = r"\b" + re.escape(keyword.lower().strip()) + r"\b"
    match = re.search(pattern, text.lower())
    return match.span() if match else None


def keyword_match(text: str, keyword: str) -> bool:
    return keyword_match_span(text, keyword) is not None


def find_theme_keyword_candidates(headline, weighted_keywords):
    candidates = []

    for strength, keywords in weighted_keywords.items():
        weight = WEIGHTS.get(strength, 1)
        for keyword in keywords:
            span = keyword_match_span(headline, keyword)
            if span:
                candidates.append(
                    {
                        "keyword": keyword,
                        "span": span,
                        "weight": weight,
                    }
                )

    return candidates


def select_non_overlapping_matches(candidates):
    kept = []
    occupied_spans = []

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            -len(candidate["keyword"]),
            candidate["span"][0],
            candidate["keyword"],
        ),
    )

    for candidate in sorted_candidates:
        start, end = candidate["span"]
        overlaps_existing_match = any(
            start < occupied_end and end > occupied_start
            for occupied_start, occupied_end in occupied_spans
        )
        if overlaps_existing_match:
            continue

        kept.append(candidate)
        occupied_spans.append(candidate["span"])

    return kept


def normalize_theme_keywords(theme_keywords):
    normalized = {}

    for theme, keywords in theme_keywords.items():
        theme = theme.strip().lower()

        if isinstance(keywords, dict):
            normalized[theme] = {
                strength: [keyword.lower().strip() for keyword in items if keyword.strip()]
                for strength, items in keywords.items()
            }
        else:
            normalized[theme] = {
                "strong": [],
                "medium": [],
                "weak": [keyword.lower().strip() for keyword in keywords if keyword.strip()],
            }

    return normalized


def load_taxonomy_config(taxonomy_file=DEFAULT_TAXONOMY_FILE):
    taxonomy_path = Path(taxonomy_file)

    with open(taxonomy_path, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)

    themes = normalize_theme_keywords(taxonomy.get("themes", {}))
    weights = taxonomy.get("weights", {})

    return {
        "taxonomy_version": taxonomy.get(
            "taxonomy_version",
            DEFAULT_TAXONOMY_VERSION,
        ),
        "themes": themes,
        "weights": {
            strength: int(weights.get(strength, default_weight))
            for strength, default_weight in WEIGHTS.items()
        },
    }


def get_taxonomy_version(taxonomy_file=DEFAULT_TAXONOMY_FILE):
    return load_taxonomy_config(taxonomy_file)["taxonomy_version"]


def load_themes(
    filename="themes.txt",
    taxonomy_file=DEFAULT_TAXONOMY_FILE,
    include_version=False,
):
    taxonomy = load_taxonomy_config(taxonomy_file)
    themes = taxonomy["themes"]

    legacy_path = Path(filename)
    if not legacy_path.exists():
        return (themes, taxonomy["taxonomy_version"]) if include_version else themes

    with open(legacy_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                continue  # skip malformed lines

            theme, triggers = line.split(":", 1)
            theme = theme.strip().lower()

            trigger_list = [t.strip().lower() for t in triggers.split(",") if t.strip()]
            if theme and trigger_list:
                themes.setdefault(theme, {"strong": [], "medium": [], "weak": []})
                for trigger in trigger_list:
                    if not any(trigger in values for values in themes[theme].values()):
                        themes[theme]["weak"].append(trigger)

    if include_version:
        return themes, taxonomy["taxonomy_version"]

    return themes


def analyze_themes(headlines, themes, examples_per_theme=3, include_attribution=False):
    """
    Returns:
      counts: dict[theme] -> raw headline match count
      examples: dict[theme] -> list[str] (up to examples_per_theme headlines)
      matched_headlines: int (how many headlines matched at least one theme)
      scores: dict[theme] -> weighted keyword score
      audit: dict[theme] -> matched keyword counts and example headlines
      attribution: optional list[dict] aligned to input headlines, with matched themes
    """
    counts = {theme: 0 for theme in themes.keys()}
    scores = {theme: 0 for theme in themes.keys()}
    examples = {theme: [] for theme in themes.keys()}
    audit = {
        theme: {"matched_terms": {}}
        for theme in themes.keys()
    }
    matched_headlines = 0
    attribution = []

    for headline in headlines:
        matched_any = False
        matched_themes = []

        for theme, weighted_keywords in themes.items():
            headline_theme_score = 0
            matched_keywords = select_non_overlapping_matches(
                find_theme_keyword_candidates(headline, weighted_keywords)
            )

            for match in matched_keywords:
                keyword = match["keyword"]
                headline_theme_score += match["weight"]
                term_audit = audit[theme]["matched_terms"].setdefault(
                    keyword,
                    {
                        "count": 0,
                        "examples": [],
                    },
                )
                term_audit["count"] += 1
                if len(term_audit["examples"]) < examples_per_theme:
                    term_audit["examples"].append(headline)

            if headline_theme_score > 0:
                counts[theme] += 1
                scores[theme] += headline_theme_score
                matched_any = True
                matched_themes.append(theme)

                if len(examples[theme]) < examples_per_theme:
                    examples[theme].append(headline)

        if matched_any:
            matched_headlines += 1
        if include_attribution:
            attribution.append(
                {
                    "headline": headline,
                    "themes": matched_themes,
                }
            )

    if include_attribution:
        return counts, examples, matched_headlines, scores, audit, attribution
    return counts, examples, matched_headlines, scores, audit
