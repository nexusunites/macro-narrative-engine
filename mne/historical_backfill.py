import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path

import config
from mne.backfill_sources import bea_gdp_pce, bls_cpi, fed_fomc
from mne.evidence import EVIDENCE_TYPE_HEADLINE, EvidenceObject, generate_evidence_id
from mne.freshness import UNKNOWN


SUPPORTED_SOURCE = "fed_fomc"
SUPPORTED_SOURCES = (SUPPORTED_SOURCE, "bls_cpi", "bea_gdp_pce")
SUPPORTED_MODE = "macro"
STORAGE_TIER = "TIER_2_NORMALIZED_EVIDENCE"
EVIDENCE_ORIGIN = "HISTORICAL_BACKFILL"
WARNING_SOURCE_SCOPE = "Fed/FOMC backfill covers only Federal Reserve communications."
WARNING_PARTIAL_COVERAGE = "This is partial historical coverage, not complete market news reconstruction."
WARNING_NO_LIVE_SOURCES = "No live sources were fetched."
WARNING_NO_PAYWALLED_NEWS = "No paywalled news was accessed."
LIMITATIONS = [
    "Historical reconstruction available for supported sources.",
    "This date has partial historical coverage.",
]
BLS_WARNINGS = (
    "BLS CPI backfill covers official CPI/inflation releases only.",
    WARNING_PARTIAL_COVERAGE,
    WARNING_NO_LIVE_SOURCES,
    WARNING_NO_PAYWALLED_NEWS,
)
BLS_LIMITATIONS = [
    "Historical reconstruction covers official BLS CPI/inflation releases only.",
    "This date range has partial historical coverage and excludes market news and other BLS releases.",
]
BEA_WARNINGS = (
    "BEA GDP/PCE backfill covers official BEA macroeconomic releases only.",
    WARNING_PARTIAL_COVERAGE,
    WARNING_NO_LIVE_SOURCES,
    WARNING_NO_PAYWALLED_NEWS,
)
BEA_LIMITATIONS = [
    "Historical reconstruction covers official BEA GDP and Personal Income and Outlays (PCE) releases only.",
    "This date range has partial historical coverage and excludes market news, other BEA releases (e.g., industry GDP, regional GDP, international trade), and other agencies' data.",
]


SOURCE_SPECS = {
    SUPPORTED_SOURCE: {
        "fetch": fed_fomc.fetch_fed_fomc_records,
        "normalize": fed_fomc.normalize_fed_fomc_record,
        "provider": "Federal Reserve",
        "category": "Central Bank Communications",
        "warnings": (
            WARNING_SOURCE_SCOPE,
            WARNING_PARTIAL_COVERAGE,
            WARNING_NO_LIVE_SOURCES,
            WARNING_NO_PAYWALLED_NEWS,
        ),
        "limitations": LIMITATIONS,
        "empty_warning": "No Fed/FOMC statement evidence was found for the requested date range.",
        "record_label": "Fed/FOMC",
    },
    "bls_cpi": {
        "fetch": bls_cpi.fetch_bls_cpi_records,
        "normalize": bls_cpi.normalize_bls_cpi_record,
        "provider": "BLS",
        "category": "Inflation / Economic Data",
        "warnings": BLS_WARNINGS,
        "limitations": BLS_LIMITATIONS,
        "empty_warning": "No BLS CPI release evidence was found for the requested date range.",
        "record_label": "BLS CPI",
    },
    "bea_gdp_pce": {
        "fetch": bea_gdp_pce.fetch_bea_gdp_pce_records,
        "normalize": bea_gdp_pce.normalize_bea_gdp_pce_record,
        "provider": "BEA",
        "category": "Economic Data / Growth / Inflation",
        "warnings": BEA_WARNINGS,
        "limitations": BEA_LIMITATIONS,
        "empty_warning": "No BEA GDP/PCE release evidence was found for the requested date range.",
        "record_label": "BEA GDP/PCE",
    },
}


@dataclass(frozen=True)
class BackfillRequest:
    backfill_id: str
    requested_date: str | None
    requested_range: tuple[str, str]
    narrative_mode: str
    source_categories: tuple[str, ...]
    evidence_cutoff: str
    generated_at: str
    status: str = "REQUESTED"
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self):
        data = asdict(self)
        data["requested_range"] = list(self.requested_range)
        data["source_categories"] = list(self.source_categories)
        data["warnings"] = list(self.warnings)
        return data


