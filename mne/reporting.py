from mne.market_context import classify_market_move
from mne.operating_modes import format_operating_mode


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


def append_market_expression(report_lines, market_expression):
    if not isinstance(market_expression, dict):
        return

    report_lines.append("=== Market Expression Map ===")
    report_lines.append("")
    report_lines.append(f"Theme: {market_expression.get('display_theme') or 'Unavailable'}")
    report_lines.append("")
    report_lines.append("Primary Expressions:")
    report_lines.extend(market_expression.get("primary") or ["None"])
    report_lines.append("")
    report_lines.append("Secondary Expressions:")
    report_lines.extend(market_expression.get("secondary") or ["None"])
    report_lines.append("")
    report_lines.append("Potential Offsets:")
    report_lines.extend(market_expression.get("offsets") or ["None"])
    report_lines.append("")
    report_lines.append("Description:")
    report_lines.append(market_expression.get("description") or "Unavailable")
    report_lines.append("")
    report_lines.append("Context Only:")
    report_lines.append(
        market_expression.get("note")
        or "These assets are narrative-expression proxies and not trade recommendations."
    )


def print_market_expression(market_expression):
    print()
    lines = []
    append_market_expression(lines, market_expression)
    print("\n".join(lines))


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


def format_catalyst_event(event):
    source = event.get("source") or "manual"
    source_labels = {
        "auto_company_earnings": "auto",
        "auto_macro_calendar": "macro",
    }
    source_label = source_labels.get(source, "manual")
    days = event.get("days_until")
    if days is None:
        return f"{event.get('name')} [{source_label}]"
    if days == 0:
        return f"{event.get('name')} (today) [{source_label}]"
    if days == 1:
        return f"{event.get('name')} (tomorrow) [{source_label}]"
    return f"{event.get('name')} ({days} days) [{source_label}]"


def print_catalyst_sources(catalyst_environment):
    sources = catalyst_environment.get("catalyst_sources")
    if not sources:
        source = catalyst_environment.get("catalyst_source")
        if source:
            print(f"Catalyst Source: {source}")
        return

    print("Catalyst Sources:")
    print(f"  Manual: {sources.get('manual')}")
    print(f"  Macro: {sources.get('macro')}")
    print(f"  Company Earnings: {sources.get('company_earnings')}")


def append_catalyst_sources(report_lines, catalyst_environment):
    sources = catalyst_environment.get("catalyst_sources")
    if not sources:
        source = catalyst_environment.get("catalyst_source")
        if source:
            report_lines.append(f"Catalyst Source: {source}")
        return

    report_lines.append("Catalyst Sources:")
    report_lines.append(f"  Manual: {sources.get('manual')}")
    report_lines.append(f"  Macro: {sources.get('macro')}")
    report_lines.append(f"  Company Earnings: {sources.get('company_earnings')}")


def print_macro_calendar_status(catalyst_environment):
    macro_calendar_status = catalyst_environment.get(
        "macro_calendar_status", "unknown"
    )
    macro_calendar_event_count = catalyst_environment.get(
        "macro_calendar_event_count", 0
    )
    macro_calendar_message = catalyst_environment.get("macro_calendar_message", "")
    macro_calendar_warning = catalyst_environment.get("macro_calendar_warning", True)
    refresh_status = catalyst_environment.get("macro_calendar_refresh_status")
    coverage_end = catalyst_environment.get("macro_calendar_coverage_end")
    failed_sources = catalyst_environment.get("macro_calendar_failed_sources") or []

    print("Macro Calendar Status:")
    print(f"  Status: {macro_calendar_status}")
    print(f"  Events Loaded: {macro_calendar_event_count}")
    if refresh_status:
        print(f"  Refresh Status: {refresh_status}")
    if coverage_end:
        print(f"  Coverage End: {coverage_end}")
    if failed_sources:
        print(f"  Failed Sources: {', '.join(failed_sources)}")
    print(
        f"  Warning: {macro_calendar_message}"
        if macro_calendar_warning
        else f"  {macro_calendar_message}"
    )


