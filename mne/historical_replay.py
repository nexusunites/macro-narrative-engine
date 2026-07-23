import argparse
import copy
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

import config
from mne import historical_backfill, historical_backfill_admin
from mne.coverage_intelligence import build_coverage_intelligence, build_replay_coverage_intelligence
from mne.evidence import persist_attributed_accepted_evidence
from mne.narrative_signals import NARRATIVE_GROUPS, compute_group_scores, get_dominant_group
from mne.source_registry import SourceRegistryError, load_source_registry
from mne.theme_analysis import analyze_themes, load_themes


REPLAY_ENGINE_VERSION = "1.0.0"
SUPPORTED_MODE = "macro"
EVIDENCE_SELECTION_RULE = (
    "Accepted persisted evidence is eligible only when published_at is at or before "
    "the replay cutoff and the source run ingestion timestamp is at or before the "
    "replay cutoff; post-cutoff runs, rejected evidence, duplicate evidence ids, "
    "and unknown-timestamp evidence are excluded."
)
LOGGER = logging.getLogger(__name__)


class HistoricalReplayError(Exception):
    """Raised when a historical replay cannot be produced for a well-formed
    request (e.g. one of several explicitly requested backfill_ids is missing,
    malformed, or fails path-safety validation)."""

    def __init__(self, message, *, missing_or_failed=None, requested=None):
        super().__init__(message)
        self.missing_or_failed = list(missing_or_failed or [])
        self.requested = list(requested or [])


@dataclass(frozen=True)
class ReplayRequest:
    replay_date: str
    mode: str
    evidence_cutoff: str
    replay_id: str
    backfill_id: str | None = None
    backfill_ids: tuple[str, ...] = ()
    include_backfilled_evidence: bool = False

    def __post_init__(self):
        ordered, seen = [], set()
        if self.backfill_id:
            ordered.append(self.backfill_id)
            seen.add(self.backfill_id)
        for bid in self.backfill_ids or ():
            if bid and bid not in seen:
                ordered.append(bid)
                seen.add(bid)
        object.__setattr__(self, "backfill_ids", tuple(ordered))
        object.__setattr__(self, "backfill_id", ordered[0] if ordered else None)
        object.__setattr__(
            self,
            "include_backfilled_evidence",
            bool(self.include_backfilled_evidence or ordered),
        )


def build_replay_request(
    replay_date,
    mode=SUPPORTED_MODE,
    evidence_cutoff=None,
    backfill_id=None,
    backfill_ids=None,
    include_backfilled_evidence=False,
):
    replay_day = _parse_replay_date(replay_date)
    normalized_mode = str(mode).strip().lower()
    if normalized_mode != SUPPORTED_MODE:
        raise ValueError(f"Unsupported historical replay mode: {mode!r}")

    cutoff = (
        _parse_utc_datetime(evidence_cutoff, "evidence_cutoff")
        if evidence_cutoff is not None
        else datetime.combine(replay_day, time.max, tzinfo=timezone.utc)
    )
    replay_id = f"replay_{replay_day.isoformat()}_{normalized_mode}"
    return ReplayRequest(
        replay_date=replay_day.isoformat(),
        mode=normalized_mode,
        evidence_cutoff=_format_utc(cutoff),
        replay_id=replay_id,
        backfill_id=backfill_id,
        backfill_ids=tuple(backfill_ids or ()),
        include_backfilled_evidence=bool(include_backfilled_evidence),
    )


def replay_output_filename(replay_request):
    request = _coerce_request(replay_request)
    return f"{request.replay_id}.json"


def ensure_replay_dir(data_dir=None):
    base_dir = Path(data_dir) if data_dir is not None else config.get_data_dir()
    replay_dir = base_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    return replay_dir


