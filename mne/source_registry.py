import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "config" / "source_registry.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "registry_version",
    "sources",
    "evidence_types",
    "categories",
    "priority_tiers",
}
REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "display_name",
    "provider",
    "category",
    "priority",
    "ingestion_type",
    "supported_evidence_types",
    "url",
    "status",
    "freshness_threshold_minutes",
    "expected_update_frequency_minutes",
    "supported_narratives",
    "supported_groups",
    "notes",
}
VALID_STATUSES = {"ACTIVE", "DISABLED", "DEPRECATED", "PLANNED"}
VALID_PRIORITIES = {"TIER_1", "TIER_2", "TIER_3"}
SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SourceRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRegistry:
    registry_version: str
    sources: tuple[dict[str, Any], ...]
    evidence_types: tuple[dict[str, Any], ...]
    categories: tuple[dict[str, Any], ...]
    priority_tiers: tuple[dict[str, Any], ...]

    @property
    def active_sources(self):
        return [source for source in self.sources if source["status"] == "ACTIVE"]

    @property
    def active_rss_sources(self):
        return [
            source
            for source in self.active_sources
            if source["ingestion_type"] == "RSS"
            and "Headline" in source["supported_evidence_types"]
        ]

    @property
    def active_rss_urls(self):
        return [source["url"] for source in self.active_rss_sources]

    def source_by_url(self, url: str | None):
        if not url:
            raise SourceRegistryError("RSS entry is missing feed_url; cannot resolve source registry entry.")
        for source in self.sources:
            if source["url"] == url:
                return source
        raise SourceRegistryError(f"RSS entry feed_url is not registered in source registry: {url}")

    def diagnostics(self):
        status_counts = {status: 0 for status in sorted(VALID_STATUSES)}
        for source in self.sources:
            status_counts[source["status"]] += 1
        return {
            "registry_version": self.registry_version,
            "status_counts": status_counts,
            "active_count": status_counts["ACTIVE"],
            "non_active_count": sum(
                count for status, count in status_counts.items() if status != "ACTIVE"
            ),
            "sources": [
                {
                    "source_id": source["source_id"],
                    "display_name": source["display_name"],
                    "status": source["status"],
                }
                for source in self.sources
            ],
        }


def load_source_registry(path: Path | str = REGISTRY_PATH):
    registry_path = Path(path)
    if not registry_path.exists():
        raise SourceRegistryError(f"Source registry file not found: {registry_path}")

    try:
        with open(registry_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as error:
        raise SourceRegistryError(f"Source registry JSON is malformed: {error}") from error
    except OSError as error:
        raise SourceRegistryError(f"Unable to read source registry {registry_path}: {error}") from error

    validate_source_registry(data)
    return SourceRegistry(
        registry_version=data["registry_version"],
        sources=tuple(data["sources"]),
        evidence_types=tuple(data["evidence_types"]),
        categories=tuple(data["categories"]),
        priority_tiers=tuple(data["priority_tiers"]),
    )


def validate_source_registry(data):
    if not isinstance(data, dict):
        raise SourceRegistryError("Source registry root must be a JSON object.")

    missing_top_level = REQUIRED_TOP_LEVEL_KEYS - set(data)
    if missing_top_level:
        missing = ", ".join(sorted(missing_top_level))
        raise SourceRegistryError(f"Source registry missing top-level keys: {missing}")

    registry_version = data["registry_version"]
    if not isinstance(registry_version, str) or not SEMVER_PATTERN.match(registry_version):
        raise SourceRegistryError(
            f"Source registry registry_version must be semantic version x.y.z: {registry_version!r}"
        )

    for key in ("sources", "evidence_types", "categories", "priority_tiers"):
        if not isinstance(data[key], list):
            raise SourceRegistryError(f"Source registry field {key!r} must be an array.")

    source_ids = set()
    urls = set()
    categories = {item.get("category") for item in data["categories"] if isinstance(item, dict)}
    tiers = {item.get("tier") for item in data["priority_tiers"] if isinstance(item, dict)}

    for index, source in enumerate(data["sources"]):
        label = _source_label(source, index)
        if not isinstance(source, dict):
            raise SourceRegistryError(f"Source registry source #{index + 1} must be an object.")

        missing_source_fields = REQUIRED_SOURCE_FIELDS - set(source)
        if missing_source_fields:
            missing = ", ".join(sorted(missing_source_fields))
            raise SourceRegistryError(f"Source registry {label} missing fields: {missing}")

        source_id = _require_non_empty_string(source, "source_id", label)
        if source_id in source_ids:
            raise SourceRegistryError(f"Source registry duplicate source_id: {source_id}")
        source_ids.add(source_id)

        url = _require_non_empty_string(source, "url", label)
        if url in urls:
            raise SourceRegistryError(f"Source registry duplicate url: {url}")
        urls.add(url)

        for field in ("display_name", "provider", "category", "priority", "ingestion_type", "status"):
            _require_non_empty_string(source, field, label)

        if source["status"] not in VALID_STATUSES:
            raise SourceRegistryError(
                f"Source registry {label} has invalid status {source['status']!r}; "
                f"expected one of {sorted(VALID_STATUSES)}"
            )
        if source["priority"] not in VALID_PRIORITIES:
            raise SourceRegistryError(
                f"Source registry {label} has invalid priority {source['priority']!r}; "
                f"expected one of {sorted(VALID_PRIORITIES)}"
            )
        if source["priority"] not in tiers:
            raise SourceRegistryError(
                f"Source registry {label} priority {source['priority']!r} is not declared in priority_tiers."
            )
        if source["category"] not in categories:
            raise SourceRegistryError(
                f"Source registry {label} category {source['category']!r} is not declared in categories."
            )
        if source["ingestion_type"] != "RSS":
            raise SourceRegistryError(
                f"Source registry {label} uses unsupported ingestion_type {source['ingestion_type']!r}."
            )

        _require_string_list(source, "supported_evidence_types", label, allow_empty=False)
        if source["supported_evidence_types"] != ["Headline"]:
            raise SourceRegistryError(
                f"Source registry {label} supported_evidence_types must be ['Headline'] this sprint."
            )
        _require_string_list(source, "supported_narratives", label, allow_empty=False)
        _require_string_list(source, "supported_groups", label, allow_empty=False)
        _require_positive_int(source, "freshness_threshold_minutes", label)
        _require_positive_int(source, "expected_update_frequency_minutes", label)
        if source["notes"] is not None and not isinstance(source["notes"], str):
            raise SourceRegistryError(f"Source registry {label} notes must be a string or null.")


def _source_label(source, index):
    if isinstance(source, dict) and source.get("source_id"):
        return f"source {source['source_id']!r}"
    return f"source #{index + 1}"


def _require_non_empty_string(source, field, label):
    value = source[field]
    if not isinstance(value, str) or not value.strip():
        raise SourceRegistryError(f"Source registry {label} field {field!r} must be a non-empty string.")
    return value


def _require_string_list(source, field, label, allow_empty):
    value = source[field]
    if not isinstance(value, list) or (not allow_empty and not value):
        raise SourceRegistryError(f"Source registry {label} field {field!r} must be a non-empty array.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise SourceRegistryError(
            f"Source registry {label} field {field!r} must contain only non-empty strings."
        )


def _require_positive_int(source, field, label):
    value = source[field]
    if not isinstance(value, int) or value <= 0:
        raise SourceRegistryError(f"Source registry {label} field {field!r} must be a positive integer.")
