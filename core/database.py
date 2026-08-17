from __future__ import annotations

import json
import hashlib
import logging
import sqlite3
import threading
import time

from core.config import Config
from core.supabase_optional import create_privileged_client

LOGGER = logging.getLogger("rog.persistence")


class PersistenceManager:
    """Profile-scoped persistence with local SQLite and optional Supabase mirror."""

    def __init__(self, db_path="rog_memory.db"):
        self.db = db_path
        self.lock = threading.RLock()
        self.client = None
        self._remote_blocked_until = 0.0
        self._remote_refresh_started = False
        try:
            self.client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
        except Exception as exc:
            LOGGER.warning("Supabase initialization failed: %s", type(exc).__name__)
        self._init_sqlite()

    def _init_sqlite(self):
        with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory ("
                "profile TEXT PRIMARY KEY, user_facts TEXT, history TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS response_feedback ("
                "profile TEXT NOT NULL, agent_id TEXT NOT NULL, message_hash TEXT NOT NULL, "
                "rating INTEGER NOT NULL, reason TEXT, provider TEXT, model TEXT, created_at INTEGER NOT NULL, "
                "PRIMARY KEY(profile, agent_id, message_hash))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS conversation_archives ("
                "id TEXT PRIMARY KEY, profile TEXT NOT NULL, agent_id TEXT NOT NULL, "
                "title TEXT NOT NULL, messages TEXT NOT NULL, archived_at INTEGER NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_archives_scope ON conversation_archives(profile, agent_id, archived_at DESC)")

    @staticmethod
    def _normalize_profile(profile) -> str:
        return str(profile or "").strip().lower()

    @staticmethod
    def _normalize_record(data) -> dict:
        data = data if isinstance(data, dict) else {}
        facts = data.get("user_facts", [])
        history = data.get("history", {})
        return {
            "user_facts": facts if isinstance(facts, list) else [],
            "history": history if isinstance(history, dict) else {},
        }

    def save(self, memory_data):
        records = {}
        for profile, data in (memory_data or {}).items():
            key = self._normalize_profile(profile)
            if key:
                records[key] = self._normalize_record(data)
        if not records:
            return

        with self.lock:
            try:
                with sqlite3.connect(self.db, timeout=10.0) as conn:
                    for profile, data in records.items():
                        conn.execute(
                            "INSERT OR REPLACE INTO memory(profile, user_facts, history) VALUES (?, ?, ?)",
                            (
                                profile,
                                json.dumps(data["user_facts"], ensure_ascii=False),
                                json.dumps(data["history"], ensure_ascii=False),
                            ),
                        )
            except Exception as exc:
                LOGGER.error("SQLite persistence failed: %s", type(exc).__name__)

            if self.client and Config.SUPABASE_SYNC_MODE != "off" and time.monotonic() >= self._remote_blocked_until:
                threading.Thread(target=self._save_supabase, args=(records,), daemon=True).start()

    def _save_supabase(self, records: dict) -> None:
        for profile, data in records.items():
            try:
                self.client.table("long_term_memory").upsert({
                    "profile": profile,
                    "user_facts": data["user_facts"],
                    "history": data["history"],
                }).execute()
            except Exception as exc:
                self._remote_blocked_until = time.monotonic() + 60.0
                LOGGER.warning("Supabase mirror paused after %s", type(exc).__name__)
                return

    def _load_sqlite(self) -> dict:
        data = {}
        try:
            with sqlite3.connect(self.db, timeout=10.0) as conn:
                cursor = conn.execute("SELECT profile, user_facts, history FROM memory")
                for profile, facts_raw, history_raw in cursor:
                    key = self._normalize_profile(profile)
                    if not key:
                        continue
                    try:
                        facts = json.loads(facts_raw) if facts_raw else []
                    except Exception:
                        facts = []
                    try:
                        history = json.loads(history_raw) if history_raw else {}
                    except Exception:
                        history = {}
                    data[key] = self._normalize_record({"user_facts": facts, "history": history})
        except Exception as exc:
            LOGGER.warning("SQLite load failed: %s", type(exc).__name__)
        return data

    def _load_supabase(self) -> dict:
        if not self.client:
            return {}
        output = {}
        try:
            response = self.client.table("long_term_memory").select("profile,user_facts,history").execute()
            rows = getattr(response, "data", None) or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = self._normalize_profile(row.get("profile"))
                if key:
                    output[key] = self._normalize_record(row)
        except Exception as exc:
            self._remote_blocked_until = time.monotonic() + 60.0
            LOGGER.warning("Supabase mirror paused after %s", type(exc).__name__)
        return output

    def _refresh_remote_cache(self) -> None:
        remote = self._load_supabase()
        if not remote:
            return
        try:
            with self.lock, sqlite3.connect(self.db, timeout=2.0) as conn:
                for profile, data in remote.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO memory(profile, user_facts, history) VALUES (?, ?, ?)",
                        (profile, json.dumps(data["user_facts"], ensure_ascii=False), json.dumps(data["history"], ensure_ascii=False)),
                    )
        except Exception as exc:
            LOGGER.warning("SQLite cache warm failed: %s", type(exc).__name__)

    def load_data(self):
        with self.lock:
            local = self._load_sqlite()
            if self.client and Config.SUPABASE_SYNC_MODE != "off" and not self._remote_refresh_started:
                self._remote_refresh_started = True
                threading.Thread(target=self._refresh_remote_cache, daemon=True).start()
            return local

    def save_feedback(self, *, profile: str, agent_id: str, message_hash: str, rating: int, reason: str = "", provider: str = "", model: str = "") -> bool:
        profile = self._normalize_profile(profile)
        agent_id = str(agent_id or "").strip().lower()[:40]
        message_hash = str(message_hash or "").strip().lower()
        reason = str(reason or "").strip()[:240]
        if not profile or not agent_id or len(message_hash) != 64 or any(char not in "0123456789abcdef" for char in message_hash) or rating not in {-1, 1}:
            return False
        record = {
            "profile": profile,
            "agent_id": agent_id,
            "message_hash": message_hash,
            "rating": rating,
            "reason": reason or None,
            "provider": str(provider or "")[:80] or None,
            "model": str(model or "")[:120] or None,
        }
        try:
            with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO response_feedback(profile,agent_id,message_hash,rating,reason,provider,model,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (profile, agent_id, message_hash, rating, record["reason"], record["provider"], record["model"], int(time.time())),
                )
        except Exception as exc:
            LOGGER.warning("Feedback persistence failed: %s", type(exc).__name__)
            return False
        if self.client and Config.SUPABASE_SYNC_MODE != "off":
            threading.Thread(target=self._save_feedback_supabase, args=(record,), daemon=True).start()
        return True

    def _save_feedback_supabase(self, record: dict) -> None:
        try:
            self.client.table("response_feedback").upsert(record, on_conflict="profile,agent_id,message_hash").execute()
        except Exception as exc:
            LOGGER.warning("Supabase feedback mirror failed: %s", type(exc).__name__)

    def feedback_summary(self, profile: str | None = None) -> dict:
        params: tuple = ()
        where = ""
        if profile:
            where = " WHERE profile = ?"
            params = (self._normalize_profile(profile),)
        try:
            with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
                rows = conn.execute("SELECT rating, COUNT(*) FROM response_feedback" + where + " GROUP BY rating", params).fetchall()
        except Exception:
            rows = []
        counts = {int(rating): int(count) for rating, count in rows}
        return {"positive": counts.get(1, 0), "negative": counts.get(-1, 0), "total": sum(counts.values())}

    def archive_conversation(self, *, profile: str, agent_id: str, messages: list) -> str | None:
        profile = self._normalize_profile(profile)
        agent_id = str(agent_id or "").strip().lower()[:40]
        clean = [item for item in list(messages or [])[-120:] if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and item.get("content")]
        if not profile or not agent_id or not clean:
            return None
        first_user = next((str(item["content"]).strip() for item in clean if item["role"] == "user"), "Conversa")
        title = " ".join(first_user.split())[:80] or "Conversa"
        archived_at = int(time.time())
        archive_id = hashlib.sha256(f"{profile}:{agent_id}:{time.time_ns()}:{title}".encode()).hexdigest()
        payload = json.dumps(clean, ensure_ascii=False)
        try:
            with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
                conn.execute("INSERT INTO conversation_archives(id,profile,agent_id,title,messages,archived_at) VALUES (?,?,?,?,?,?)", (archive_id, profile, agent_id, title, payload, archived_at))
        except Exception as exc:
            LOGGER.warning("Conversation archive failed: %s", type(exc).__name__)
            return None
        if self.client and Config.SUPABASE_SYNC_MODE != "off":
            record = {"id": archive_id, "profile": profile, "agent_id": agent_id, "title": title, "messages": clean}
            threading.Thread(target=self._save_archive_supabase, args=(record,), daemon=True).start()
        return archive_id

    def _save_archive_supabase(self, record: dict) -> None:
        try:
            self.client.table("conversation_archives").upsert(record).execute()
        except Exception as exc:
            LOGGER.warning("Supabase archive mirror failed: %s", type(exc).__name__)

    def list_conversation_archives(self, *, profile: str, agent_id: str, search: str = "", limit: int = 30) -> list[dict]:
        profile = self._normalize_profile(profile)
        agent_id = str(agent_id or "").strip().lower()
        search = str(search or "").strip().casefold()
        try:
            with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
                rows = conn.execute("SELECT id,title,archived_at FROM conversation_archives WHERE profile=? AND agent_id=? ORDER BY archived_at DESC LIMIT ?", (profile, agent_id, max(1, min(int(limit), 100)))).fetchall()
        except Exception:
            rows = []
        output = [{"id": row[0], "title": row[1], "archived_at": row[2]} for row in rows]
        if not output and self.client and Config.SUPABASE_SYNC_MODE != "off":
            try:
                response = (
                    self.client.table("conversation_archives")
                    .select("id,title,archived_at")
                    .eq("profile", profile)
                    .eq("agent_id", agent_id)
                    .order("archived_at", desc=True)
                    .limit(max(1, min(int(limit), 100)))
                    .execute()
                )
                output = [item for item in (getattr(response, "data", None) or []) if isinstance(item, dict)]
            except Exception as exc:
                LOGGER.warning("Supabase archive list failed: %s", type(exc).__name__)
        return [item for item in output if not search or search in item["title"].casefold()]

    def load_conversation_archive(self, *, profile: str, agent_id: str, archive_id: str) -> list[dict]:
        try:
            with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
                row = conn.execute("SELECT messages FROM conversation_archives WHERE id=? AND profile=? AND agent_id=?", (archive_id, self._normalize_profile(profile), str(agent_id or "").strip().lower())).fetchone()
            value = json.loads(row[0]) if row else []
            if not value and self.client and Config.SUPABASE_SYNC_MODE != "off":
                response = (
                    self.client.table("conversation_archives")
                    .select("messages")
                    .eq("id", str(archive_id or ""))
                    .eq("profile", self._normalize_profile(profile))
                    .eq("agent_id", str(agent_id or "").strip().lower())
                    .limit(1)
                    .execute()
                )
                records = getattr(response, "data", None) or []
                value = records[0].get("messages", []) if records and isinstance(records[0], dict) else []
            return [item for item in value if isinstance(item, dict)]
        except Exception:
            return []

    def delete_conversation_archive(self, *, profile: str, agent_id: str, archive_id: str) -> bool:
        profile = self._normalize_profile(profile)
        agent_id = str(agent_id or "").strip().lower()
        with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
            cursor = conn.execute("DELETE FROM conversation_archives WHERE id=? AND profile=? AND agent_id=?", (archive_id, profile, agent_id))
        deleted_local = cursor.rowcount > 0
        if self.client and Config.SUPABASE_SYNC_MODE != "off":
            deleted_remote = self._delete_archive_supabase(archive_id, profile, agent_id)
            return deleted_local or deleted_remote
        return deleted_local

    def _delete_archive_supabase(self, archive_id: str, profile: str, agent_id: str) -> bool:
        try:
            scoped = self.client.table("conversation_archives").select("id").eq("id", archive_id).eq("profile", profile).eq("agent_id", agent_id).limit(1).execute()
            if not (getattr(scoped, "data", None) or []):
                return False
            self.client.table("conversation_archives").delete().eq("id", archive_id).eq("profile", profile).eq("agent_id", agent_id).execute()
            return True
        except Exception as exc:
            LOGGER.warning("Supabase archive delete failed: %s", type(exc).__name__)
            return False
