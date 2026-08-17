from __future__ import annotations

import logging
from typing import Sequence

from core.config import Config
from core.supabase_optional import create_privileged_client

LOGGER = logging.getLogger("rog.supabase_rag")
TABLE = "document_chunks"


def _client():
    try:
        return create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    except Exception as exc:
        LOGGER.warning("Supabase RAG unavailable: %s", type(exc).__name__)
        return None


def mirror_document(rows: list[dict], *, client=None) -> bool:
    if not rows:
        return False
    remote = client or _client()
    if remote is None:
        return False
    namespace = str(rows[0].get("namespace") or "")
    file_hash = str(rows[0].get("file_hash") or "")
    if not namespace or not file_hash:
        return False
    if any(row.get("namespace") != namespace or row.get("file_hash") != file_hash for row in rows):
        return False
    try:
        remote.table(TABLE).delete().eq("namespace", namespace).eq("file_hash", file_hash).execute()
        for start in range(0, len(rows), 100):
            remote.table(TABLE).upsert(rows[start : start + 100], on_conflict="namespace,file_hash,chunk_index").execute()
        return True
    except Exception as exc:
        LOGGER.warning("Supabase RAG mirror failed: %s", type(exc).__name__)
        return False


def delete_remote_document(file_hash: str, namespace: str, *, client=None) -> bool:
    remote = client or _client()
    if remote is None or not file_hash or not namespace:
        return False
    try:
        remote.table(TABLE).delete().eq("namespace", namespace).eq("file_hash", file_hash).execute()
        return True
    except Exception as exc:
        LOGGER.warning("Supabase RAG delete failed: %s", type(exc).__name__)
        return False


def fetch_remote_chunks(namespaces: Sequence[str], *, limit: int = 250, client=None) -> list[dict]:
    allowed = [str(item) for item in namespaces if item]
    remote = client or _client()
    if remote is None or not allowed:
        return []
    try:
        response = (
            remote.table(TABLE)
            .select("id,namespace,profile,agent_id,file_hash,filename,mime_type,content,chunk_index,chunk_count")
            .in_("namespace", allowed)
            .limit(max(1, min(int(limit), 500)))
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return [row for row in rows if isinstance(row, dict) and row.get("namespace") in allowed]
    except Exception as exc:
        LOGGER.warning("Supabase RAG read failed: %s", type(exc).__name__)
        return []
