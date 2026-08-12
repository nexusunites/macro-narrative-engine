"""Deterministic, fail-closed product entitlement registry."""

from __future__ import annotations

FREE = "FREE"
PRO = "PRO"
TEAM = "TEAM"
PLANS = (FREE, PRO, TEAM)

LIVE_DASHBOARD = "LIVE_DASHBOARD"
RESEARCH_WORKSPACE = "RESEARCH_WORKSPACE"
EVIDENCE_READER = "EVIDENCE_READER"
NARRATIVE_HISTORY = "NARRATIVE_HISTORY"
HISTORICAL_RESEARCH = "HISTORICAL_RESEARCH"
HISTORICAL_COMPARISON = "HISTORICAL_COMPARISON"
HISTORICAL_REQUEST = "HISTORICAL_REQUEST"
AI_ANALYST_PROVIDER = "AI_ANALYST_PROVIDER"
FOLLOWED_NARRATIVES = "FOLLOWED_NARRATIVES"
SAVED_STORIES = "SAVED_STORIES"
ALERT_RULES = "ALERT_RULES"
SAVED_HISTORICAL_VIEWS = "SAVED_HISTORICAL_VIEWS"
EXPORTS = "EXPORTS"
API_ACCESS = "API_ACCESS"
TEAM_WORKSPACE = "TEAM_WORKSPACE"
ADMIN_DIAGNOSTICS = "ADMIN_DIAGNOSTICS"

FEATURES = (
    LIVE_DASHBOARD, RESEARCH_WORKSPACE, EVIDENCE_READER, NARRATIVE_HISTORY,
    HISTORICAL_RESEARCH, HISTORICAL_COMPARISON, HISTORICAL_REQUEST,
    AI_ANALYST_PROVIDER, FOLLOWED_NARRATIVES, SAVED_STORIES, ALERT_RULES,
    SAVED_HISTORICAL_VIEWS, EXPORTS, API_ACCESS, TEAM_WORKSPACE,
    ADMIN_DIAGNOSTICS,
)

_FREE_FEATURES = {
    LIVE_DASHBOARD, RESEARCH_WORKSPACE, EVIDENCE_READER, NARRATIVE_HISTORY,
    HISTORICAL_RESEARCH, HISTORICAL_COMPARISON, HISTORICAL_REQUEST,
    FOLLOWED_NARRATIVES, SAVED_STORIES, ALERT_RULES, SAVED_HISTORICAL_VIEWS,
}
_PRO_FEATURES = _FREE_FEATURES | {AI_ANALYST_PROVIDER}
_TEAM_FEATURES = _PRO_FEATURES | {EXPORTS, API_ACCESS, TEAM_WORKSPACE}
_FEATURE_MATRIX = {FREE: _FREE_FEATURES, PRO: _PRO_FEATURES, TEAM: _TEAM_FEATURES}


class EntitlementDenied(PermissionError):
    def __init__(self, reason: str = "feature_unavailable", metric: str | None = None):
        self.reason = reason
        self.metric = metric
        super().__init__(reason)


def get_plan_entitlements(plan: str) -> frozenset[str]:
    return frozenset(_FEATURE_MATRIX.get(plan, set()))


def check_entitlement(user, feature: str) -> bool:
    if feature not in FEATURES or not user or getattr(user, "account_status", None) != "ACTIVE":
        return False
    if feature == ADMIN_DIAGNOSTICS:
        return getattr(user, "role", None) == "ADMIN"
    if bool(getattr(user, "internal_full_access", False)):
        return True
    return feature in get_plan_entitlements(getattr(user, "plan", None))


def require_entitlement(user, feature: str) -> None:
    if not check_entitlement(user, feature):
        reason = "temporarily_unavailable" if not user or getattr(user, "account_status", None) != "ACTIVE" else "upgrade_required"
        raise EntitlementDenied(reason)


def build_entitlement_context(user) -> dict:
    plan = getattr(user, "plan", None) if user else None
    safe_plan = plan if plan in PLANS else FREE
    return {
        "plan": safe_plan,
        "internal_full_access": bool(user and getattr(user, "internal_full_access", False)),
        "features": {feature: check_entitlement(user, feature) for feature in FEATURES},
    }