def load_historical_run_records(results_dir=None):
    if results_dir is None:
        results_dir = config.get_data_dir() / "results"
    results_path = Path(results_dir)
    if not results_path.exists():
        return []

    runs = []
    for path in sorted(results_path.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                run = json.load(fh)
        except (OSError, json.JSONDecodeError) as error:
            LOGGER.warning("Skipped malformed historical run file %s: %s", path, error)
            continue
        runs.append({"path": str(path), "run": run})
    return runs


def select_historical_evidence(historical_records, replay_request):
    request = _coerce_request(replay_request)
    cutoff = _parse_utc_datetime(request.evidence_cutoff, "evidence_cutoff")
    candidates = []

    for index, record in enumerate(historical_records):
        run = record.get("run", record) if isinstance(record, dict) else {}
        if not isinstance(run, dict):
            continue
        run_timestamp = _run_ingested_at(run, record)
        if run_timestamp is None or run_timestamp > cutoff:
            continue

        for evidence_index, evidence in enumerate(_accepted_evidence_records(run)):
            if not isinstance(evidence, dict):
                continue
            if evidence.get("accepted") is False:
                continue
            evidence_id = evidence.get("evidence_id")
            published_at_value = evidence.get("published_at") or evidence.get("timestamp")
            if not evidence_id or not published_at_value:
                continue
            try:
                published_at = _parse_utc_datetime(published_at_value, "published_at")
            except ValueError:
                continue
            if published_at > cutoff:
                continue

            normalized = copy.deepcopy(evidence)
            normalized["published_at"] = _format_utc(published_at)
            normalized["timestamp"] = normalized["published_at"]
            normalized["ingested_at"] = _format_utc(run_timestamp)
            normalized["accepted"] = True
            candidates.append(
                {
                    "run_timestamp": run_timestamp,
                    "run_index": index,
                    "evidence_index": evidence_index,
                    "evidence": normalized,
                }
            )

    first_by_id = {}
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item["run_timestamp"],
            item["run_index"],
            item["evidence_index"],
            str(item["evidence"]["evidence_id"]),
        ),
    ):
        evidence_id = str(candidate["evidence"]["evidence_id"])
        if evidence_id not in first_by_id:
            first_by_id[evidence_id] = candidate["evidence"]

    return sorted(
        first_by_id.values(),
        key=lambda evidence: (
            evidence.get("timestamp") or evidence.get("published_at") or "",
            evidence.get("evidence_id") or "",
        ),
    )


def build_replay_metadata(
    evidence_count,
    warnings=None,
    *,
    backfilled_evidence_included=False,
    backfill_ids_requested=None,
    backfill_ids_used=None,
    backfilled_evidence_counts_by_id=None,
    live_persisted_evidence_included=True,
    live_evidence_count=0,
    backfilled_evidence_count=0,
):
    evidence_sources_used = []
    if live_persisted_evidence_included and live_evidence_count:
        evidence_sources_used.append("live_persisted")
    if backfilled_evidence_included and backfilled_evidence_count:
        evidence_sources_used.append("historical_backfill")
    if not evidence_sources_used:
        evidence_sources_used = ["live_persisted"]

    return {
        "replay_mode": "HISTORICAL_REPLAY",
        "live_run_source": False,
        "future_evidence_excluded": True,
        "evidence_selection_rule": EVIDENCE_SELECTION_RULE,
        "replay_engine_version": REPLAY_ENGINE_VERSION,
        "warnings": list(warnings or _thin_evidence_warnings(evidence_count)),
        "backfilled_evidence_included": bool(backfilled_evidence_included),
        "backfill_ids_requested": list(backfill_ids_requested or []),
        "backfill_ids_used": list(backfill_ids_used or []),
        "backfilled_evidence_counts_by_id": dict(backfilled_evidence_counts_by_id or {}),
        "live_persisted_evidence_included": bool(live_persisted_evidence_included),
        "evidence_sources_used": evidence_sources_used,
        "backfilled_evidence_count": backfilled_evidence_count,
        "live_evidence_count": live_evidence_count,
        "total_evidence_count": live_evidence_count + backfilled_evidence_count,
    }


