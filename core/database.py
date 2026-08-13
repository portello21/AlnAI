from __future__ import annotations

import json
import logging
import sqlite3
import threading

from core.config import Config

try:
    from supabase import create_client
except Exception:  # graceful local/test fallback
    create_client = None

LOGGER = logging.getLogger("rog.persistence")


class PersistenceManager:
    """Profile-scoped persistence with local SQLite and optional Supabase mirror."""

    def __init__(self, db_path="rog_memory.db"):
        self.db = db_path
        self.lock = threading.RLock()
        self.client = None
        try:
            if create_client and Config.SUPABASE_URL and Config.SUPABASE_KEY:
                self.client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        except Exception as exc:
            LOGGER.warning("Supabase initialization failed: %s", type(exc).__name__)
        self._init_sqlite()

    def _init_sqlite(self):
        with self.lock, sqlite3.connect(self.db, timeout=10.0) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory ("
                "profile TEXT PRIMARY KEY, user_facts TEXT, history TEXT)"
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

            if self.client:
                for profile, data in records.items():
                    try:
                        self.client.table("long_term_memory").upsert({
                            "profile": profile,
                            "user_facts": data["user_facts"],
                            "history": data["history"],
                        }).execute()
                    except Exception as exc:
                        LOGGER.warning("Supabase save failed for profile %s: %s", profile, type(exc).__name__)

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
            LOGGER.warning("Supabase load failed: %s", type(exc).__name__)
        return output

    def load_data(self):
        with self.lock:
            local = self._load_sqlite()
            remote = self._load_supabase()
            if remote:
                local.update(remote)
                # Warm the local cache without a second network write.
                try:
                    with sqlite3.connect(self.db, timeout=10.0) as conn:
                        for profile, data in remote.items():
                            conn.execute(
                                "INSERT OR REPLACE INTO memory(profile, user_facts, history) VALUES (?, ?, ?)",
                                (
                                    profile,
                                    json.dumps(data["user_facts"], ensure_ascii=False),
                                    json.dumps(data["history"], ensure_ascii=False),
                                ),
                            )
                except Exception as exc:
                    LOGGER.warning("SQLite cache warm failed: %s", type(exc).__name__)
            return local
