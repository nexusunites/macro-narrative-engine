import json
import re
from datetime import datetime
from pathlib import Path

import feedparser

print("STARTING main.py")


def trigger_matches(text: str, trigger: str) -> bool:
    trigger = trigger.lower().strip()

    # Phrase match (e.g., "artificial intelligence")
    if " " in trigger:
        return trigger in text

    # Whole-word match for single words (e.g., "ai", "rates")
    pattern = rf"\b{re.escape(trigger)}\b"
    return re.search(pattern, text) is not None


def fetch_headlines_from_rss(rss_urls, limit_per_feed=25):
    headlines = []
    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if title:
                headlines.append(title)

    # De-dupe while preserving order
    deduped = list(dict.fromkeys(headlines))
    return deduped


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


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_last_two_result_files(results_dir: Path):
    files = sorted(results_dir.glob("*.json"))
    if len(files) < 2:
        return None, None
    return files[-1], files[-2]


def main():
    print("=== Daily Narrative Snapshot ===")

    rss_urls = [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",          # WSJ Markets
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
    ]

    headlines = fetch_headlines_from_rss(rss_urls, limit_per_feed=30)
    print(f"Loaded headlines from RSS: {len(headlines)}")

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    # Save raw headlines
    headlines_dir = Path("data/headlines")
    headlines_dir.mkdir(parents=True, exist_ok=True)
    headlines_file = headlines_dir / f"{stamp}.txt"
    with open(headlines_file, "w", encoding="utf-8") as f:
        for headline in headlines:
            f.write(headline + "\n")
    print(f"Headlines saved to {headlines_file}")

    # Theme analysis
    themes = load_themes("themes.txt")
    results, examples, matched_headlines = analyze_themes(headlines, themes, examples_per_theme=3)

    coverage_pct = (matched_headlines / len(headlines) * 100) if headlines else 0
    print(f"Coverage: {matched_headlines}/{len(headlines)} ({coverage_pct:.1f}%) headlines matched at least one theme")

    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    nonzero = [(k, c) for k, c in sorted_results if c > 0]

    for theme, count in nonzero:
        print(f"{theme}: {count}")

    # Defaults (keep JSON + momentum safe even if empty)
    top_theme = None
    top_count = 0
    total_mentions = 0
    share = 0.0
    concentration = 0

    if nonzero:
        top_theme, top_count = nonzero[0]
        total_mentions = sum(c for _, c in nonzero)
        share = (top_count / total_mentions) if total_mentions > 0 else 0.0

        if len(nonzero) >= 2:
            _, second_count = nonzero[1]
            concentration = top_count - second_count
        else:
            concentration = top_count

        print(f"\nDominant Narrative: {top_theme} ({top_count} mentions)")
        print(f"Total Mentions: {total_mentions}")
        print(f"Dominant Narrative Share: {share * 100:.1f}%")
        print(f"Concentration Gap: {concentration}")

        print("\nExamples for top themes:")
        for theme, count in nonzero[:3]:
            print(f"\n[{theme}] ({count})")
            for i, h in enumerate(examples[theme], start=1):
                print(f"  {i}. {h}")
    else:
        print("\nNo narratives detected today.")

    # Save results JSON
    results_dir = Path("data/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    run = {
        "timestamp": stamp,
        "rss_urls": rss_urls,
        "headline_count": len(headlines),
        "matched_headlines": matched_headlines,
        "coverage_pct": round(coverage_pct, 1),
        "theme_counts": results,
        "sorted_nonzero": nonzero,  # tuples become arrays in JSON (fine)
        "dominant_theme": top_theme,
        "dominant_count": top_count,
        "total_mentions": total_mentions,
        "dominant_share": round(float(share), 4),
        "concentration_gap": int(concentration),
        # keep examples for top 3 themes
        "examples": {k: v for k, v in examples.items() if k in dict(nonzero[:3])},
    }

    results_file = results_dir / f"{stamp}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {results_file}")

    # Momentum (compare latest run vs previous run)
    latest, previous = get_last_two_result_files(results_dir)
    if previous is None:
        print("Momentum: not enough history yet (need 2 runs).")
    else:
        current = load_json(latest)
        prior = load_json(previous)

        cur_counts = current.get("theme_counts", {})
        prev_counts = prior.get("theme_counts", {})
        all_themes = sorted(set(cur_counts.keys()) | set(prev_counts.keys()))

        print("\n=== Momentum (vs previous run) ===")
        printed_any = False
        for theme in all_themes:
            cur = int(cur_counts.get(theme, 0))
            prev = int(prev_counts.get(theme, 0))
            delta = cur - prev
            if delta != 0:
                printed_any = True
                sign = "+" if delta > 0 else ""
                print(f"{theme}: {cur} ({sign}{delta})")

        cur_share = float(current.get("dominant_share", 0))
        prev_share = float(prior.get("dominant_share", 0))
        cur_gap = int(current.get("concentration_gap", 0))
        prev_gap = int(prior.get("concentration_gap", 0))

        print(f"Dominant theme: {current.get('dominant_theme')} (was {prior.get('dominant_theme')})")

        cur_cov = float(current.get("coverage_pct", 0))
        prev_cov = float(prior.get("coverage_pct", 0))
        print(f"Coverage: {cur_cov:.1f}% ({cur_cov - prev_cov:+.1f}pp)")

        print(f"Dominant share: {cur_share*100:.1f}% ({(cur_share-prev_share)*100:+.1f}pp)")
        print(f"Concentration gap: {cur_gap} ({cur_gap - prev_gap:+d})")

        if not printed_any:
            print("(No per-theme count changes)")

        print("===============================")

    print("\n=============================")


if __name__ == "__main__":
    main()