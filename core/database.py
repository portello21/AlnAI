import sqlite3
import json
import logging
import threading
from core.config import Config
from supabase import create_client

class PersistenceManager:
    def __init__(self, db_path="rog_memory.db"):
        self.db = db_path
        self.lock = threading.Lock()
        self.client = None
        try:
            if Config.SUPABASE_URL and Config.SUPABASE_KEY:
                self.client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        except Exception as e:
            logging.error(f"Erro inicializando Supabase: {e}")
        self._init_sqlite()

    def _init_sqlite(self):
        with self.lock:
            with sqlite3.connect(self.db, timeout=10.0) as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS memory (profile TEXT PRIMARY KEY, user_facts TEXT, history TEXT)')

    def save(self, memory_data):
        with self.lock:
            try:
                with sqlite3.connect(self.db, timeout=10.0) as conn:
                    for p, data in memory_data.items():
                        conn.execute('INSERT OR REPLACE INTO memory VALUES (?, ?, ?)', 
                                     (p, json.dumps(data.get("user_facts", [])), json.dumps(data.get("history", {}))))
                if self.client:
                    for p, data in memory_data.items():
                        try:
                            self.client.table("long_term_memory").upsert({
                                "profile": p, 
                                "user_facts": data.get("user_facts", []), 
                                "history": data.get("history", {})
                            }).execute()
                        except Exception:
                            pass
            except Exception as e:
                logging.error(f"Falha na persistência: {e}")

    def load_data(self):
        data = {}
        with self.lock:
            try:
                with sqlite3.connect(self.db, timeout=10.0) as conn:
                    cursor = conn.execute('SELECT profile, user_facts, history FROM memory')
                    for row in cursor:
                        p = row[0]
                        data[p] = {
                            "user_facts": json.loads(row[1]) if row[1] else [],
                            "history": json.loads(row[2]) if row[2] else {}
                        }
            except Exception as e:
                logging.error(f"Falha ao carregar SQLite: {e}")
        return data