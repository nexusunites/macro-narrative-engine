import unittest
from tests.auth_test_support import fresh_database
from mne.auth import create_account
from mne import account_repository
from mne.database import session_scope
from mne.models import SavedStory
from mne.personalization import follow_narrative, save_historical_view, save_story, set_story_tracked, unsave_story

class AccountRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=fresh_database(); self.a=create_account("a@example.com","long-password-a","A",accepted_terms=True,accepted_privacy=True); self.b=create_account("b@example.com","long-password-b","B",accepted_terms=True,accepted_privacy=True)
    def tearDown(self): self.tmp.cleanup()
    def test_preferences_and_views_are_isolated(self):
        profile=follow_narrative(account_repository.load_preferences(self.a.user_id),"theme","ai"); profile=save_historical_view(profile,"investigation",["replay_2026-01-01"]); account_repository.save_preferences(self.a.user_id,profile)
        self.assertEqual(len(account_repository.load_preferences(self.a.user_id)["followed_narratives"]),1); self.assertEqual(account_repository.load_preferences(self.b.user_id)["followed_narratives"],[]); self.assertEqual(account_repository.load_preferences(self.b.user_id)["saved_historical_views"],[])
    def test_alert_state_is_isolated(self):
        state=account_repository.load_alert_state(self.a.user_id); state["last_evaluated_run_id"]="run-a"; account_repository.save_alert_state(self.a.user_id,state)
        self.assertEqual(account_repository.load_alert_state(self.a.user_id)["last_evaluated_run_id"],"run-a"); self.assertIsNone(account_repository.load_alert_state(self.b.user_id)["last_evaluated_run_id"])
    def test_saved_story_round_trip_updates_in_place_and_deletes(self):
        profile = save_story(account_repository.load_preferences(self.a.user_id), "ai_chips")
        account_repository.save_preferences(self.a.user_id, profile)
        with session_scope() as db:
            original_id = db.query(SavedStory).filter_by(user_id=self.a.user_id).one().id
        profile = set_story_tracked(account_repository.load_preferences(self.a.user_id), "ai_chips", True)
        account_repository.save_preferences(self.a.user_id, profile)
        with session_scope() as db:
            row = db.query(SavedStory).filter_by(user_id=self.a.user_id).one()
            self.assertEqual(row.id, original_id)
            self.assertTrue(row.tracked)
        self.assertEqual(account_repository.load_preferences(self.b.user_id)["saved_stories"], [])
        account_repository.save_preferences(
            self.a.user_id,
            unsave_story(account_repository.load_preferences(self.a.user_id), "ai_chips"),
        )
        with session_scope() as db:
            self.assertEqual(db.query(SavedStory).filter_by(user_id=self.a.user_id).count(), 0)
    def test_anonymous_claim_at_most_once(self):
        self.assertTrue(account_repository.record_migration_decision(self.a.user_id,"IMPORTED")); self.assertFalse(account_repository.record_migration_decision(self.b.user_id,"IMPORTED"))
if __name__=="__main__": unittest.main()
