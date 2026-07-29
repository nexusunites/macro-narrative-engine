"""Run MNE locally with optional pull and success-gated backup push."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mne.data_sync import SyncConfigurationError, pull, push


PUSH_FAILURE_EXIT_CODE = 2


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Optionally pull, run MNE, then push after success."
    )
    parser.add_argument("--pull", action="store_true", help="Pull before running MNE.")
    return parser.parse_known_args(args)


def main(args=None) -> int:
    wrapper_args, engine_args = parse_args(args)

    if wrapper_args.pull:
        try:
            pull_result = pull()
        except SyncConfigurationError as error:
            print(error, file=sys.stderr)
            return 1
        if pull_result.exit_code:
            print("Pull failed; MNE was not run.", file=sys.stderr)
            return pull_result.exit_code

    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *engine_args],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode

    if not os.environ.get("MNE_SYNC_DIR"):
        print("MNE_SYNC_DIR is not set; successful run was not pushed.")
        return 0

    try:
        push_result = push()
    except SyncConfigurationError as error:
        print(error, file=sys.stderr)
        return PUSH_FAILURE_EXIT_CODE
    if push_result.exit_code:
        print("MNE completed successfully, but push failed.", file=sys.stderr)
        return PUSH_FAILURE_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
