import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from mne_test_utils import reload_config
except ImportError:
    from tests.mne_test_utils import reload_config


def reload_config_diagnostics():
    reload_config()
    import mne.config_diagnostics

    return importlib.reload(mne.config_diagnostics)


class ConfigDiagnosticsTests(unittest.TestCase):
    def tearDown(self):
        reload_config()
        import mne.config_diagnostics

        importlib.reload(mne.config_diagnostics)

    def build_report(self, module, **overrides):
        values = {
            "active_data_dir": "/tmp/mne",
            "results_dir": "/tmp/mne/results",
            "headlines_dir": "/tmp/mne/headlines",
            "config_source": "environment_variable",
            "is_portable_default": False,
            "result_file_count": 10,
            "archive_status": "POPULATED",
            "registry_version": "1.0.0",
            "registry_error": None,
            "documented_google_drive_archive": "/tmp/google-drive/MNE-data",
            "documented_google_drive_archive_exists": False,
        }
        values.update(overrides)
        return module.ConfigurationReport(**values)

    def test_env_data_dir_reports_environment_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MNE_DATA_DIR": tmpdir}, clear=False):
                diagnostics = reload_config_diagnostics()

                report = diagnostics.build_configuration_report()

        self.assertEqual(report.config_source, "environment_variable")
        self.assertFalse(report.is_portable_default)

    def test_unset_data_dir_reports_portable_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MNE_DATA_DIR", None)
            diagnostics = reload_config_diagnostics()

            report = diagnostics.build_configuration_report()

        self.assertEqual(report.config_source, "portable_default")
        self.assertTrue(report.is_portable_default)

    def test_empty_results_dir_reports_empty_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MNE_DATA_DIR": tmpdir}, clear=False):
                diagnostics = reload_config_diagnostics()
                Path(tmpdir, "results").mkdir()

                report = diagnostics.build_configuration_report()

        self.assertEqual(report.result_file_count, 0)
        self.assertEqual(report.archive_status, "EMPTY")

    def test_three_result_files_reports_minimal_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MNE_DATA_DIR": tmpdir}, clear=False):
                diagnostics = reload_config_diagnostics()
                results_dir = Path(tmpdir, "results")
                results_dir.mkdir()
                for index in range(3):
                    (results_dir / f"run-{index}.json").write_text("{}", encoding="utf-8")

                report = diagnostics.build_configuration_report()

        self.assertEqual(report.result_file_count, 3)
        self.assertEqual(report.archive_status, "MINIMAL")

    def test_five_result_files_reports_populated_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MNE_DATA_DIR": tmpdir}, clear=False):
                diagnostics = reload_config_diagnostics()
                results_dir = Path(tmpdir, "results")
                results_dir.mkdir()
                for index in range(5):
                    (results_dir / f"run-{index}.json").write_text("{}", encoding="utf-8")

                report = diagnostics.build_configuration_report()

        self.assertEqual(report.result_file_count, 5)
        self.assertEqual(report.archive_status, "POPULATED")

    def test_startup_report_notes_are_state_specific(self):
        diagnostics = reload_config_diagnostics()

        portable = self.build_report(
            diagnostics,
            config_source="portable_default",
            is_portable_default=True,
            archive_status="POPULATED",
        )
        populated = self.build_report(diagnostics, archive_status="POPULATED")
        empty = self.build_report(diagnostics, archive_status="EMPTY", result_file_count=0)
        minimal = self.build_report(diagnostics, archive_status="MINIMAL", result_file_count=3)

        self.assertIn("MNE_DATA_DIR is not set", diagnostics.format_startup_report(portable))
        self.assertNotIn("MNE_DATA_DIR is not set", diagnostics.format_startup_report(populated))
        self.assertIn("no prior runs", diagnostics.format_startup_report(empty))
        self.assertIn("only has 3 prior run(s)", diagnostics.format_startup_report(minimal))
        self.assertNotIn("no prior runs", diagnostics.format_startup_report(populated))
        self.assertNotIn("prior run(s)", diagnostics.format_startup_report(populated))

    def test_startup_report_mentions_documented_archive_only_for_portable_default(self):
        diagnostics = reload_config_diagnostics()

        portable = self.build_report(
            diagnostics,
            config_source="portable_default",
            is_portable_default=True,
            documented_google_drive_archive_exists=True,
        )
        configured = self.build_report(
            diagnostics,
            documented_google_drive_archive_exists=True,
        )

        self.assertIn(
            "MNE_DATA_DIR may not be configured",
            diagnostics.format_startup_report(portable),
        )
        self.assertNotIn(
            "MNE_DATA_DIR may not be configured",
            diagnostics.format_startup_report(configured),
        )

    def test_build_report_detects_documented_archive_when_portable_default_is_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "Google Drive" / "MNE-data"
            archive.mkdir(parents=True)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MNE_DATA_DIR", None)
                diagnostics = reload_config_diagnostics()
                with patch.object(
                    diagnostics,
                    "DOCUMENTED_GOOGLE_DRIVE_ARCHIVE_PATH",
                    archive,
                ):
                    report = diagnostics.build_configuration_report()

        self.assertTrue(report.is_portable_default)
        self.assertEqual(report.documented_google_drive_archive, str(archive))
        self.assertTrue(report.documented_google_drive_archive_exists)
        self.assertIn(
            "MNE_DATA_DIR may not be configured",
            diagnostics.format_startup_report(report),
        )

    def test_registry_error_is_reported_without_raising(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"MNE_DATA_DIR": tmpdir}, clear=False):
                diagnostics = reload_config_diagnostics()
                from mne.source_registry import SourceRegistryError

                with patch.object(
                    diagnostics,
                    "load_source_registry",
                    side_effect=SourceRegistryError("malformed registry"),
                ):
                    report = diagnostics.build_configuration_report()

        self.assertIsNone(report.registry_version)
        self.assertEqual(report.registry_error, "malformed registry")

    def test_dashboard_view_model_includes_configuration_report(self):
        import dashboard

        report = self.build_report(reload_config_diagnostics())
        with patch.object(dashboard, "build_configuration_report", return_value=report):
            view = dashboard.build_view_model(
                {"timestamp": "2026-07-07T12:00:00Z"},
                Path("run.json"),
            )

        self.assertIn("configuration_report", view)
        self.assertEqual(
            view["configuration_report"]["active_data_dir"],
            report.active_data_dir,
        )
        self.assertIn("archive_status", view["configuration_report"])


if __name__ == "__main__":
    unittest.main()
