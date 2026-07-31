"""Central deterministic authentication, authorization, CSRF, and ownership checks."""

from __future__ import annotations

import hmac
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from mne.auth import SESSION_COOKIE_NAME, resolve_session


def get_current_user(request: Request):
    cached = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached
    resolved = resolve_session(request.cookies.get(SESSION_COOKIE_NAME))
    request.state.current_user = resolved[0] if resolved else False
    request.state.auth_session = resolved[1] if resolved else None
    return resolved[0] if resolved else None


def require_authenticated_user(request: Request):
    user = get_current_user(request)
    if not user:
        target = request.url.path
        if request.url.query:
            target += "?" + request.url.query
        raise HTTPException(status_code=401, detail=quote(target, safe="/?=&"))
    return user


def require_admin(request: Request):
    user = require_authenticated_user(request)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="This area is available to administrators only.")
    return user


def can_access_feature(user, feature: str) -> bool:
    if feature == "admin":
        return bool(user and user.account_status == "ACTIVE" and user.role == "ADMIN")
    return bool(user and user.account_status == "ACTIVE")


def can_modify_resource(user, resource) -> bool:
    return bool(user and str(getattr(resource, "user_id", "")) == str(user.user_id))


def csrf_token(request: Request) -> str | None:
    get_current_user(request)
    session = getattr(request.state, "auth_session", None)
    return session.csrf_token if session else None


def validate_csrf(request: Request, submitted: str | None) -> None:
    expected = csrf_token(request)
    if not expected or not submitted or not hmac.compare_digest(expected, submitted):
        raise HTTPException(status_code=403, detail="This form expired. Refresh the page and try again.")
