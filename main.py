import argparse
import json
from datetime import datetime, timezone

from analysis.leadership_rotation import compute_rotation
from analysis.narrative_dynamics import calculate_narrative_dynamics
from config import DATA_DIR, OPERATING_MODE, RESULTS_DIR, ensure_data_dir
from mne.breadth import BREADTH_TICKERS, classify_breadth_confirmation
from mne.catalyst_environment import classify_catalyst_environment
from mne.change_summary import build_change_summary
from mne.config_diagnostics import build_configuration_report, format_startup_report
from mne.environment import classify_market_environment
from mne.event_lifecycle import ENGINE_VERSION as EVENT_LIFECYCLE_ENGINE_VERSION
from mne.event_lifecycle import evaluate_event_lifecycle_run
from mne.coverage_intelligence import (
    ENGINE_VERSION as EQE_ENGINE_VERSION,
    accepted_deduped_evidence,
    build_coverage_intelligence,
    evidence_titles,
)
from mne.evidence import (
    ENGINE_VERSION as SIP_ENGINE_VERSION,
    evidence_to_headlines,
    finalize_source_intelligence_diagnostics,
    normalize_rss_entries_to_evidence,
    persist_attributed_accepted_evidence,
    source_intelligence_counts,
)
from mne.headline_deduplication import dedupe_headlines
from mne.market_context import get_market_snapshot
from mne.network_confidence import build_network_confidence
from mne.network_health import build_network_health
from mne.narrative_brief import ENGINE_VERSION as NARRATIVE_BRIEF_ENGINE_VERSION
from mne.narrative_brief import generate_narrative_brief
from mne.narrative_leadership import build_narrative_leadership
from mne.narrative_memory import build_narrative_memory
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
from mne.platform_observability import (
    FAILED,
    PARTIAL,
    SKIPPED,
    SUCCESS,
    PipelineTelemetryRecorder,
    event_lifecycle_counts,
    evidence_normalization_counts,
    evidence_quality_counts,
    freshness_counts,
    freshness_status,
    narrative_brief_counts,
    narrative_intelligence_counts,
    rss_fetch_counts,
    source_health_state_counts,
    status_from_source_health,
)
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
from mne.source_confidence import build_source_confidence
from mne.source_reliability import build_source_reliability
from mne.source_registry import load_source_registry
from mne.storage import (
    build_daily_snapshot_preview,
    get_recent_runs,
    load_daily_snapshots,
    save_headlines,
    save_report,
    save_run_json,
)
from mne.theme_analysis import ENGINE_VERSION as NARRATIVE_INTELLIGENCE_ENGINE_VERSION
from mne.theme_analysis import analyze_themes, load_themes
from mne.trends import print_daily_count_trends, print_daily_share_trends, print_momentum

print("STARTING main.py")


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


def engine_versions():
    return {
        "sip": SIP_ENGINE_VERSION,
        "narrative_intelligence": NARRATIVE_INTELLIGENCE_ENGINE_VERSION,
        "eqe": EQE_ENGINE_VERSION,
        "event_lifecycle": EVENT_LIFECYCLE_ENGINE_VERSION,
        "narrative_brief": NARRATIVE_BRIEF_ENGINE_VERSION,
    }


