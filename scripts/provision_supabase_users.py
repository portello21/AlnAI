from __future__ import annotations

import os
import sys

from core.auth_v8 import ALLOWED_PROFILES
from core.config import Config
from core.supabase_optional import create_privileged_client


def main() -> int:
    client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    if client is None:
        print("Privileged Supabase configuration is unavailable.")
        return 2
    changed = 0
    for profile in ALLOWED_PROFILES:
        email = Config.profile_auth_email(profile)
        password = os.getenv(f"{profile.upper()}_PASSWORD", "")
        if not email or not password:
            print(f"{profile}: skipped (email/password environment variables are incomplete)")
            continue
        response = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "app_metadata": {"rog_profile": profile, "rog_role": "admin" if profile == "Allan" else "member"},
        })
        user = getattr(response, "user", None)
        user_id = str(getattr(user, "id", "") or "")
        if not user_id:
            print(f"{profile}: provisioning failed")
            continue
        client.table("rog_user_profiles").upsert({
            "user_id": user_id,
            "profile": profile.casefold(),
            "role": "admin" if profile == "Allan" else "member",
            "active": True,
        }, on_conflict="user_id").execute()
        changed += 1
        print(f"{profile}: provisioned")
    print(f"Provisioned {changed} profile(s). Passwords were not printed.")
    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())
