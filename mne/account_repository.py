"""Repository boundary for all account-owned persistence."""

from __future__ import annotations

from sqlalchemy import select

from mne.alert_engine import build_default_alert_state
from mne.database import session_scope
from mne.entitlements import PLANS
from mne.models import AccountPreferences, AlertState, AnonymousProfileDecision, AuditLog, FollowedNarrative, HistoricalRequestOwner, SavedHistoricalView, User
from mne.personalization import SUPPORTED_ALERT_TYPES, build_default_preferences, validate_preferences


def get_user(user_id: str) -> User | None:
    with session_scope() as db:
        user = db.get(User, user_id)
        if user: db.expunge(user)
        return user


def update_display_name(user_id: str, display_name: str) -> bool:
    name = (display_name or "").strip()
    if not name or len(name) > 120: return False
    with session_scope() as db:
        user = db.get(User, user_id)
        if not user: return False
        user.display_name = name
        return True


def assign_account_access(actor_user_id: str, target_user_id: str, *, plan: str | None = None,
                          internal_full_access: bool | None = None) -> bool:
    """The sole audited repository path for server-controlled product access."""
    if plan is not None and plan not in PLANS:
        raise ValueError("Invalid plan.")
    with session_scope() as db:
        actor, target = db.get(User, actor_user_id), db.get(User, target_user_id)
        if not actor or actor.account_status != "ACTIVE" or actor.role != "ADMIN" or not target:
            return False
        details = {"old_plan": target.plan, "new_plan": target.plan,
                   "old_internal_full_access": bool(target.internal_full_access),
                   "new_internal_full_access": bool(target.internal_full_access)}
        if plan is not None:
            target.plan = plan
            details["new_plan"] = plan
        if internal_full_access is not None:
            target.internal_full_access = bool(internal_full_access)
            details["new_internal_full_access"] = bool(internal_full_access)
        if details["old_plan"] == details["new_plan"] and details["old_internal_full_access"] == details["new_internal_full_access"]:
            return True
        db.add(AuditLog(actor_user_id=actor_user_id, action="ACCOUNT_ACCESS_CHANGED",
                        target_ref=target_user_id, details=details))
        return True


def load_preferences(user_id: str) -> dict:
    with session_scope() as db:
        settings = db.get(AccountPreferences, user_id)
        if not settings:
            settings = AccountPreferences(user_id=user_id, preferred_alert_types=list(SUPPORTED_ALERT_TYPES))
            db.add(settings); db.flush()
        followed = db.scalars(select(FollowedNarrative).where(FollowedNarrative.user_id == user_id).order_by(FollowedNarrative.id)).all()
        views = db.scalars(select(SavedHistoricalView).where(SavedHistoricalView.user_id == user_id).order_by(SavedHistoricalView.id)).all()
        result = build_default_preferences()
        result["profile_type"] = "account"
        result.update(enabled=settings.enabled, preferred_alert_types=list(settings.preferred_alert_types or []),
                      alert_thresholds=dict(settings.alert_thresholds or {}), alert_rules=list(settings.alert_rules or []),
                      followed_narratives=[{"narrative_level": x.narrative_level, "narrative_key": x.narrative_key} for x in followed],
                      saved_historical_views=[{"view_type": x.view_type, "replay_ids": list(x.replay_ids), "label": x.label} for x in views])
        return result


def save_preferences(user_id: str, profile: dict) -> dict:
    normalized = validate_preferences(profile)
    if normalized is None: raise ValueError("Invalid account preference profile.")
    with session_scope() as db:
        settings = db.get(AccountPreferences, user_id) or AccountPreferences(user_id=user_id)
        db.add(settings); settings.enabled=normalized["enabled"]; settings.preferred_alert_types=normalized["preferred_alert_types"]
        settings.alert_thresholds=normalized["alert_thresholds"]; settings.alert_rules=normalized["alert_rules"]
        existing = {(x.narrative_level,x.narrative_key):x for x in db.scalars(select(FollowedNarrative).where(FollowedNarrative.user_id==user_id))}
        wanted = {(x["narrative_level"],x["narrative_key"]) for x in normalized["followed_narratives"]}
        for key,row in existing.items():
            if key not in wanted: db.delete(row)
        for level,key in wanted-existing.keys(): db.add(FollowedNarrative(user_id=user_id,narrative_level=level,narrative_key=key))
        old = {x.identity_key:x for x in db.scalars(select(SavedHistoricalView).where(SavedHistoricalView.user_id==user_id))}
        wanted_views = {f'{x["view_type"]}:{"|".join(x["replay_ids"])}':x for x in normalized["saved_historical_views"]}
        for key,row in old.items():
            if key not in wanted_views: db.delete(row)
        for identity,item in wanted_views.items():
            if identity not in old: db.add(SavedHistoricalView(user_id=user_id,identity_key=identity,**item))
    return load_preferences(user_id)


def load_alert_state(user_id: str) -> dict:
    with session_scope() as db:
        row=db.get(AlertState,user_id)
        if not row: return build_default_alert_state()
        return {"schema_version":1,"last_evaluated_run_id":row.last_evaluated_run_id,"meaningful_run_count":row.meaningful_run_count,
                "rule_last_triggered_run":dict(row.rule_last_triggered_run or {}),"events":list(row.events or []),"limitation_note":None}


def save_alert_state(user_id: str, state: dict) -> None:
    with session_scope() as db:
        row=db.get(AlertState,user_id) or AlertState(user_id=user_id); db.add(row)
        row.last_evaluated_run_id=state.get("last_evaluated_run_id"); row.meaningful_run_count=int(state.get("meaningful_run_count") or 0)
        row.rule_last_triggered_run=dict(state.get("rule_last_triggered_run") or {}); row.events=list(state.get("events") or [])


def migration_status(user_id: str, anonymous_exists: bool) -> dict:
    with session_scope() as db:
        own=db.get(AnonymousProfileDecision,user_id)
        claimed=db.scalar(select(AnonymousProfileDecision).where(AnonymousProfileDecision.global_claim.is_(True)))
        return {"offered": bool(anonymous_exists and not own and not claimed), "decision": own.decision if own else None,
                "claimed": bool(claimed), "summary": dict(own.summary or {}) if own else {}}


def record_migration_decision(user_id: str, decision: str, summary: dict | None=None) -> bool:
    if decision not in {"IMPORTED","DECLINED"}: raise ValueError("Invalid migration decision.")
    with session_scope() as db:
        if db.get(AnonymousProfileDecision,user_id): return False
        if decision=="IMPORTED" and db.scalar(select(AnonymousProfileDecision).where(AnonymousProfileDecision.global_claim.is_(True))): return False
        db.add(AnonymousProfileDecision(user_id=user_id,decision=decision,summary=summary or {},global_claim=decision=="IMPORTED"))
        return True


def claim_historical_request(user_id: str, request_id: str) -> None:
    with session_scope() as db:
        db.add(HistoricalRequestOwner(user_id=user_id, request_id=request_id))


def owns_historical_request(user_id: str, request_id: str) -> bool:
    with session_scope() as db:
        row=db.get(HistoricalRequestOwner,request_id)
        return bool(row and row.user_id==user_id)


def record_admin_action(actor_user_id: str, action: str, target_ref: str | None=None, details: dict | None=None) -> None:
    with session_scope() as db:
        db.add(AuditLog(actor_user_id=actor_user_id,action=action,target_ref=target_ref,details=details or {}))
