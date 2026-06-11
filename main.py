from datetime import datetime

from analysis.narrative_dynamics import calculate_narrative_dynamics
from config import DATA_DIR, RESULTS_DIR
from mne.breadth import BREADTH_TICKERS, classify_breadth_confirmation
from mne.catalyst_environment import classify_catalyst_environment
from mne.environment import classify_market_environment
from mne.headline_deduplication import dedupe_headlines
from mne.market_context import get_market_snapshot
from mne.narrative_market_relationship import classify_narrative_market_relationship
from mne.narrative_signals import (
    compute_group_scores,
    compute_narrative_concentration,
    compute_narrative_signals,
    get_dominant_group,
)
from mne.reporting import (
    build_daily_report,
    print_breadth_confirmation,
    print_catalyst_environment,
    print_dominant_narratives,
    print_group_scores,
    print_market_context,
    print_market_environment,
    print_narrative_market_relationship,
    print_narrative_concentration,
    print_narrative_dynamics,
    print_narrative_signals,
    print_theme_counts,
    print_theme_match_audit,
    print_top_theme_examples,
)
from mne.rss_fetch import fetch_headlines_from_rss
from mne.storage import get_recent_runs, save_headlines, save_report, save_run_json
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
    print(f"Active Data Directory: {DATA_DIR}")
    print()

    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M")
    readable_time = now.strftime("%Y-%m-%d %H:%M")

    print(f"Run Timestamp: {readable_time}")
    print()

    raw_headlines = fetch_headlines_from_rss(RSS_URLS)
    deduplication = dedupe_headlines(raw_headlines)
    headlines = deduplication["deduped_headlines"]
    raw_headlines_file = save_headlines(raw_headlines, stamp, label="raw")
    deduped_headlines_file = save_headlines(headlines, stamp, label="deduped")

    print(f"Loaded {deduplication['raw_headline_count']} raw headlines from RSS")
    print(f"Deduped to {deduplication['deduped_headline_count']} unique headlines")
    print(f"Removed {deduplication['duplicate_count']} duplicates")
    print(f"Loaded {len(RSS_URLS)} RSS feeds")
    print(f"Raw headlines saved to {raw_headlines_file}")
    print(f"Deduped headlines saved to {deduped_headlines_file}")
    print()

    themes, taxonomy_version = load_themes("themes.txt", include_version=True)
    results, examples, matched_headlines, theme_scores, theme_match_audit = analyze_themes(
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
    sorted_group_scores = sorted(group_scores.items(), key=lambda item: item[1], reverse=True)

    concentration = compute_narrative_concentration(nonzero)
    top_theme = concentration["dominant_theme"]
    top_count = concentration["dominant_count"]
    total_mentions = concentration["total_mentions"]
    share = concentration["dominant_share"]
    concentration_gap = concentration["concentration_gap"]
    signals = {}
    market_snapshot = {}
    market_environment = None
    narrative_market_relationship = None
    breadth_confirmation = None
    catalyst_environment = classify_catalyst_environment()

    if nonzero:
        print_dominant_narratives(top_theme, dominant_group)
        print_narrative_concentration(concentration)
        signals = compute_narrative_signals(top_theme, share, concentration_gap, theme_scores)
        print_narrative_signals(signals)

        market_snapshot = get_market_snapshot({**NASDAQ_TICKERS, **BREADTH_TICKERS})
        market_environment = classify_market_environment(
            theme_scores=theme_scores,
            group_scores=group_scores,
            signals=signals,
            market_snapshot=market_snapshot,
            concentration=concentration,
            dominant_group=dominant_group,
        )
    else:
        print()
        print("No narratives detected today.")

    run = {
        "timestamp": stamp,
        "taxonomy_version": taxonomy_version,
        "rss_urls": RSS_URLS,
        "raw_headline_count": deduplication["raw_headline_count"],
        "deduped_headline_count": deduplication["deduped_headline_count"],
        "duplicate_count": deduplication["duplicate_count"],
        "headline_count": len(headlines),
        "matched_headlines": matched_headlines,
        "coverage_pct": round(coverage_pct, 1),
        "theme_counts": results,
        "theme_scores": theme_scores,
        "theme_match_audit": theme_match_audit,
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
        "breadth_confirmation": breadth_confirmation,
        "catalyst_environment": catalyst_environment,
        "examples": {k: v for k, v in examples.items() if k in dict(nonzero[:3])},
    }

    narrative_dynamics = calculate_narrative_dynamics(
        results_dir=RESULTS_DIR,
        current_run=run,
        top_themes=nonzero,
        top_groups=sorted_group_scores,
        lookback=5,
    )
    run["narrative_dynamics"] = narrative_dynamics

    if nonzero:
        prior_runs = get_recent_runs(RESULTS_DIR, 1)
        prior_dominant_group = prior_runs[-1].get("dominant_group") if prior_runs else None
        narrative_market_relationship = classify_narrative_market_relationship(
            current_run=run,
            narrative_dynamics=narrative_dynamics,
            market_snapshot=market_snapshot,
            prior_dominant_group=prior_dominant_group,
        )
        run["narrative_market_relationship"] = narrative_market_relationship
        breadth_confirmation = classify_breadth_confirmation(market_snapshot)
        run["breadth_confirmation"] = breadth_confirmation

        print_market_environment(market_environment)
        print_narrative_market_relationship(narrative_market_relationship)
        print_breadth_confirmation(breadth_confirmation)
        print_catalyst_environment(catalyst_environment)
        print_market_context(
            {name: market_snapshot.get(name) for name in NASDAQ_TICKERS.keys()}
        )
        print_top_theme_examples(nonzero, examples)
        print_theme_match_audit(nonzero, theme_match_audit)
    else:
        neutral_relationship = {
            "state": "Neutral / Mixed",
            "confidence": "Low",
            "reason": (
                "No narratives were detected, so no narrative and market "
                "relationship could be classified."
            ),
        }
        run["narrative_market_relationship"] = neutral_relationship
        narrative_market_relationship = neutral_relationship
        breadth_confirmation = {
            "state": "Neutral Breadth",
            "confidence": "Low",
            "reason": "No narratives were detected, so breadth was not evaluated.",
        }
        run["breadth_confirmation"] = breadth_confirmation
        print_catalyst_environment(catalyst_environment)

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
        narrative_market_relationship=narrative_market_relationship,
        breadth_confirmation=breadth_confirmation,
        catalyst_environment=catalyst_environment,
        narrative_dynamics=narrative_dynamics,
        top_themes=nonzero,
        top_groups=sorted_group_scores,
        market_snapshot={name: market_snapshot.get(name) for name in NASDAQ_TICKERS.keys()},
        raw_headline_count=deduplication["raw_headline_count"],
        deduped_headline_count=deduplication["deduped_headline_count"],
        duplicate_count=deduplication["duplicate_count"],
        theme_match_audit=theme_match_audit,
    )
    report_file = save_report(report_text, stamp)
    print(f"Report saved to {report_file}")

    print_momentum(results_dir)
    print_daily_count_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_daily_share_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_narrative_dynamics(narrative_dynamics, nonzero, sorted_group_scores)


if __name__ == "__main__":
    main()
