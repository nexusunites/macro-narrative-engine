import unittest

from mne.auth import create_account
from mne.studio_board import BOARD_MAX_X, BOARD_MAX_Y, MAX_BOARDS, create_board, delete_board, empty_board, list_boards, load_board, save_board, validate_board
from tests.auth_test_support import fresh_database


class StudioBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account("board@example.com", "long-password-board", "Board", accepted_terms=True, accepted_privacy=True)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self):
        return {
            "schema_version": 1,
            "thesis": "<b>Rates</b>\x00 stay higher",
            "nodes": [
                {"id": "a", "kind": "story", "slug": "ai_chips", "x": -10, "y": 9999},
                {"id": "dead", "kind": "story", "slug": "not_real", "x": 1, "y": 2},
            ],
            "connections": [
                {"id": "dangling", "from": "a", "to": "dead", "label": "drives"},
            ],
        }

    def test_normalizes_text_positions_and_dead_references(self):
        board = validate_board(self.payload())
        self.assertEqual(board["thesis"], "Rates stay higher")
        self.assertEqual(board["nodes"], [{"id": "a", "kind": "story", "slug": "ai_chips", "x": 0, "y": BOARD_MAX_Y}])
        self.assertEqual(board["connections"], [])

    def test_invalid_labels_are_dropped(self):
        payload = self.payload()
        payload["nodes"].append({"id": "b", "kind": "story", "slug": "natural_gas", "x": BOARD_MAX_X, "y": BOARD_MAX_Y})
        payload["connections"] = [{"id": "c", "from": "a", "to": "b", "label": "predicts"}]
        self.assertEqual(validate_board(payload)["connections"], [])

    def test_caps_and_schema_fail_closed(self):
        payload = self.payload()
        payload["nodes"] = [{"id": f"n{i}", "kind": "story", "slug": "ai_chips", "x": 0, "y": 0} for i in range(41)]
        with self.assertRaises(ValueError): validate_board(payload)
        payload = self.payload(); payload["connections"] = [{}] * 81
        with self.assertRaises(ValueError): validate_board(payload)
        with self.assertRaises(ValueError): validate_board({})

    def test_thesis_is_capped(self):
        payload = self.payload(); payload["thesis"] = "<i>" + "x" * 300 + "</i>"
        self.assertEqual(len(validate_board(payload)["thesis"]), 240)

    def test_evidence_kinds_normalize_sanitize_and_validate_sources(self):
        payload = empty_board()
        payload["nodes"] = [
            {"id": "story", "kind": "story", "slug": "ai_chips", "x": 10, "y": 20},
            {"id": "headline", "kind": "headline", "title": "<b>Chip demand</b>\x00 " + "x" * 250, "source": "<i>Wire</i>", "source_story": "story", "x": -4, "y": 22},
            {"id": "catalyst", "kind": "catalyst", "name": "<b>Developer conference</b>", "timing": "<i>Next week</i>", "source_story": "story", "x": 30, "y": 40},
            {"id": "orphan", "kind": "headline", "title": "Still valid", "source": "Desk", "source_story": "missing", "x": 1, "y": 2},
            {"id": "non-story-source", "kind": "catalyst", "name": "Valid leaf", "source_story": "headline", "x": 1, "y": 2},
            {"id": "empty-headline", "kind": "headline", "title": "<b></b>", "x": 1, "y": 2},
            {"id": "empty-catalyst", "kind": "catalyst", "name": "", "x": 1, "y": 2},
            {"id": "unknown", "kind": "asset", "name": "QQQ", "x": 1, "y": 2},
        ]
        board = validate_board(payload)
        by_id = {node["id"]: node for node in board["nodes"]}
        self.assertEqual(set(by_id), {"story", "headline", "catalyst", "orphan", "non-story-source"})
        self.assertEqual(len(by_id["headline"]["title"]), 200)
        self.assertTrue(by_id["headline"]["title"].startswith("Chip demand"))
        self.assertEqual(by_id["headline"]["source"], "Wire")
        self.assertEqual(by_id["headline"]["source_story"], "story")
        self.assertEqual(by_id["catalyst"]["name"], "Developer conference")
        self.assertEqual(by_id["catalyst"]["timing"], "Next week")
        self.assertNotIn("source_story", by_id["orphan"])
        self.assertNotIn("source_story", by_id["non-story-source"])

    def test_supports_requires_evidence_to_its_source_story(self):
        payload = empty_board()
        payload["nodes"] = [
            {"id": "story", "kind": "story", "slug": "ai_chips", "x": 10, "y": 20},
            {"id": "other", "kind": "story", "slug": "natural_gas", "x": 20, "y": 20},
            {"id": "headline", "kind": "headline", "title": "Chip demand expands", "source": "Wire", "source_story": "story", "x": 30, "y": 20},
        ]
        payload["connections"] = [
            {"id": "valid", "from": "headline", "to": "story", "label": "supports"},
            {"id": "wrong-target", "from": "headline", "to": "other", "label": "supports"},
            {"id": "wrong-source", "from": "story", "to": "other", "label": "supports"},
            {"id": "invalid-label", "from": "headline", "to": "story", "label": "proves"},
            {"id": "dangling", "from": "headline", "to": "missing", "label": "supports"},
        ]
        self.assertEqual(validate_board(payload)["connections"], [{"id": "valid", "from": "headline", "to": "story", "label": "supports"}])

    def test_repo_round_trips_story_headline_catalyst_and_supports(self):
        board_id = create_board(self.user.user_id)
        payload = empty_board()
        payload["nodes"] = [
            {"id": "story", "kind": "story", "slug": "ai_chips", "x": 10, "y": 20},
            {"id": "headline", "kind": "headline", "title": "Chip demand expands", "source": "Wire", "source_story": "story", "x": 230, "y": 20},
            {"id": "catalyst", "kind": "catalyst", "name": "Developer conference", "timing": "Upcoming", "source_story": "story", "x": 230, "y": 132},
        ]
        payload["connections"] = [
            {"id": "headline-link", "from": "headline", "to": "story", "label": "supports"},
            {"id": "catalyst-link", "from": "catalyst", "to": "story", "label": "supports"},
        ]
        saved = save_board(self.user.user_id, board_id, payload)
        self.assertEqual(load_board(self.user.user_id, board_id), saved)

    def test_repo_create_list_and_full_replace_round_trip(self):
        board_id = create_board(self.user.user_id)
        self.assertEqual(load_board(self.user.user_id, board_id), empty_board())
        first = save_board(self.user.user_id, board_id, self.payload())
        self.assertEqual(load_board(self.user.user_id, board_id), first)
        replacement = empty_board(); replacement["thesis"] = "A different view"
        self.assertEqual(save_board(self.user.user_id, board_id, replacement), replacement)
        self.assertEqual(load_board(self.user.user_id, board_id), replacement)
        projection = list_boards(self.user.user_id)
        self.assertEqual(projection[0]["board_id"], board_id)
        self.assertEqual(projection[0]["thesis"], "A different view")
        self.assertEqual((projection[0]["node_count"], projection[0]["connection_count"]), (0, 0))
        self.assertTrue(delete_board(self.user.user_id, board_id))
        self.assertIsNone(load_board(self.user.user_id, board_id))

    def test_repo_enforces_cap_and_ownership(self):
        other = create_account("other-board@example.com", "long-password-other", "Other", accepted_terms=True, accepted_privacy=True)
        board_id = create_board(other.user_id)
        self.assertIsNone(load_board(self.user.user_id, board_id))
        with self.assertRaises(KeyError):
            save_board(self.user.user_id, board_id, empty_board())
        self.assertFalse(delete_board(self.user.user_id, board_id))
        self.assertEqual(load_board(other.user_id, board_id), empty_board())
        for _ in range(MAX_BOARDS):
            create_board(self.user.user_id)
        with self.assertRaises(ValueError):
            create_board(self.user.user_id)


if __name__ == "__main__":
    unittest.main()
