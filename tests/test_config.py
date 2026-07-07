import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from mne_test_utils import reload_config, temporary_mne_data_dir
except ImportError:
    from tests.mne_test_utils import reload_config, temporary_mne_data_dir


class ConfigDataDirTests(unittest.TestCase):
    def tearDown(self):
        reload_config()

    def test_env_data_dir_is_respected_and_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first"
            second = Path(tmpdir) / "second"
            with patch.dict(os.environ, {"MNE_DATA_DIR": str(first)}, clear=False):
                config = reload_config()

                self.assertEqual(config.DATA_DIR, first.resolve())
                self.assertEqual(config.get_data_dir(), first.resolve())

                os.environ["MNE_DATA_DIR"] = str(second)
                self.assertEqual(config.get_data_dir(), first.resolve())

    def test_import_without_env_does_not_create_default_directory(self):
        with tempfile.TemporaryDirectory() as tmp_home:
            env = os.environ.copy()
            env.pop("MNE_DATA_DIR", None)
            env["HOME"] = tmp_home
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

            script = (
                "from pathlib import Path\n"
                "import config\n"
                "default_dir = Path.home() / '.mne' / 'data'\n"
                "assert config.DATA_DIR == default_dir\n"
                "assert not default_dir.exists()\n"
            )
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                env=env,
                cwd=Path(__file__).resolve().parents[1],
            )

    def test_ensure_data_dir_creates_nested_directory_explicitly(self):
        with temporary_mne_data_dir() as data_dir:
            config = reload_config()

            self.assertFalse(data_dir.exists())
            self.assertEqual(config.ensure_data_dir(), data_dir.resolve())
            self.assertTrue(data_dir.is_dir())
            self.assertEqual(config.ensure_data_dir(), data_dir.resolve())

    def test_ensure_data_dir_failure_message_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            blocking_file = Path(tmpdir) / "not-a-directory"
            blocking_file.write_text("blocked", encoding="utf-8")
            data_dir = blocking_file / "child"

            with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
                config = reload_config()

                with self.assertRaises(RuntimeError) as raised:
                    config.ensure_data_dir()

            message = str(raised.exception)
            self.assertIn(str(data_dir.resolve()), message)
            self.assertIn("MNE_DATA_DIR", message)


if __name__ == "__main__":
    unittest.main()
