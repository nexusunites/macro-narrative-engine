import unittest
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient

import dashboard
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.database import session_scope
from mne.entitlements import EntitlementDenied
from mne.models import User
from mne.presentation_language import HISTORICAL_COPY
from tests.auth_test_support import fresh_database


def historical_context(*, replays=None, comparison=None, invalid=False, replay_a="", replay_b=""):
    return {
        "request": object(),
        "replays": replays if replays is not None else [],
        "comparison": comparison,
        "invalid": invalid,
        "copy": HISTORICAL_COPY,
        "replay_a": replay_a,
        "replay_b": replay_b,
    }


def comparison_result():
    return {
        "same_reconstruction": False,
        "period_a": {"date": "2026-07-01", "dominant_group": "Macro Pressure", "dominant_theme": "Rates"},
        "period_b": {"date": "2026-07-02", "dominant_group": "AI / Tech Growth", "dominant_theme": "AI"},
        "summary": "The leading narrative changed.",
        "dominance_sentences": ["The dominant narrative group changed from Macro Pressure to AI / Tech Growth."],
        "rank_sentences": [],
        "theme_changes": [{"name": "AI", "delta": 3, "arrow": "▲", "delta_label": "+3"}],
        "group_changes": [],
        "explanation": {
            "headline": "Leadership moved toward AI / Tech Growth.",
            "why_it_matters": "The two persisted periods emphasized different narratives.",
            "supporting_points": [],
            "limitations": ["Historical evidence coverage differs by period."],
        },
    }


REPLAYS = [
    {"url_id": "replay_a", "date": "2026-07-01", "dominant_group": "Macro Pressure", "dominant_theme": "Rates", "evidence_label": None, "breadth": {"label": None}, "summary": None},
    {"url_id": "replay_b", "date": "2026-07-02", "dominant_group": "AI / Tech Growth", "dominant_theme": "AI", "evidence_label": None, "breadth": {"label": None}, "summary": None},
]


class StudioCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account(
            "studio-compare@example.com",
            "long-password-studio-compare",
            "Studio Compare",
            accepted_terms=True,
            accepted_privacy=True,
        )
        auth_session = create_session(self.user.user_id)
        self.client = TestClient(dashboard.app)
        self.client.cookies.set(SESSION_COOKIE_NAME, auth_session.session_id)

    def tearDown(self):
        self.tmp.cleanup()

    def test_studio_lists_point_pickers_and_initial_prompt(self):
        with patch("dashboard.build_user_historical_comparison_context", return_value=historical_context(replays=REPLAYS)):
            response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/studio/compare"', response.text)
        self.assertIn("Point A", response.text)
        self.assertIn("Point B", response.text)
        self.assertIn("Pick two points in time to compare", response.text)

    def test_no_replays_and_invalid_selection_render_honestly(self):
        with patch("dashboard.build_user_historical_comparison_context", return_value=historical_context()):
            self.assertIn("No saved reconstructions to compare yet", self.client.get("/studio").text)
        invalid = historical_context(replays=REPLAYS, invalid=True, replay_a="replay_a")
        with patch("dashboard.build_user_historical_comparison_context", return_value=invalid):
            response = self.client.get("/studio/compare?replay_a=replay_a")
        self.assertIn("This historical comparison isn", response.text)
        self.assertNotIn("Leadership moved toward", response.text)

    def test_valid_comparison_renders_inline_and_reapplies_gate(self):
        context = historical_context(
            replays=REPLAYS,
            comparison=comparison_result(),
            replay_a="replay_a",
            replay_b="replay_b",
        )
        with (
            patch("dashboard.build_user_historical_comparison_context", return_value=context),
            patch("dashboard.require_entitlement") as entitlement,
            patch("dashboard.consume_usage") as consume,
        ):
            response = self.client.get("/studio/compare?replay_a=replay_a&replay_b=replay_b")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Leadership moved toward AI / Tech Growth", response.text)
        self.assertIn("The leading narrative changed", response.text)
        entitlement.assert_called_once_with(ANY, dashboard.HISTORICAL_COMPARISON)
        consume.assert_called_once_with(
            ANY,
            dashboard.HISTORICAL_COMPARISONS,
            object_reference="replay_a|replay_b",
        )

    def test_invalid_comparison_does_not_consume_usage(self):
        with (
            patch("dashboard.build_user_historical_comparison_context", return_value=historical_context(replays=REPLAYS, invalid=True)),
            patch("dashboard.consume_usage") as consume,
        ):
            response = self.client.get("/studio/compare?replay_a=bad&replay_b=replay_b")
        self.assertEqual(response.status_code, 200)
        consume.assert_not_called()

    def test_disabled_and_over_allowance_accounts_receive_403(self):
        context = historical_context(replays=REPLAYS, comparison=comparison_result(), replay_a="replay_a", replay_b="replay_b")
        with session_scope() as db:
            disabled_user = db.get(User, self.user.user_id)
            disabled_user.account_status = "DISABLED"
            db.flush()
            db.expunge(disabled_user)
        with (
            patch("dashboard.build_user_historical_comparison_context", return_value=context),
            patch("dashboard.get_current_user", return_value=disabled_user),
        ):
            response = self.client.get("/studio/compare?replay_a=replay_a&replay_b=replay_b")
        self.assertEqual(response.status_code, 403)

        with session_scope() as db:
            active_user = db.get(User, self.user.user_id)
            active_user.account_status = "ACTIVE"
            db.flush()
            db.expunge(active_user)
        with (
            patch("dashboard.build_user_historical_comparison_context", return_value=context),
            patch("dashboard.get_current_user", return_value=active_user),
            patch("dashboard.consume_usage", side_effect=EntitlementDenied("monthly_allowance_used")),
        ):
            response = self.client.get("/studio/compare?replay_a=replay_a&replay_b=replay_b")
        self.assertEqual(response.status_code, 403)

    def test_standalone_history_compare_route_remains_available(self):
        with patch(
            "dashboard.build_user_historical_comparison_context",
            side_effect=lambda request, *args: {
                **historical_context(replays=REPLAYS),
                "request": request,
            },
        ):
            response = self.client.get("/history/compare")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Compare narratives", response.text)


if __name__ == "__main__":
    unittest.main()
