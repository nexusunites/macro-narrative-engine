import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mne import data_sync
from scripts import run_mne, sync_data


class DataSyncPathTests(unittest.TestCase):
    def test_missing_data_dir_uses_config_default_resolution(self):
        default_dir = Path.home() / ".mne" / "data"
        with patch.dict(
            os.environ, {"MNE_SYNC_DIR": "/tmp/mne-sync-test"}, clear=True
        ), patch.object(data_sync.config, "get_data_dir", return_value=default_dir):
            paths = data_sync.get_sync_paths()

        self.assertEqual(paths.data_dir, default_dir.resolve())

    def test_missing_sync_dir_diagnostic_for_each_command(self):
        for command in ("status", "pull", "push"):
            with self.subTest(command=command), patch.dict(os.environ, {}, clear=True):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    exit_code = sync_data.main([command])
                self.assertNotEqual(exit_code, 0)
                self.assertEqual(
                    stderr.getvalue().strip(), data_sync.MISSING_SYNC_DIR_MESSAGE
                )

    def test_same_resolved_path_is_refused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(data_sync.SyncConfigurationError):
                data_sync.validate_distinct_paths(root, root / ".." / root.name)

    def test_nested_paths_are_refused_in_both_directions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            for first, second in ((root, nested), (nested, root)):
                with self.subTest(first=first, second=second):
                    with self.assertRaises(data_sync.SyncConfigurationError):
                        data_sync.validate_distinct_paths(first, second)

    def test_missing_source_is_refused_without_creating_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "missing"
            destination = root / "destination"
            with self.assertRaisesRegex(
                data_sync.SyncConfigurationError, "does not exist"
            ):
                data_sync.sync_directories(source, destination)
            self.assertFalse(destination.exists())


class DataSyncCopyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_initial_recursive_copy_including_nested_directories(self):
        (self.source / "top.json").write_text("top", encoding="utf-8")
        nested = self.source / "results" / "daily"
        nested.mkdir(parents=True)
        (nested / "run.json").write_text("nested", encoding="utf-8")

        result = data_sync.sync_directories(self.source, self.destination)

        self.assertEqual(result.copied, 2)
        self.assertEqual(
            (self.destination / "results" / "daily" / "run.json").read_text(),
            "nested",
        )

    def test_changed_file_is_updated(self):
        self.destination.mkdir()
        source_file = self.source / "run.json"
        destination_file = self.destination / "run.json"
        source_file.write_text("new value", encoding="utf-8")
        destination_file.write_text("old", encoding="utf-8")

        result = data_sync.sync_directories(self.source, self.destination)

        self.assertEqual(result.updated, 1)
        self.assertEqual(destination_file.read_text(), "new value")

    def test_unchanged_file_is_skipped(self):
        self.destination.mkdir()
        source_file = self.source / "run.json"
        destination_file = self.destination / "run.json"
        source_file.write_text("same", encoding="utf-8")
        destination_file.write_text("same", encoding="utf-8")
        source_stat = source_file.stat()
        os.utime(
            destination_file,
            ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
        )

        with patch.object(data_sync.shutil, "copy2") as copy:
            result = data_sync.sync_directories(self.source, self.destination)

        self.assertEqual(result.skipped, 1)
        copy.assert_not_called()

    def test_destination_only_file_is_preserved(self):
        self.destination.mkdir()
        destination_only = self.destination / "destination-only.json"
        destination_only.write_text("preserve me", encoding="utf-8")
        (self.source / "source.json").write_text("copy me", encoding="utf-8")

        data_sync.sync_directories(self.source, self.destination)

        self.assertEqual(destination_only.read_text(), "preserve me")

    def test_transient_artifacts_are_excluded(self):
        (self.source / ".DS_Store").write_text("skip", encoding="utf-8")
        (self.source / ".tmp-upload").write_text("skip", encoding="utf-8")
        transient_directory = self.source / ".tmp-work"
        transient_directory.mkdir()
        (transient_directory / "inside.json").write_text("skip", encoding="utf-8")
        (self.source / "keep.json").write_text("keep", encoding="utf-8")

        result = data_sync.sync_directories(self.source, self.destination)

        self.assertEqual(result.copied, 1)
        self.assertFalse((self.destination / ".DS_Store").exists())
        self.assertFalse((self.destination / ".tmp-upload").exists())
        self.assertFalse((self.destination / ".tmp-work").exists())

    def test_per_file_failure_is_contained_and_returns_nonzero(self):
        first = self.source / "first.json"
        second = self.source / "second.json"
        first.write_text("first", encoding="utf-8")
        second.write_text("second", encoding="utf-8")
        real_copy2 = data_sync.shutil.copy2

        def failing_copy(source, destination):
            if Path(source).name == "first.json":
                raise OSError("Drive timed out")
            return real_copy2(source, destination)

        reports = []
        with patch.object(data_sync.shutil, "copy2", side_effect=failing_copy):
            result = data_sync.sync_directories(
                self.source, self.destination, report=reports.append
            )

        self.assertEqual(result.failed, 1)
        self.assertNotEqual(result.exit_code, 0)
        self.assertTrue((self.destination / "second.json").exists())
        self.assertIn("Drive timed out", reports[0])
        self.assertIn("first.json", reports[0])

    def test_status_reports_paths_counts_bytes_and_pending_directions(self):
        self.destination.mkdir()
        (self.source / "results").mkdir()
        (self.source / "results" / "run.json").write_bytes(b"1234")
        (self.destination / "reports").mkdir()
        (self.destination / "reports" / "brief.txt").write_bytes(b"12")
        with patch.object(
            data_sync,
            "get_sync_paths",
            return_value=data_sync.SyncPaths(
                self.source.resolve(), self.destination.resolve()
            ),
        ):
            output = "\n".join(data_sync.status_lines())

        self.assertIn(f"MNE_DATA_DIR: {self.source.resolve()}", output)
        self.assertIn(f"MNE_SYNC_DIR: {self.destination.resolve()}", output)
        self.assertIn("local results: 1 file(s), 4 byte(s)", output)
        self.assertIn("sync reports: 1 file(s), 2 byte(s)", output)
        self.assertIn("pull would copy or update: 1 file(s)", output)
        self.assertIn("push would copy or update: 1 file(s)", output)

    def test_pull_and_push_use_expected_directions(self):
        paths = data_sync.SyncPaths(self.destination, self.source)
        (self.source / "from-sync.json").write_text("pull", encoding="utf-8")
        with patch.object(data_sync, "get_sync_paths", return_value=paths):
            pull_result = data_sync.pull()
        self.assertEqual(pull_result.copied, 1)
        self.assertTrue((self.destination / "from-sync.json").exists())

        (self.destination / "from-local.json").write_text("push", encoding="utf-8")
        with patch.object(data_sync, "get_sync_paths", return_value=paths):
            push_result = data_sync.push()
        self.assertEqual(push_result.copied, 1)
        self.assertTrue((self.source / "from-local.json").exists())


