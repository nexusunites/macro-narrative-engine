"""Explicit development-only account fixture command."""
import os
from mne.auth import create_account

def main():
    if os.getenv("MNE_DEV_MODE", "").lower() not in {"1","true","yes"}:
        print("Development users require MNE_DEV_MODE=true."); return 2
    try:
        create_account("user@example.test","development-only-password","Development User",accepted_terms=True,accepted_privacy=True)
    except ValueError:
        print("Development user already exists or could not be created."); return 0
    print("Development user created."); return 0
if __name__=="__main__": raise SystemExit(main())
