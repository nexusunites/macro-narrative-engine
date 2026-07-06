import argparse
from datetime import datetime, timezone

from analysis.leadership_rotation import compute_rotation
from analysis.narrative_dynamics import calculate_narrative_dynamics
from config import DATA_DIR, OPERATING_MODE, RESULTS_DIR
from mne.breadth import BREADTH_TICKERS, classify_breadth_confirmation
from mne.catalyst_environment import classify_catalyst_environment
from mne.change_summary import build_change_summary
from mne.environment import classify_market_environment
from mne.event_lifecycle import evaluate_event_lifecycle_run
from mne.evidence import (
    evidence_to_headlines,
    normalize_rss_entries_to_evidence,
    source_intelligence_counts,
)
from mne.headline_deduplication import dedupe_headlines
from mne.market_context import get_market_snapshot
from mne.narrative_brief import generate_narrative_brief
from mne.narrative_leadership import build_narrative_leadership
from mne.narrative_market_map import get_market_expression
from mne.narrative_pulse import calculate_narrative_pulse
from mne.narrative_market_relationship import classify_narrative_market_relationship
from mne.narrative_signals import (
    compute_group_scores,
    compute_narrative_concentration,
    compute_narrative_signals,
    get_dominant_group,
)
from mne.operating_modes import generate_mode_context, normalize_operating_mode
from mne.positioning_environment import classify_positioning_environment
from mne.regime_alignment import calculate_regime_alignment
from mne.reporting import (
    build_daily_report,
    print_breadth_confirmation,
    print_catalyst_environment,
    print_dominant_narratives,
    print_group_scores,
    print_market_context,
    print_market_environment,
    print_market_expression,
    print_narrative_market_relationship,
    print_narrative_concentration,
    print_narrative_dynamics,
    print_narrative_signals,
    print_operating_mode,
    print_positioning_environment,
    print_regime_alignment,
    print_mode_context,
    print_theme_counts,
    print_theme_match_audit,
    print_top_theme_examples,
)
from mne.rss_fetch import fetch_headlines_from_rss
from mne.storage import (
    build_daily_snapshot_preview,
    get_recent_runs,
    load_daily_snapshots,
    save_headlines,
    save_report,
    save_run_json,
)
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
ZERO_HEADLINE_WARNING = (
    "RSS fetch failed or returned zero headlines.\n"
    "Narrative run will not be generated."
)


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Run the Macro Narrative Engine.")
    parser.add_argument(
        "--mode",
        help="Operating mode for this run. Overrides config.py without rewriting it.",
    )
    return parser.parse_args(args)


def headline_collection_failure_reason(deduplication):
    if deduplication["raw_headline_count"] == 0:
        return "0 raw headlines"
    if deduplication["deduped_headline_count"] == 0:
        return "0 deduped headlines"
    return None


def should_abort_for_failed_headline_collection(deduplication):
    return headline_collection_failure_reason(deduplication) is not None


