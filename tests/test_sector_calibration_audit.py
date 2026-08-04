import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_sector_observations import audit_sector_observations


class SectorCalibrationAuditTests(unittest.TestCase):
    def test_audit_is_deterministic_and_excludes_malformed_observations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.json").write_text(json.dumps({"market_snapshot": {"technology": {"pct_change": 1.2, "observed_at": "2026-08-04T20:00:00Z"}}}))
            (root / "b.json").write_text(json.dumps({"market_snapshot": {"energy": {"pct_change": "bad", "observed_at": "2026-08-04T20:00:00Z"}, "materials": {"pct_change": .2, "observed_at": "bad"}}}))
            (root / "c.json").write_text("not-json")
            expected = {"run_files": 3, "sector_entries": 3, "valid_sector_observations": 1}
            self.assertEqual(expected, audit_sector_observations(root))
            self.assertEqual(expected, audit_sector_observations(root))


if __name__ == "__main__":
    unittest.main()