def append_macro_calendar_status(report_lines, catalyst_environment):
    macro_calendar_status = catalyst_environment.get(
        "macro_calendar_status", "unknown"
    )
    macro_calendar_event_count = catalyst_environment.get(
        "macro_calendar_event_count", 0
    )
    macro_calendar_message = catalyst_environment.get("macro_calendar_message", "")
    macro_calendar_warning = catalyst_environment.get("macro_calendar_warning", True)
    refresh_status = catalyst_environment.get("macro_calendar_refresh_status")
    coverage_end = catalyst_environment.get("macro_calendar_coverage_end")
    failed_sources = catalyst_environment.get("macro_calendar_failed_sources") or []

    report_lines.append("Macro Calendar Status:")
    report_lines.append(f"  Status: {macro_calendar_status}")
    report_lines.append(f"  Events Loaded: {macro_calendar_event_count}")
    if refresh_status:
        report_lines.append(f"  Refresh Status: {refresh_status}")
    if coverage_end:
        report_lines.append(f"  Coverage End: {coverage_end}")
    if failed_sources:
        report_lines.append(f"  Failed Sources: {', '.join(failed_sources)}")
    report_lines.append(
        f"  Warning: {macro_calendar_message}"
        if macro_calendar_warning
        else f"  {macro_calendar_message}"
    )


def print_catalyst_environment(catalyst_environment):
    print()
    print("=== Catalyst Environment ===")
    print(f"State: {catalyst_environment['state']}")
    print(f"Confidence: {catalyst_environment['confidence']}")
    print_catalyst_sources(catalyst_environment)

    if not catalyst_environment.get("calendar_found", True):
        print()
        print("Reason:")
        print(catalyst_environment["reason"])
        print()
        print_macro_calendar_status(catalyst_environment)
        return

    print()
    print(
        f"Catalyst Density: {catalyst_environment['density_score']} "
        f"({catalyst_environment['density_state']})"
    )

    print()
    print("Red Folder Events:")
    if catalyst_environment.get("red_events"):
        for event in catalyst_environment["red_events"]:
            print(f"  {format_catalyst_event(event)}")
    else:
        print("  None")

    print()
    print("Orange Folder Events:")
    if catalyst_environment.get("orange_events"):
        for event in catalyst_environment["orange_events"]:
            print(f"  {format_catalyst_event(event)}")
    else:
        print("  None")

    print()
    print("Reason:")
    print(catalyst_environment["reason"])
    print()
    print_macro_calendar_status(catalyst_environment)


def print_positioning_environment(positioning_environment):
    print()
    print("=== Positioning Environment ===")
    print(f"State: {positioning_environment['state']}")
    print(f"Confidence: {positioning_environment['confidence']}")
    print()
    print("Reason:")
    print(positioning_environment["reason"])


def print_regime_alignment(regime_alignment):
    print()
    print("=== Regime Alignment Score ===")
    print(f"Score: {regime_alignment['score']}/100")
    print(f"State: {regime_alignment['state']}")
    print(f"Confidence: {regime_alignment['confidence']}")
    print()
    print("Reason:")
    print(regime_alignment["reason"])


def print_operating_mode(mode):
    print("=== Operating Mode ===")
    print(f"Mode: {format_operating_mode(mode)}")


def print_mode_context(mode_context):
    print()
    print("=== Mode Context ===")
    print(f"State: {mode_context['state']}")
    print(f"Confidence: {mode_context['confidence']}")
    print()
    print("Read:")
    print(mode_context["read"])


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


def format_theme_match_audit(nonzero_results, theme_match_audit, limit=3, terms_per_theme=5):
    lines = ["=== Theme Match Audit ==="]

    for theme, _ in nonzero_results[:limit]:
        matched_terms = theme_match_audit.get(theme, {}).get("matched_terms", {})
        if not matched_terms:
            continue

        sorted_terms = sorted(
            matched_terms.items(),
            key=lambda item: (-item[1].get("count", 0), item[0]),
        )

        lines.append("")
        lines.append(f"{theme}:")
        lines.append("  Top matched terms:")

        for term, data in sorted_terms[:terms_per_theme]:
            lines.append(f"  - {term}: {data.get('count', 0)}")
            for headline in data.get("examples", [])[:3]:
                lines.append(f"    example: {headline}")

    return "\n".join(lines)