def main(args=None):
    parsed_args = parse_args(args)
    configured_mode = parsed_args.mode or OPERATING_MODE
    operating_mode, mode_warning = normalize_operating_mode(configured_mode)

    print("=== Daily Narrative Snapshot ===")
    print()
    print(f"Active Data Directory: {DATA_DIR}")
    print()

    now = datetime.now()
    now_utc = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    readable_time = now.strftime("%Y-%m-%d %H:%M")

    print(f"Run Timestamp: {readable_time}")
    print()
    print_operating_mode(operating_mode)
    if mode_warning:
        print(mode_warning)
    print()

    rss_entries = fetch_headlines_from_rss(RSS_URLS, as_entries=True)
    evidence_objects = normalize_rss_entries_to_evidence(
        rss_entries,
        run_timestamp=now_utc.isoformat(),
    )
    source_intelligence = source_intelligence_counts(evidence_objects)
    raw_headlines = evidence_to_headlines(evidence_objects)
    deduplication = dedupe_headlines(raw_headlines)
    headlines = deduplication["deduped_headlines"]

    print(f"Loaded {deduplication['raw_headline_count']} raw headlines from RSS")
    print(f"Deduped to {deduplication['deduped_headline_count']} unique headlines")
    print(f"Removed {deduplication['duplicate_count']} duplicates")
    print(f"Loaded {len(RSS_URLS)} RSS feeds")

    if should_abort_for_failed_headline_collection(deduplication):
        print()
        print(ZERO_HEADLINE_WARNING)
        failure_reason = headline_collection_failure_reason(deduplication)
        print(f"Failure reason: {failure_reason}")
        failed_run = {
            "timestamp": stamp,
            "rss_urls": RSS_URLS,
            "raw_headline_count": deduplication["raw_headline_count"],
            "deduped_headline_count": deduplication["deduped_headline_count"],
            "duplicate_count": deduplication["duplicate_count"],
            "source_intelligence": source_intelligence,
            "headline_count": len(headlines),
            "narrative_run_status": "skipped_failed_headline_collection",
            "headline_collection_failure_reason": failure_reason,
        }
        _results_dir, results_file = save_run_json(failed_run, stamp)
        print(f"Source diagnostics saved to {results_file}")
        return

    raw_headlines_file = save_headlines(raw_headlines, stamp, label="raw")
    deduped_headlines_file = save_headlines(headlines, stamp, label="deduped")

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
    market_expression = get_market_expression(top_theme)
    signals = {}
    market_snapshot = {}
    market_environment = None
    narrative_market_relationship = None
    breadth_confirmation = None
    regime_alignment = None
    mode_context = None
    catalyst_environment = classify_catalyst_environment()
    event_lifecycle = evaluate_event_lifecycle_run(now_utc=now_utc)
    positioning_environment = classify_positioning_environment(catalyst_environment)

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
        "source_intelligence": source_intelligence,
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
        "market_expression": market_expression,
        "market_snapshot": market_snapshot,
        "market_environment": market_environment,
        "breadth_confirmation": breadth_confirmation,
        "catalyst_environment": catalyst_environment,
        "event_lifecycle": event_lifecycle,
        "positioning_environment": positioning_environment,
        "regime_alignment": regime_alignment,
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
    narrative_pulse = calculate_narrative_pulse(run, narrative_dynamics)
    run["narrative_pulse"] = narrative_pulse
    run["narrative_leadership"] = build_narrative_leadership(
        group_scores,
        narrative_pulse,
        narrative_dynamics,
    )

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
        regime_alignment = calculate_regime_alignment(
            narrative_signals=signals,
            market_environment=market_environment,
            narrative_market_relationship=narrative_market_relationship,
            breadth_confirmation=breadth_confirmation,
            catalyst_environment=catalyst_environment,
            positioning_environment=positioning_environment,
            market_snapshot=market_snapshot,
            dominant_group=dominant_group,
            dominant_theme=top_theme,
        )
        run["regime_alignment"] = regime_alignment
        mode_context = generate_mode_context(
            mode=operating_mode,
            dominant_theme=top_theme,
            dominant_group=dominant_group,
            narrative_signals=signals,
            market_environment=market_environment,
            narrative_market_relationship=narrative_market_relationship,
            breadth_confirmation=breadth_confirmation,
            catalyst_environment=catalyst_environment,
            positioning_environment=positioning_environment,
            regime_alignment=regime_alignment,
            market_snapshot=market_snapshot,
        )
        run["operating_mode"] = operating_mode
        run["mode_context"] = mode_context

        print_market_environment(market_environment)
        print_market_expression(market_expression)
        print_narrative_market_relationship(narrative_market_relationship)
        print_breadth_confirmation(breadth_confirmation)
        print_catalyst_environment(catalyst_environment)
        print_positioning_environment(positioning_environment)
        print_regime_alignment(regime_alignment)
        print_mode_context(mode_context)
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
        print_positioning_environment(positioning_environment)
        regime_alignment = calculate_regime_alignment(
            narrative_signals=signals,
            market_environment=market_environment,
            narrative_market_relationship=narrative_market_relationship,
            breadth_confirmation=breadth_confirmation,
            catalyst_environment=catalyst_environment,
            positioning_environment=positioning_environment,
            market_snapshot=market_snapshot,
            dominant_group=dominant_group,
            dominant_theme=top_theme,
        )
        run["regime_alignment"] = regime_alignment
        mode_context = generate_mode_context(
            mode=operating_mode,
            dominant_theme=top_theme,
            dominant_group=dominant_group,
            narrative_signals=signals,
            market_environment=market_environment,
            narrative_market_relationship=narrative_market_relationship,
            breadth_confirmation=breadth_confirmation,
            catalyst_environment=catalyst_environment,
            positioning_environment=positioning_environment,
            regime_alignment=regime_alignment,
            market_snapshot=market_snapshot,
        )
        run["operating_mode"] = operating_mode
        run["mode_context"] = mode_context
        print_market_expression(market_expression)
        print_regime_alignment(regime_alignment)
        print_mode_context(mode_context)

    prior_runs = get_recent_runs(RESULTS_DIR, 1)
    prior_run = prior_runs[-1] if prior_runs else None
    run["change_summary"] = build_change_summary(run, prior_run)

    rotation_snapshots = load_daily_snapshots(limit=6)
    current_snapshot = build_daily_snapshot_preview(
        run,
        snapshot_date=now.date().isoformat(),
    )
    rotation_snapshots = [
        snapshot
        for snapshot in rotation_snapshots
        if snapshot.get("date") != current_snapshot.get("date")
    ]
    run["leadership_rotation"] = compute_rotation(rotation_snapshots + [current_snapshot])

    try:
        run["narrative_brief"] = generate_narrative_brief(
            run,
            run_timestamp_utc=now_utc.isoformat(),
        )
    except Exception as error:
        run["narrative_brief"] = None
        run["narrative_brief_generation_error"] = {
            "error_type": type(error).__name__,
            "message": str(error),
        }

    results_dir, results_file = save_run_json(run, stamp)
    from mne.storage import write_daily_snapshot

    write_daily_snapshot(run)
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
        positioning_environment=positioning_environment,
        regime_alignment=regime_alignment,
        narrative_dynamics=narrative_dynamics,
        top_themes=nonzero,
        top_groups=sorted_group_scores,
        market_snapshot={name: market_snapshot.get(name) for name in NASDAQ_TICKERS.keys()},
        raw_headline_count=deduplication["raw_headline_count"],
        deduped_headline_count=deduplication["deduped_headline_count"],
        duplicate_count=deduplication["duplicate_count"],
        theme_match_audit=theme_match_audit,
        operating_mode=operating_mode,
        mode_context=mode_context,
        market_expression=market_expression,

    )
    report_file = save_report(report_text, stamp)
    print(f"Report saved to {report_file}")

    print_momentum(results_dir)
    print_daily_count_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_daily_share_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_narrative_dynamics(narrative_dynamics, nonzero, sorted_group_scores)


if __name__ == "__main__":
    main()
