from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import Config
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "rog_memory_v2.db"

TABLE_NAME = "memories_v2"


VALID_MEMORY_TYPES = {
    "fact",
    "preference",
    "goal",
    "constraint",
    "identity",
    "routine",
    "project",
    "relationship",
    "finance",
    "work",
    "learning",
    "other",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    return " ".join(
        (value or "").strip().split()
    )


def make_memory_id(
    profile: str,
    memory_type: str,
    content: str,
) -> str:

    raw = (
        f"{profile.strip().lower()}|"
        f"{memory_type.strip().lower()}|"
        f"{normalize_text(content).lower()}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


class MemoryEngine:

    def __init__(self, db_path: Optional[str] = None):

        self.db_path = Path(
            db_path
        ) if db_path else DB_PATH

        self.lock = threading.RLock()
        self.client = None

        try:
            if Config.SUPABASE_URL and Config.SUPABASE_KEY:
                self.client = create_client(
                    Config.SUPABASE_URL,
                    Config.SUPABASE_KEY,
                )
        except Exception:
            self.client = None

        self._init_sqlite()


    def _connect(self):
        return sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
        )


    def _init_sqlite(self):

        with self.lock:
            with self._connect() as conn:

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories_v2 (
                        id TEXT PRIMARY KEY,
                        profile TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        importance REAL NOT NULL DEFAULT 0.5,
                        confidence REAL NOT NULL DEFAULT 1.0,
                        source TEXT,
                        metadata TEXT,
                        active INTEGER NOT NULL DEFAULT 1,
                        usage_count INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_used_at TEXT
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_profile
                    ON memories_v2(profile)
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_type
                    ON memories_v2(memory_type)
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_active
                    ON memories_v2(active)
                    """
                )


    def add_memory(
        self,
        profile: str,
        content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "user",
        metadata: Optional[dict] = None,
    ) -> dict:

        profile = normalize_text(profile)
        content = normalize_text(content)
        memory_type = normalize_text(memory_type).lower()

        if not profile:
            raise ValueError("profile obrigatorio")

        if not content:
            raise ValueError("content obrigatorio")

        if memory_type not in VALID_MEMORY_TYPES:
            memory_type = "other"

        importance = max(
            0.0,
            min(float(importance), 1.0)
        )

        confidence = max(
            0.0,
            min(float(confidence), 1.0)
        )

        memory_id = make_memory_id(
            profile,
            memory_type,
            content,
        )

        now = utc_now()

        metadata = dict(metadata or {})

        with self.lock:
            with self._connect() as conn:

                existing = conn.execute(
                    """
                    SELECT created_at, usage_count
                    FROM memories_v2
                    WHERE id = ?
                    """,
                    (memory_id,),
                ).fetchone()

                created_at = (
                    existing[0]
                    if existing
                    else now
                )

                usage_count = (
                    existing[1]
                    if existing
                    else 0
                )

                conn.execute(
                    """
                    INSERT OR REPLACE INTO memories_v2 (
                        id,
                        profile,
                        memory_type,
                        content,
                        importance,
                        confidence,
                        source,
                        metadata,
                        active,
                        usage_count,
                        created_at,
                        updated_at,
                        last_used_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        profile,
                        memory_type,
                        content,
                        importance,
                        confidence,
                        source,
                        json.dumps(
                            metadata,
                            ensure_ascii=False
                        ),
                        1,
                        usage_count,
                        created_at,
                        now,
                        None,
                    ),
                )

        record = {
            "id": memory_id,
            "profile": profile,
            "memory_type": memory_type,
            "content": content,
            "importance": importance,
            "confidence": confidence,
            "source": source,
            "metadata": metadata,
            "active": True,
            "usage_count": usage_count,
            "created_at": created_at,
            "updated_at": now,
            "last_used_at": None,
        }

        self._sync_remote(record)

        return record


    def _sync_remote(self, record: dict) -> dict:

        if not self.client:
            return {
                "success": False,
                "error": "supabase_client_unavailable",
            }

        try:
            response = self.client.table(TABLE_NAME).upsert(
                {
                    "id": record["id"],
                    "profile": record["profile"],
                    "memory_type": record["memory_type"],
                    "content": record["content"],
                    "importance": record["importance"],
                    "confidence": record["confidence"],
                    "source": record["source"],
                    "metadata": record["metadata"],
                    "active": record["active"],
                    "usage_count": record["usage_count"],
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                    "last_used_at": record["last_used_at"],
                }
            ).execute()

            return {
                "success": True,
                "rows": len(response.data or []),
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "rows": 0,
                "error": str(exc),
            }


    def list_memories(
        self,
        profile: str,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[dict]:

        profile = normalize_text(profile)

        sql = """
            SELECT
                id,
                profile,
                memory_type,
                content,
                importance,
                confidence,
                source,
                metadata,
                active,
                usage_count,
                created_at,
                updated_at,
                last_used_at
            FROM memories_v2
            WHERE profile = ?
        """

        params = [profile]

        if active_only:
            sql += " AND active = 1"

        sql += """
            ORDER BY
                importance DESC,
                updated_at DESC
            LIMIT ?
        """

        params.append(limit)

        with self.lock:
            with self._connect() as conn:

                rows = conn.execute(
                    sql,
                    params,
                ).fetchall()

        output = []

        for row in rows:

            try:
                metadata = json.loads(
                    row[7]
                ) if row[7] else {}
            except Exception:
                metadata = {}

            output.append(
                {
                    "id": row[0],
                    "profile": row[1],
                    "memory_type": row[2],
                    "content": row[3],
                    "importance": row[4],
                    "confidence": row[5],
                    "source": row[6],
                    "metadata": metadata,
                    "active": bool(row[8]),
                    "usage_count": row[9],
                    "created_at": row[10],
                    "updated_at": row[11],
                    "last_used_at": row[12],
                }
            )

        return output


    def search_memories(
        self,
        profile: str,
        query: str,
        limit: int = 8,
    ) -> list[dict]:

        profile = normalize_text(profile)
        query = normalize_text(query).lower()

        if not profile:
            return []

        if limit <= 0:
            return []

        memories = self.list_memories(
            profile=profile,
            active_only=True,
            limit=500,
        )

        if not memories:
            return []

        if not query:
            return memories[:limit]

        # ----------------------------------------------------
        # Lexical preparation
        # ----------------------------------------------------

        query_terms = {
            term
            for term in query.split()
            if len(term) >= 3
        }

        # ----------------------------------------------------
        # Semantic embeddings
        #
        # Reutiliza o mesmo embedding model do Vector RAG.
        # Os embeddings sao normalizados no vector_rag,
        # portanto dot product equivale a cosine similarity.
        # ----------------------------------------------------

        semantic_scores = {}

        try:

            from core.vector_rag import (
                _embed_documents,
                _embed_query,
            )

            contents = [
                memory["content"]
                for memory in memories
            ]

            query_embedding = _embed_query(
                query
            )

            memory_embeddings = _embed_documents(
                contents
            )

            for memory, embedding in zip(
                memories,
                memory_embeddings,
            ):

                similarity = sum(
                    a * b
                    for a, b in zip(
                        query_embedding,
                        embedding,
                    )
                )

                semantic_scores[
                    memory["id"]
                ] = max(
                    -1.0,
                    min(
                        1.0,
                        float(similarity),
                    ),
                )

        except Exception:

            # Retrieval lexical continua funcionando
            # mesmo se o embedding estiver indisponivel.
            semantic_scores = {}

        # ----------------------------------------------------
        # Hybrid scoring
        # ----------------------------------------------------

        scored = []

        for memory in memories:

            content_lower = memory[
                "content"
            ].lower()

            content_terms = set(
                content_lower.split()
            )

            overlap = len(
                query_terms.intersection(
                    content_terms
                )
            )

            lexical_ratio = (
                overlap
                / max(
                    len(query_terms),
                    1,
                )
            )

            phrase_bonus = (
                1.0
                if query in content_lower
                else 0.0
            )

            semantic = semantic_scores.get(
                memory["id"]
            )

            semantic_component = (
                max(
                    0.0,
                    semantic,
                )
                if semantic is not None
                else 0.0
            )

            importance = float(
                memory.get(
                    "importance",
                    0.5,
                )
            )

            confidence = float(
                memory.get(
                    "confidence",
                    1.0,
                )
            )

            usage_count = int(
                memory.get(
                    "usage_count",
                    0,
                )
            )

            usage_component = min(
                usage_count / 10.0,
                1.0,
            )

            # ------------------------------------------------
            # Hybrid Retrieval Score V3.1
            #
            # semantic       60%
            # lexical        17%
            # importance     10%
            # confidence      8%
            # usage           5%
            #
            # Exact phrase recebe bonus separado.
            # ------------------------------------------------

            score = (
                semantic_component * 0.60
                + lexical_ratio * 0.17
                + importance * 0.10
                + confidence * 0.08
                + usage_component * 0.05
                + phrase_bonus * 0.10
            )

            enriched = dict(
                memory
            )

            enriched[
                "retrieval_score"
            ] = round(
                score,
                6,
            )

            enriched[
                "semantic_score"
            ] = (
                round(
                    semantic,
                    6,
                )
                if semantic is not None
                else None
            )

            enriched[
                "lexical_overlap"
            ] = overlap

            enriched[
                "lexical_ratio"
            ] = round(
                lexical_ratio,
                6,
            )

            scored.append(
                {
                    "score": score,
                    "semantic": semantic,
                    "overlap": overlap,
                    "phrase_bonus": phrase_bonus,
                    "memory": enriched,
                }
            )

        if not scored:
            return []

        # ----------------------------------------------------
        # Global ranking
        # ----------------------------------------------------

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        semantic_available = any(
            item["semantic"] is not None
            for item in scored
        )

        semantic_values = [
            item["semantic"]
            for item in scored
            if item["semantic"] is not None
        ]

        best_semantic = (
            max(semantic_values)
            if semantic_values
            else None
        )

        # ----------------------------------------------------
        # Adaptive Candidate Gate V3.1
        #
        # DIRECT:
        #   lexical/phrase match sempre pode entrar.
        #
        # STRONG SEMANTIC:
        #   >= 0.32 continua sendo sinal forte.
        #
        # RELATIVE SEMANTIC:
        #   aceita resultado abaixo de 0.32 quando:
        #
        #   - possui pelo menos 0.20 de similaridade
        #   - esta muito proximo do melhor resultado
        #
        # Isso resolve consultas semanticamente corretas
        # com scores naturalmente mais baixos sem abrir
        # completamente o retrieval para ruido.
        # ----------------------------------------------------

        ranked = []

        for item in scored:

            semantic = item["semantic"]
            overlap = item["overlap"]
            phrase_bonus = item[
                "phrase_bonus"
            ]

            direct_match = (
                overlap > 0
                or phrase_bonus > 0
            )

            strong_semantic = (
                semantic is not None
                and semantic >= 0.32
            )

            relative_semantic = (
                semantic is not None
                and best_semantic is not None
                and semantic >= 0.20
                and semantic
                >= (
                    best_semantic - 0.08
                )
            )

            # Se embeddings falharem completamente,
            # somente lexical/direct matching entra.
            candidate = (
                direct_match
                or strong_semantic
                or relative_semantic
            )

            if not candidate:
                continue

            enriched = item["memory"]

            enriched[
                "retrieval_match"
            ] = (
                "direct"
                if direct_match
                else "strong_semantic"
                if strong_semantic
                else "relative_semantic"
            )

            enriched[
                "best_semantic_score"
            ] = (
                round(
                    best_semantic,
                    6,
                )
                if best_semantic is not None
                else None
            )

            enriched[
                "semantic_available"
            ] = semantic_available

            ranked.append(
                (
                    item["score"],
                    enriched,
                )
            )

        ranked.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            memory
            for _, memory
            in ranked[:limit]
        ]


    def mark_used(
        self,
        memory_id: str,
    ) -> None:

        now = utc_now()

        with self.lock:
            with self._connect() as conn:

                conn.execute(
                    """
                    UPDATE memories_v2
                    SET
                        usage_count = usage_count + 1,
                        last_used_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        now,
                        memory_id,
                    ),
                )


    def forget_memory(
        self,
        memory_id: str,
    ) -> bool:

        now = utc_now()

        with self.lock:
            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    UPDATE memories_v2
                    SET
                        active = 0,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        memory_id,
                    ),
                )

                changed = cursor.rowcount > 0

        if changed and self.client:

            try:
                self.client.table(
                    TABLE_NAME
                ).update(
                    {
                        "active": False,
                        "updated_at": now,
                    }
                ).eq(
                    "id",
                    memory_id
                ).execute()

            except Exception:
                pass

        return changed


    def upsert_local_record(
        self,
        record: dict,
    ) -> None:

        metadata = record.get("metadata") or {}

        with self.lock:
            with self._connect() as conn:

                conn.execute(
                    """
                    INSERT INTO memories_v2 (
                        id,
                        profile,
                        memory_type,
                        content,
                        importance,
                        confidence,
                        source,
                        metadata,
                        active,
                        usage_count,
                        created_at,
                        updated_at,
                        last_used_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                    ON CONFLICT(id) DO UPDATE SET
                        profile = excluded.profile,
                        memory_type = excluded.memory_type,
                        content = excluded.content,
                        importance = excluded.importance,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        metadata = excluded.metadata,
                        active = excluded.active,
                        usage_count = excluded.usage_count,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        last_used_at = excluded.last_used_at
                    """,
                    (
                        record["id"],
                        record["profile"],
                        record["memory_type"],
                        record["content"],
                        float(record.get("importance", 0.5)),
                        float(record.get("confidence", 1.0)),
                        record.get("source"),
                        json.dumps(
                            metadata,
                            ensure_ascii=False
                        ),
                        1 if record.get("active", True) else 0,
                        int(record.get("usage_count", 0)),
                        record.get("created_at") or utc_now(),
                        record.get("updated_at") or utc_now(),
                        record.get("last_used_at"),
                    ),
                )


    def pull_from_remote(
        self,
        profile: Optional[str] = None,
    ) -> dict:

        if not self.client:
            return {
                "success": False,
                "pulled": 0,
                "error": "supabase_client_unavailable",
            }

        try:
            query = self.client.table(
                TABLE_NAME
            ).select("*")

            if profile:
                query = query.eq(
                    "profile",
                    normalize_text(profile)
                )

            response = query.execute()

            rows = response.data or []

            for record in rows:
                self.upsert_local_record(record)

            return {
                "success": True,
                "pulled": len(rows),
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "pulled": 0,
                "error": str(exc),
            }


    def push_profile_to_remote(
        self,
        profile: str,
    ) -> dict:

        memories = self.list_memories(
            profile=profile,
            active_only=False,
            limit=10000,
        )

        synced = 0
        errors = []

        for record in memories:

            result = self._sync_remote(record)

            if result.get("success"):
                synced += 1
            else:
                errors.append({
                    "id": record["id"],
                    "error": result.get("error"),
                })

        return {
            "success": len(errors) == 0,
            "attempted": len(memories),
            "synced": synced,
            "errors": errors,
        }


    def remote_healthcheck(self) -> dict:

        if not self.client:
            return {
                "success": False,
                "error": "supabase_client_unavailable",
            }

        try:
            response = (
                self.client
                .table(TABLE_NAME)
                .select("id")
                .limit(1)
                .execute()
            )

            return {
                "success": True,
                "rows": len(response.data or []),
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "rows": 0,
                "error": str(exc),
            }

    def stats(
        self,
        profile: Optional[str] = None,
    ) -> dict:

        with self.lock:
            with self._connect() as conn:

                if profile:

                    total = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memories_v2
                        WHERE profile = ?
                        """,
                        (profile,),
                    ).fetchone()[0]

                    active = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memories_v2
                        WHERE profile = ?
                        AND active = 1
                        """,
                        (profile,),
                    ).fetchone()[0]

                else:

                    total = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memories_v2
                        """
                    ).fetchone()[0]

                    active = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memories_v2
                        WHERE active = 1
                        """
                    ).fetchone()[0]

        return {
            "database": str(self.db_path),
            "profile": profile,
            "total": total,
            "active": active,
            "supabase_client": self.client is not None,
        }