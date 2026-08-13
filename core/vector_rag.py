from __future__ import annotations

"""Compatibility facade for the hardened V9 RAG service."""

from core.context_security import guard_untrusted_context
from core.vector_rag_v9 import (
    add_document as add_document_to_rag,
    delete_document as delete_document_from_rag,
    make_chunk_id as _make_chunk_id,
    namespace_where as _namespace_where,
    normalize_namespaces as _normalize_namespaces,
    query_documents as query_rag_detailed,
    query_rag as _query_rag,
    rag_stats,
    validate_ownership,
)


def query_rag(query: str, n_results: int = 3, profile: str | None = None, agent_id: str | None = None, namespaces=None) -> list[str]:
    documents = _query_rag(
        query,
        n_results=n_results,
        profile=profile,
        agent_id=agent_id,
        namespaces=namespaces,
    )
    return [
        guard_untrusted_context(document, source="rag_document")
        for document in documents
        if document
    ]


__all__ = [
    "add_document_to_rag",
    "delete_document_from_rag",
    "query_rag",
    "query_rag_detailed",
    "rag_stats",
    "validate_ownership",
]
