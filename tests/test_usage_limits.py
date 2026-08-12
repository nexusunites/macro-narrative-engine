import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from mne import account_repository
from mne.auth import create_account
from mne.database import session_scope
from mne.entitlements import EntitlementDenied, FREE, PRO
from mne.models import AccountPreferences, FollowedNarrative, SavedHistoricalView, SavedStory, UsageEvent, User
from mne.usage_limits import (
    ALERT_RULES, FOLLOWED_NARRATIVES, HISTORICAL_COMPARISONS,
    HISTORICAL_INVESTIGATION_VIEWS, HISTORICAL_REQUESTS, SAVED_HISTORICAL_VIEWS,
    SAVED_STORIES,
    can_consume_usage, consume_usage, get_usage_consumed, get_usage_limit,
    get_usage_remaining, monthly_period, require_capacity,
)
from tests.auth_test_support import fresh_database


class UsageLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fresh_database()
        self.user = create_account("usage@example.com", "long-password-usage", "Usage", accepted_terms=True, accepted_privacy=True)

    def tearDown(self):
        self.tmp.cleanup()

    def reload(self):
        return account_repository.get_user(self.user.user_id)

    def test_utc_calendar_month_boundaries(self):
        start, end = monthly_period(datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 12, 1))
        self.assertEqual(end, datetime(2027, 1, 1))
        next_start, _ = monthly_period(datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(next_start, end)

    def test_distinct_object_is_charged_once_and_period_resets(self):
        july = datetime(2026, 7, 10, tzinfo=timezone.utc)
        first = consume_usage(self.user, HISTORICAL_INVESTIGATION_VIEWS, object_reference="replay_a", at=july)
        duplicate = consume_usage(self.user, HISTORICAL_INVESTIGATION_VIEWS, object_reference="replay_a", at=july)
        self.assertTrue(first.newly_consumed)
        self.assertFalse(duplicate.newly_consumed)
        self.assertEqual(get_usage_consumed(self.user, HISTORICAL_INVESTIGATION_VIEWS, july), 1)
        august = consume_usage(self.user, HISTORICAL_INVESTIGATION_VIEWS, object_reference="replay_a", at=datetime(2026, 8, 1, tzinfo=timezone.utc))
        self.assertTrue(august.newly_consumed)

    def test_free_allowances_and_pro_higher_limit(self):
        self.assertEqual(get_usage_limit(self.user, HISTORICAL_INVESTIGATION_VIEWS), 3)
        self.assertEqual(get_usage_limit(self.user, HISTORICAL_COMPARISONS), 1)
        self.assertEqual(get_usage_limit(self.user, HISTORICAL_REQUESTS), 3)
        with session_scope() as db:
            db.get(User, self.user.user_id).plan = PRO
        self.assertEqual(get_usage_limit(self.reload(), HISTORICAL_REQUESTS), 25)

    def test_allowance_blocks_overage_calmly(self):
        for ref in ("a", "b", "c"):
            consume_usage(self.user, HISTORICAL_INVESTIGATION_VIEWS, object_reference=ref)
        self.assertEqual(get_usage_remaining(self.user, HISTORICAL_INVESTIGATION_VIEWS), 0)
        with self.assertRaises(EntitlementDenied) as denied:
            consume_usage(self.user, HISTORICAL_INVESTIGATION_VIEWS, object_reference="d")
        self.assertEqual(denied.exception.reason, "monthly_allowance_used")

    def test_capacity_is_counted_live_not_from_counter(self):
        with session_scope() as db:
            for index in range(3):
                db.add(FollowedNarrative(user_id=self.user.user_id, narrative_level="theme", narrative_key=f"theme_{index}"))
            for index in range(2):
                db.add(SavedHistoricalView(user_id=self.user.user_id, view_type="investigation", replay_ids=[f"replay_{index}"], label="Saved", identity_key=f"view:{index}"))
            for slug in ("ai_chips", "cloud_spending", "data_center_power"):
                db.add(SavedStory(user_id=self.user.user_id, story_slug=slug))
            db.add(AccountPreferences(user_id=self.user.user_id, preferred_alert_types=[], alert_rules=[{"id": "one"}]))
        self.assertEqual(get_usage_consumed(self.user, FOLLOWED_NARRATIVES), 3)
        self.assertEqual(get_usage_consumed(self.user, SAVED_HISTORICAL_VIEWS), 2)
        self.assertEqual(get_usage_consumed(self.user, SAVED_STORIES), 3)
        self.assertEqual(get_usage_consumed(self.user, ALERT_RULES), 1)
        for metric in (FOLLOWED_NARRATIVES, SAVED_HISTORICAL_VIEWS, SAVED_STORIES, ALERT_RULES):
            self.assertFalse(can_consume_usage(self.user, metric))
            with self.assertRaises(EntitlementDenied): require_capacity(self.user, metric)

    def test_downgrade_preserves_resources_and_allows_deletion(self):
        with session_scope() as db:
            db.get(User, self.user.user_id).plan = PRO
            for index in range(5):
                db.add(FollowedNarrative(user_id=self.user.user_id, narrative_level="theme", narrative_key=f"saved_{index}"))
        with session_scope() as db:
            db.get(User, self.user.user_id).plan = FREE
        user = self.reload()
        self.assertEqual(get_usage_consumed(user, FOLLOWED_NARRATIVES), 5)
        with self.assertRaises(EntitlementDenied): require_capacity(user, FOLLOWED_NARRATIVES)
        with session_scope() as db:
            db.delete(db.query(FollowedNarrative).filter_by(user_id=user.user_id).first())
        self.assertEqual(get_usage_consumed(user, FOLLOWED_NARRATIVES), 4)

    def test_concurrent_duplicate_is_one_charge(self):
        def charge(_):
            return consume_usage(self.reload(), HISTORICAL_REQUESTS, object_reference="same-request")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(charge, range(4)))
        self.assertEqual(get_usage_consumed(self.user, HISTORICAL_REQUESTS), 1)
        with session_scope() as db:
            self.assertEqual(db.query(UsageEvent).count(), 1)
        self.assertEqual(sum(item.newly_consumed for item in results), 1)

    def test_concurrent_distinct_objects_cannot_exceed_limit(self):
        with session_scope() as db:
            db.get(User, self.user.user_id).plan = FREE
        def charge(index):
            try:
                consume_usage(self.reload(), HISTORICAL_COMPARISONS, object_reference=f"comparison-{index}")
                return True
            except EntitlementDenied:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(charge, range(4)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(get_usage_consumed(self.user, HISTORICAL_COMPARISONS), 1)


if __name__ == "__main__":
    unittest.main()
