import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from mne.narrative_relationships import (
    DIRECTIONALITIES,
    RELATIONSHIP_TYPES,
    STRENGTHS,
    NarrativeRelationshipError,
    build_relationship_adjacency,
    build_relationship_summary,
    get_display_relationships,
    get_relationships_for_group,
    load_narrative_relationships,
    normalize_relationship,
    relationship_exists,
    validate_relationship_config,
)


def record(**changes):
    value = {
        "source_group": "Macro Pressure",
        "target_group": "AI / Tech Growth",
        "relationship_type": "TRANSMISSION",
        "directionality": "SOURCE_TO_TARGET",
        "strength": "STRONG",
        "public_label": "Financial conditions connection",
        "explanation": "Interest-rate pressure can weigh on growth-sensitive narratives.",
        "display_enabled": True,
        "evidence_basis": "CURATED_DOMAIN_LOGIC",
    }
    value.update(changes)
    return value


class NarrativeRelationshipTests(unittest.TestCase):
    def test_checked_in_config_loads_as_immutable_records(self):
        config = load_narrative_relationships()
        self.assertEqual(config.version, "1.0.0")
        self.assertEqual(len(config.relationships), 3)
        with self.assertRaises(FrozenInstanceError):
            config.relationships[0].strength = "LIMITED"

    def test_schema_enums_are_exact(self):
        self.assertEqual(len(RELATIONSHIP_TYPES), 7)
        self.assertEqual(DIRECTIONALITIES, {"SOURCE_TO_TARGET", "TARGET_TO_SOURCE", "BIDIRECTIONAL"})
        self.assertEqual(STRENGTHS, {"STRONG", "MODERATE", "LIMITED"})

    def test_all_existing_groups_validate_including_unconnected_geopolitical_risk(self):
        config = validate_relationship_config({"version": "1.2.3", "relationships": [record(target_group="Geopolitical Risk")]})
        self.assertEqual(config.relationships[0].target_group, "Geopolitical Risk")

    def test_invalid_config_fails_closed(self):
        invalid_cases = [
            {"version": "1", "relationships": []},
            {"version": "1.0.0", "relationships": "wrong"},
            {"version": "1.0.0", "relationships": [record(source_group="Unknown")]},
            {"version": "1.0.0", "relationships": [record(target_group="Macro Pressure")]},
            {"version": "1.0.0", "relationships": [record(relationship_type="RELATED")]},
            {"version": "1.0.0", "relationships": [record(directionality="BOTH")]},
            {"version": "1.0.0", "relationships": [record(strength="HIGH")]},
            {"version": "1.0.0", "relationships": [record(public_label="")]},
            {"version": "1.0.0", "relationships": [record(explanation=None)]},
            {"version": "1.0.0", "relationships": [record(display_enabled="yes")]},
        ]
        for case in invalid_cases:
            with self.subTest(case=case), self.assertRaises(NarrativeRelationshipError):
                validate_relationship_config(case)

    def test_duplicate_fails_closed(self):
        with self.assertRaises(NarrativeRelationshipError):
            validate_relationship_config({"version": "1.0.0", "relationships": [record(), record()]})

    def test_loader_wraps_io_and_json_errors(self):
        with self.assertRaises(NarrativeRelationshipError):
            load_narrative_relationships("/definitely/missing/relationships.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(NarrativeRelationshipError):
                load_narrative_relationships(path)

    def test_directionality_is_respected(self):
        config = validate_relationship_config({"version": "1.0.0", "relationships": [record()]})
        self.assertTrue(relationship_exists("Macro Pressure", "AI / Tech Growth", config))
        self.assertFalse(relationship_exists("AI / Tech Growth", "Macro Pressure", config))
        self.assertEqual(get_relationships_for_group("Macro Pressure", config)[0]["directionality"], "outbound")
        self.assertEqual(get_relationships_for_group("AI / Tech Growth", config)[0]["directionality"], "inbound")

    def test_target_to_source_and_bidirectional_resolution(self):
        reverse = validate_relationship_config({"version": "1.0.0", "relationships": [record(directionality="TARGET_TO_SOURCE")]})
        self.assertTrue(relationship_exists("AI / Tech Growth", "Macro Pressure", reverse))
        both = validate_relationship_config({"version": "1.0.0", "relationships": [record(directionality="BIDIRECTIONAL")]})
        self.assertTrue(relationship_exists("AI / Tech Growth", "Macro Pressure", both))
        self.assertEqual(get_relationships_for_group("AI / Tech Growth", both)[0]["directionality"], "bidirectional")

    def test_disabled_relationships_never_reach_public_reads(self):
        config = validate_relationship_config({"version": "1.0.0", "relationships": [record(display_enabled=False)]})
        self.assertEqual(get_display_relationships(config), ())
        self.assertEqual(get_relationships_for_group("Macro Pressure", config), ())

    def test_public_shape_excludes_internal_fields(self):
        relationship = load_narrative_relationships().relationships[0]
        public = normalize_relationship(relationship, relationship.source_group)
        self.assertNotIn("evidence_basis", public)
        self.assertNotIn("display_enabled", public)
        self.assertIn("type_label", public)
        self.assertIn("strength_label", public)

    def test_adjacency_and_summary_are_deterministic_and_sparse(self):
        adjacency = build_relationship_adjacency()
        self.assertEqual(adjacency["Geopolitical Risk"], ())
        self.assertEqual(adjacency["AI / Tech Growth"], tuple(sorted(adjacency["AI / Tech Growth"])))
        summary = build_relationship_summary("AI / Tech Growth")
        self.assertEqual(summary["count"], 2)


if __name__ == "__main__":
    unittest.main()
