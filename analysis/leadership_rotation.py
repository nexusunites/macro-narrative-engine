try:
    from storage import load_daily_snapshots
except ModuleNotFoundError:
    from mne.storage import load_daily_snapshots

import statistics
from datetime import date
from typing import Optional


VALID_STATES = {
    "Dominant",
    "Holding",
    "Challenged",
    "Challenging",
    "Emerging",
    "Losing",
    "Stable",
}


def _snapshot_gap(snapshot: dict) -> Optional[float]:
    narratives = snapshot.get("narratives") if isinstance(snapshot, dict) else []
    if not isinstance(narratives, list):
        return None

    leader = next((item for item in narratives if item.get("rank") == 1), None)
    challenger = next((item for item in narratives if item.get("rank") == 2), None)
    if not leader or not challenger:
        return None

    try:
        return float(leader.get("share") or 0) - float(challenger.get("share") or 0)
    except (TypeError, ValueError):
        return None


def _build_history(snapshots: list[dict]) -> dict[str, list[dict]]:
    histories = {}
    for snapshot in snapshots:
        snapshot_date = snapshot.get("date")
        narratives = snapshot.get("narratives") if isinstance(snapshot.get("narratives"), list) else []
        for item in narratives:
            group = item.get("group")
            if not group:
                continue
            histories.setdefault(group, []).append(
                {
                    "date": str(snapshot_date or ""),
                    "share": float(item.get("share") or 0),
                    "rank": int(item.get("rank") or 0),
                    "score": int(item.get("score") or 0),
                }
            )
    return histories


def _are_consecutive_dates(previous_date: str, current_date: str) -> bool:
    try:
        return (date.fromisoformat(current_date) - date.fromisoformat(previous_date)).days == 1
    except (TypeError, ValueError):
        return False


def _are_three_days_apart(earlier_date: str, later_date: str) -> bool:
    try:
        return (date.fromisoformat(later_date) - date.fromisoformat(earlier_date)).days == 3
    except (TypeError, ValueError):
        return False


def compute_rotation(snapshots: list[dict]) -> list[dict]:
    if len(snapshots) < 2:
        if not snapshots:
            return []
        narratives = snapshots[-1].get("narratives") if isinstance(snapshots[-1].get("narratives"), list) else []
        return [
            {
                "group": item.get("group"),
                "rotation_state": "Stable",
                "share_delta": None,
                "rotation_streak": 1,
                "reason": "Not enough daily history for rotation analysis.",
            }
            for item in narratives
            if item.get("group")
        ]

    histories = _build_history(snapshots)
    today_snapshot = snapshots[-1]
    today_narratives = (
        today_snapshot.get("narratives")
        if isinstance(today_snapshot.get("narratives"), list)
        else []
    )
    gap_to_leader = _snapshot_gap(today_snapshot) or 0.0
    gap_three_days_ago = None
    if len(snapshots) >= 3:
        try:
            snapshots_are_adjacent = (
                date.fromisoformat(snapshots[-1]["date"])
                - date.fromisoformat(snapshots[-3]["date"])
            ).days == 2
        except (KeyError, TypeError, ValueError):
            snapshots_are_adjacent = False
        if snapshots_are_adjacent:
            gap_three_days_ago = _snapshot_gap(snapshots[-3])

    rotations = []
    for item in today_narratives:
        group = item.get("group")
        if not group:
            continue

        history = histories.get(group, [])
        today_share = history[-1]["share"]
        has_adjacent_history = len(history) >= 2 and _are_consecutive_dates(
            history[-2]["date"], history[-1]["date"]
        )
        yesterday_share = history[-2]["share"] if has_adjacent_history else None
        share_delta = (
            round(today_share - yesterday_share, 1)
            if yesterday_share is not None
            else None
        )

        current_rank = history[-1]["rank"]
        streak = 1
        current_streak_date = history[-1]["date"]
        for prior in reversed(history[:-1]):
            if not _are_consecutive_dates(prior["date"], current_streak_date):
                break
            if prior["rank"] == current_rank:
                streak += 1
                current_streak_date = prior["date"]
            else:
                break

        gap_narrowing = None
        if len(history) >= 3 and current_rank == 1 and gap_three_days_ago is not None:
            gap_narrowing = gap_three_days_ago - gap_to_leader

        day1_delta = None
        day2_delta = None
        if has_adjacent_history:
            day2_delta = history[-1]["share"] - history[-2]["share"]
        if len(history) >= 3 and _are_consecutive_dates(history[-3]["date"], history[-2]["date"]):
            day1_delta = history[-2]["share"] - history[-3]["share"]

        share_change_3d = None
        if len(history) >= 4 and _are_three_days_apart(history[-4]["date"], history[-1]["date"]):
            share_change_3d = history[-1]["share"] - history[-4]["share"]

        if current_rank == 1 and streak >= 5 and gap_to_leader >= 20:
            rotation_state = "Dominant"
            reason = (
                f"{group} is Dominant: rank 1 for {streak} consecutive days "
                f"with a {gap_to_leader:.1f} pt gap over #2."
            )
        elif current_rank == 1 and streak >= 3 and gap_to_leader >= 10:
            rotation_state = "Holding"
            reason = (
                f"{group} is Holding: rank 1 for {streak} consecutive days "
                f"with a {gap_to_leader:.1f} pt gap over #2."
            )
        elif current_rank == 1 and gap_narrowing is not None and gap_narrowing >= 8:
            rotation_state = "Challenged"
            reason = (
                f"{group} is Challenged: gap to #2 has narrowed by "
                f"{gap_narrowing:.1f} pts over 3 days."
            )
        elif (
            current_rank != 1
            and day1_delta is not None
            and day2_delta is not None
            and day1_delta >= 3
            and day2_delta >= 3
        ):
            rotation_state = "Challenging"
            reason = (
                f"{group} is Challenging: share has grown {share_delta:+.1f} pts "
                "over 2 consecutive days."
            )
        elif (
            current_rank not in (1, 2)
            and share_change_3d is not None
            and share_change_3d >= 5
        ):
            rotation_state = "Emerging"
            reason = f"{group} is Emerging: share up {share_change_3d:.1f} pts over 3 days."
        elif day1_delta is not None and day2_delta is not None and day1_delta <= -3 and day2_delta <= -3:
            rotation_state = "Losing"
            reason = (
                f"{group} is Losing: share has declined {share_delta:.1f} pts "
                "over 2 consecutive days."
            )
        else:
            rotation_state = "Stable"
            reason = (
                f"{group} is Stable: no significant share movement or rank change detected."
            )

        rotations.append(
            {
                "group": group,
                "rotation_state": rotation_state,
                "share_delta": share_delta,
                "rotation_streak": streak,
                "reason": reason,
            }
        )

    return rotations


def get_rotation() -> list[dict]:
    snapshots = load_daily_snapshots(limit=7)
    return compute_rotation(snapshots)