def select_backfilled_evidence(backfill_evidence, replay_request):
    """Applies the same publish-cutoff/validity discipline select_historical_evidence
    already applies to live evidence, to a flat list of backfilled EvidenceObject
    dicts. There is no run-ingestion timestamp gate here - backfilled evidence has
    no live ingestion event; only its own published_at matters against the cutoff."""
    request = _coerce_request(replay_request)
    cutoff = _parse_utc_datetime(request.evidence_cutoff, "evidence_cutoff")
    candidates = []

    for evidence in backfill_evidence or []:
        if not isinstance(evidence, dict) or evidence.get("accepted") is not True:
            continue
        evidence_id = evidence.get("evidence_id")
        published_at_value = evidence.get("timestamp") or evidence.get("published_at")
        if not evidence_id or not published_at_value:
            continue
        try:
            published_at = _parse_utc_datetime(published_at_value, "published_at")
        except ValueError:
            continue
        if published_at > cutoff:
            continue

        normalized = copy.deepcopy(evidence)
        normalized["published_at"] = _format_utc(published_at)
        normalized["timestamp"] = normalized["published_at"]
        candidates.append(normalized)

    first_by_id = {}
    for candidate in candidates:
        evidence_id = str(candidate["evidence_id"])
        if evidence_id not in first_by_id:
            first_by_id[evidence_id] = candidate

    return sorted(
        first_by_id.values(),
        key=lambda evidence: (evidence.get("timestamp") or "", evidence.get("evidence_id") or ""),
    )


def _load_backfill_evidence_for_replay(request):
    """Loads raw (un-cutoff-filtered) backfilled evidence for a replay request.

    Three cases, per the multiple-backfill design:
    - No explicit ids (include flag only): resolve by date, exact legacy path.
    - Exactly one requested id: exact legacy single-id behavior; an invalid or
      path-unsafe id is treated as missing (empty evidence, calm warning
      downstream), never raised.
    - Two or more requested ids: any missing, malformed, path-unsafe, or
      unreadable id raises HistoricalReplayError before any replay artifact is
      produced. Per-id evidence lists are concatenated in request order so the
      first-listed backfill wins evidence_id collisions during dedup.
    """
    backfill_ids = request.backfill_ids

    if not backfill_ids:
        return historical_backfill.load_backfilled_evidence(
            backfill_id=None,
            requested_date=request.replay_date,
        )

    if len(backfill_ids) == 1:
        backfill_id = backfill_ids[0]
        if not historical_backfill_admin.is_valid_backfill_id(backfill_id):
            return []
        return historical_backfill.load_backfilled_evidence(
            backfill_id=backfill_id,
            requested_date=None,
        )

    per_id_evidence = {}
    missing_or_failed = []
    for backfill_id in backfill_ids:
        if not historical_backfill_admin.is_valid_backfill_id(backfill_id):
            missing_or_failed.append(backfill_id)
            continue
        if historical_backfill.load_backfill_manifest(backfill_id) is None:
            missing_or_failed.append(backfill_id)
            continue
        try:
            per_id_evidence[backfill_id] = historical_backfill.load_backfilled_evidence(
                backfill_id=backfill_id,
                requested_date=None,
            )
        except (OSError, json.JSONDecodeError):
            missing_or_failed.append(backfill_id)

    if missing_or_failed:
        raise HistoricalReplayError(
            "Historical replay could not load requested backfill(s): "
            f"{', '.join(missing_or_failed)}. "
            f"Requested: {', '.join(backfill_ids)}.",
            missing_or_failed=missing_or_failed,
            requested=list(backfill_ids),
        )

    combined = []
    for backfill_id in backfill_ids:
        combined.extend(per_id_evidence.get(backfill_id) or [])
    return combined


