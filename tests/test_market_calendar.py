import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from mne.market_calendar import STALE_GRACE_WINDOW, classify_session_freshness


UTC = timezone.utc


class MarketCalendarTests(unittest.TestCase):
    def test_friday_close_remains_fresh_through_weekend(self):
        observed = datetime(2026, 7, 10, 20, tzinfo=UTC)
        for as_of in (datetime(2026, 7, 11, 20, tzinfo=UTC), datetime(2026, 7, 12, 23, 59, tzinfo=UTC)):
            with self.subTest(as_of=as_of):
                self.assertEqual("FRESH", classify_session_freshness(observed, as_of))

    def test_holiday_preserves_prior_completed_session(self):
        observed = datetime(2026, 7, 2, 20, tzinfo=UTC)
        self.assertEqual("FRESH", classify_session_freshness(observed, datetime(2026, 7, 3, 23, tzinfo=UTC)))
        self.assertEqual("FRESH", classify_session_freshness(observed, datetime(2026, 7, 5, 23, tzinfo=UTC)))

    def test_next_close_has_eight_hour_grace_then_becomes_stale(self):
        observed = datetime(2026, 7, 10, 20, tzinfo=UTC)
        next_close = datetime(2026, 7, 13, 20, tzinfo=UTC)
        self.assertEqual("FRESH", classify_session_freshness(observed, next_close + STALE_GRACE_WINDOW))
        self.assertEqual("STALE", classify_session_freshness(observed, next_close + STALE_GRACE_WINDOW + timedelta(seconds=1)))

    def test_two_completed_sessions_are_stale_without_second_grace(self):
        observed = datetime(2026, 7, 10, 20, tzinfo=UTC)
        self.assertEqual("STALE", classify_session_freshness(observed, datetime(2026, 7, 14, 20, tzinfo=UTC)))

    def test_future_and_naive_timestamps_fail_closed(self):
        reference = datetime(2026, 7, 10, 20, tzinfo=UTC)
        self.assertEqual("UNAVAILABLE", classify_session_freshness(reference + timedelta(seconds=1), reference))
        self.assertEqual("UNAVAILABLE", classify_session_freshness(reference.replace(tzinfo=None), reference))

    def test_calendar_failure_is_conservative_not_fresh(self):
        observed = datetime(2026, 7, 10, 20, tzinfo=UTC)
        with patch("mne.market_calendar._nyse_session_closes", return_value=None):
            self.assertEqual("UNAVAILABLE", classify_session_freshness(observed, observed + timedelta(hours=1)))

    def test_same_input_and_as_of_are_deterministic(self):
        observed = datetime(2026, 7, 10, 20, tzinfo=UTC)
        as_of = datetime(2026, 7, 12, 20, tzinfo=UTC)
        self.assertEqual(classify_session_freshness(observed, as_of), classify_session_freshness(observed, as_of))


if __name__ == "__main__":
    unittest.main()