def build_backfill_request(
    requested_date=None,
    requested_range=None,
    source_categories=(SUPPORTED_SOURCE,),
    narrative_mode=SUPPORTED_MODE,
) -> BackfillRequest:
    normalized_mode = str(narrative_mode).strip().lower()
    if normalized_mode != SUPPORTED_MODE:
        raise ValueError(f"Unsupported historical backfill narrative_mode: {narrative_mode!r}")

    categories = tuple(str(item).strip().lower() for item in source_categories)
    if len(categories) != 1 or categories[0] not in SUPPORTED_SOURCES:
        raise ValueError(_unsupported_source_message())
    source_id = categories[0]
    if requested_date is None and requested_range is None:
        raise ValueError("Either requested_date or requested_range is required.")
    if requested_date is not None and requested_range is not None:
        raise ValueError("Use requested_date or requested_range, not both.")

    if requested_date is not None:
        start = end = _parse_date(requested_date, "requested_date")
        request_date = start.isoformat()
        id_date_part = request_date
    else:
        if len(requested_range) != 2:
            raise ValueError("requested_range must contain start and end dates.")
        start = _parse_date(requested_range[0], "requested_range start")
        end = _parse_date(requested_range[1], "requested_range end")
        if start > end:
            raise ValueError("requested_range start must be on or before end.")
        request_date = None
        id_date_part = f"{start.isoformat()}_{end.isoformat()}"

    return BackfillRequest(
        backfill_id=f"backfill_{id_date_part}_{normalized_mode}_{source_id}",
        requested_date=request_date,
        requested_range=(start.isoformat(), end.isoformat()),
        narrative_mode=normalized_mode,
        source_categories=categories,
        evidence_cutoff=_format_utc(datetime.combine(end, time.max, tzinfo=timezone.utc)),
        generated_at=_format_utc(datetime.now(timezone.utc)),
        warnings=SOURCE_SPECS[source_id]["warnings"],
    )


def run_historical_backfill(request, connector=None, fetch=None) -> dict:
    coerced = _coerce_request(request)
    _validate_supported_request(coerced)
    source_id = coerced.source_categories[0]
    source_spec = SOURCE_SPECS[source_id]
    connector_fn = connector or source_spec["fetch"]
    raw_records = connector_fn(
        coerced.requested_range[0],
        coerced.requested_range[1],
        get=fetch,
    )

    warnings = list(coerced.warnings)
    connector_records = []
    evidence_objects = []
    normalization_errors = []
    seen_ids = set()

    for raw_record in raw_records:
        try:
            connector_record = source_spec["normalize"](raw_record)
            connector_records.append(connector_record)
            evidence = normalize_backfill_record(
                connector_record,
                coerced.backfill_id,
                historical_source_id=source_id,
                provider=source_spec["provider"],
                category=source_spec["category"],
            )
        except (TypeError, ValueError) as error:
            normalization_errors.append(str(error))
            continue

        if evidence.evidence_id in seen_ids:
            continue
        seen_ids.add(evidence.evidence_id)
        evidence_objects.append(evidence)

    if normalization_errors:
        warnings.append(
            f"{len(normalization_errors)} raw {source_spec['record_label']} record(s) could not be normalized."
        )
    if len(connector_records) != len(evidence_objects):
        warnings.append(f"Duplicate {source_spec['record_label']} records were deduped deterministically.")
    source_coverage = _source_coverage(connector_records, source_id=source_id)
    manifest = build_backfill_manifest(coerced, evidence_objects, warnings, source_coverage, len(raw_records))
    return {
        "request": coerced,
        "raw_records": raw_records,
        "connector_records": connector_records,
        "evidence_objects": evidence_objects,
        "manifest": manifest,
        "warnings": warnings,
    }


