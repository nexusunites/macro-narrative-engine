"""Administrator CLI for audited plan and internal-access assignment."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from mne import account_repository
from mne.database import session_scope
from mne.entitlements import PLANS
from mne.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Assign server-controlled MNE account access.")
    parser.add_argument("--actor-email", required=True)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--plan", choices=PLANS)
    internal = parser.add_mutually_exclusive_group()
    internal.add_argument("--internal-full-access", dest="internal_full_access", action="store_true")
    internal.add_argument("--no-internal-full-access", dest="internal_full_access", action="store_false")
    parser.set_defaults(internal_full_access=None)
    args = parser.parse_args()
    if args.plan is None and args.internal_full_access is None:
        parser.error("Specify --plan or an internal-access option.")
    with session_scope() as db:
        actor = db.scalar(select(User).where(User.email == args.actor_email.strip().casefold()))
        target = db.scalar(select(User).where(User.email == args.user_email.strip().casefold()))
        actor_id = actor.user_id if actor else None
        target_id = target.user_id if target else None
    if not actor_id or not target_id or not account_repository.assign_account_access(
        actor_id, target_id, plan=args.plan, internal_full_access=args.internal_full_access
    ):
        print("Access assignment was not authorized or the account was not found.")
        return 1
    print("Account access updated and audited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
