"""Central usage-limit API with UTC calendar-month periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from mne.entitlements import FREE, PRO, TEAM, EntitlementDenied, build_entitlement_context as _base_context
from mne import usage_repository

HISTORICAL_INVESTIGATION_VIEWS = "HISTORICAL_INVESTIGATION_VIEWS"
HISTORICAL_COMPARISONS = "HISTORICAL_COMPARISONS"
HISTORICAL_REQUESTS = "HISTORICAL_REQUESTS"
AI_ANALYST_QUESTIONS = "AI_ANALYST_QUESTIONS"
SAVED_HISTORICAL_VIEWS = "SAVED_HISTORICAL_VIEWS"
FOLLOWED_NARRATIVES = "FOLLOWED_NARRATIVES"
ALERT_RULES = "ALERT_RULES"

CONSUMPTION_METRICS = (HISTORICAL_INVESTIGATION_VIEWS, HISTORICAL_COMPARISONS, HISTORICAL_REQUESTS, AI_ANALYST_QUESTIONS)
CAPACITY_METRICS = (SAVED_HISTORICAL_VIEWS, FOLLOWED_NARRATIVES, ALERT_RULES)
METRICS = CONSUMPTION_METRICS + CAPACITY_METRICS

FREE_HISTORICAL_INVESTIGATIONS_MONTHLY = 3
FREE_HISTORICAL_COMPARISONS_MONTHLY = 1
FREE_HISTORICAL_REQUESTS_MONTHLY = 3
FREE_AI_ANALYST_QUESTIONS_MONTHLY = 0
FREE_FOLLOWED_NARRATIVES = 3
FREE_SAVED_HISTORICAL_VIEWS = 2
FREE_ALERT_RULES = 1
PRO_HISTORICAL_REQUESTS_MONTHLY = 25
PRO_HISTORICAL_INVESTIGATIONS_MONTHLY = 25
PRO_HISTORICAL_COMPARISONS_MONTHLY = 25
PRO_AI_ANALYST_QUESTIONS_MONTHLY = 0
PRO_FOLLOWED_NARRATIVES = 25
PRO_SAVED_HISTORICAL_VIEWS = 50
PRO_ALERT_RULES = 20
TEAM_HISTORICAL_REQUESTS_MONTHLY = 100
TEAM_HISTORICAL_INVESTIGATIONS_MONTHLY = 100
TEAM_HISTORICAL_COMPARISONS_MONTHLY = 100
TEAM_AI_ANALYST_QUESTIONS_MONTHLY = 0
TEAM_FOLLOWED_NARRATIVES = 100
TEAM_SAVED_HISTORICAL_VIEWS = 200
TEAM_ALERT_RULES = 100
INTERNAL_FULL_ACCESS_LIMIT = 1_000_000_000

_LIMITS = {
    FREE: {HISTORICAL_INVESTIGATION_VIEWS: FREE_HISTORICAL_INVESTIGATIONS_MONTHLY,
           HISTORICAL_COMPARISONS: FREE_HISTORICAL_COMPARISONS_MONTHLY,
           HISTORICAL_REQUESTS: FREE_HISTORICAL_REQUESTS_MONTHLY,
           AI_ANALYST_QUESTIONS: FREE_AI_ANALYST_QUESTIONS_MONTHLY,
           FOLLOWED_NARRATIVES: FREE_FOLLOWED_NARRATIVES,
           SAVED_HISTORICAL_VIEWS: FREE_SAVED_HISTORICAL_VIEWS, ALERT_RULES: FREE_ALERT_RULES},
    PRO: {HISTORICAL_INVESTIGATION_VIEWS: PRO_HISTORICAL_INVESTIGATIONS_MONTHLY,
          HISTORICAL_COMPARISONS: PRO_HISTORICAL_COMPARISONS_MONTHLY,
          HISTORICAL_REQUESTS: PRO_HISTORICAL_REQUESTS_MONTHLY,
          AI_ANALYST_QUESTIONS: PRO_AI_ANALYST_QUESTIONS_MONTHLY,
          FOLLOWED_NARRATIVES: PRO_FOLLOWED_NARRATIVES,
          SAVED_HISTORICAL_VIEWS: PRO_SAVED_HISTORICAL_VIEWS, ALERT_RULES: PRO_ALERT_RULES},
    TEAM: {HISTORICAL_INVESTIGATION_VIEWS: TEAM_HISTORICAL_INVESTIGATIONS_MONTHLY,
           HISTORICAL_COMPARISONS: TEAM_HISTORICAL_COMPARISONS_MONTHLY,
           HISTORICAL_REQUESTS: TEAM_HISTORICAL_REQUESTS_MONTHLY,
           AI_ANALYST_QUESTIONS: TEAM_AI_ANALYST_QUESTIONS_MONTHLY,
           FOLLOWED_NARRATIVES: TEAM_FOLLOWED_NARRATIVES,
           SAVED_HISTORICAL_VIEWS: TEAM_SAVED_HISTORICAL_VIEWS, ALERT_RULES: TEAM_ALERT_RULES},
}


@dataclass(frozen=True)
class UsageResult:
    allowed: bool
    consumed: int
    remaining: int
    newly_consumed: bool = False


def monthly_period(at: datetime | None = None) -> tuple[datetime, datetime]:
    value = at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    start = datetime(value.year, value.month, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    if value.month == 12:
        end = datetime(value.year + 1, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    else:
        end = datetime(value.year, value.month + 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    return start, end


def get_usage_limit(user, metric: str) -> int:
    if metric not in METRICS or not user or getattr(user, "account_status", None) != "ACTIVE":
        return 0
    if getattr(user, "internal_full_access", False):
        return INTERNAL_FULL_ACCESS_LIMIT
    return _LIMITS.get(getattr(user, "plan", None), {}).get(metric, 0)


def get_usage_consumed(user, metric: str, at: datetime | None = None) -> int:
    if metric in CAPACITY_METRICS:
        return usage_repository.capacity_count(user.user_id, metric) if user else 0
    if metric in CONSUMPTION_METRICS and user:
        return usage_repository.consumed(user.user_id, metric, monthly_period(at)[0])
    return 0


def get_usage_remaining(user, metric: str, at: datetime | None = None) -> int:
    return max(0, get_usage_limit(user, metric) - get_usage_consumed(user, metric, at))


def can_consume_usage(user, metric: str, amount: int = 1, at: datetime | None = None) -> bool:
    return amount == 1 and get_usage_remaining(user, metric, at) >= 1


def consume_usage(user, metric: str, amount: int = 1, *, object_reference: str, at: datetime | None = None) -> UsageResult:
    if amount != 1 or metric not in CONSUMPTION_METRICS or not object_reference or not user or getattr(user, "account_status", None) != "ACTIVE":
        raise EntitlementDenied("temporarily_unavailable", metric)
    limit = get_usage_limit(user, metric)
    start, end = monthly_period(at)
    allowed, fresh, consumed = usage_repository.consume(user.user_id, metric, str(object_reference), start, end, limit)
    if not allowed:
        raise EntitlementDenied("monthly_allowance_used", metric)
    return UsageResult(True, consumed, max(0, limit - consumed), fresh)


def require_capacity(user, metric: str) -> None:
    if metric not in CAPACITY_METRICS or not can_consume_usage(user, metric):
        raise EntitlementDenied("capacity_reached", metric)


def build_entitlement_context(user) -> dict:
    context = _base_context(user)
    context["usage"] = {
        metric: {"limit": get_usage_limit(user, metric), "used": get_usage_consumed(user, metric), "remaining": get_usage_remaining(user, metric)}
        for metric in METRICS
    }
    return context
