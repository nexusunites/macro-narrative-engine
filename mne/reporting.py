from mne.market_context import classify_market_move


def print_theme_counts(nonzero_results):
    print("=== Narrative Theme Scores ===")
    for theme, count in nonzero_results:
        print(f"{theme}: {count}")


def print_group_scores(group_scores):
    print()
    print("=== Narrative Group Scores ===")

    for group, score in sorted(group_scores.items(), key=lambda item: item[1], reverse=True):
        print(f"{group}: {score}")


def print_dominant_narratives(dominant_theme, dominant_group):
    print()
    print(f"Dominant Theme: {dominant_theme}")
    print(f"Dominant Narrative Group: {dominant_group}")


def print_narrative_concentration(concentration):
    print()
    print("=== Narrative Concentration ===")
    print(
        f"Dominant Narrative: {concentration['dominant_theme']} "
        f"({concentration['dominant_count']} score)"
    )
    print(f"Total Score: {concentration['total_mentions']}")
    print(f"Dominant Narrative Share: {concentration['dominant_share'] * 100:.1f}%")
    print(f"Concentration Gap: {concentration['concentration_gap']}")


def print_narrative_signals(signals):
    print()
    print("=== Narrative Signals ===")

    for signal, value in signals.items():
        print(f"{signal}: {value}")


def print_market_environment(environment):
    print()
    print("=== Market Environment ===")
    print(f"State: {environment['state']}")
    print(f"Confidence: {environment['confidence']}")
    print()
    print("Reason:")
    print(environment["reason"])


def print_market_context(market_snapshot):
    print()
    print("=== Nasdaq Context ===")

    for name, data in market_snapshot.items():
        if data is None:
            print(f"{name}: unavailable")
            continue

        move_label = classify_market_move(data["pct_change"])

        print(
            f"{name}: {data['latest_close']} "
            f"({data['pct_change']:+.2f}%) - {move_label}"
        )


def print_top_theme_examples(nonzero_results, examples, limit=3):
    print()
    print("=== Examples for Top Themes ===")

    for theme, count in nonzero_results[:limit]:
        print()
        print(f"[{theme}] ({count} score)")
        for i, headline in enumerate(examples[theme], start=1):
            print(f"  {i}. {headline}")


def build_daily_report(
    readable_time,
    headline_count,
    feed_count,
    coverage_pct,
    signals,
    nonzero_results,
    concentration,
    group_scores=None,
    dominant_group=None,
    market_environment=None,
    market_snapshot=None,
):
    report_lines = []

    report_lines.append("=== Daily Narrative Snapshot ===")
    report_lines.append("")
    report_lines.append(f"Run Timestamp: {readable_time}")
    report_lines.append("")
    report_lines.append(f"Loaded {headline_count} headlines")
    report_lines.append(f"Loaded {feed_count} RSS feeds")
    report_lines.append(f"Coverage: {coverage_pct:.1f}%")
    report_lines.append("")

    report_lines.append("=== Narrative Signals ===")
    for signal, value in signals.items():
        report_lines.append(f"{signal}: {value}")

    if market_environment:
        report_lines.append("")
        report_lines.append("=== Market Environment ===")
        report_lines.append(f"State: {market_environment['state']}")
        report_lines.append(f"Confidence: {market_environment['confidence']}")
        report_lines.append("")
        report_lines.append("Reason:")
        report_lines.append(market_environment["reason"])

    report_lines.append("")
    report_lines.append("=== Narrative Theme Scores ===")
    for theme, count in nonzero_results[:3]:
        report_lines.append(f"{theme}: {count}")

    if group_scores:
        report_lines.append("")
        report_lines.append("=== Narrative Group Scores ===")
        for group, score in sorted(group_scores.items(), key=lambda item: item[1], reverse=True):
            report_lines.append(f"{group}: {score}")

    report_lines.append("")
    report_lines.append("=== Narrative Concentration ===")
    report_lines.append(f"Dominant Theme: {concentration['dominant_theme']}")
    report_lines.append(f"Dominant Narrative Group: {dominant_group}")
    report_lines.append(f"Dominant Share: {concentration['dominant_share'] * 100:.1f}%")
    report_lines.append(f"Concentration Gap: {concentration['concentration_gap']}")

    if market_snapshot:
        report_lines.append("")
        report_lines.append("=== Nasdaq Context ===")
        for name, data in market_snapshot.items():
            if data is None:
                report_lines.append(f"{name}: unavailable")
                continue

            move_label = classify_market_move(data["pct_change"])
            report_lines.append(
                f"{name}: {data['latest_close']} "
                f"({data['pct_change']:+.2f}%) - {move_label}"
            )

    return "\n".join(report_lines)
