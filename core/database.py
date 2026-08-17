from __future__ import annotations

import json
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
