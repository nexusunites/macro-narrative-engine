import unittest

from fastapi.testclient import TestClient

from mne import account_repository
from mne.auth import SESSION_COOKIE_NAME, create_account, create_session
from mne.database import session_scope
from mne.entitlements import (
    ADMIN_DIAGNOSTICS, AI_ANALYST_PROVIDER, API_ACCESS, EXPORTS, FREE,
    HISTORICAL_RESEARCH, LIVE_DASHBOARD, PRO, SAVED_STORIES, TEAM, TEAM_WORKSPACE,
    check_entitlement, get_plan_entitlements,
)
from mne.models import AuditLog, User
from tests.auth_test_support import fresh_database
from dashboard import app


class EntitlementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account("user@example.com", "long-password-user", "User", accepted_terms=True, accepted_privacy=True)
        self.admin = create_account("admin@example.com", "long-password-admin", "Admin", accepted_terms=True, accepted_privacy=True)
        with session_scope() as db:
            db.get(User, self.admin.user_id).role = "ADMIN"

    def tearDown(self):
        self.tmp.cleanup()

    def reload(self, user):
        return account_repository.get_user(user.user_id)

    def test_free_pro_and_team_matrices(self):
        self.assertIn(LIVE_DASHBOARD, get_plan_entitlements(FREE))
        self.assertIn(HISTORICAL_RESEARCH, get_plan_entitlements(FREE))
        self.assertIn(SAVED_STORIES, get_plan_entitlements(FREE))
        self.assertNotIn(AI_ANALYST_PROVIDER, get_plan_entitlements(FREE))
        self.assertIn(AI_ANALYST_PROVIDER, get_plan_entitlements(PRO))
        self.assertNotIn(API_ACCESS, get_plan_entitlements(PRO))
        self.assertTrue({TEAM_WORKSPACE, API_ACCESS, EXPORTS} <= get_plan_entitlements(TEAM))

    def test_unknown_plan_and_disabled_user_fail_closed(self):
        with session_scope() as db:
            row = db.get(User, self.user.user_id); row.plan = "UNKNOWN"
        self.assertFalse(check_entitlement(self.reload(self.user), LIVE_DASHBOARD))
        with session_scope() as db:
            row = db.get(User, self.user.user_id); row.plan = FREE; row.account_status = "DISABLED"
        self.assertFalse(check_entitlement(self.reload(self.user), LIVE_DASHBOARD))

    def test_admin_role_does_not_bypass_product_plan(self):
        admin = self.reload(self.admin)
        self.assertTrue(check_entitlement(admin, ADMIN_DIAGNOSTICS))
        self.assertFalse(check_entitlement(admin, API_ACCESS))

    def test_assignment_and_internal_access_are_audited(self):
        self.assertTrue(account_repository.assign_account_access(self.admin.user_id, self.user.user_id, plan=PRO, internal_full_access=True))
        user = self.reload(self.user)
        self.assertEqual(user.plan, PRO)
        self.assertTrue(user.internal_full_access)
        self.assertTrue(check_entitlement(user, API_ACCESS))
        with session_scope() as db:
            audit = db.query(AuditLog).filter_by(target_ref=self.user.user_id).one()
            self.assertEqual(audit.action, "ACCOUNT_ACCESS_CHANGED")
            self.assertEqual(audit.details["old_plan"], FREE)
            self.assertEqual(audit.details["new_plan"], PRO)

    def test_non_admin_cannot_assign_plan(self):
        self.assertFalse(account_repository.assign_account_access(self.user.user_id, self.admin.user_id, plan=TEAM))
        self.assertEqual(self.reload(self.admin).plan, FREE)

    def test_client_plan_fields_are_ignored_and_account_copy_is_safe(self):
        auth_session = create_session(self.user.user_id)
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE_NAME, auth_session.session_id)
        response = client.post("/account/profile", data={
            "csrf_token": auth_session.csrf_token, "display_name": "Still Free",
            "plan": PRO, "role": "ADMIN", "internal_full_access": "true",
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        user = self.reload(self.user)
        self.assertEqual((user.plan, user.role, user.internal_full_access), (FREE, "USER", False))
        page = client.get("/account")
        self.assertEqual(page.status_code, 200)
        self.assertIn("0 of 3 historical investigations used this month", page.text)
        self.assertNotIn("HISTORICAL_INVESTIGATION_VIEWS", page.text)


if __name__ == "__main__":
    unittest.main()
