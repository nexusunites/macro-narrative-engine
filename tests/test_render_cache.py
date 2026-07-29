import os
import tempfile
import unittest
from pathlib import Path

from mne import render_cache


class RenderCacheTests(unittest.TestCase):
    def setUp(self):
        render_cache.clear()

    def test_cache_hit_avoids_rereading_unchanged_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            path.write_text("first", encoding="utf-8")
            calls = []

            def loader(candidate):
                calls.append(candidate)
                return candidate.read_text(encoding="utf-8")

            self.assertEqual(render_cache.get_or_load(path, loader), "first")
            self.assertEqual(render_cache.get_or_load(path, loader), "first")
            self.assertEqual(len(calls), 1)

    def test_modified_mtime_invalidates_cached_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            path.write_text("first", encoding="utf-8")
            calls = []

            def loader(candidate):
                calls.append(candidate)
                return candidate.read_text(encoding="utf-8")

            self.assertEqual(render_cache.get_or_load(path, loader), "first")
            original = path.stat()
            path.write_text("second", encoding="utf-8")
            os.utime(
                path,
                ns=(original.st_atime_ns, original.st_mtime_ns + 1_000_000),
            )
            self.assertEqual(render_cache.get_or_load(path, loader), "second")
            self.assertEqual(len(calls), 2)
