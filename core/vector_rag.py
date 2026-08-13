from __future__ import annotations

"""Compatibility facade for the hardened V9 RAG service.

New code should import core.vector_rag_v9 directly. This module remains so older
runtime imports keep working while all reads and writes use the V9 namespace
boundary.
"""

from core.vector_rag_v9 import (
    add_document as add_document_to_rag,
    delete_document as delete_document_from_rag,
    make_chunk_id as _make_chunk_id,
    namespace_where as _namespace_where,
    normalize_namespaces as _normalize_namespaces,
    query_documents as query_rag_detailed,
    query_rag,
    rag_stats,
    validate_ownership,
)

__all__ = [
    "add_document_to_rag",
    "delete_document_from_rag",
    "query_rag",
    "query_rag_detailed",
    "rag_stats",
    "validate_ownership",
]