class RunMneWrapperTests(unittest.TestCase):
    def test_engine_failure_propagates_and_suppresses_push(self):
        with patch.dict(os.environ, {"MNE_SYNC_DIR": "/backup"}, clear=True), patch.object(
            run_mne.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=7),
        ), patch.object(run_mne, "push") as push:
            exit_code = run_mne.main(["--mode", "macro"])

        self.assertEqual(exit_code, 7)
        push.assert_not_called()

    def test_push_occurs_after_success(self):
        events = []

        def engine(*args, **kwargs):
            events.append("engine")
            return SimpleNamespace(returncode=0)

        def push():
            events.append("push")
            return data_sync.SyncResult(copied=1)

        with patch.dict(os.environ, {"MNE_SYNC_DIR": "/backup"}, clear=True), patch.object(
            run_mne.subprocess, "run", side_effect=engine
        ), patch.object(run_mne, "push", side_effect=push):
            exit_code = run_mne.main([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["engine", "push"])

    def test_push_failure_after_success_has_distinct_nonzero_exit(self):
        with patch.dict(os.environ, {"MNE_SYNC_DIR": "/backup"}, clear=True), patch.object(
            run_mne.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0),
        ), patch.object(
            run_mne, "push", return_value=data_sync.SyncResult(failed=1)
        ):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = run_mne.main([])

        self.assertEqual(exit_code, run_mne.PUSH_FAILURE_EXIT_CODE)
        self.assertIn("push failed", stderr.getvalue())

    def test_pull_failure_aborts_before_engine(self):
        with patch.object(
            run_mne, "pull", return_value=data_sync.SyncResult(failed=1)
        ), patch.object(run_mne.subprocess, "run") as engine:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = run_mne.main(["--pull"])

        self.assertNotEqual(exit_code, 0)
        engine.assert_not_called()
        self.assertIn("not run", stderr.getvalue())

    def test_unset_sync_dir_runs_engine_and_skips_push(self):
        stdout = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(
            run_mne.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0),
        ), patch.object(run_mne, "push") as push, redirect_stdout(stdout):
            exit_code = run_mne.main([])

        self.assertEqual(exit_code, 0)
        push.assert_not_called()
        self.assertIn("not set", stdout.getvalue())
        self.assertIn("not pushed", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
