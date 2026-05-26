import re


WEIGHTS = {
    "strong": 3,
    "medium": 2,
    "weak": 1,
}


THEME_KEYWORDS = {
    "ai": {
        "strong": ["artificial intelligence", "openai", "nvidia", "deepseek", "ai chip", "ai chips"],
        "medium": ["generative ai", "genai", "machine learning", "data center", "data centers", "copilot"],
        "weak": ["ai", "chatbot"],
    },
    "rates": {
        "strong": ["fed rate cut", "treasury yield", "treasury yields", "interest rates", "interest rate"],
        "medium": ["bond yield", "bond yields", "fed funds", "powell", "fomc", "central bank"],
        "weak": ["yields", "rates", "rate cut", "rate cuts", "rate hike", "rate hikes", "borrowing costs", "mortgage rates"],
    },
    "inflation": {
        "strong": ["inflation", "cpi", "pce", "sticky inflation"],
        "medium": ["price pressures", "price shock", "cost of living", "disinflation", "deflation"],
        "weak": ["prices rise"],
    },
    "energy": {
        "strong": ["crude oil", "natural gas", "opec", "brent", "wti"],
        "medium": ["oil", "crude", "energy prices", "gas prices", "petroleum", "lng"],
        "weak": ["fuel prices", "gasoline"],
    },
    "recession": {
        "strong": ["recession", "hard landing", "economic weakness"],
        "medium": ["downturn", "slowdown", "contraction", "unemployment", "layoffs"],
        "weak": ["soft landing", "job losses"],
    },
}


def keyword_match(text: str, keyword: str) -> bool:
    pattern = r"\b" + re.escape(keyword.lower().strip()) + r"\b"
    return re.search(pattern, text.lower()) is not None


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


def load_themes(filename):
    themes = normalize_theme_keywords(THEME_KEYWORDS)

    with open(filename, "r", encoding="utf-8") as f:
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

    return themes


def analyze_themes(headlines, themes, examples_per_theme=3):
    """
    Returns:
      counts: dict[theme] -> raw headline match count
      examples: dict[theme] -> list[str] (up to examples_per_theme headlines)
      matched_headlines: int (how many headlines matched at least one theme)
      scores: dict[theme] -> weighted keyword score
    """
    counts = {theme: 0 for theme in themes.keys()}
    scores = {theme: 0 for theme in themes.keys()}
    examples = {theme: [] for theme in themes.keys()}
    matched_headlines = 0

    for headline in headlines:
        matched_any = False

        for theme, weighted_keywords in themes.items():
            headline_theme_score = 0

            for strength, keywords in weighted_keywords.items():
                weight = WEIGHTS.get(strength, 1)
                for keyword in keywords:
                    if keyword_match(headline, keyword):
                        headline_theme_score += weight

            if headline_theme_score > 0:
                counts[theme] += 1
                scores[theme] += headline_theme_score
                matched_any = True

                if len(examples[theme]) < examples_per_theme:
                    examples[theme].append(headline)

        if matched_any:
            matched_headlines += 1

    return counts, examples, matched_headlines, scores
