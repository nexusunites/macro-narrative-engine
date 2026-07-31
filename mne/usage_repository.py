"""Transactional persistence for monthly usage and live capacity counts."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from mne.database import session_scope
from mne.models import AccountPreferences, FollowedNarrative, SavedHistoricalView, UsageEvent, UsageRecord


def idempotency_key(user_id: str, metric: str, object_reference: str, period_start) -> str:
    value = f"{user_id}\x1f{metric}\x1f{object_reference}\x1f{period_start.isoformat()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def consumed(user_id: str, metric: str, period_start) -> int:
    with session_scope() as db:
        value = db.scalar(select(UsageRecord.consumed).where(
            UsageRecord.user_id == user_id, UsageRecord.metric == metric,
            UsageRecord.period_start == period_start))
        return int(value or 0)


def consume(user_id: str, metric: str, object_reference: str, period_start, period_end, limit: int) -> tuple[bool, bool, int]:
    """Return (allowed, newly_consumed, consumed), charging a unique object once."""
    key = idempotency_key(user_id, metric, object_reference, period_start)
    class LimitReached(Exception):
        pass
    try:
        with session_scope() as db:
            existing = db.scalar(select(UsageEvent.event_id).where(UsageEvent.idempotency_key == key))
            if existing:
                current = db.scalar(select(UsageRecord.consumed).where(
                    UsageRecord.user_id == user_id, UsageRecord.metric == metric,
                    UsageRecord.period_start == period_start)) or 0
                return True, False, int(current)
            values = dict(user_id=user_id, metric=metric, period_start=period_start,
                          period_end=period_end, consumed=0)
            dialect = db.get_bind().dialect.name
            if dialect == "sqlite":
                db.execute(sqlite_insert(UsageRecord).values(**values).on_conflict_do_nothing(
                    index_elements=["user_id", "metric", "period_start"]))
            elif dialect == "postgresql":
                db.execute(postgresql_insert(UsageRecord).values(**values).on_conflict_do_nothing(
                    index_elements=["user_id", "metric", "period_start"]))
            else:
                if not db.scalar(select(UsageRecord.usage_id).where(
                    UsageRecord.user_id == user_id, UsageRecord.metric == metric,
                    UsageRecord.period_start == period_start)):
                    db.add(UsageRecord(**values)); db.flush()
            db.add(UsageEvent(user_id=user_id, metric=metric, period_start=period_start,
                              object_reference=object_reference[:255], idempotency_key=key))
            db.flush()
            changed = db.execute(update(UsageRecord).where(
                UsageRecord.user_id == user_id, UsageRecord.metric == metric,
                UsageRecord.period_start == period_start, UsageRecord.consumed < limit,
            ).values(consumed=UsageRecord.consumed + 1)).rowcount
            if changed != 1:
                raise LimitReached
            current = db.scalar(select(UsageRecord.consumed).where(
                UsageRecord.user_id == user_id, UsageRecord.metric == metric,
                UsageRecord.period_start == period_start)) or 0
            return True, True, int(current)
    except LimitReached:
        return False, False, consumed(user_id, metric, period_start)
    except IntegrityError:
        # A concurrent insert of the same server-derived key won. It is the
        # same distinct object, so the request is allowed without another charge.
        return True, False, consumed(user_id, metric, period_start)


def capacity_count(user_id: str, metric: str) -> int:
    from mne.usage_limits import ALERT_RULES, FOLLOWED_NARRATIVES, SAVED_HISTORICAL_VIEWS
    with session_scope() as db:
        if metric == FOLLOWED_NARRATIVES:
            return int(db.scalar(select(func.count()).select_from(FollowedNarrative).where(FollowedNarrative.user_id == user_id)) or 0)
        if metric == SAVED_HISTORICAL_VIEWS:
            return int(db.scalar(select(func.count()).select_from(SavedHistoricalView).where(SavedHistoricalView.user_id == user_id)) or 0)
        if metric == ALERT_RULES:
            row = db.get(AccountPreferences, user_id)
            return len(row.alert_rules or []) if row else 0
    return 0
