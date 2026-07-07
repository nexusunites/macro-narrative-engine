import importlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def temporary_mne_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "mne-data"
        with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
            reload_config()
            try:
                yield data_dir
            finally:
                reload_config()


def reload_config():
    import config

    return importlib.reload(config)