def run_historical_replay(replay_request, historical_records=None, generated_at=None):
    request = _coerce_request(replay_request)
    records = historical_records if historical_records is not None else load_historical_run_records()
    live_evidence = select_historical_evidence(records, request)

    backfilled_evidence = []
    backfill_ids_used = []
    backfilled_evidence_counts_by_id = {}
    backfill_warning = None
    if request.include_backfilled_evidence:
        raw_backfill_evidence = _load_backfill_evidence_for_replay(request)
        selected_backfill_evidence = select_backfilled_evidence(raw_backfill_evidence, request)
        combined_evidence, backfilled_evidence = _merge_live_and_backfilled_evidence(
            live_evidence, selected_backfill_evidence
        )
        if not backfilled_evidence:
            backfill_warning = "No eligible backfilled evidence was available for this replay."
        else:
            backfill_ids_used = sorted(
                {
                    (evidence.get("metadata") or {}).get("backfill_id")
                    for evidence in backfilled_evidence
                    if (evidence.get("metadata") or {}).get("backfill_id")
                }
            )
            backfilled_evidence_counts_by_id = dict(
                Counter(
                    (evidence.get("metadata") or {}).get("backfill_id")
                    for evidence in backfilled_evidence
                    if (evidence.get("metadata") or {}).get("backfill_id")
                )
            )
    else:
        combined_evidence = list(live_evidence)

    warnings = _thin_evidence_warnings(len(combined_evidence))
    if backfill_warning:
        warnings.append(backfill_warning)

    source_registry = load_source_registry()
    themes, taxonomy_version = load_themes("themes.txt", include_version=True)
    headlines = [evidence.get("title", "") for evidence in combined_evidence if evidence.get("title")]
    theme_analysis = analyze_themes(
        headlines,
        themes,
        examples_per_theme=3,
        include_attribution=True,
    )
    (
        theme_counts,
        examples,
        matched_headlines,
        theme_scores,
        theme_match_audit,
        theme_attribution,
    ) = theme_analysis
    group_scores = compute_group_scores(theme_scores)
    dominant_theme = _dominant_theme(theme_scores)
    dominant_group, _dominant_group_score = get_dominant_group(group_scores)

    live_theme_attribution = theme_attribution[: len(live_evidence)]
    backfill_theme_attribution = theme_attribution[len(live_evidence) :]

    source_intelligence = _build_replay_source_intelligence(combined_evidence)
    source_intelligence = persist_attributed_accepted_evidence(
        source_intelligence,
        live_evidence,
        live_theme_attribution,
        source_registry,
    )
    if backfilled_evidence:
        source_intelligence["accepted_evidence"].extend(
            _backfill_attributed_records(backfilled_evidence, backfill_theme_attribution)
        )
        source_intelligence["accepted_evidence_count"] = len(source_intelligence["accepted_evidence"])

    source_intelligence["coverage_intelligence"] = build_replay_coverage_intelligence(
        source_intelligence["accepted_evidence"],
        source_registry,
    )

    # Scoped to live evidence only: build_coverage_intelligence is
    # live-registry-bound (registry.source_by_id per source_id), and
    # historical source ids such as fed_fomc are deliberately not registry
    # members. Feeding it combined_evidence would raise SourceRegistryError
    # and blank out coverage for the whole replay, including narratives with
    # no backfilled evidence at all. source_intelligence.coverage_intelligence
    # above is the source-agnostic replay-level counterpart.
    coverage = _build_coverage_if_available(
        live_evidence,
        live_theme_attribution,
        source_registry,
        warnings,
    )

    output = {
        "replay_id": request.replay_id,
        "replay_date": request.replay_date,
        "generated_at": _format_utc(generated_at or datetime.now(timezone.utc)),
        "evidence_cutoff": request.evidence_cutoff,
        "evidence_count": len(combined_evidence),
        "source_count": len(
            {
                evidence.get("source_id")
                for evidence in combined_evidence
                if evidence.get("source_id")
            }
        ),
        "taxonomy_version": taxonomy_version,
        "registry_version": source_registry.registry_version,
        "theme_scores": theme_scores,
        "group_scores": group_scores,
        "dominant_theme": dominant_theme,
        "dominant_group": dominant_group,
        "coverage": coverage,
        "source_intelligence": source_intelligence,
        "replay_metadata": build_replay_metadata(
            len(combined_evidence),
            warnings,
            backfilled_evidence_included=bool(backfilled_evidence),
            backfill_ids_requested=list(request.backfill_ids),
            backfill_ids_used=backfill_ids_used,
            backfilled_evidence_counts_by_id=backfilled_evidence_counts_by_id,
            live_persisted_evidence_included=True,
            live_evidence_count=len(live_evidence),
            backfilled_evidence_count=len(backfilled_evidence),
        ),
        "theme_counts": theme_counts,
        "matched_headlines": matched_headlines,
        "theme_match_audit": theme_match_audit,
        "examples": examples,
    }
    if coverage is None:
        del output["coverage"]
    return output


