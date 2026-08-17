from __future__ import annotations

import json
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

BACKUP_TABLES = (
    "long_term_memory",
    "memories_v2",
    "document_chunks",
    "response_feedback",
    "conversation_archives",
    "rog_user_profiles",
    "rog_api_usage",
    "rog_audit_events",
)


def encrypt_backup(data: dict, key: str) -> bytes:
    return Fernet(str(key or "").encode("ascii")).encrypt(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def decrypt_backup(payload: bytes, key: str) -> dict:
    try:
        value = json.loads(Fernet(str(key or "").encode("ascii")).decrypt(payload).decode("utf-8"))
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid backup or encryption key") from exc
    if not isinstance(value, dict) or value.get("format") != "rog-ai-backup-v1":
        raise ValueError("unsupported backup format")
    return value


def export_tables(client, *, page_size: int = 500) -> dict:
    tables: dict[str, list] = {}
    for table in BACKUP_TABLES:
        rows = []
        start = 0
        while True:
            response = client.table(table).select("*").range(start, start + page_size - 1).execute()
            batch = getattr(response, "data", None) or []
            rows.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < page_size:
                break
            start += page_size
        tables[table] = rows
    return {"format": "rog-ai-backup-v1", "created_at": datetime.now(timezone.utc).isoformat(), "tables": tables}


def restore_tables(client, backup: dict) -> int:
    tables = backup.get("tables") if isinstance(backup, dict) else None
    if not isinstance(tables, dict):
        raise ValueError("backup tables missing")
    restored = 0
    for table in BACKUP_TABLES:
        rows = tables.get(table, [])
        if not isinstance(rows, list):
            raise ValueError(f"invalid table payload: {table}")
        for start in range(0, len(rows), 100):
            batch = [item for item in rows[start : start + 100] if isinstance(item, dict)]
            if batch:
                client.table(table).upsert(batch).execute()
                restored += len(batch)
    return restored
