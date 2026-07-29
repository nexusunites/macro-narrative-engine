"""Command-line interface for non-destructive MNE data synchronization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mne.data_sync import SyncConfigurationError, pull, push, status_lines


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Synchronize MNE runtime data.")
    parser.add_argument("command", choices=("status", "pull", "push"))
    return parser.parse_args(args)


def main(args=None) -> int:
    command = parse_args(args).command
    try:
        if command == "status":
            for line in status_lines():
                print(line)
            return 0

        result = pull() if command == "pull" else push()
        print(
            f"{command}: {result.copied} copied, {result.updated} updated, "
            f"{result.skipped} unchanged, {result.failed} failed"
        )
        return result.exit_code
    except SyncConfigurationError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