def persist_historical_replay(replay_output, data_dir=None):
    replay_dir = ensure_replay_dir(data_dir)
    replay_id = replay_output.get("replay_id")
    if not replay_id:
        raise ValueError("Replay output is missing replay_id.")
    path = replay_dir / f"{replay_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(replay_output, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def run_and_persist_historical_replay(
    replay_date,
    mode=SUPPORTED_MODE,
    evidence_cutoff=None,
    backfill_id=None,
    backfill_ids=None,
    include_backfilled_evidence=False,
):
    request = build_replay_request(
        replay_date,
        mode=mode,
        evidence_cutoff=evidence_cutoff,
        backfill_id=backfill_id,
        backfill_ids=backfill_ids,
        include_backfilled_evidence=include_backfilled_evidence,
    )
    output = run_historical_replay(request)
    path = persist_historical_replay(output)
    return path, output


def main(args=None):
    parser = argparse.ArgumentParser(description="Run a deterministic historical replay.")
    parser.add_argument("--date", required=True, help="Replay date as YYYY-MM-DD.")
    parser.add_argument("--mode", default=SUPPORTED_MODE, help="Replay mode; only macro is supported.")
    parser.add_argument("--evidence-cutoff", help="Optional UTC ISO-8601 cutoff timestamp.")
    parser.add_argument(
        "--include-backfilled",
        action="store_true",
        help="Include eligible already-persisted backfilled historical evidence in this replay.",
    )
    parser.add_argument(
        "--backfill-id",
        dest="backfill_ids",
        action="append",
        default=None,
        help="Backfill ID to include; may be repeated. Implies --include-backfilled.",
    )
    parsed = parser.parse_args(args)
    path, output = run_and_persist_historical_replay(
        parsed.date,
        mode=parsed.mode,
        evidence_cutoff=parsed.evidence_cutoff,
        backfill_ids=parsed.backfill_ids or [],
        include_backfilled_evidence=parsed.include_backfilled,
    )
    print(f"Historical replay saved to {path}")
    print(f"Evidence selected: {output['evidence_count']}")
    replay_metadata = output.get("replay_metadata") or {}
    if replay_metadata.get("backfilled_evidence_included"):
        print(f"Backfilled evidence included: {replay_metadata['backfilled_evidence_count']}")


def _coerce_request(value):
    if isinstance(value, ReplayRequest):
        return value
    if isinstance(value, dict):
        return ReplayRequest(**value)
    raise TypeError("Expected ReplayRequest or request dictionary.")


def _parse_replay_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid replay_date {value!r}; expected YYYY-MM-DD.") from error


def _parse_utc_datetime(value, field_name):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        elif len(text) == 17 and text[10] == "_":
            text = (
                f"{text[:4]}-{text[5:7]}-{text[8:10]}"
                f"T{text[11:13]}:{text[13:15]}:{text[15:17]}+00:00"
            )
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"Invalid {field_name} {value!r}; expected UTC ISO-8601 timestamp.") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value):
    return _parse_utc_datetime(value, "timestamp").isoformat().replace("+00:00", "Z")


def _run_ingested_at(run, record):
    for field in ("timestamp", "run_date", "generated_at"):
        value = run.get(field)
        if value:
            try:
                return _parse_utc_datetime(value, field)
            except ValueError:
                pass
    path = record.get("path") if isinstance(record, dict) else None
    if path:
        stem = Path(path).stem
        try:
            return _parse_utc_datetime(stem[:17], "run filename timestamp")
        except ValueError:
            return None
    return None


def _accepted_evidence_records(run):
    direct = run.get("accepted_evidence")
    if isinstance(direct, list):
        return direct
    source_intelligence = run.get("source_intelligence")
    if isinstance(source_intelligence, dict) and isinstance(
        source_intelligence.get("accepted_evidence"),
        list,
    ):
        return source_intelligence["accepted_evidence"]
    return []


def _thin_evidence_warnings(evidence_count):
    if evidence_count == 0:
        return ["No accepted evidence objects were available at this cutoff."]
    if evidence_count < 5:
        return [f"Only {evidence_count} evidence objects were available at this cutoff."]
    return []


