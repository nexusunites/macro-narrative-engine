import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard import app
from mne import account_repository
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.personalization import save_story, set_story_tracked
from tests.auth_test_support import fresh_database


class StudioShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account(
            "studio@example.com",
            "long-password-studio",
            "Studio User",
            accepted_terms=True,
            accepted_privacy=True,
        )
        self.client = TestClient(app)
        auth_session = create_session(self.user.user_id)
        self.client.cookies.set(SESSION_COOKIE_NAME, auth_session.session_id)

    def tearDown(self):
        self.tmp.cleanup()

    def test_anonymous_studio_is_public_and_prompts_for_sign_in(self):
        response = TestClient(app).get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sign in to see your saved stories and watchlist", response.text)
        self.assertIn('href="/login?next=/studio"', response.text)
        self.assertNotIn('class="studio-rail-row"', response.text)

    def test_authenticated_empty_state_and_active_nav_render(self):
        response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Star stories in Research to build your collection", response.text)
        self.assertIn('class="active" aria-current="page" href="/studio"', response.text)
        self.assertIn("Your artboard is coming next", response.text)
        self.assertIn("Compare over time", response.text)
        self.assertNotIn("dropzone", response.text)
        self.assertNotIn("connectors", response.text)

    def test_saved_rail_and_tracked_subset_use_current_directions(self):
        profile = save_story(account_repository.load_preferences(self.user.user_id), "ai_chips")
        profile = set_story_tracked(profile, "ai_chips", True)
        profile = save_story(profile, "natural_gas")
        account_repository.save_preferences(self.user.user_id, profile)
        selector = [
            {
                "stories": [
                    {"slug": "ai_chips", "direction": "up", "direction_label": "Strengthening"},
                    {"slug": "natural_gas", "direction": "down", "direction_label": "Fading"},
                ]
            }
        ]
        with (
            patch("dashboard.select_latest_meaningful_run", return_value=SimpleNamespace(run={"ready": True}, path=None)),
            patch("dashboard.build_narrative_selector", return_value=selector),
        ):
            response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text.count("AI Chips"), 2)
        self.assertEqual(response.text.count("Natural Gas"), 1)
        self.assertIn("direction-up", response.text)
        self.assertIn("direction-down", response.text)
        self.assertIn("Tracked", response.text)

    def test_saved_story_missing_from_current_read_falls_back_to_steady(self):
        profile = save_story(account_repository.load_preferences(self.user.user_id), "oil_supply_shock")
        account_repository.save_preferences(self.user.user_id, profile)
        with patch("dashboard.select_latest_meaningful_run", return_value=SimpleNamespace(run=None, path=None)):
            response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Oil Supply Shock", response.text)
        self.assertIn("direction-steady", response.text)


if __name__ == "__main__":
    unittest.main()
