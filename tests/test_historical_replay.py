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


def backfill_evidence(
    evidence_id,
    title,
    published_at,
    backfill_id="backfill_2020-01-01_2020-01-31_macro_fed_fomc",
    source_id="fed_fomc",
    provider="Federal Reserve",
    accepted=True,
):
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_name": "Federal Reserve",
        "evidence_type": "Headline",
        "timestamp": published_at,
        "title": title,
        "summary": None,
        "url": f"https://example.com/{evidence_id}",
        "metadata": {
            "evidence_origin": "HISTORICAL_BACKFILL",
            "backfill_id": backfill_id,
            "connector_source_id": source_id,
            "raw_id": evidence_id,
            "retrieval_timestamp": "2026-07-15T00:00:00Z",
            "usage_storage_rights": "NORMALIZED_EVIDENCE",
            "provider": provider,
            "category": "Central Bank Communications",
            "source_type": "official_central_bank_statement",
        },
        "accepted": accepted,
        "rejection_reason": None,
        "freshness_state": "UNKNOWN",
        "freshness_age_minutes": None,
        "freshness_checked_at": None,
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

    # -- Historical Backfill Replay Integration -----------------------------

    def test_replay_without_backfill_option_is_unchanged(self):
        request = historical_replay.build_replay_request("2026-07-06")
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [evidence("e1", "Fed rate cut expected", "2026-07-06T09:00:00Z")],
            )
        ]

        output = historical_replay.run_historical_replay(request, historical_records=records)

        self.assertIsNone(request.backfill_id)
        self.assertFalse(request.include_backfilled_evidence)
        metadata = output["replay_metadata"]
        self.assertFalse(metadata["backfilled_evidence_included"])
        self.assertEqual(metadata["backfill_ids_used"], [])
        self.assertEqual(metadata["evidence_sources_used"], ["live_persisted"])
        self.assertEqual(metadata["live_evidence_count"], 1)
        self.assertEqual(metadata["backfilled_evidence_count"], 0)
        self.assertEqual(metadata["total_evidence_count"], 1)
        self.assertEqual(output["evidence_count"], 1)

    def test_build_replay_request_accepts_backfill_id_and_infers_inclusion(self):
        request = historical_replay.build_replay_request(
            "2026-07-06",
            backfill_id="backfill_2026-07-06_macro_fed_fomc",
        )
        self.assertTrue(request.include_backfilled_evidence)
        self.assertEqual(request.backfill_id, "backfill_2026-07-06_macro_fed_fomc")

        explicit = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        self.assertTrue(explicit.include_backfilled_evidence)
        self.assertIsNone(explicit.backfill_id)

    def test_replay_loads_backfilled_evidence_by_backfill_id(self):
        request = historical_replay.build_replay_request(
            "2026-07-06",
            backfill_id="backfill_2026-07-06_macro_fed_fomc",
        )
        fixture = [backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")]

        with patch.object(
            historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture
        ) as mock_loader:
            output = historical_replay.run_historical_replay(request, historical_records=[])

        mock_loader.assert_called_once_with(
            backfill_id="backfill_2026-07-06_macro_fed_fomc",
            requested_date=None,
        )
        self.assertEqual(output["evidence_count"], 1)
        self.assertTrue(output["replay_metadata"]["backfilled_evidence_included"])

    def test_replay_loads_bea_backfill_by_id_and_enforces_cutoff(self):
        backfill_id = "backfill_2020-01-01_2020-03-31_macro_bea_gdp_pce"
        request = historical_replay.build_replay_request("2020-01-31", backfill_id=backfill_id)
        included = backfill_evidence(
            "bea1", "Gross Domestic Product, 4th Quarter 2019", "2020-01-30T13:30:00Z",
            backfill_id=backfill_id, source_id="bea_gdp_pce", provider="BEA",
        )
        future = backfill_evidence(
            "bea2", "Personal Income and Outlays, January 2020", "2020-02-28T13:30:00Z",
            backfill_id=backfill_id, source_id="bea_gdp_pce", provider="BEA",
        )
        for row in (included, future):
            row["source_name"] = "BEA"
            row["metadata"]["category"] = "Economic Data / Growth / Inflation"
        with patch.object(
            historical_replay.historical_backfill, "load_backfilled_evidence",
            return_value=[included, future],
        ) as loader:
            output = historical_replay.run_historical_replay(request, historical_records=[])
        loader.assert_called_once_with(backfill_id=backfill_id, requested_date=None)
        self.assertEqual(output["evidence_count"], 1)
        accepted = output["source_intelligence"]["accepted_evidence"][0]
        self.assertEqual(accepted["evidence_id"], "bea1")
        self.assertEqual(accepted["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(accepted["backfill_id"], backfill_id)

    def test_replay_resolves_backfill_by_date_when_only_include_flag_set(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        fixture = [backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")]

        with patch.object(
            historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture
        ) as mock_loader:
            historical_replay.run_historical_replay(request, historical_records=[])

        mock_loader.assert_called_once_with(backfill_id=None, requested_date="2026-07-06")

    def test_backfilled_evidence_after_cutoff_is_excluded(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        fixture = [
            backfill_evidence("b1", "Included statement", "2026-07-06T19:00:00Z"),
            backfill_evidence("b2", "Future statement", "2026-07-07T19:00:00Z"),
        ]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=[])

        accepted_ids = [row["evidence_id"] for row in output["source_intelligence"]["accepted_evidence"]]
        self.assertIn("b1", accepted_ids)
        self.assertNotIn("b2", accepted_ids)
        self.assertEqual(output["replay_metadata"]["backfilled_evidence_count"], 1)

    def test_backfilled_evidence_before_cutoff_is_included_and_scored(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        fixture = [backfill_evidence("b1", "Fed rate cut and interest rates", "2026-07-06T19:00:00Z")]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=[])

        self.assertEqual(output["evidence_count"], 1)
        self.assertGreater(output["theme_scores"].get("rates", 0), 0)

    def test_missing_backfill_produces_calm_warning_not_exception(self):
        request = historical_replay.build_replay_request(
            "2026-07-06",
            backfill_id="backfill_does_not_exist_macro_fed_fomc",
        )

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=[]):
            output = historical_replay.run_historical_replay(request, historical_records=[])

        self.assertFalse(output["replay_metadata"]["backfilled_evidence_included"])
        self.assertIn(
            "No eligible backfilled evidence was available for this replay.",
            output["replay_metadata"]["warnings"],
        )

    def test_live_and_backfilled_evidence_dedupe_by_evidence_id_live_wins(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [evidence("shared-id", "Live version of this evidence", "2026-07-06T09:00:00Z")],
            )
        ]
        fixture = [backfill_evidence("shared-id", "Backfilled version of this evidence", "2026-07-06T09:00:00Z")]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=records)

        self.assertEqual(output["evidence_count"], 1)
        matching = [
            row for row in output["source_intelligence"]["accepted_evidence"] if row["evidence_id"] == "shared-id"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["title"], "Live version of this evidence")

    def test_replay_metadata_records_backfill_ids_used(self):
        request = historical_replay.build_replay_request(
            "2026-07-06",
            backfill_id="backfill_2026-07-06_macro_fed_fomc",
        )
        fixture = [
            backfill_evidence(
                "b1",
                "Federal Reserve issues FOMC statement",
                "2026-07-06T19:00:00Z",
                backfill_id="backfill_2026-07-06_macro_fed_fomc",
            )
        ]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=[])

        self.assertEqual(
            output["replay_metadata"]["backfill_ids_used"],
            ["backfill_2026-07-06_macro_fed_fomc"],
        )

    def test_replay_metadata_evidence_source_counts(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        records = [
            run_record(
                "2026-07-06T10:00:00Z",
                [evidence("e1", "AI data center investment", "2026-07-06T09:00:00Z")],
            )
        ]
        fixture = [backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=records)

        metadata = output["replay_metadata"]
        self.assertEqual(metadata["live_evidence_count"], 1)
        self.assertEqual(metadata["backfilled_evidence_count"], 1)
        self.assertEqual(metadata["total_evidence_count"], 2)
        self.assertEqual(output["evidence_count"], 2)
        self.assertEqual(sorted(metadata["evidence_sources_used"]), ["historical_backfill", "live_persisted"])

    def test_accepted_evidence_includes_backfilled_record_without_registry_error(self):
        request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
        fixture = [backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")]

        with patch.object(historical_replay.historical_backfill, "load_backfilled_evidence", return_value=fixture):
            output = historical_replay.run_historical_replay(request, historical_records=[])

        records = output["source_intelligence"]["accepted_evidence"]
        backfilled = next(row for row in records if row["evidence_id"] == "b1")
        self.assertEqual(backfilled["evidence_origin"], "HISTORICAL_BACKFILL")
        self.assertEqual(backfilled["backfill_id"], "backfill_2020-01-01_2020-01-31_macro_fed_fomc")
        self.assertEqual(backfilled["provider"], "Federal Reserve")
        # Coverage Intelligence is registry-driven and fed_fomc is not a live
        # registry source; this is an accepted, pre-existing graceful degradation,
        # not a regression introduced by backfill support.
        self.assertNotIn("coverage", output)

    def test_backfill_evidence_files_are_not_modified_by_replay(self):
        with writable_temporary_mne_data_dir() as data_dir:
            backfill_dir = data_dir / "historical_evidence" / "backfill_2026-07-06_macro_fed_fomc"
            backfill_dir.mkdir(parents=True)
            manifest = {
                "backfill_id": "backfill_2026-07-06_macro_fed_fomc",
                "requested_start_date": "2026-07-06",
                "requested_end_date": "2026-07-06",
                "status": "COMPLETE",
                "generated_at": "2026-07-06T20:00:00Z",
            }
            evidence_payload = [
                backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")
            ]
            (backfill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (backfill_dir / "evidence.json").write_text(json.dumps(evidence_payload), encoding="utf-8")
            before = directory_digest(data_dir / "historical_evidence")

            request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
            output = historical_replay.run_historical_replay(request, historical_records=[])
            after = directory_digest(data_dir / "historical_evidence")

            self.assertEqual(before, after)
            self.assertEqual(output["evidence_count"], 1)

    def test_no_backfill_fetching_or_source_network_calls_during_replay(self):
        with writable_temporary_mne_data_dir() as data_dir:
            backfill_dir = data_dir / "historical_evidence" / "backfill_2026-07-06_macro_fed_fomc"
            backfill_dir.mkdir(parents=True)
            manifest = {
                "backfill_id": "backfill_2026-07-06_macro_fed_fomc",
                "requested_start_date": "2026-07-06",
                "requested_end_date": "2026-07-06",
                "status": "COMPLETE",
                "generated_at": "2026-07-06T20:00:00Z",
            }
            evidence_payload = [
                backfill_evidence("b1", "Federal Reserve issues FOMC statement", "2026-07-06T19:00:00Z")
            ]
            (backfill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (backfill_dir / "evidence.json").write_text(json.dumps(evidence_payload), encoding="utf-8")

            request = historical_replay.build_replay_request("2026-07-06", include_backfilled_evidence=True)
            with patch(
                "mne.backfill_sources.fed_fomc.fetch_fed_fomc_records",
                side_effect=AssertionError("connector fetch called during replay"),
            ), patch(
                "mne.rss_fetch.fetch_headlines_from_rss",
                side_effect=AssertionError("live RSS fetch called during replay"),
            ):
                output = historical_replay.run_historical_replay(request, historical_records=[])

            self.assertEqual(output["evidence_count"], 1)


if __name__ == "__main__":
    unittest.main()
