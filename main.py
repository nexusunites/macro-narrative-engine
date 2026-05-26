from datetime import datetime

from mne.environment import classify_market_environment
from mne.market_context import get_market_snapshot
from mne.narrative_signals import (
    compute_group_scores,
    compute_narrative_concentration,
    compute_narrative_signals,
    get_dominant_group,
)
from mne.reporting import (
    build_daily_report,
    print_dominant_narratives,
    print_group_scores,
    print_market_context,
    print_market_environment,
    print_narrative_concentration,
    print_narrative_signals,
    print_theme_counts,
    print_top_theme_examples,
)
from mne.rss_fetch import fetch_headlines_from_rss
from mne.storage import save_headlines, save_report, save_run_json
from mne.theme_analysis import analyze_themes, load_themes
from mne.trends import print_daily_count_trends, print_daily_share_trends, print_momentum

print("STARTING main.py")


RSS_URLS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # WSJ Markets
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.ft.com/?format=rss",  # Financial Times
    "https://www.bloomberg.com/feed/podcast/etf-report.xml",  # Bloomberg ETF Report
    "https://www.bbc.co.uk/news/business/rss.xml",  # BBC Business
    "https://www.npr.org/rss/rss.php?id=1001",  # NPR Business
    "https://www.economist.com/finance-and-economics/rss.xml",  # Economist Finance
]

NASDAQ_TICKERS = {
    "QQQ": "QQQ",
    "NVDA": "NVDA",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
}

TREND_LOOKBACK = 5
TREND_EPSILON = 0.02


def main():
    print("=== Daily Narrative Snapshot ===")
    print()

    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M")
    readable_time = now.strftime("%Y-%m-%d %H:%M")

    print(f"Run Timestamp: {readable_time}")
    print()

    headlines = fetch_headlines_from_rss(RSS_URLS)
    headlines_file = save_headlines(headlines, stamp)

    print(f"Loaded {len(headlines)} headlines from RSS")
    print(f"Loaded {len(RSS_URLS)} RSS feeds")
    print(f"Headlines saved to {headlines_file}")
    print()

    themes = load_themes("themes.txt")
    results, examples, matched_headlines, theme_scores = analyze_themes(
        headlines,
        themes,
        examples_per_theme=3,
    )

    coverage_pct = (matched_headlines / len(headlines) * 100) if headlines else 0
    print(
        f"Coverage: {matched_headlines}/{len(headlines)} "
        f"({coverage_pct:.1f}%) headlines matched at least one theme"
    )
    print()

    sorted_results = sorted(theme_scores.items(), key=lambda item: item[1], reverse=True)
    nonzero = [(theme, count) for theme, count in sorted_results if count > 0]
    print_theme_counts(nonzero)

    group_scores = compute_group_scores(theme_scores)
    dominant_group, dominant_group_score = get_dominant_group(group_scores)
    print_group_scores(group_scores)

    concentration = compute_narrative_concentration(nonzero)
    top_theme = concentration["dominant_theme"]
    top_count = concentration["dominant_count"]
    total_mentions = concentration["total_mentions"]
    share = concentration["dominant_share"]
    concentration_gap = concentration["concentration_gap"]
    signals = {}
    market_snapshot = {}
    market_environment = None

    if nonzero:
        print_dominant_narratives(top_theme, dominant_group)
        print_narrative_concentration(concentration)
        signals = compute_narrative_signals(top_theme, share, concentration_gap, theme_scores)
        print_narrative_signals(signals)

        market_snapshot = get_market_snapshot(NASDAQ_TICKERS)
        market_environment = classify_market_environment(
            theme_scores=theme_scores,
            group_scores=group_scores,
            signals=signals,
            market_snapshot=market_snapshot,
            concentration=concentration,
            dominant_group=dominant_group,
        )
        print_market_environment(market_environment)
        print_market_context(market_snapshot)
        print_top_theme_examples(nonzero, examples)
    else:
        print()
        print("No narratives detected today.")

    run = {
        "timestamp": stamp,
        "rss_urls": RSS_URLS,
        "headline_count": len(headlines),
        "matched_headlines": matched_headlines,
        "coverage_pct": round(coverage_pct, 1),
        "theme_counts": results,
        "theme_scores": theme_scores,
        "group_scores": group_scores,
        "sorted_nonzero": nonzero,
        "dominant_theme": top_theme,
        "dominant_score": top_count,
        "dominant_count": results.get(top_theme, 0) if top_theme else 0,
        "dominant_group": dominant_group,
        "dominant_group_score": dominant_group_score,
        "total_mentions": total_mentions,
        "dominant_share": round(float(share), 4),
        "concentration_gap": int(concentration_gap),
        "market_environment": market_environment,
        "examples": {k: v for k, v in examples.items() if k in dict(nonzero[:3])},
    }

    results_dir, results_file = save_run_json(run, stamp)
    print()
    print(f"Results saved to {results_file}")

    report_text = build_daily_report(
        readable_time=readable_time,
        headline_count=len(headlines),
        feed_count=len(RSS_URLS),
        coverage_pct=coverage_pct,
        signals=signals,
        nonzero_results=nonzero,
        concentration=concentration,
        group_scores=group_scores,
        dominant_group=dominant_group,
        market_environment=market_environment,
        market_snapshot=market_snapshot,
    )
    report_file = save_report(report_text, stamp)
    print(f"Report saved to {report_file}")

    print_momentum(results_dir)
    print_daily_count_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_daily_share_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)


if __name__ == "__main__":
    main()