def persist_platform_observability(results_file, run):
    if not results_file or not results_file.exists():
        return
    try:
        with open(results_file, "w", encoding="utf-8") as fh:
            json.dump(run, fh, ensure_ascii=False, indent=2)
    except OSError:
        return


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
    ensure_data_dir()
    parsed_args = parse_args(args)
    configured_mode = parsed_args.mode or OPERATING_MODE
    operating_mode, mode_warning = normalize_operating_mode(configured_mode)

    print("=== Daily Narrative Snapshot ===")
    print()
    print(format_startup_report(build_configuration_report()))
    print()

    now = datetime.now()
    now_utc = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    readable_time = now.strftime("%Y-%m-%d %H:%M")
    telemetry = PipelineTelemetryRecorder(
        engine_versions=engine_versions(),
        run_start_time=now_utc,
    )

    print(f"Run Timestamp: {readable_time}")
    print()
    print_operating_mode(operating_mode)
    if mode_warning:
        print(mode_warning)
    print()

    source_registry = load_source_registry()
    rss_urls = source_registry.active_rss_urls

    with telemetry.observe("RSS_FETCH") as stage:
        rss_fetch_result = fetch_headlines_from_rss(
            rss_urls,
            as_entries=True,
            include_health=True,
            registry=source_registry,
        )
        observed_source_health = (
            rss_fetch_result.get("source_health", [])
            if isinstance(rss_fetch_result, dict)
            else []
        )
        status, diagnostic = status_from_source_health(observed_source_health)
        stage.set_result(
            status=status,
            diagnostic_message=diagnostic,
            result_counts=rss_fetch_counts(rss_urls, observed_source_health),
        )
    if isinstance(rss_fetch_result, dict):
        rss_entries = rss_fetch_result.get("entries", [])
        source_health = rss_fetch_result.get("source_health", [])
    else:
        rss_entries = rss_fetch_result
        source_health = []
    with telemetry.observe("EVIDENCE_NORMALIZATION") as stage:
        evidence_objects = normalize_rss_entries_to_evidence(
            rss_entries,
            run_timestamp=now_utc.isoformat(),
            registry=source_registry,
            source_health=source_health,
        )
        source_intelligence = source_intelligence_counts(
            evidence_objects,
            registry_version=source_registry.registry_version,
            source_health=source_health,
            registry=source_registry,
        )
        counts = evidence_normalization_counts(source_intelligence)
        stage.set_result(
            status=FAILED if counts["evidence_created"] == 0 else SUCCESS,
            diagnostic_message=(
                "No evidence objects were created from fetched entries."
                if counts["evidence_created"] == 0
                else "Evidence normalization completed from fetched entries."
            ),
            result_counts=counts,
        )
    with telemetry.observe("FEED_HEALTH") as stage:
        status, diagnostic = status_from_source_health(source_health)
        stage.set_result(
            status=status,
            diagnostic_message=diagnostic,
            result_counts=source_health_state_counts(source_health),
        )
    with telemetry.observe("FRESHNESS_VALIDATION") as stage:
        status, diagnostic = freshness_status(source_intelligence)
        stage.set_result(
            status=status,
            diagnostic_message=diagnostic,
            result_counts=freshness_counts(source_intelligence),
        )
    raw_headlines = evidence_to_headlines(evidence_objects)
    scored_evidence = accepted_deduped_evidence(evidence_objects)
    deduplication = dedupe_headlines(raw_headlines)
    headlines = evidence_titles(scored_evidence)

    print(f"Loaded {deduplication['raw_headline_count']} raw headlines from RSS")
    print(f"Deduped to {deduplication['deduped_headline_count']} unique headlines")
    print(f"Removed {deduplication['duplicate_count']} duplicates")
    print(f"Loaded {len(rss_urls)} RSS feeds")

    if should_abort_for_failed_headline_collection(deduplication):
        print()
        print(ZERO_HEADLINE_WARNING)
        failure_reason = headline_collection_failure_reason(deduplication)
        print(f"Failure reason: {failure_reason}")
        source_intelligence["network_health"] = build_network_health(
            source_registry,
            source_intelligence.get("source_health", []),
            source_intelligence.get("source_freshness", []),
            source_intelligence.get("accepted_evidence", []),
        )
        source_intelligence["source_confidence"] = build_source_confidence(
            source_registry,
            source_intelligence,
        )
        failed_run = {
            "timestamp": stamp,
            "rss_urls": rss_urls,
            "raw_headline_count": deduplication["raw_headline_count"],
            "deduped_headline_count": deduplication["deduped_headline_count"],
            "duplicate_count": deduplication["duplicate_count"],
            "source_intelligence": source_intelligence,
            "headline_count": len(headlines),
            "narrative_run_status": "skipped_failed_headline_collection",
            "headline_collection_failure_reason": failure_reason,
        }
        source_intelligence["source_reliability"] = build_source_reliability(
            source_registry,
            failed_run,
            RESULTS_DIR,
        )
        source_intelligence["network_confidence"] = build_network_confidence(
            source_intelligence,
        )
        telemetry.skip("NARRATIVE_INTELLIGENCE", "Skipped because headline collection failed.")
        telemetry.skip("EVIDENCE_QUALITY", "Skipped because narrative intelligence did not run.")
        telemetry.skip("NARRATIVE_BRIEF", "Skipped because narrative intelligence did not run.")
        telemetry.skip("EVENT_LIFECYCLE", "Skipped because the run aborted after headline collection.")
        telemetry.skip("REPORT_GENERATION", "Skipped because the run aborted after headline collection.")
        with telemetry.observe("RUN_PERSISTENCE") as stage:
            failed_run["platform_observability"] = telemetry.to_block()
            stage.set_result(
                status=SUCCESS,
                diagnostic_message="Failed-run JSON persistence prepared.",
                result_counts={},
            )
        failed_run["platform_observability"] = telemetry.to_block()
        _results_dir, results_file = save_run_json(failed_run, stamp)
        persist_platform_observability(results_file, failed_run)
        print(f"Source diagnostics saved to {results_file}")
        return

    raw_headlines_file = save_headlines(raw_headlines, stamp, label="raw")
    deduped_headlines_file = save_headlines(headlines, stamp, label="deduped")

    print(f"Raw headlines saved to {raw_headlines_file}")
    print(f"Deduped headlines saved to {deduped_headlines_file}")
    print()

    themes, taxonomy_version = load_themes("themes.txt", include_version=True)
    with telemetry.observe("NARRATIVE_INTELLIGENCE") as stage:
        theme_analysis = analyze_themes(
            headlines,
            themes,
            examples_per_theme=3,
            include_attribution=True,
        )
        if len(theme_analysis) == 6:
            (
                results,
                examples,
                matched_headlines,
                theme_scores,
                theme_match_audit,
                theme_attribution,
            ) = theme_analysis
        else:
            results, examples, matched_headlines, theme_scores, theme_match_audit = theme_analysis
            theme_attribution = [{"headline": headline, "themes": []} for headline in headlines]
        group_scores = compute_group_scores(theme_scores)
        source_intelligence = finalize_source_intelligence_diagnostics(
            source_intelligence,
            scored_evidence,
            matched_headlines=matched_headlines,
        )
        source_intelligence = persist_attributed_accepted_evidence(
            source_intelligence,
            scored_evidence,
            theme_attribution,
            source_registry,
        )
        source_intelligence["network_health"] = build_network_health(
            source_registry,
            source_intelligence.get("source_health", []),
            source_intelligence.get("source_freshness", []),
            source_intelligence.get("accepted_evidence", []),
        )
        source_intelligence["source_confidence"] = build_source_confidence(
            source_registry,
            source_intelligence,
        )
        stage.set_result(
            status=SUCCESS,
            diagnostic_message="Narrative scoring completed from accepted evidence.",
            result_counts=narrative_intelligence_counts(theme_scores, group_scores),
        )
    with telemetry.observe("EVIDENCE_QUALITY") as stage:
        source_intelligence["coverage_intelligence"] = build_coverage_intelligence(
            scored_evidence,
            theme_attribution,
            source_registry,
        )
        stage.set_result(
            status=SUCCESS,
            diagnostic_message="Coverage Intelligence measured attributed accepted evidence.",
            result_counts=evidence_quality_counts(source_intelligence["coverage_intelligence"]),
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
    with telemetry.observe("EVENT_LIFECYCLE") as stage:
        event_lifecycle = evaluate_event_lifecycle_run(now_utc=now_utc)
        event_counts = event_lifecycle_counts(event_lifecycle)
        if not event_lifecycle.get("events"):
            stage.set_result(
                status=SKIPPED,
                diagnostic_message="No tracked events were available for event lifecycle evaluation.",
                result_counts=event_counts,
            )
        else:
            stage.set_result(
                status=SUCCESS,
                diagnostic_message="Event lifecycle evaluation completed.",
                result_counts=event_counts,
            )
    if not event_lifecycle.get("events"):
        telemetry.skip(
            "EVENT_LIFECYCLE",
            "No tracked events were available for event lifecycle evaluation.",
        )
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
        "rss_urls": rss_urls,
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
    source_intelligence["source_reliability"] = build_source_reliability(
        source_registry,
        run,
        RESULTS_DIR,
    )
    source_intelligence["network_confidence"] = build_network_confidence(
        source_intelligence,
    )

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

    with telemetry.observe("NARRATIVE_BRIEF") as stage:
        try:
            run["narrative_brief"] = generate_narrative_brief(
                run,
                run_timestamp_utc=now_utc.isoformat(),
            )
            stage.set_result(
                status=SUCCESS,
                diagnostic_message="Narrative Brief Engine generated a brief.",
                result_counts=narrative_brief_counts(run["narrative_brief"]),
            )
        except Exception as error:
            run["narrative_brief"] = None
            run["narrative_brief_generation_error"] = {
                "error_type": type(error).__name__,
                "message": str(error),
            }
            stage.set_result(
                status=FAILED,
                diagnostic_message=f"{type(error).__name__}: {error}",
                result_counts=narrative_brief_counts(run["narrative_brief"]),
            )

    with telemetry.observe("NARRATIVE_MEMORY") as stage:
        try:
            run["narrative_memory"] = build_narrative_memory(
                current_run=run,
                results_dir=RESULTS_DIR,
            )
            window = run["narrative_memory"].get("memory_window", {})
            stage.set_result(
                status=SUCCESS,
                diagnostic_message="Narrative Memory Foundation generated deterministic memory.",
                result_counts={
                    "runs_used": window.get("runs_used", 0),
                    "themes": len(run["narrative_memory"].get("themes", [])),
                    "groups": len(run["narrative_memory"].get("groups", [])),
                    "warnings": len(run["narrative_memory"].get("warnings", [])),
                },
            )
        except Exception as error:
            run["narrative_memory"] = None
            run["narrative_memory_generation_error"] = {
                "error_type": type(error).__name__,
                "message": str(error),
            }
            stage.set_result(
                status=FAILED,
                diagnostic_message=f"{type(error).__name__}: {error}",
                result_counts={},
            )

    with telemetry.observe("RUN_PERSISTENCE") as stage:
        run["platform_observability"] = telemetry.to_block()
        stage.set_result(
            status=SUCCESS,
            diagnostic_message="Run JSON and daily snapshot persistence prepared.",
            result_counts={},
        )
    run["platform_observability"] = telemetry.to_block()
    results_dir, results_file = save_run_json(run, stamp)
    from mne.storage import write_daily_snapshot

    write_daily_snapshot(run)
    print()
    print(f"Results saved to {results_file}")

    with telemetry.observe("REPORT_GENERATION") as stage:
        report_text = build_daily_report(
            readable_time=readable_time,
            headline_count=len(headlines),
            feed_count=len(rss_urls),
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
        stage.set_result(
            status=SUCCESS,
            diagnostic_message="Daily report generated and saved.",
            result_counts={},
        )
    run["platform_observability"] = telemetry.to_block()
    persist_platform_observability(results_file, run)
    print(f"Report saved to {report_file}")

    print_momentum(results_dir)
    print_daily_count_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_daily_share_trends(results_dir, TREND_LOOKBACK, TREND_EPSILON)
    print_narrative_dynamics(narrative_dynamics, nonzero, sorted_group_scores)


if __name__ == "__main__":
    main()
