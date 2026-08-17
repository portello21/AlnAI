from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.config import Config
from core.encrypted_backup import decrypt_backup, restore_tables
from core.supabase_optional import create_privileged_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore an encrypted ROG AI application-data backup.")
    parser.add_argument("backup")
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    if not args.confirm_restore:
        print("Restore refused. Re-run with --confirm-restore after validating the target project.")
        return 2
    key = os.getenv("ROG_BACKUP_ENCRYPTION_KEY", "")
    client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    if client is None or not key:
        print("Supabase or ROG_BACKUP_ENCRYPTION_KEY is unavailable.")
        return 2
    backup = decrypt_backup(Path(args.backup).expanduser().resolve().read_bytes(), key)
    restored = restore_tables(client, backup)
    print(f"Restored {restored} application row(s). Auth users require Supabase managed backup recovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
