import json
from datetime import datetime
from pathlib import Path

from mne.rss_fetch import fetch_headlines_from_rss
from mne.theme_analysis import load_themes, analyze_themes
from mne.storage import load_json, get_last_two_result_files, get_recent_runs, get_recent_daily_runs
from mne.market_context import get_market_snapshot, classify_market_move

print("STARTING main.py")


rss_urls = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",             # WSJ Markets
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",     # CNBC Top News
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.ft.com/?format=rss",                            # Financial Times
    "https://www.bloomberg.com/feed/podcast/etf-report.xml",     # Bloomberg ETF Report
    "https://www.bbc.co.uk/news/business/rss.xml",               # BBC Business
    "https://www.npr.org/rss/rss.php?id=1001",                   # NPR Business
    "https://www.economist.com/finance-and-economics/rss.xml",   # Economist Finance
]

TREND_LOOKBACK = 5

def compute_narrative_signals(top_theme, share, concentration, results):
    signals = {}

    energy_count = results.get("energy", 0)
    ai_count = results.get("ai", 0)
    rates_count = results.get("rates", 0)
    inflation_count = results.get("inflation", 0)
    recession_count = results.get("recession", 0)

    # Energy Dominance
    if top_theme == "energy" and share >= 0.60 and concentration >= 15:
        signals["Energy Dominance"] = "HIGH"
    elif top_theme == "energy" and share >= 0.40:
        signals["Energy Dominance"] = "ELEVATED"
    else:
        signals["Energy Dominance"] = "LOW"

    # AI Narrative Strength
    if top_theme == "ai" and share >= 0.60:
        signals["AI Narrative Strength"] = "DOMINANT"
    elif ai_count >= 10:
        signals["AI Narrative Strength"] = "STRONG"
    elif ai_count >= 5:
        signals["AI Narrative Strength"] = "ACTIVE"
    else:
        signals["AI Narrative Strength"] = "WEAK"

    # Macro Stress
    stress_score = 0

    if energy_count >= 10:
        stress_score += 1
    if rates_count >= 4:
        stress_score += 1
    if inflation_count >= 3:
        stress_score += 1
    if recession_count >= 2:
        stress_score += 1

    if stress_score >= 3:
        signals["Macro Stress"] = "HIGH"
    elif stress_score == 2:
        signals["Macro Stress"] = "ELEVATED"
    elif stress_score == 1:
        signals["Macro Stress"] = "MODERATE"
    else:
        signals["Macro Stress"] = "LOW"

    return signals

