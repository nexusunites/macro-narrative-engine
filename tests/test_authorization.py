import unittest
from fastapi.testclient import TestClient
from tests.auth_test_support import fresh_database
from mne.auth import create_account
from mne.database import session_scope
from mne.models import User
from mne.security import can_access_feature, can_modify_resource
from dashboard import app

class AuthorizationTests(unittest.TestCase):
    def setUp(self): self.tmp=fresh_database(); self.client=TestClient(app); self.user=create_account("user@example.com","a-long-password","User",accepted_terms=True,accepted_privacy=True)
    def tearDown(self): self.tmp.cleanup()
    def login(self): self.client.post("/login",data={"email":"user@example.com","password":"a-long-password"})
    def test_public_and_protected_matrix(self):
        self.assertIn(self.client.get("/",follow_redirects=False).status_code,{200,404}); self.assertEqual(self.client.get("/preferences",follow_redirects=False).status_code,303); self.assertEqual(self.client.get("/history/request",follow_redirects=False).status_code,303)
    def test_user_forbidden_admin_admin_allowed(self):
        self.login(); self.assertEqual(self.client.get("/admin",follow_redirects=False).status_code,403)
        with session_scope() as db: db.get(User,self.user.user_id).role="ADMIN"
        self.assertEqual(self.client.get("/admin",follow_redirects=False).status_code,200)
    def test_csrf_and_deterministic_helpers(self):
        self.login(); self.assertEqual(self.client.post("/preferences/alerts",data={}).status_code,403); self.assertFalse(can_access_feature(self.user,"admin")); self.assertFalse(can_access_feature(self.user,"admin")); self.assertFalse(can_modify_resource(self.user,type("R",(),{"user_id":"someone-else"})()))
if __name__=="__main__": unittest.main()
