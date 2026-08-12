import unittest

from fastapi.testclient import TestClient

from dashboard import app
from mne import account_repository
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from tests.auth_test_support import fresh_database


class SavedStoryRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account(
            "stories@example.com",
            "long-password-stories",
            "Stories",
            accepted_terms=True,
            accepted_privacy=True,
        )
        self.auth_session = create_session(self.user.user_id)
        self.client = TestClient(app)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.auth_session.session_id)

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, action, slug="ai_chips", return_to="/preferences", csrf=True):
        data = {
            "story_slug": slug,
            "action": action,
            "return_to": return_to,
        }
        if csrf:
            data["csrf_token"] = self.auth_session.csrf_token
        return self.client.post("/preferences/stories", data=data, follow_redirects=False)

    def test_authentication_and_csrf_are_required(self):
        anonymous = TestClient(app)
        self.assertEqual(
            anonymous.post("/preferences/stories", data={}, follow_redirects=False).status_code,
            303,
        )
        self.assertEqual(self.post("save", csrf=False).status_code, 403)

    def test_save_track_untrack_unsave_and_redirect_whitelist(self):
        response = self.post("save", return_to="/research")
        self.assertEqual((response.status_code, response.headers["location"]), (303, "/research"))
        self.assertEqual(
            account_repository.load_preferences(self.user.user_id)["saved_stories"],
            [{"story_slug": "ai_chips", "tracked": False}],
        )
        self.post("track")
        self.assertTrue(account_repository.load_preferences(self.user.user_id)["saved_stories"][0]["tracked"])
        self.post("untrack")
        self.assertFalse(account_repository.load_preferences(self.user.user_id)["saved_stories"][0]["tracked"])
        response = self.post("unsave", return_to="https://example.com")
        self.assertEqual(response.headers["location"], "/preferences")
        self.assertEqual(account_repository.load_preferences(self.user.user_id)["saved_stories"], [])

    def test_bad_slug_and_over_capacity_save_are_quiet_no_ops(self):
        self.assertEqual(self.post("save", slug="unknown_story").status_code, 303)
        for slug in ("ai_chips", "cloud_spending", "data_center_power"):
            self.post("save", slug=slug)
        self.assertEqual(len(account_repository.load_preferences(self.user.user_id)["saved_stories"]), 3)
        self.assertEqual(self.post("save", slug="natural_gas").status_code, 303)
        self.assertEqual(len(account_repository.load_preferences(self.user.user_id)["saved_stories"]), 3)


if __name__ == "__main__":
    unittest.main()
