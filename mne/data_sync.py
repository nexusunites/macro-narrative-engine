"""Non-destructive synchronization for MNE runtime data."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import config


MISSING_SYNC_DIR_MESSAGE = (
    "MNE_SYNC_DIR is not set — set it to your shared backup directory to enable sync"
)


class SyncConfigurationError(ValueError):
    """Raised when sync paths are missing or unsafe."""


@dataclass(frozen=True)
class SyncPaths:
    data_dir: Path
    sync_dir: Path


@dataclass
class SyncResult:
    copied: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def changed(self) -> int:
        return self.copied + self.updated

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


def get_sync_paths() -> SyncPaths:
    """Resolve and validate the active and backup data directories."""
    sync_value = os.environ.get("MNE_SYNC_DIR")
    if not sync_value:
        raise SyncConfigurationError(MISSING_SYNC_DIR_MESSAGE)

    paths = SyncPaths(
        data_dir=config.get_data_dir().expanduser().resolve(),
        sync_dir=Path(sync_value).expanduser().resolve(),
    )
    validate_distinct_paths(paths.data_dir, paths.sync_dir)
    return paths


def validate_distinct_paths(first: Path, second: Path) -> None:
    """Refuse equal or nested paths, which could recursively copy into themselves."""
    first = first.expanduser().resolve()
    second = second.expanduser().resolve()
    if first == second:
        raise SyncConfigurationError(
            f"Sync refused: MNE_DATA_DIR and MNE_SYNC_DIR resolve to the same path: {first}"
        )
    if first in second.parents or second in first.parents:
        raise SyncConfigurationError(
            "Sync refused: MNE_DATA_DIR and MNE_SYNC_DIR must not be nested "
            f"({first}; {second})"
        )


def is_transient(path: Path) -> bool:
    """Return whether a path is a known transient artifact."""
    return path.name == ".DS_Store" or path.name.startswith(".tmp")


def iter_files(root: Path) -> Iterable[Path]:
    """Yield non-transient files below root in deterministic order."""
    for current, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name for name in directory_names if not is_transient(Path(name))
        )
        for file_name in sorted(file_names):
            if not is_transient(Path(file_name)):
                yield Path(current) / file_name


def files_differ(source: Path, destination: Path) -> bool:
    """Compare the handoff-defined size and nanosecond mtime tuple."""
    source_stat = source.stat()
    destination_stat = destination.stat()
    return (source_stat.st_size, source_stat.st_mtime_ns) != (
        destination_stat.st_size,
        destination_stat.st_mtime_ns,
    )


def count_pending(source: Path, destination: Path) -> int:
    """Count files that would be copied or updated."""
    if not source.is_dir():
        return 0

    pending = 0
    for source_file in iter_files(source):
        relative_path = source_file.relative_to(source)
        destination_file = destination / relative_path
        try:
            if not destination_file.is_file() or files_differ(
                source_file, destination_file
            ):
                pending += 1
        except OSError:
            # Status is advisory. If metadata cannot be read, copy when in doubt.
            pending += 1
    return pending


def directory_summary(root: Path) -> list[tuple[str, int, int]]:
    """Return file and byte counts grouped by top-level directory."""
    if not root.is_dir():
        return []

    totals: dict[str, list[int]] = {}
    for file_path in iter_files(root):
        relative_path = file_path.relative_to(root)
        group = relative_path.parts[0] if len(relative_path.parts) > 1 else "."
        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0
        totals.setdefault(group, [0, 0])
        totals[group][0] += 1
        totals[group][1] += size
    return [
        (group, values[0], values[1])
        for group, values in sorted(totals.items())
    ]


def sync_directories(
    source: Path,
    destination: Path,
    *,
    report: Callable[[str], None] = print,
) -> SyncResult:
    """Copy new and changed files without deleting destination content."""
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    validate_distinct_paths(source, destination)
    if not source.is_dir():
        raise SyncConfigurationError(f"Sync source directory does not exist: {source}")

    result = SyncResult()
    for source_file in iter_files(source):
        relative_path = source_file.relative_to(source)
        destination_file = destination / relative_path
        try:
            destination_exists = destination_file.is_file()
            if destination_exists and not files_differ(source_file, destination_file):
                result.skipped += 1
                continue
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
            if destination_exists:
                result.updated += 1
            else:
                result.copied += 1
        except OSError as error:
            result.failed += 1
            report(f"Failed to sync {source_file}: {error}")
    return result


def pull(*, report: Callable[[str], None] = print) -> SyncResult:
    paths = get_sync_paths()
    return sync_directories(paths.sync_dir, paths.data_dir, report=report)


def push(*, report: Callable[[str], None] = print) -> SyncResult:
    paths = get_sync_paths()
    return sync_directories(paths.data_dir, paths.sync_dir, report=report)


def status_lines() -> list[str]:
    paths = get_sync_paths()
    lines = [
        f"MNE_DATA_DIR: {paths.data_dir}",
        f"MNE_DATA_DIR exists: {paths.data_dir.is_dir()}",
        f"MNE_SYNC_DIR: {paths.sync_dir}",
        f"MNE_SYNC_DIR exists: {paths.sync_dir.is_dir()}",
    ]
    for label, root in (
        ("local", paths.data_dir),
        ("sync", paths.sync_dir),
    ):
        summaries = directory_summary(root)
        if not summaries:
            lines.append(f"{label} contents: no files")
        else:
            for group, file_count, byte_count in summaries:
                lines.append(
                    f"{label} {group}: {file_count} file(s), {byte_count} byte(s)"
                )
    lines.extend(
        (
            f"pull would copy or update: {count_pending(paths.sync_dir, paths.data_dir)} file(s)",
            f"push would copy or update: {count_pending(paths.data_dir, paths.sync_dir)} file(s)",
        )
    )
    return lines
