import re


def trigger_matches(text: str, trigger: str) -> bool:
    trigger = trigger.lower().strip()

    # Phrase match (e.g., "artificial intelligence")
    if " " in trigger:
        return trigger in text

    # Whole-word match for single words (e.g., "ai", "rates")
    pattern = rf"\b{re.escape(trigger)}\b"
    return re.search(pattern, text) is not None


def load_themes(filename):
    themes = {}  # theme -> list of trigger phrases
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
                themes[theme] = trigger_list

    return themes


def analyze_themes(headlines, themes, examples_per_theme=3):
    """
    Returns:
      counts: dict[theme] -> int
      examples: dict[theme] -> list[str]  (up to examples_per_theme headlines)
      matched_headlines: int  (how many headlines matched at least one theme)
    """
    counts = {theme: 0 for theme in themes.keys()}
    examples = {theme: [] for theme in themes.keys()}
    matched_headlines = 0

    for headline in headlines:
        text = headline.lower()
        matched_any = False

        for theme, triggers in themes.items():
            if any(trigger_matches(text, trigger) for trigger in triggers):
                counts[theme] += 1
                matched_any = True

                if len(examples[theme]) < examples_per_theme:
                    examples[theme].append(headline)

        if matched_any:
            matched_headlines += 1

    return counts, examples, matched_headlines