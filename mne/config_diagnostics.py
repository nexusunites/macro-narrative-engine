from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR, HEADLINES_DIR, RESULTS_DIR, data_dir_source
from mne.source_registry import SourceRegistryError, load_source_registry


EMPTY_THRESHOLD = 0
MINIMAL_THRESHOLD = 5

README_CONFIG_SECTION = "README.md -> 'Runtime Data Storage' section"
DOCUMENTED_GOOGLE_DRIVE_ARCHIVE_PATH = Path.home() / "Google Drive" / "MNE-data"


@dataclass(frozen=True)
class ConfigurationReport:
    active_data_dir: str
    results_dir: str
    headlines_dir: str
    config_source: str
    is_portable_default: bool
    result_file_count: int
    archive_status: str
    registry_version: str | None
    registry_error: str | None
    documented_google_drive_archive: str | None
    documented_google_drive_archive_exists: bool

    def to_dict(self):
        return {
            "active_data_dir": self.active_data_dir,
            "results_dir": self.results_dir,
            "headlines_dir": self.headlines_dir,
            "config_source": self.config_source,
            "is_portable_default": self.is_portable_default,
            "result_file_count": self.result_file_count,
            "archive_status": self.archive_status,
            "registry_version": self.registry_version,
            "registry_error": self.registry_error,
            "documented_google_drive_archive": self.documented_google_drive_archive,
            "documented_google_drive_archive_exists": self.documented_google_drive_archive_exists,
        }


def _count_result_files(results_dir: Path) -> int:
    try:
        return sum(1 for _ in results_dir.glob("*.json"))
    except OSError:
        return 0


def _classify_archive(count: int) -> str:
    if count <= EMPTY_THRESHOLD:
        return "EMPTY"
    if count < MINIMAL_THRESHOLD:
        return "MINIMAL"
    return "POPULATED"


def _registry_version_safe():
    try:
        return load_source_registry().registry_version, None
    except SourceRegistryError as error:
        return None, str(error)


def _documented_google_drive_archive_safe() -> tuple[str | None, bool]:
    path = DOCUMENTED_GOOGLE_DRIVE_ARCHIVE_PATH
    try:
        return str(path), path.exists()
    except OSError:
        return str(path), False


def build_configuration_report() -> ConfigurationReport:
    count = _count_result_files(RESULTS_DIR)
    registry_version, registry_error = _registry_version_safe()
    source = data_dir_source()
    archive_path, archive_exists = _documented_google_drive_archive_safe()
    return ConfigurationReport(
        active_data_dir=str(DATA_DIR),
        results_dir=str(RESULTS_DIR),
        headlines_dir=str(HEADLINES_DIR),
        config_source=source,
        is_portable_default=source == "portable_default",
        result_file_count=count,
        archive_status=_classify_archive(count),
        registry_version=registry_version,
        registry_error=registry_error,
        documented_google_drive_archive=archive_path,
        documented_google_drive_archive_exists=archive_exists,
    )


def format_startup_report(report: ConfigurationReport) -> str:
    lines = [
        "=== MNE Configuration ===",
        f"Active Data Directory : {report.active_data_dir}",
        f"Configuration Source  : {report.config_source}",
        f"Results Directory     : {report.results_dir}",
        f"Headlines Directory   : {report.headlines_dir}",
    ]
    if report.registry_version:
        lines.append(f"Registry Version      : {report.registry_version}")

    if report.is_portable_default:
        lines.append("")
        lines.append(
            "NOTE: MNE_DATA_DIR is not set, so MNE is using its portable default "
            "directory. Historical Google Drive data will NOT be loaded from here."
        )
        lines.append(f"See {README_CONFIG_SECTION} to point MNE at your existing archive.")
        if report.documented_google_drive_archive_exists:
            lines.append(
                "A documented Google Drive archive appears to exist at "
                f"{report.documented_google_drive_archive}. If that is your intended "
                "archive, MNE_DATA_DIR may not be configured."
            )

    if report.archive_status == "EMPTY":
        lines.append("")
        lines.append(
            "NOTE: This data directory has no prior runs. MNE is starting a fresh archive."
        )
    elif report.archive_status == "MINIMAL":
        lines.append("")
        lines.append(
            f"NOTE: This data directory only has {report.result_file_count} prior run(s). "
            "History/trend views will be sparse until more runs accumulate."
        )

    lines.append("=========================")
    return "\n".join(lines)
