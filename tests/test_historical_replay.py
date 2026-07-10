import hashlib
import importlib
import json
import os
import shutil
import unittest
import uuid
from datetime import date
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch

from mne import historical_replay


ANALYTICAL_FIELDS = (
    "evidence_count",
    "source_count",
    "taxonomy_version",
    "registry_version",
    "theme_scores",
    "group_scores",
    "dominant_theme",
    "dominant_group",
    "coverage",
    "source_intelligence",
    "theme_counts",
    "matched_headlines",
    "theme_match_audit",
    "examples",
)


def evidence(
    evidence_id,
    title,
    published_at,
    source_id="cnbc-top-news",
    accepted=True,
):
    return {
        "evidence_id": evidence_id,
        "title": title,
        "source_id": source_id,
        "source_name": source_id,
        "evidence_type": "Headline",
        "published_at": published_at,
        "timestamp": published_at,
        "url": f"https://example.com/{evidence_id}",
        "accepted": accepted,
    }


def run_record(timestamp, accepted_evidence):
    return {
        "run": {
            "timestamp": timestamp,
            "source_intelligence": {
                "accepted_evidence": accepted_evidence,
            },
        }
    }


def write_run(results_dir, stamp, accepted_evidence, extra=None):
    run = {
        "timestamp": stamp,
        "source_intelligence": {
            "accepted_evidence": accepted_evidence,
        },
    }
    if extra:
        run.update(extra)
    path = results_dir / f"{stamp}.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    return path


def directory_digest(path):
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


@contextmanager
def writable_temporary_mne_data_dir():
    workspace_tmp = Path(".tmp_mne_data")
    workspace_tmp.mkdir(exist_ok=True)
    tmpdir = workspace_tmp / f"historical_replay_{uuid.uuid4().hex}"
    tmpdir.mkdir()
    data_dir = tmpdir / "mne-data"
    with patch.dict(os.environ, {"MNE_DATA_DIR": str(data_dir)}, clear=False):
        importlib.reload(historical_replay.config)
        try:
            yield data_dir
        finally:
            importlib.reload(historical_replay.config)
            shutil.rmtree(tmpdir, ignore_errors=True)