def print_theme_match_audit(nonzero_results, theme_match_audit, limit=3, terms_per_theme=5):
    if not nonzero_results or not theme_match_audit:
        return

    print()
    print(format_theme_match_audit(nonzero_results, theme_match_audit, limit, terms_per_theme))


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
    catalyst_environment=None,
    positioning_environment=None,
    regime_alignment=None,
    narrative_dynamics=None,
    top_themes=None,
    top_groups=None,
    market_snapshot=None,
    raw_headline_count=None,
    deduped_headline_count=None,
    duplicate_count=None,
    theme_match_audit=None,
    operating_mode=None,
    mode_context=None,
    market_expression=None,
):
    report_lines = []

    report_lines.append("=== Daily Narrative Snapshot ===")
    report_lines.append("")
    report_lines.append(f"Run Timestamp: {readable_time}")
    report_lines.append("")
    if operating_mode:
        report_lines.append("=== Operating Mode ===")
        report_lines.append(f"Mode: {format_operating_mode(operating_mode)}")
        report_lines.append("")
    if raw_headline_count is not None and deduped_headline_count is not None:
        report_lines.append(f"Loaded {raw_headline_count} raw headlines")
        report_lines.append(f"Deduped to {deduped_headline_count} unique headlines")
        report_lines.append(f"Removed {duplicate_count or 0} duplicates")
    else:
        report_lines.append(f"Loaded {headline_count} headlines")
    report_lines.append(f"Loaded {feed_count} RSS feeds")
    report_lines.append(f"Coverage: {coverage_pct:.1f}%")
    report_lines.append("")

    report_lines.append("=== Narrative Signals ===")
    for signal, value in signals.items():
        report_lines.append(f"{signal}: {value}")

    if market_expression:
        report_lines.append("")
        append_market_expression(report_lines, market_expression)

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

    if catalyst_environment:
        report_lines.append("")
        report_lines.append("=== Catalyst Environment ===")
        report_lines.append(f"State: {catalyst_environment['state']}")
        report_lines.append(f"Confidence: {catalyst_environment['confidence']}")
        append_catalyst_sources(report_lines, catalyst_environment)

        if not catalyst_environment.get("calendar_found", True):
            report_lines.append("")
            report_lines.append("Reason:")
            report_lines.append(catalyst_environment["reason"])
        else:
            report_lines.append("")
            report_lines.append(
                f"Catalyst Density: {catalyst_environment['density_score']} "
                f"({catalyst_environment['density_state']})"
            )
            report_lines.append("")
            report_lines.append("Red Folder Events:")
            if catalyst_environment.get("red_events"):
                for event in catalyst_environment["red_events"]:
                    report_lines.append(f"  {format_catalyst_event(event)}")
            else:
                report_lines.append("  None")
            report_lines.append("")
            report_lines.append("Orange Folder Events:")
            if catalyst_environment.get("orange_events"):
                for event in catalyst_environment["orange_events"]:
                    report_lines.append(f"  {format_catalyst_event(event)}")
            else:
                report_lines.append("  None")
            report_lines.append("")
            report_lines.append("Reason:")
            report_lines.append(catalyst_environment["reason"])

        report_lines.append("")
        append_macro_calendar_status(report_lines, catalyst_environment)

    if positioning_environment:
        report_lines.append("")
        report_lines.append("=== Positioning Environment ===")
        report_lines.append(f"State: {positioning_environment['state']}")
        report_lines.append(f"Confidence: {positioning_environment['confidence']}")
        report_lines.append("")
        report_lines.append("Reason:")
        report_lines.append(positioning_environment["reason"])

    if regime_alignment:
        report_lines.append("")
        report_lines.append("=== Regime Alignment Score ===")
        report_lines.append(f"Score: {regime_alignment['score']}/100")
        report_lines.append(f"State: {regime_alignment['state']}")
        report_lines.append(f"Confidence: {regime_alignment['confidence']}")
        report_lines.append("")
        report_lines.append("Reason:")
        report_lines.append(regime_alignment["reason"])

    if mode_context:
        report_lines.append("")
        report_lines.append("=== Mode Context ===")
        report_lines.append(f"State: {mode_context['state']}")
        report_lines.append(f"Confidence: {mode_context['confidence']}")
        report_lines.append("")
        report_lines.append("Read:")
        report_lines.append(mode_context["read"])

    report_lines.append("")
    report_lines.append("=== Narrative Theme Scores ===")
    for theme, count in nonzero_results[:3]:
        report_lines.append(f"{theme}: {count}")

    if group_scores:
        report_lines.append("")
        report_lines.append("=== Narrative Group Scores ===")
        for group, score in sorted(group_scores.items(), key=lambda item: item[1], reverse=True):
            report_lines.append(f"{group}: {score}")

    if theme_match_audit:
        report_lines.append("")
        report_lines.append(format_theme_match_audit(nonzero_results, theme_match_audit))

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