def normalize_backfill_record(
    raw_record,
    backfill_id,
    historical_source_id=SUPPORTED_SOURCE,
    provider="Federal Reserve",
    category="Central Bank Communications",
) -> EvidenceObject:
    title = _required_text(raw_record.get("title"), "title")
    timestamp = _format_utc(_required_text(raw_record.get("published_at"), "published_at"))
    url = raw_record.get("url")
    source_id = raw_record.get("source_id") or historical_source_id
    source_name = raw_record.get("provider") or provider
    evidence_id = generate_evidence_id(
        source_id=source_id,
        evidence_type=EVIDENCE_TYPE_HEADLINE,
        timestamp=timestamp,
        title=title,
        url=url,
    )
    return EvidenceObject(
        evidence_id=evidence_id,
        source_id=source_id,
        source_name=source_name,
        evidence_type=EVIDENCE_TYPE_HEADLINE,
        timestamp=timestamp,
        title=title,
        summary=None,
        url=url,
        metadata={
            "evidence_origin": EVIDENCE_ORIGIN,
            "backfill_id": backfill_id,
            "connector_source_id": historical_source_id,
            "raw_id": raw_record.get("raw_id"),
            "retrieval_timestamp": raw_record.get("retrieval_timestamp"),
            "usage_storage_rights": raw_record.get("usage_storage_rights"),
            "provider": source_name,
            "category": raw_record.get("category") or category,
            "source_type": raw_record.get("source_type"),
        },
        accepted=True,
        rejection_reason=None,
        freshness_state=UNKNOWN,
        freshness_age_minutes=None,
        freshness_checked_at=None,
    )


def build_backfill_manifest(
    request,
    normalized_evidence,
    warnings,
    source_coverage,
    records_found=None,
) -> dict:
    coerced = _coerce_request(request)
    source_id = coerced.source_categories[0]
    source_spec = SOURCE_SPECS[source_id]
    evidence_count = len(normalized_evidence)
    unresolved_errors = any("could not be normalized" in warning for warning in warnings)
    replay_ready = evidence_count > 0 and not unresolved_errors
    final_warnings = list(dict.fromkeys(warnings))
    if evidence_count == 0:
        final_warnings.append(source_spec["empty_warning"])
    if not replay_ready:
        final_warnings.append("Backfill evidence is not replay-ready because no accepted evidence was produced or normalization errors remain.")

    return {
        "backfill_id": coerced.backfill_id,
        "requested_start_date": coerced.requested_range[0],
        "requested_end_date": coerced.requested_range[1],
        "generated_at": _format_utc(datetime.now(timezone.utc)),
        "source_id": source_id,
        "provider": source_spec["provider"],
        "category": source_spec["category"],
        "records_found": len(normalized_evidence) if records_found is None else records_found,
        "evidence_count": evidence_count,
        "date_range_covered": source_coverage,
        "storage_tier": STORAGE_TIER,
        "warnings": list(dict.fromkeys(final_warnings)),
        "replay_ready": replay_ready,
        "limitations": source_spec["limitations"],
        "status": "COMPLETE" if replay_ready else "PARTIAL",
    }


def persist_backfill_result(request, evidence_objects, manifest, data_dir=None) -> Path:
    coerced = _coerce_request(request)
    output_dir = ensure_historical_evidence_dir(coerced.backfill_id, data_dir=data_dir)
    write_backfill_manifest(coerced.backfill_id, manifest, data_dir=data_dir)
    write_backfill_evidence(coerced.backfill_id, evidence_objects, data_dir=data_dir)
    return output_dir


def backfill_output_dir(backfill_id, data_dir=None) -> Path:
    return _historical_evidence_root(data_dir=data_dir) / str(backfill_id)


