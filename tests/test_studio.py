import unittest
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard import app
from mne import account_repository
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.personalization import save_story, set_story_tracked
from mne.studio_board import create_board, empty_board, save_board
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
        self.auth_session = create_session(self.user.user_id)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.auth_session.session_id)
        self.board_id = create_board(self.user.user_id)

    def tearDown(self):
        self.tmp.cleanup()

    def test_anonymous_studio_is_public_and_prompts_for_sign_in(self):
        response = TestClient(app).get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sign in to build and revisit your theses", response.text)
        self.assertIn('href="/login?next=/studio"', response.text)
        self.assertNotIn('class="studio-rail-row"', response.text)

    def test_authenticated_empty_state_and_active_nav_render(self):
        response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Untitled thesis", response.text)
        self.assertIn('class="active" aria-current="page" href="/studio"', response.text)
        self.assertIn("Your thesis library", response.text)
        self.assertNotIn('data-board-thesis', response.text)
        self.assertNotIn("Compare over time", response.text)
        self.assertNotIn("dropzone", response.text)
        self.assertNotIn("connectors", response.text)

        class VisibleText(HTMLParser):
            def __init__(self): super().__init__(); self.parts=[]; self.hidden=0
            def handle_starttag(self, tag, attrs): self.hidden += tag in {"script", "style"}
            def handle_endtag(self, tag): self.hidden -= tag in {"script", "style"}
            def handle_data(self, data):
                if not self.hidden: self.parts.append(data)
        parser=VisibleText(); parser.feed(response.text); visible=" ".join(parser.parts).lower()
        for forbidden in ("node", "edge", "graph", "canvas"):
            self.assertNotIn(forbidden, visible)

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
            patch("dashboard.build_research_index", return_value={"stories": {story["slug"]: story for story in selector[0]["stories"]}}),
        ):
            response = self.client.get(f"/studio/board/{self.board_id}")
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
            response = self.client.get(f"/studio/board/{self.board_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Oil Supply Shock", response.text)
        self.assertIn("direction-steady", response.text)

    def test_boarded_story_uses_current_run_direction_even_when_not_saved(self):
        payload = empty_board()
        payload["nodes"] = [{"id": "a", "kind": "story", "slug": "ai_chips", "x": 10, "y": 20}]
        save_board(self.user.user_id, self.board_id, payload)
        selector = [{"stories": [{"slug": "ai_chips", "direction": "up", "direction_label": "Strengthening"}]}]
        with (
            patch("dashboard.select_latest_meaningful_run", return_value=SimpleNamespace(run={"ready": True}, path=None)),
            patch("dashboard.build_research_index", return_value={"stories": {"ai_chips": selector[0]["stories"][0]}}),
        ):
            response = self.client.get(f"/studio/board/{self.board_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-story-slug="ai_chips"', response.text)
        self.assertIn("studio-evidence direction-up", response.text)
        self.assertIn("Strengthening", response.text)
        self.assertIn("← All theses", response.text)

    def test_editor_server_renders_headline_catalyst_and_supports(self):
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
        save_board(self.user.user_id, self.board_id, payload)
        with patch("dashboard.select_latest_meaningful_run", return_value=SimpleNamespace(run=None, path=None)):
            response = self.client.get(f"/studio/board/{self.board_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("studio-evidence-headline", response.text)
        self.assertIn("studio-evidence-catalyst", response.text)
        self.assertIn("Chip demand expands", response.text)
        self.assertIn("Developer conference", response.text)
        self.assertEqual(response.text.count('class="connection-supports"'), 2)
        self.assertIn("Headline evidence", response.text)
        self.assertIn("Catalyst evidence", response.text)


if __name__ == "__main__":
    unittest.main()
