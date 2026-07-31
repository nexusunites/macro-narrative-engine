import os
import unittest
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.auth_test_support import fresh_database
from mne.auth import SESSION_COOKIE_NAME, authenticate, create_account, create_session, generate_password_reset, consume_password_reset, utcnow
from mne.database import session_scope
from mne.models import AuthSession, User
from dashboard import app

class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=fresh_database(); self.user=create_account("User@Example.com","a-long-password","User",accepted_terms=True,accepted_privacy=True)
    def tearDown(self): self.tmp.cleanup()
    def test_password_is_argon2_and_credentials_are_safe(self):
        with session_scope() as db: stored=db.get(User,self.user.user_id).password_hash
        self.assertTrue(stored.startswith("$argon2id$")); self.assertIsNone(authenticate("missing@example.com","wrong","1.2.3.4")); self.assertIsNone(authenticate("user@example.com","wrong","1.2.3.4"))
    def test_duplicate_and_client_authority(self):
        with self.assertRaises(ValueError): create_account("USER@example.com","another-long-password","Other",accepted_terms=True,accepted_privacy=True)
        with session_scope() as db: user=db.get(User,self.user.user_id); self.assertEqual((user.role,user.plan),("USER","FREE"))
    def test_session_expiry_logout_and_disable(self):
        session=create_session(self.user.user_id)
        with session_scope() as db: db.get(AuthSession,session.session_id).expires_at=utcnow()-timedelta(seconds=1)
        from mne.auth import resolve_session, disable_account
        self.assertIsNone(resolve_session(session.session_id)); active=create_session(self.user.user_id); disable_account(self.user.user_id); self.assertIsNone(resolve_session(active.session_id))
    def test_reset_single_use(self):
        token=generate_password_reset("user@example.com"); self.assertTrue(consume_password_reset(token,"replacement-password")); self.assertFalse(consume_password_reset(token,"replacement-again"))
    def test_http_session_cookie_and_logout_csrf(self):
        with patch.dict(os.environ,{"MNE_SECURE_COOKIES":"true"}):
            client=TestClient(app); response=client.post("/login",data={"email":"user@example.com","password":"a-long-password"},follow_redirects=False)
        cookie=response.headers["set-cookie"]; self.assertIn("HttpOnly",cookie); self.assertIn("SameSite=lax",cookie); self.assertIn("Secure",cookie)

if __name__=="__main__": unittest.main()