def ensure_historical_evidence_dir(backfill_id, data_dir=None) -> Path:
    output_dir = backfill_output_dir(backfill_id, data_dir=data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_backfill_manifest(backfill_id, manifest, data_dir=None) -> Path:
    output_dir = ensure_historical_evidence_dir(backfill_id, data_dir=data_dir)
    path = output_dir / "manifest.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def write_backfill_evidence(backfill_id, evidence_objects, data_dir=None) -> Path:
    output_dir = ensure_historical_evidence_dir(backfill_id, data_dir=data_dir)
    path = output_dir / "evidence.json"
    payload = [
        evidence.to_dict() if isinstance(evidence, EvidenceObject) else dict(evidence)
        for evidence in evidence_objects
    ]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def load_backfill_manifest(backfill_id, data_dir=None) -> dict | None:
    path = backfill_output_dir(backfill_id, data_dir=data_dir) / "manifest.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_backfilled_evidence(backfill_id=None, requested_date=None, data_dir=None) -> list[dict]:
    if backfill_id is None:
        if requested_date is None:
            raise ValueError("backfill_id or requested_date is required.")
        backfill_id = _latest_backfill_id_for_date(requested_date, data_dir=data_dir)
        if backfill_id is None:
            return []

    path = backfill_output_dir(backfill_id, data_dir=data_dir) / "evidence.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, list) else []


def run_and_persist_historical_backfill(source, start, end, fetch=None, data_dir=None):
    source_id = str(source).strip().lower()
    if source_id not in SUPPORTED_SOURCES:
        raise ValueError(_unsupported_source_message())
    request = build_backfill_request(
        requested_range=(start, end),
        source_categories=(source_id,),
    )
    result = run_historical_backfill(request, fetch=fetch)
    path = persist_backfill_result(
        result["request"],
        result["evidence_objects"],
        result["manifest"],
        data_dir=data_dir,
    )
    return path, result


def main(args=None):
    parser = argparse.ArgumentParser(description="Run a historical evidence backfill.")
    parser.add_argument(
        "--source",
        required=True,
        choices=SUPPORTED_SOURCES,
        help="Backfill source (fed_fomc, bls_cpi, or bea_gdp_pce).",
    )
    parser.add_argument("--start", required=True, help="Start date as YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date as YYYY-MM-DD.")
    parsed = parser.parse_args(args)

    path, result = run_and_persist_historical_backfill(parsed.source, parsed.start, parsed.end)
    print(f"Historical backfill saved to {path}")
    print(f"Evidence produced: {result['manifest']['evidence_count']}")
    print(f"Replay ready: {result['manifest']['replay_ready']}")


def _historical_evidence_root(data_dir=None) -> Path:
    base_dir = Path(data_dir) if data_dir is not None else config.get_data_dir()
    return base_dir / "historical_evidence"


def _coerce_request(value) -> BackfillRequest:
    if isinstance(value, BackfillRequest):
        return value
    if isinstance(value, dict):
        data = dict(value)
        data["requested_range"] = tuple(data["requested_range"])
        data["source_categories"] = tuple(data["source_categories"])
        data["warnings"] = tuple(data.get("warnings", ()))
        return BackfillRequest(**data)
    raise TypeError("Expected BackfillRequest or request dictionary.")


def _validate_supported_request(request: BackfillRequest):
    if request.narrative_mode != SUPPORTED_MODE:
        raise ValueError(f"Unsupported historical backfill narrative_mode: {request.narrative_mode!r}")
    if len(request.source_categories) != 1 or request.source_categories[0] not in SUPPORTED_SOURCES:
        raise ValueError(_unsupported_source_message())


def _source_coverage(records: list[dict], source_id=SUPPORTED_SOURCE) -> dict:
    dates = [
        _format_utc(record["published_at"])[:10]
        for record in records
        if record.get("published_at")
    ]
    if source_id == SUPPORTED_SOURCE:
        return {"earliest": min(dates) if dates else None, "latest": max(dates) if dates else None}
    return {"start": min(dates) if dates else None, "end": max(dates) if dates else None}


def _unsupported_source_message() -> str:
    return "Unsupported historical backfill source; valid options are: fed_fomc, bls_cpi, bea_gdp_pce."


def _latest_backfill_id_for_date(requested_date, data_dir=None) -> str | None:
    day = _parse_date(requested_date, "requested_date").isoformat()
    root = _historical_evidence_root(data_dir=data_dir)
    if not root.exists():
        return None
    candidates = []
    for manifest_path in root.glob("*/manifest.json"):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("status") not in {"COMPLETE", "PARTIAL"}:
            continue
        start = manifest.get("requested_start_date")
        end = manifest.get("requested_end_date")
        if start and end and start <= day <= end:
            candidates.append((manifest.get("generated_at") or "", manifest.get("backfill_id")))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def _parse_date(value, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid {field_name} {value!r}; expected YYYY-MM-DD.") from error


def _format_utc(value) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _required_text(value, field_name: str) -> str:
    if value is None:
        raise ValueError(f"Backfill record is missing {field_name}.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Backfill record is missing {field_name}.")
    return text


if __name__ == "__main__":
    main()