class HistoricalReplayTests(unittest.TestCase):
    def test_replay_request_creation_normalizes_and_rejects_malformed_input(self):
        request = historical_replay.build_replay_request(date(2026, 7, 6))

        self.assertEqual(request.replay_date, "2026-07-06")
        self.assertEqual(request.mode, "macro")
        self.assertEqual(request.evidence_cutoff, "2026-07-06T23:59:59.999999Z")
        self.assertEqual(request.replay_id, "replay_2026-07-06_macro")
        self.assertEqual(
            historical_replay.replay_output_filename(request),
            "replay_2026-07-06_macro.json",
        )
        self.assertEqual(
            historical_replay.build_replay_request(
                "2026-07-06",
                evidence_cutoff="2026-07-06T12:30:00Z",
            ).evidence_cutoff,
            "2026-07-06T12:30:00Z",
        )

        with self.assertRaises(ValueError):
            historical_replay.build_replay_request("July 6")
        with self.assertRaises(ValueError):
            historical_replay.build_replay_request("2026-07-06", mode="micro")

    def test_evidence_cutoff_enforces_publication_and_knowledge_boundaries(self):
        request = historical_replay.build_replay_request("2026-07-06")
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [
                    evidence("included", "AI data center expansion", "2026-07-06T09:00:00Z"),
                    evidence("future-published", "AI chip future", "2026-07-07T09:00:00Z"),
                ],
            ),
            run_record(
                "2026-07-07T10:00:00Z",
                [
                    evidence("post-cutoff-run", "Fed rate cut odds", "2026-07-06T11:00:00Z"),
                ],
            ),
        ]

        selected = historical_replay.select_historical_evidence(records, request)

        self.assertEqual([item["evidence_id"] for item in selected], ["included"])

    def test_rejected_unknown_and_duplicate_evidence_are_excluded(self):
        request = historical_replay.build_replay_request("2026-07-06")
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [
                    evidence("duplicate", "AI data center first", "2026-07-06T09:00:00Z"),
                    evidence("rejected", "Fed rates rejected", "2026-07-06T09:05:00Z", accepted=False),
                    {
                        "evidence_id": "unknown-timestamp",
                        "title": "Oil headline",
                        "source_id": "cnbc-top-news",
                        "accepted": True,
                    },
                ],
            ),
            run_record(
                "2026-07-06T11:00:00Z",
                [
                    evidence("duplicate", "AI data center second", "2026-07-06T09:30:00Z"),
                    evidence("complete", "Inflation and CPI report", "2026-07-06T09:40:00Z"),
                ],
            ),
        ]

        selected = historical_replay.select_historical_evidence(records, request)

        self.assertEqual([item["evidence_id"] for item in selected], ["duplicate", "complete"])
        self.assertEqual(selected[0]["title"], "AI data center first")

    def test_replay_persists_under_replay_storage_without_modifying_live_results(self):
        with writable_temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2026-07-06_100000",
                [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
            )
            before = directory_digest(results_dir)

            request = historical_replay.build_replay_request("2026-07-06")
            output = historical_replay.run_historical_replay(request)
            path = historical_replay.persist_historical_replay(output)
            after = directory_digest(results_dir)

            self.assertEqual(before, after)
            self.assertEqual(path.parent.name, "replays")
            self.assertTrue(path.name.startswith("replay_2026-07-06_macro"))
            self.assertTrue(path.exists())

    def test_metadata_includes_cutoff_selection_rule_and_future_evidence_flag(self):
        request = historical_replay.build_replay_request("2026-07-06")
        output = historical_replay.run_historical_replay(
            request,
            historical_records=[
                run_record(
                    "2026-07-06T10:00:00Z",
                    [evidence("e1", "Fed rate cut expected", "2026-07-06T09:00:00Z")],
                )
            ],
        )

        metadata = output["replay_metadata"]
        self.assertEqual(output["evidence_cutoff"], "2026-07-06T23:59:59.999999Z")
        self.assertTrue(metadata["future_evidence_excluded"])
        self.assertIn("published_at", metadata["evidence_selection_rule"])
        self.assertFalse(metadata["live_run_source"])

    def test_same_inputs_produce_identical_analytical_outputs(self):
        request = historical_replay.build_replay_request("2026-07-06")
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [
                    evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z"),
                    evidence("e2", "Fed rate cut and interest rates", "2026-07-06T09:05:00Z"),
                ],
            )
        ]

        first = historical_replay.run_historical_replay(request, historical_records=records)
        second = historical_replay.run_historical_replay(request, historical_records=records)

        self.assertEqual(first["replay_id"], second["replay_id"])
        for field in ANALYTICAL_FIELDS:
            self.assertEqual(first.get(field), second.get(field), field)
        self.assertNotEqual(first["generated_at"], "")

    def test_empty_evidence_produces_valid_warned_replay(self):
        request = historical_replay.build_replay_request("2026-07-06")
        output = historical_replay.run_historical_replay(request, historical_records=[])

        self.assertEqual(output["evidence_count"], 0)
        self.assertEqual(output["theme_scores"]["ai"], 0)
        self.assertEqual(output["group_scores"], {})
        self.assertIsNone(output["dominant_theme"])
        self.assertIsNone(output["dominant_group"])
        self.assertIn("No accepted evidence", output["replay_metadata"]["warnings"][0])

    def test_replay_does_not_call_live_rss_fetch(self):
        request = historical_replay.build_replay_request("2026-07-06")
        with patch("mne.rss_fetch.fetch_headlines_from_rss", side_effect=AssertionError("network fetch called")):
            output = historical_replay.run_historical_replay(
                request,
                historical_records=[
                    run_record(
                        "2026-07-06T10:00:00Z",
                        [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
                    )
                ],
            )

        self.assertEqual(output["evidence_count"], 1)

    def test_config_portability_uses_mne_data_dir_for_history_and_replays(self):
        with writable_temporary_mne_data_dir() as data_dir:
            results_dir = data_dir / "results"
            results_dir.mkdir(parents=True)
            write_run(
                results_dir,
                "2026-07-06_100000",
                [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
            )

            path, output = historical_replay.run_and_persist_historical_replay("2026-07-06")

            self.assertEqual(output["evidence_count"], 1)
            self.assertEqual(path.parent, (data_dir / "replays").resolve())

    def test_cross_validation_matches_known_live_run_scores_from_same_accepted_evidence(self):
        accepted = [
            evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z"),
            evidence("e2", "Nvidia AI chips demand", "2026-07-06T09:05:00Z"),
            evidence("e3", "Fed rate cut and interest rates", "2026-07-06T09:10:00Z"),
        ]
        themes, _taxonomy_version = historical_replay.load_themes("themes.txt", include_version=True)
        analysis = historical_replay.analyze_themes(
            [item["title"] for item in accepted],
            themes,
            include_attribution=True,
        )
        live_theme_scores = analysis[3]
        live_group_scores = historical_replay.compute_group_scores(live_theme_scores)
        request = historical_replay.build_replay_request("2026-07-06")

        output = historical_replay.run_historical_replay(
            request,
            historical_records=[run_record("2026-07-06T10:00:00Z", accepted)],
        )

        self.assertEqual(output["theme_scores"], live_theme_scores)
        self.assertEqual(output["group_scores"], live_group_scores)


if __name__ == "__main__":
    unittest.main()
