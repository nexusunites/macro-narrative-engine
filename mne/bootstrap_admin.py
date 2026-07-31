"""One-time interactive ADMIN bootstrap and password-reset token command."""

from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from mne.auth import create_account, generate_password_reset, normalize_email
from mne.database import session_scope
from mne.models import AuditLog, User


def bootstrap_admin() -> int:
    email=normalize_email(os.getenv("MNE_ADMIN_EMAIL", ""))
    if not email:
        print("MNE_ADMIN_EMAIL must name the administrator account."); return 2
    with session_scope() as db:
        if db.scalar(select(User).where(User.role=="ADMIN")):
            print("An administrator already exists; no changes made."); return 0
        user=db.scalar(select(User).where(User.email==email))
    if not user:
        password=getpass.getpass("New administrator password: ")
        display_name=input("Administrator display name: ").strip()
        try: user=create_account(email,password,display_name,accepted_terms=True,accepted_privacy=True)
        except ValueError as error: print(str(error)); return 2
    with session_scope() as db:
        target=db.get(User,user.user_id); target.role="ADMIN"
        db.add(AuditLog(actor_user_id=target.user_id,action="ADMIN_BOOTSTRAPPED",target_ref=target.user_id))
    print(f"Administrator access enabled for {email}."); return 0


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--reset-password", metavar="EMAIL")
    args=parser.parse_args()
    if args.reset_password:
        token=generate_password_reset(args.reset_password)
        if not token: print("No reset token was generated."); return 1
        print("Deliver this one-time token out-of-band; it expires in 30 minutes:")
        print(token); return 0
    return bootstrap_admin()


if __name__=="__main__": raise SystemExit(main())

