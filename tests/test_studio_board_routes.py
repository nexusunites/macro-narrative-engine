import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import dashboard
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.studio_board import create_board, empty_board, load_board, save_board
from tests.auth_test_support import fresh_database


class StudioBoardRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account("board-routes@example.com", "long-password-routes", "Routes", accepted_terms=True, accepted_privacy=True)
        self.session = create_session(self.user.user_id)
        self.client = TestClient(dashboard.app)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.session.session_id)
        self.board_id = create_board(self.user.user_id)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, thesis="My view"):
        return {"schema_version": 1, "thesis": thesis, "nodes": [{"id":"a","kind":"story","slug":"ai_chips","x":10,"y":20}], "connections": []}

    def test_save_requires_auth_and_csrf(self):
        anonymous = TestClient(dashboard.app)
        path = f"/studio/board/{self.board_id}"
        self.assertEqual(anonymous.post(path, data={"payload": json.dumps(empty_board())}).status_code, 401)
        self.assertEqual(self.client.post(path, data={"payload": json.dumps(empty_board())}).status_code, 403)

    def test_save_is_full_replace_and_rejects_bad_payload(self):
        path = f"/studio/board/{self.board_id}"
        response = self.client.post(path, data={"csrf_token": self.session.csrf_token, "payload": json.dumps(self.payload())})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(load_board(self.user.user_id, self.board_id)["thesis"], "My view")
        replacement = empty_board(); replacement["thesis"] = "Replacement"
        self.assertEqual(self.client.post(path, data={"csrf_token": self.session.csrf_token, "payload": json.dumps(replacement)}).status_code, 204)
        self.assertEqual(load_board(self.user.user_id, self.board_id), replacement)
        bad = self.payload(); bad["nodes"] = [bad["nodes"][0]] * 41
        self.assertEqual(self.client.post(path, data={"csrf_token": self.session.csrf_token, "payload": json.dumps(bad)}).status_code, 400)
        bad = self.payload(); bad["nodes"].append({"id":"b","kind":"story","slug":"natural_gas","x":1,"y":1}); bad["connections"]=[{"id":"c","from":"a","to":"b","label":"predicts"}]
        self.assertEqual(self.client.post(path, data={"csrf_token": self.session.csrf_token, "payload": json.dumps(bad)}).status_code, 204)
        self.assertEqual(load_board(self.user.user_id, self.board_id)["connections"], [])

    def test_editor_save_and_delete_are_ownership_guarded(self):
        other = create_account("route-other@example.com", "long-password-other", "Other", accepted_terms=True, accepted_privacy=True)
        other_board = create_board(other.user_id)
        self.assertEqual(self.client.get(f"/studio/board/{other_board}").status_code, 404)
        mutation = {"csrf_token": self.session.csrf_token, "payload": json.dumps(empty_board())}
        self.assertEqual(self.client.post(f"/studio/board/{other_board}", data=mutation).status_code, 404)
        self.assertEqual(self.client.post(f"/studio/board/{other_board}/delete", data={"csrf_token": self.session.csrf_token}).status_code, 404)
        self.assertIsNotNone(load_board(other.user_id, other_board))

    def test_new_library_and_delete_flow(self):
        save_board(self.user.user_id, self.board_id, self.payload("Rates stay high"))
        library = self.client.get("/studio")
        self.assertIn("Rates stay high", library.text)
        self.assertIn("1 evidence · 0 links", library.text)
        self.assertIn(f'href="/studio/board/{self.board_id}"', library.text)
        created = self.client.post("/studio/board/new", data={"csrf_token": self.session.csrf_token}, follow_redirects=False)
        self.assertEqual(created.status_code, 303)
        self.assertRegex(created.headers["location"], r"^/studio/board/[0-9a-f-]+$")
        deleted = self.client.post(f"/studio/board/{self.board_id}/delete", data={"csrf_token": self.session.csrf_token}, follow_redirects=False)
        self.assertEqual((deleted.status_code, deleted.headers["location"]), (303, "/studio"))
        self.assertIsNone(load_board(self.user.user_id, self.board_id))
        self.assertIn("Untitled thesis", self.client.get("/studio").text)

    def test_empty_library_prompt(self):
        self.assertTrue(dashboard.delete_board(self.user.user_id, self.board_id))
        self.assertIn("Start your first thesis", self.client.get("/studio").text)

    def test_new_and_delete_require_auth_and_csrf(self):
        anonymous = TestClient(dashboard.app)
        response = anonymous.post("/studio/board/new", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/login?next="))
        self.assertEqual(self.client.post("/studio/board/new").status_code, 403)
        self.assertEqual(self.client.post(f"/studio/board/{self.board_id}/delete").status_code, 403)

    def test_intelligence_projection_is_whitelisted_and_does_not_leak(self):
        investigation = {
            "stories": ({"slug":"ai_chips","direction":"up","direction_label":"Strengthening","workflow_id":"secret"},),
            "supporting_evidence_display": ({"title":"Chip demand expands","source_name":"Wire","path":"/secret/path","evidence_id":"private"},),
            "events": ({"event_name":"Developer conference","lifecycle_state":"Upcoming","event_id":"workflow-secret"},),
            "narrative_id": "internal-id",
        }
        with patch("dashboard.build_narrative_investigation", return_value=investigation):
            result = dashboard.build_studio_node_intelligence({"path":"/secret/run.json"}, "ai_chips")
        self.assertEqual(set(result), {"story","direction","direction_label","related","headlines","catalyst","relationship_hints","empty_message","research_url"})
        serialized = json.dumps(result).lower()
        for forbidden in ("/secret", "workflow", "evidence_id", "internal-id", "run.json"):
            self.assertNotIn(forbidden, serialized)
        hinted_slugs = {slug for hint in result["relationship_hints"] for slug in hint["story_slugs"]}
        self.assertIn("natural_gas", hinted_slugs)
        self.assertNotIn("cloud_spending", hinted_slugs)

    def test_intelligence_endpoint_requires_auth(self):
        self.assertEqual(TestClient(dashboard.app).get("/studio/node/ai_chips").status_code, 401)
        with (
            patch("dashboard.select_latest_meaningful_run", return_value=SimpleNamespace(run={}, path=None)),
            patch("dashboard.build_studio_node_intelligence", return_value={"story":"AI Chips"}),
        ):
            response = self.client.get("/studio/node/ai_chips")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"story":"AI Chips"})


if __name__ == "__main__":
    unittest.main()
