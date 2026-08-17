from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.config import Config
from core.encrypted_backup import encrypt_backup, export_tables
from core.supabase_optional import create_privileged_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an encrypted ROG AI application-data backup.")
    parser.add_argument("--output", required=True, help="Destination outside the repository, ending in .rogbackup")
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    key = os.getenv("ROG_BACKUP_ENCRYPTION_KEY", "")
    client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    if client is None or not key:
        print("Supabase or ROG_BACKUP_ENCRYPTION_KEY is unavailable.")
        return 2
    if output.suffix != ".rogbackup":
        print("Backup destination must end in .rogbackup.")
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encrypt_backup(export_tables(client), key))
    print(f"Encrypted backup written to {output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
