import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import dashboard
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.studio_board import empty_board, load_board
from tests.auth_test_support import fresh_database


class StudioBoardRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account("board-routes@example.com", "long-password-routes", "Routes", accepted_terms=True, accepted_privacy=True)
        self.session = create_session(self.user.user_id)
        self.client = TestClient(dashboard.app)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.session.session_id)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, thesis="My view"):
        return {"schema_version": 1, "thesis": thesis, "nodes": [{"id":"a","kind":"story","slug":"ai_chips","x":10,"y":20}], "connections": []}

    def test_save_requires_auth_and_csrf(self):
        anonymous = TestClient(dashboard.app)
        self.assertEqual(anonymous.post("/studio/board", data={"payload": json.dumps(empty_board())}).status_code, 401)
        self.assertEqual(self.client.post("/studio/board", data={"payload": json.dumps(empty_board())}).status_code, 403)

    def test_save_is_full_replace_and_rejects_bad_payload(self):
        response = self.client.post("/studio/board", data={"csrf_token": self.session.csrf_token, "payload": json.dumps(self.payload())})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(load_board(self.user.user_id)["thesis"], "My view")
        replacement = empty_board(); replacement["thesis"] = "Replacement"
        self.assertEqual(self.client.post("/studio/board", data={"csrf_token": self.session.csrf_token, "payload": json.dumps(replacement)}).status_code, 204)
        self.assertEqual(load_board(self.user.user_id), replacement)
        bad = self.payload(); bad["nodes"] = [bad["nodes"][0]] * 41
        self.assertEqual(self.client.post("/studio/board", data={"csrf_token": self.session.csrf_token, "payload": json.dumps(bad)}).status_code, 400)
        bad = self.payload(); bad["nodes"].append({"id":"b","kind":"story","slug":"natural_gas","x":1,"y":1}); bad["connections"]=[{"id":"c","from":"a","to":"b","label":"predicts"}]
        self.assertEqual(self.client.post("/studio/board", data={"csrf_token": self.session.csrf_token, "payload": json.dumps(bad)}).status_code, 204)
        self.assertEqual(load_board(self.user.user_id)["connections"], [])

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
