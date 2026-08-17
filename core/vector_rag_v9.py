from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Optional, Sequence

BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "rog_documents_v9"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_MIN_SCORE = 0.18

_client = None
_collection = None
_embedding_model = None


def _normalize_profile(profile: Optional[str]) -> str:
    return str(profile or "").strip().lower()


def _normalize_namespace(namespace: Optional[str]) -> str:
    return str(namespace or "").strip().lower()


def normalize_namespaces(namespaces: Sequence[str] | None) -> tuple[str, ...]:
    output: list[str] = []
    for item in namespaces or ():
        value = _normalize_namespace(item)
        if value and value not in output:
            output.append(value)
    return tuple(output)


def namespace_where(namespaces: Sequence[str] | None) -> dict | None:
    allowed = normalize_namespaces(namespaces)
    if not allowed:
        return None
    if len(allowed) == 1:
        return {"namespace": allowed[0]}
    return {"$or": [{"namespace": value} for value in allowed]}


def make_chunk_id(file_hash: str, namespace: str, chunk_index: int) -> str:
    raw = f"{_normalize_namespace(namespace)}:{str(file_hash).strip()}:{int(chunk_index)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_ownership(profile: str, agent_id: str, namespace: str) -> bool:
    profile = _normalize_profile(profile)
    agent_id = str(agent_id or "").strip().lower()
    namespace = _normalize_namespace(namespace)
    if not profile or not agent_id or not namespace:
        return False
    if namespace.startswith("profile:"):
        return namespace == f"profile:{profile}"
    if namespace == "shared:allan_beatriz:finance":
        return profile in {"allan", "beatriz"} and agent_id == "finance"
    return False


def _get_client():
    global _client
    if _client is None:
        import chromadb
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(RAG_DIR))
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "ROG AI V9 private document memory", "hnsw:space": "cosine"},
        )
    return _collection


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("invalid chunk configuration")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _get_embedding_model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def _embed_query(text: str) -> list[float]:
    return _get_embedding_model().encode([text], normalize_embeddings=True, show_progress_bar=False)[0].tolist()


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[\wÀ-ÿ]+", str(text or "").casefold()) if len(term) >= 3}


def lexical_score(query: str, document: str) -> float:
    """Small deterministic keyword signal used alongside vector similarity."""
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    document_terms = _terms(document)
    return len(query_terms & document_terms) / len(query_terms)


def citation_label(metadata: dict) -> str:
    filename = str((metadata or {}).get("filename") or "documento").strip()
    chunk_index = int((metadata or {}).get("chunk_index", 0) or 0) + 1
    return f"{filename} · trecho {chunk_index}"


def format_rag_result(item: dict[str, Any]) -> str:
    label = citation_label(item.get("metadata") or {})
    return f"[Fonte: {label}]\n{str(item.get('text') or '').strip()}"


def delete_document(file_hash: str, namespace: str) -> bool:
    file_hash = str(file_hash or "").strip()
    namespace = _normalize_namespace(namespace)
    if not file_hash or not namespace:
        return False
    try:
        _get_collection().delete(where={"$and": [{"file_hash": file_hash}, {"namespace": namespace}]})
        return True
    except Exception:
        return False


def add_document(file_hash: str, text: str, metadata: dict) -> dict:
    metadata = dict(metadata or {})
    profile = _normalize_profile(metadata.get("profile"))
    agent_id = str(metadata.get("agent_id") or "").strip().lower()
    namespace = _normalize_namespace(metadata.get("namespace"))
    file_hash = str(file_hash or "").strip()
    text = str(text or "").strip()
    if not file_hash or not text:
        return {"success": False, "error": "missing document content"}
    if not validate_ownership(profile, agent_id, namespace):
        return {"success": False, "error": "ownership denied"}

    chunks = _chunk_text(text)
    if not chunks:
        return {"success": False, "error": "empty document"}

    delete_document(file_hash, namespace)
    clean_meta = {
        "profile": profile,
        "agent_id": agent_id,
        "namespace": namespace,
        "file_hash": file_hash,
        "filename": str(metadata.get("filename") or "unknown"),
        "mime_type": str(metadata.get("mime_type") or "unknown"),
        "extraction_method": str(metadata.get("extraction_method") or "unknown"),
    }
    ids = [make_chunk_id(file_hash, namespace, i) for i in range(len(chunks))]
    metadatas = []
    for i in range(len(chunks)):
        item = dict(clean_meta)
        item.update({"chunk_index": i, "chunk_count": len(chunks)})
        metadatas.append(item)
    _get_collection().upsert(ids=ids, documents=chunks, embeddings=_embed_documents(chunks), metadatas=metadatas)
    return {"success": True, "file_hash": file_hash, "chunks": len(chunks), "namespace": namespace, "filename": clean_meta["filename"]}


def query_documents(query: str, *, profile: str, agent_id: str, namespaces: Sequence[str], n_results: int = 3, min_score: float = DEFAULT_MIN_SCORE) -> list[dict[str, Any]]:
    query = str(query or "").strip()
    profile_norm = _normalize_profile(profile)
    agent_norm = str(agent_id or "").strip().lower()
    allowed = tuple(ns for ns in normalize_namespaces(namespaces) if validate_ownership(profile_norm, agent_norm, ns))
    if not query or not profile_norm or not allowed or n_results <= 0:
        return []
    where = namespace_where(allowed)
    if where is None:
        return []
    collection = _get_collection()
    count = collection.count()
    if count <= 0:
        return []
    try:
        result = collection.query(
            query_embeddings=[_embed_query(query)],
            n_results=min(max(1, int(n_results) * 4), count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    documents = (result.get("documents", [[]]) or [[]])[0] or []
    metadatas = (result.get("metadatas", [[]]) or [[]])[0] or []
    distances = (result.get("distances", [[]]) or [[]])[0] or []
    ids = (result.get("ids", [[]]) or [[]])[0] or []
    allowed_set = set(allowed)
    output: list[dict[str, Any]] = []
    for i, document in enumerate(documents):
        metadata = metadatas[i] if i < len(metadatas) else {}
        if _normalize_namespace((metadata or {}).get("namespace")) not in allowed_set:
            continue
        distance = distances[i] if i < len(distances) else None
        semantic_score = 1.0 - float(distance) if isinstance(distance, (int, float)) else 0.0
        keyword_score = lexical_score(query, str(document or ""))
        # Weighted hybrid score: semantic retrieval remains primary while exact
        # names, numbers and domain terms can promote an otherwise close chunk.
        hybrid_score = max(0.0, min(1.0, semantic_score * 0.72 + keyword_score * 0.28))
        if hybrid_score < max(0.0, min(float(min_score), 1.0)):
            continue
        output.append({
            "id": ids[i] if i < len(ids) else None,
            "text": str(document or ""),
            "metadata": metadata or {},
            "distance": distance,
            "semantic_score": semantic_score,
            "lexical_score": keyword_score,
            "score": hybrid_score,
            "citation": citation_label(metadata or {}),
        })
    output.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return output[: max(1, int(n_results))]


def query_rag(query: str, n_results: int = 3, profile: str | None = None, agent_id: str | None = None, namespaces: Sequence[str] | None = None) -> list[str]:
    if not profile or not agent_id:
        return []
    return [format_rag_result(item) for item in query_documents(query, profile=profile, agent_id=agent_id, namespaces=namespaces or (), n_results=n_results) if item.get("text")]


def rag_stats() -> dict:
    collection = _get_collection()
    return {"collection": COLLECTION_NAME, "path": str(RAG_DIR), "chunks": collection.count(), "embedding_model": EMBEDDING_MODEL_NAME}
