"""Self-hosted credentials and opaque server-side session services."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import and_, func, or_, select

from mne.database import session_scope
from mne.models import AuthSession, LoginAttempt, PasswordResetToken, User

MIN_PASSWORD_LENGTH = 10
SESSION_ABSOLUTE_EXPIRY = timedelta(days=30)
SESSION_IDLE_EXPIRY = timedelta(days=7)
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=15)
LOGIN_LOCKOUT_WINDOW = timedelta(minutes=15)
LOGIN_MAX_ACCOUNT_ATTEMPTS = 5
LOGIN_MAX_IP_ATTEMPTS = 20
PASSWORD_RESET_EXPIRY = timedelta(minutes=30)
SESSION_COOKIE_NAME = "mne_session"
AUTH_ERROR = "The email or password was not recognized."

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash("mne-comparable-timing-placeholder")


def utcnow() -> datetime:
    # SQLAlchemy's SQLite dialect returns naive UTC values; use the same
    # representation across dialects so expiry comparisons remain portable.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return (email or "").strip().casefold()


def hash_password(password: str) -> str:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_account(email: str, password: str, display_name: str, *, accepted_terms: bool, accepted_privacy: bool) -> User:
    normalized = normalize_email(email)
    name = (display_name or "").strip()
    if "@" not in normalized or len(normalized) > 320 or not name or len(name) > 120:
        raise ValueError("Check the account details and try again.")
    if not accepted_terms or not accepted_privacy:
        raise ValueError("Accept the terms and privacy notice to continue.")
    password_hash = hash_password(password)
    now = utcnow()
    with session_scope() as db:
        if db.scalar(select(User.user_id).where(User.email == normalized)):
            raise ValueError("An account could not be created with those details.")
        user = User(email=normalized, password_hash=password_hash, display_name=name,
                    role="USER", plan="FREE", terms_accepted_at=now, privacy_accepted_at=now)
        db.add(user)
        db.flush()
        return user


def _rate_limited(db, email: str, ip: str, now: datetime) -> bool:
    cutoff = now - LOGIN_ATTEMPT_WINDOW
    account = db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.email == email, LoginAttempt.attempted_at >= cutoff, LoginAttempt.succeeded.is_(False))) or 0
    address = db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.ip_address == ip, LoginAttempt.attempted_at >= cutoff, LoginAttempt.succeeded.is_(False))) or 0
    return account >= LOGIN_MAX_ACCOUNT_ATTEMPTS or address >= LOGIN_MAX_IP_ATTEMPTS


def authenticate(email: str, password: str, ip_address: str) -> User | None:
    normalized, ip, now = normalize_email(email), (ip_address or "unknown")[:64], utcnow()
    with session_scope() as db:
        if _rate_limited(db, normalized, ip, now):
            return None
        user = db.scalar(select(User).where(User.email == normalized))
        valid = verify_password(user.password_hash if user else _dummy_hash, password or "")
        success = bool(user and valid and user.account_status == "ACTIVE")
        db.add(LoginAttempt(email=normalized, ip_address=ip, succeeded=success))
        if not success:
            return None
        user.last_login_at = now
        db.flush()
        return user


def create_session(user_id: str) -> AuthSession:
    now = utcnow()
    record = AuthSession(session_id=secrets.token_urlsafe(32), user_id=user_id,
                         csrf_token=secrets.token_urlsafe(32), created_at=now,
                         last_seen_at=now, expires_at=now + SESSION_ABSOLUTE_EXPIRY)
    with session_scope() as db:
        db.add(record); db.flush()
        return record


def resolve_session(session_id: str | None, *, touch: bool = True) -> tuple[User, AuthSession] | None:
    if not session_id:
        return None
    now = utcnow()
    with session_scope() as db:
        record = db.get(AuthSession, session_id)
        if not record or record.invalidated or record.expires_at <= now or record.last_seen_at + SESSION_IDLE_EXPIRY <= now:
            if record:
                record.invalidated = True
            return None
        user = db.get(User, record.user_id)
        if not user or user.account_status != "ACTIVE":
            record.invalidated = True
            return None
        if touch:
            record.last_seen_at = now
        db.flush()
        db.expunge(user); db.expunge(record)
        return user, record


def invalidate_session(session_id: str | None) -> None:
    if not session_id:
        return
    with session_scope() as db:
        record = db.get(AuthSession, session_id)
        if record:
            record.invalidated = True


def disable_account(user_id: str) -> None:
    with session_scope() as db:
        user = db.get(User, user_id)
        if user:
            user.account_status = "DISABLED"
            for record in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
                record.invalidated = True


def generate_password_reset(email: str) -> str | None:
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if not user:
            return None
        db.add(PasswordResetToken(user_id=user.user_id, token_hash=digest, expires_at=utcnow() + PASSWORD_RESET_EXPIRY))
    return raw


def consume_password_reset(token: str, new_password: str) -> bool:
    digest, now = hashlib.sha256((token or "").encode()).hexdigest(), utcnow()
    new_hash = hash_password(new_password)
    with session_scope() as db:
        record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest))
        if not record or record.consumed_at or record.expires_at <= now:
            return False
        user = db.get(User, record.user_id)
        if not user:
            return False
        user.password_hash = new_hash; record.consumed_at = now
        for session in db.scalars(select(AuthSession).where(AuthSession.user_id == user.user_id)):
            session.invalidated = True
        return True


def secure_cookies() -> bool:
    value = os.getenv("MNE_SECURE_COOKIES")
    if value is not None:
        return value.strip().lower() not in {"0", "false", "no"}
    return os.getenv("MNE_ENV", "production").lower() != "development"
