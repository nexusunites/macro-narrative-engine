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


def print_narrative_market_relationship(relationship):
    print()
    print("=== Narrative / Market Relationship ===")
    print(f"State: {relationship['state']}")
    print(f"Confidence: {relationship['confidence']}")
    print()
    print("Reason:")
    print(relationship["reason"])


def print_breadth_confirmation(breadth_confirmation):
    print()
    print("=== Breadth Confirmation ===")
    print(f"State: {breadth_confirmation['state']}")
    print(f"Confidence: {breadth_confirmation['confidence']}")
    print()
    print("Reason:")
    print(breadth_confirmation["reason"])


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


def print_narrative_dynamics(dynamics, top_themes=None, top_groups=None, limit=3):
    print()
    print("=== Narrative Dynamics ===")

    top_themes = top_themes or []
    top_groups = top_groups or []

    print()
    print("Top Theme Dynamics:")
    for theme, _ in top_themes[:limit]:
        values = dynamics.get("themes", {}).get(theme)
        if not values:
            continue

        print(f"{theme}:")
        print(f"  Current Score: {values['current_score']}")
        print(f"  3-Run Avg: {values['rolling_avg_3']}")
        print(f"  5-Run Avg: {values['rolling_avg_5']}")
        print(f"  Acceleration: {values['acceleration']}")
        print(f"  Decay: {values['decay']}")

    print()
    print("Top Group Dynamics:")
    for group, _ in top_groups[:limit]:
        values = dynamics.get("groups", {}).get(group)
        if not values:
            continue

        print(f"{group}:")
        print(f"  Current Score: {values['current_score']}")
        print(f"  3-Run Avg: {values['rolling_avg_3']}")
        print(f"  5-Run Avg: {values['rolling_avg_5']}")
        print(f"  Acceleration: {values['acceleration']}")
        print(f"  Decay: {values['decay']}")

    persistence = dynamics.get("persistence", {})
    print()
    print("Dominance Persistence:")
    print(
        f"  Dominant Theme: {persistence.get('dominant_theme')} "
        f"for {persistence.get('dominant_theme_runs', 0)} consecutive runs"
    )
    print(
        f"  Dominant Group: {persistence.get('dominant_group')} "
        f"for {persistence.get('dominant_group_runs', 0)} consecutive runs"
    )

    crowding = dynamics.get("narrative_crowding", {})
    print()
    print("Narrative Crowding Risk:")
    print(f"  Risk: {crowding.get('risk')}")
    print(f"  Reason: {crowding.get('reason')}")
    print(f"  Note: {crowding.get('note')}")


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
    narrative_market_relationship=None,
    breadth_confirmation=None,
    narrative_dynamics=None,
    top_themes=None,
    top_groups=None,
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

    if narrative_market_relationship:
        report_lines.append("")
        report_lines.append("=== Narrative / Market Relationship ===")
        report_lines.append(f"State: {narrative_market_relationship['state']}")
        report_lines.append(f"Confidence: {narrative_market_relationship['confidence']}")
        report_lines.append("")
        report_lines.append("Reason:")
        report_lines.append(narrative_market_relationship["reason"])

    if breadth_confirmation:
        report_lines.append("")
        report_lines.append("=== Breadth Confirmation ===")
        report_lines.append(f"State: {breadth_confirmation['state']}")
        report_lines.append(f"Confidence: {breadth_confirmation['confidence']}")
        report_lines.append("")
        report_lines.append("Reason:")
        report_lines.append(breadth_confirmation["reason"])

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

    if narrative_dynamics:
        top_themes = top_themes or []
        top_groups = top_groups or []

        report_lines.append("")
        report_lines.append("=== Narrative Dynamics ===")
        report_lines.append("")
        report_lines.append("Top Theme Dynamics:")
        for theme, _ in top_themes[:3]:
            values = narrative_dynamics.get("themes", {}).get(theme)
            if not values:
                continue
            report_lines.append(f"{theme}:")
            report_lines.append(f"  Current Score: {values['current_score']}")
            report_lines.append(f"  3-Run Avg: {values['rolling_avg_3']}")
            report_lines.append(f"  5-Run Avg: {values['rolling_avg_5']}")
            report_lines.append(f"  Acceleration: {values['acceleration']}")
            report_lines.append(f"  Decay: {values['decay']}")

        report_lines.append("")
        report_lines.append("Top Group Dynamics:")
        for group, _ in top_groups[:3]:
            values = narrative_dynamics.get("groups", {}).get(group)
            if not values:
                continue
            report_lines.append(f"{group}:")
            report_lines.append(f"  Current Score: {values['current_score']}")
            report_lines.append(f"  3-Run Avg: {values['rolling_avg_3']}")
            report_lines.append(f"  5-Run Avg: {values['rolling_avg_5']}")
            report_lines.append(f"  Acceleration: {values['acceleration']}")
            report_lines.append(f"  Decay: {values['decay']}")

        persistence = narrative_dynamics.get("persistence", {})
        report_lines.append("")
        report_lines.append("Dominance Persistence:")
        report_lines.append(
            f"  Dominant Theme: {persistence.get('dominant_theme')} "
            f"for {persistence.get('dominant_theme_runs', 0)} consecutive runs"
        )
        report_lines.append(
            f"  Dominant Group: {persistence.get('dominant_group')} "
            f"for {persistence.get('dominant_group_runs', 0)} consecutive runs"
        )

        crowding = narrative_dynamics.get("narrative_crowding", {})
        report_lines.append("")
        report_lines.append("Narrative Crowding Risk:")
        report_lines.append(f"  Risk: {crowding.get('risk')}")
        report_lines.append(f"  Reason: {crowding.get('reason')}")
        report_lines.append(f"  Note: {crowding.get('note')}")

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