def main():

    print("=== Daily Narrative Snapshot ===")
    print()

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    readable_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"Run Timestamp: {readable_time}")
    print()

    headlines = fetch_headlines_from_rss(rss_urls)

    # Save raw headlines
    headlines_dir = Path("data/headlines")
    headlines_dir.mkdir(parents=True, exist_ok=True)
    headlines_file = headlines_dir / f"{stamp}.txt"

    with open(headlines_file, "w", encoding="utf-8") as f:
        for headline in headlines:
            f.write(headline + "\n")

    print(f"Loaded {len(headlines)} headlines from RSS")
    print(f"Loaded {len(rss_urls)} RSS feeds")
    print(f"Headlines saved to {headlines_file}")
    print()

    # Theme analysis
    themes = load_themes("themes.txt")
    results, examples, matched_headlines = analyze_themes(
        headlines, themes, examples_per_theme=3
    )

    coverage_pct = (matched_headlines / len(headlines) * 100) if headlines else 0
    print(
        f"Coverage: {matched_headlines}/{len(headlines)} "
        f"({coverage_pct:.1f}%) headlines matched at least one theme"
    )
    
    print()

    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    nonzero = [(k, c) for k, c in sorted_results if c > 0]

    for theme, count in nonzero:
        print(f"{theme}: {count}")

    #Thresholds for narrative concentration (these are arbitrary and can be tuned based on historical data)
    TREND_LOOKBACK = 5
    TREND_EPSILON = 0.02
    NASDAQ_TICKERS = {
    "QQQ": "QQQ",
    "NVDA": "NVDA",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
}

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

        print()
        print("=== Narrative Concentration ===")
        print(f"Dominant Narrative: {top_theme} ({top_count} mentions)")
        print(f"Total Mentions: {total_mentions}")
        print(f"Dominant Narrative Share: {share * 100:.1f}%")
        print(f"Concentration Gap: {concentration}")
        signals = compute_narrative_signals(
        top_theme,
        share,
        concentration,
        results
        )

        print()
        print("=== Narrative Signals ===")

        for signal, value in signals.items():
            print(f"{signal}: {value}")

        print()
        print("=== Nasdaq Context ===")

        market_snapshot = get_market_snapshot(NASDAQ_TICKERS)

        for name, data in market_snapshot.items():
            if data is None:
                print(f"{name}: unavailable")
                continue

            move_label = classify_market_move(data["pct_change"])

            print(
                f"{name}: {data['latest_close']} "
                f"({data['pct_change']:+.2f}%) - {move_label}"
            )

        print()
        print("=== Examples for Top Themes ===")
        for theme, count in nonzero[:3]:
            print()
            print(f"[{theme}] ({count})")
            for i, h in enumerate(examples[theme], start=1):
                print(f"  {i}. {h}")
    else:
        print()
        print("No narratives detected today.")


    # Save results JSON
    results_dir = Path("data/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

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
        "examples": {k: v for k, v in examples.items() if k in dict(nonzero[:3])},
    }

    results_file = results_dir / f"{stamp}.json"
    report_file = reports_dir / f"{stamp}.txt"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)

    print()
    print(f"Results saved to {results_file}")

    report_lines = []

    report_lines.append("=== Daily Narrative Snapshot ===")
    report_lines.append("")
    report_lines.append(f"Run Timestamp: {readable_time}")
    report_lines.append("")

    report_lines.append(f"Loaded {len(headlines)} headlines")
    report_lines.append(f"Coverage: {coverage_pct:.1f}%")
    report_lines.append("")

    report_lines.append("=== Narrative Signals ===")

    for signal, value in signals.items():
        report_lines.append(f"{signal}: {value}")

    report_lines.append("")
    report_lines.append("=== Top Narratives ===")

    for theme, count in nonzero[:3]:
        report_lines.append(f"{theme}: {count}")

    report_lines.append("")
    report_lines.append("=== Narrative Concentration ===")
    report_lines.append(f"Dominant Narrative: {top_theme}")
    report_lines.append(f"Dominant Share: {share * 100:.1f}%")
    report_lines.append(f"Concentration Gap: {concentration}")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"Report saved to {report_file}")

    # Momentum (compare latest run vs previous run)
    latest, previous = get_last_two_result_files(results_dir)

    print()
    print("=== Momentum (vs previous run) ===")

    if previous is None:
        print("Not enough history yet (need 2 runs).")
    else:
        current = load_json(latest)
        prior = load_json(previous)

        cur_counts = current.get("theme_counts", {})
        prev_counts = prior.get("theme_counts", {})
        all_themes = sorted(set(cur_counts.keys()) | set(prev_counts.keys()))

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

        print(f"Dominant share: {cur_share * 100:.1f}% ({(cur_share - prev_share) * 100:+.1f}pp)")
        print(f"Concentration gap: {cur_gap} ({cur_gap - prev_gap:+d})")

        if not printed_any:
            print("(No per-theme count changes)")

    print()
    print("=== Narrative Trends (Daily) ===")

    recent_runs = get_recent_daily_runs(results_dir, TREND_LOOKBACK)

    if len(recent_runs) < 2:
        print("Not enough daily history for trend analysis.")
    else:
        theme_history = {}

        for run in recent_runs:
            counts = run.get("theme_counts", {})

            for theme, count in counts.items():
                theme_history.setdefault(theme, []).append(count)

        for theme, values in sorted(theme_history.items()):
            if len(values) < 2:
                continue

            # Arrow (last step)
            delta = values[-1] - values[-2]

            if delta > TREND_EPSILON:
                trend_arrow = "↑"
            elif delta < -TREND_EPSILON:
                trend_arrow = "↓"
            else:
                trend_arrow = "→"

            # Label (slightly smarter)
            label = "stable"

            label = "stable"

            if len(values) >= 3:
                prev = values[-2]
                prev2 = values[-3]
                current = values[-1]

                d1 = current - prev
                d2 = prev - prev2

                current_up = d1 > TREND_EPSILON
                current_down = d1 < -TREND_EPSILON
                prev_up = d2 > TREND_EPSILON
                prev_down = d2 < -TREND_EPSILON

                if current_up and prev_up:
                    label = "building"
                elif current_down and prev_down:
                    label = "fading"
                elif current_down and (prev_up or abs(d2) <= TREND_EPSILON):
                    label = "cooling"
                elif current_up and (prev_down or abs(d2) <= TREND_EPSILON):
                    label = "re-accelerating"
                elif abs(d1) <= TREND_EPSILON:
                    label = "flat"

            series = " → ".join(str(v) for v in values)

            print(f"{theme}: {series} {trend_arrow}  {label}")

    print()
    print("=== Narrative Trends (Daily - Share) ===")

    recent_runs = get_recent_daily_runs(results_dir, TREND_LOOKBACK)

    if len(recent_runs) < 2:
        print("Not enough daily history for share trend analysis.")
    else:
        theme_share_history = {}

        for run in recent_runs:
            counts = run.get("theme_counts", {})

            total = sum(c for c in counts.values() if c > 0)
            if total == 0:
                continue

            for theme, count in counts.items():
                share = count / total if total > 0 else 0.0
                theme_share_history.setdefault(theme, []).append(share)

        # sort by latest share descending
        sorted_themes = sorted(
            theme_share_history.items(),
            key=lambda x: x[1][-1],
            reverse=True
        )

        top_n = 3

        print()
        print("Top Narratives:")

        for theme, values in sorted_themes[:top_n]:
            if len(values) < 2:
                continue

            if values[-1] > values[-2]:
                trend_arrow = "↑"
            elif values[-1] < values[-2]:
                trend_arrow = "↓"
            else:
                trend_arrow = "→"

            label = "stable"

            if len(values) >= 3:
                prev = values[-2]
                prev2 = values[-3]
                current = values[-1]

                if current > prev and prev > prev2:
                    label = "building"
                elif current < prev and prev < prev2:
                    label = "fading"
                elif current < prev and prev >= prev2:
                    label = "cooling"
                elif current > prev and prev <= prev2:
                    label = "re-accelerating"
                elif current == prev:
                    label = "flat"

            series = " → ".join(f"{v*100:.1f}%" for v in values)
            print(f"{theme}: {series} {trend_arrow}  {label}")

        if len(sorted_themes) > top_n:
            print()
            print("Other Narratives:")

            for theme, values in sorted_themes[top_n:]:
                if len(values) < 2:
                    continue

                delta = values[-1] - values[-2]

                if delta > TREND_EPSILON:
                    trend_arrow = "↑"
                elif delta < -TREND_EPSILON:
                    trend_arrow = "↓"
                else:
                    trend_arrow = "→"

                series = " → ".join(f"{v*100:.1f}%" for v in values)
                print(f"{theme}: {series} {trend_arrow}")

        print()
        print("=============================")


if __name__ == "__main__":
    main()