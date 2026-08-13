import unittest

from mne.auth import create_account
from mne.studio_board import BOARD_MAX_X, BOARD_MAX_Y, empty_board, load_board, save_board, validate_board
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

    def test_repo_empty_and_full_replace_round_trip(self):
        self.assertEqual(load_board(self.user.user_id), empty_board())
        first = save_board(self.user.user_id, self.payload())
        self.assertEqual(load_board(self.user.user_id), first)
        replacement = empty_board(); replacement["thesis"] = "A different view"
        self.assertEqual(save_board(self.user.user_id, replacement), replacement)
        self.assertEqual(load_board(self.user.user_id), replacement)


if __name__ == "__main__":
    unittest.main()