def _dominant_theme(theme_scores):
    nonzero = [(theme, score) for theme, score in theme_scores.items() if score > 0]
    if not nonzero:
        return None
    return sorted(nonzero, key=lambda item: (-item[1], item[0]))[0][0]


def _build_replay_source_intelligence(selected_evidence):
    by_source = {}
    for evidence in selected_evidence:
        source_id = evidence.get("source_id")
        if not source_id:
            continue
        source = by_source.setdefault(
            source_id,
            {
                "source_id": source_id,
                "source_name": evidence.get("source_name"),
                "evidence_count": 0,
            },
        )
        source["evidence_count"] += 1
        if not source.get("source_name") and evidence.get("source_name"):
            source["source_name"] = evidence.get("source_name")
    return {
        "historical_replay": True,
        "accepted_evidence_count": len(selected_evidence),
        "source_contribution_breakdown": sorted(
            by_source.values(),
            key=lambda item: (-item["evidence_count"], item["source_id"]),
        ),
    }


def _merge_live_and_backfilled_evidence(live_evidence, backfilled_evidence):
    """Combines live-run evidence with already-cutoff-filtered backfilled evidence,
    deduping by evidence_id with live evidence taking precedence on any collision.
    Returns (combined_evidence, deduped_backfilled_evidence)."""
    if not backfilled_evidence:
        return list(live_evidence), []

    seen_ids = {str(evidence.get("evidence_id")) for evidence in live_evidence if evidence.get("evidence_id")}
    deduped_backfilled = []
    for evidence in backfilled_evidence:
        evidence_id = str(evidence.get("evidence_id"))
        if evidence_id in seen_ids:
            continue
        seen_ids.add(evidence_id)
        deduped_backfilled.append(evidence)

    return list(live_evidence) + deduped_backfilled, deduped_backfilled


def _backfill_attributed_records(backfilled_evidence, theme_attribution_slice):
    """Builds accepted_evidence records for backfilled evidence without consulting
    the live source registry - fed_fomc (and any future historical source) is
    deliberately not a live registry source, and registry.source_by_id() raises
    for unknown ids, so this mirrors mne.evidence._accepted_attributed_record's
    output shape using only fields the backfilled EvidenceObject already carries."""
    records = []
    for evidence, attribution in zip(backfilled_evidence, theme_attribution_slice):
        themes = attribution.get("themes", []) if isinstance(attribution, dict) else []
        attributed_themes = [theme for theme in themes if theme]
        metadata = evidence.get("metadata") or {}
        attributed_groups = sorted(
            {
                group
                for group, group_themes in NARRATIVE_GROUPS.items()
                if any(theme in group_themes for theme in attributed_themes)
            }
        )
        records.append(
            {
                "evidence_id": evidence.get("evidence_id"),
                "title": evidence.get("title"),
                "source_id": evidence.get("source_id"),
                "source_name": evidence.get("source_name"),
                "provider": metadata.get("provider"),
                "evidence_type": evidence.get("evidence_type"),
                "published_at": evidence.get("timestamp"),
                "timestamp": evidence.get("timestamp"),
                "url": evidence.get("url"),
                "freshness_state": evidence.get("freshness_state"),
                "accepted": True,
                "rejection_state": None,
                "themes": attributed_themes,
                "groups": attributed_groups,
                "narrative_keys": [
                    *[f"theme:{theme}" for theme in attributed_themes],
                    *[f"group:{group}" for group in attributed_groups],
                ],
                "evidence_origin": metadata.get("evidence_origin"),
                "backfill_id": metadata.get("backfill_id"),
                "category": metadata.get("category"),
                "connector_source_id": metadata.get("connector_source_id"),
            }
        )
    return records


def _build_coverage_if_available(selected_evidence, theme_attribution, source_registry, warnings):
    try:
        return build_coverage_intelligence(
            selected_evidence,
            theme_attribution,
            source_registry,
        )
    except SourceRegistryError as error:
        warnings.append(f"Coverage omitted because selected evidence could not be mapped to registry sources: {error}")
        return None


if __name__ == "__main__":
    main()
