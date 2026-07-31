"""Account workflows, including validated anonymous-profile migration."""

from __future__ import annotations

import json
from pathlib import Path

from mne import account_repository
from mne.narrative_signals import NARRATIVE_GROUPS
from mne.personalization import preferences_path, validate_preferences
from mne.source_registry import load_source_registry


def anonymous_profile_status(user_id: str, data_dir: Path | None = None) -> dict:
    return account_repository.migration_status(user_id, preferences_path(data_dir).is_file())


def decline_anonymous_profile(user_id: str) -> bool:
    return account_repository.record_migration_decision(user_id, "DECLINED")


def import_anonymous_profile(user_id: str, data_dir: Path | None = None) -> dict:
    path = preferences_path(data_dir)
    summary = {"followed_imported": 0, "views_imported": 0, "skipped": 0}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        profile = validate_preferences(raw)
    except (OSError, json.JSONDecodeError):
        profile = None
    if profile is None:
        summary["skipped"] += 1
        return {"imported": False, "summary": summary}
    load_source_registry()  # validates registry availability without changing it
    taxonomy_path = Path(__file__).resolve().parents[1] / "config" / "theme_taxonomy.json"
    try:
        taxonomy_data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        taxonomy_data = {}
    valid_themes = set((taxonomy_data.get("themes") or {}).keys())
    valid_groups = set(NARRATIVE_GROUPS)
    valid_followed=[]
    for item in profile["followed_narratives"]:
        allowed = item["narrative_key"] in (valid_themes if item["narrative_level"]=="theme" else valid_groups)
        if allowed: valid_followed.append(item)
        else: summary["skipped"] += 1
    valid_views=[]
    for view in profile["saved_historical_views"]:
        # Safe loaders ultimately require the referenced replay files to exist.
        from mne.historical_research import load_replay_for_historical_research
        try:
            for replay_id in view["replay_ids"]: load_replay_for_historical_research(replay_id)
            valid_views.append(view)
        except Exception: summary["skipped"] += 1
    profile["followed_narratives"], profile["saved_historical_views"] = valid_followed, valid_views
    if not account_repository.record_migration_decision(user_id,"IMPORTED",summary):
        return {"imported":False,"summary":summary}
    account_repository.save_preferences(user_id,profile)
    summary["followed_imported"],summary["views_imported"] = len(valid_followed),len(valid_views)
    return {"imported":True,"summary":summary}
