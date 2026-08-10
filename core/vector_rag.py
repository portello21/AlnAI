from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

import chromadb
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "rog_documents"

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


_client = None
_collection = None
_embedding_model = None


def _get_client():
    global _client

    if _client is None:
        RAG_DIR.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(
            path=str(RAG_DIR)
        )

    return _client


def _get_collection():
    global _collection

    if _collection is None:
        client = _get_client()

        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "description": "ROG AI semantic document memory",
                "hnsw:space": "cosine",
            },
        )

    return _collection


def _get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME
        )

    return _embedding_model


def _normalize_metadata(metadata: Optional[dict]) -> dict:
    metadata = dict(metadata or {})

    clean = {}

    for key, value in metadata.items():
        if value is None:
            continue

        if isinstance(value, (str, int, float, bool)):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)

    return clean


def _normalize_profile(profile: Optional[str]) -> Optional[str]:
    if profile is None:
        return None

    value = str(profile).strip()

    return value if value else None


def _chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:

    text = (text or "").strip()

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero.")

    if overlap < 0:
        raise ValueError("overlap nao pode ser negativo.")

    if overlap >= chunk_size:
        raise ValueError(
            "overlap deve ser menor que chunk_size."
        )

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(
            start + chunk_size,
            text_length
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

    return chunks


def _make_chunk_id(
    file_hash: str,
    chunk_index: int,
) -> str:

    raw = f"{file_hash}:{chunk_index}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def _embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = _get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()


def _embed_query(text: str) -> list[float]:
    model = _get_embedding_model()

    embedding = model.encode(
        [text],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    return embedding.tolist()


def delete_document_from_rag(
    file_hash: str,
    profile: Optional[str] = None,
) -> None:

    collection = _get_collection()

    where = {
        "file_hash": file_hash
    }

    normalized_profile = _normalize_profile(profile)

    if normalized_profile:
        where = {
            "$and": [
                {
                    "file_hash": file_hash
                },
                {
                    "profile": normalized_profile
                },
            ]
        }

    try:
        collection.delete(
            where=where
        )
    except Exception:
        pass


def add_document_to_rag(
    file_hash: str,
    text: str,
    metadata: dict,
) -> dict:

    if not file_hash:
        raise ValueError(
            "file_hash obrigatorio."
        )

    text = (text or "").strip()

    if not text:
        return {
            "success": False,
            "file_hash": file_hash,
            "chunks": 0,
            "error": "Documento sem texto.",
        }

    metadata = _normalize_metadata(metadata)

    profile = _normalize_profile(
        metadata.get("profile")
    )

    if profile:
        metadata["profile"] = profile

    metadata.setdefault(
        "filename",
        "unknown"
    )

    metadata.setdefault(
        "mime_type",
        "unknown"
    )

    metadata.setdefault(
        "extraction_method",
        "unknown"
    )

    metadata["file_hash"] = file_hash

    chunks = _chunk_text(text)

    if not chunks:
        return {
            "success": False,
            "file_hash": file_hash,
            "chunks": 0,
            "error": "Nenhum chunk criado.",
        }

    # Reindexacao segura:
    # remove chunks antigos do mesmo arquivo/perfil.
    delete_document_from_rag(
        file_hash=file_hash,
        profile=profile,
    )

    ids = []
    metadatas = []

    for index, _chunk in enumerate(chunks):
        chunk_metadata = dict(metadata)

        chunk_metadata["chunk_index"] = index
        chunk_metadata["chunk_count"] = len(chunks)

        ids.append(
            _make_chunk_id(
                file_hash,
                index
            )
        )

        metadatas.append(
            chunk_metadata
        )

    embeddings = _embed_documents(chunks)

    collection = _get_collection()

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "success": True,
        "file_hash": file_hash,
        "chunks": len(chunks),
        "profile": profile,
        "filename": metadata.get("filename"),
    }


def query_rag_detailed(
    query: str,
    n_results: int = 4,
    profile: Optional[str] = None,
) -> list[dict[str, Any]]:

    query = (query or "").strip()

    if not query:
        return []

    if n_results <= 0:
        return []

    collection = _get_collection()

    if collection.count() == 0:
        return []

    query_embedding = _embed_query(query)

    kwargs = {
        "query_embeddings": [
            query_embedding
        ],
        "n_results": min(
            n_results,
            collection.count()
        ),
        "include": [
            "documents",
            "metadatas",
            "distances",
        ],
    }

    normalized_profile = _normalize_profile(profile)

    if normalized_profile:
        kwargs["where"] = {
            "profile": normalized_profile
        }

    result = collection.query(
        **kwargs
    )

    documents = (
        result.get("documents", [[]])[0]
        or []
    )

    metadatas = (
        result.get("metadatas", [[]])[0]
        or []
    )

    distances = (
        result.get("distances", [[]])[0]
        or []
    )

    ids = (
        result.get("ids", [[]])[0]
        or []
    )

    output = []

    for index, document in enumerate(documents):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        chunk_id = (
            ids[index]
            if index < len(ids)
            else None
        )

        score = None

        if isinstance(distance, (int, float)):
            score = 1.0 - float(distance)

        output.append(
            {
                "id": chunk_id,
                "text": document,
                "metadata": metadata or {},
                "distance": distance,
                "score": score,
            }
        )

    return output


def _query_rag_legacy(
    query: str,
    n_results: int = 2,
    profile: Optional[str] = None,
) -> list[str]:

    results = query_rag_detailed(
        query=query,
        n_results=n_results,
        profile=profile,
    )

    return [
        item["text"]
        for item in results
        if item.get("text")
    ]




def query_rag(
    query: str,
    n_results: int = 3,
    profile: str | None = None,
    agent_id: str | None = None,
    namespaces: tuple[str, ...] | list[str] | None = None,
):
    """
    Secure RAG wrapper.

    Nunca permite acesso global quando um profile foi fornecido.
    """

    profile_norm = str(
        profile
        or ""
    ).strip().lower()


    allowed_namespaces = tuple(
        str(item)
        for item in (
            namespaces
            or ()
        )
        if item
    )


    if profile_norm:

        # Se a implementa??o Chroma exp?e collection,
        # fazemos query com filtro de metadados.

        collection_obj = globals().get(
            "collection"
        )


        if collection_obj is not None:

            try:

                where_filter = None


                if len(
                    allowed_namespaces
                ) == 1:

                    where_filter = {
                        "namespace":
                            allowed_namespaces[0]
                    }


                elif len(
                    allowed_namespaces
                ) > 1:

                    where_filter = {
                        "$or": [
                            {
                                "namespace":
                                    namespace
                            }
                            for namespace
                            in allowed_namespaces
                        ]
                    }


                else:

                    # Perfil fornecido sem namespace permitido:
                    # retorna vazio por seguran?a.
                    return []


                result = (
                    collection_obj.query(
                        query_texts=[
                            query
                        ],
                        n_results=
                            n_results,
                        where=
                            where_filter,
                    )
                )


                documents = (
                    result.get(
                        "documents",
                        []
                    )
                    or []
                )


                if (
                    documents
                    and isinstance(
                        documents[0],
                        list,
                    )
                ):

                    return documents[0]


                return documents


            except Exception:

                # Falha fechada:
                # nunca cai para busca global.
                return []


        # Sem collection identific?vel,
        # n?o fazemos busca global.
        return []


    # Chamadas legadas sem perfil continuam funcionando
    # apenas para compatibilidade interna.
    return _query_rag_legacy(
        query,
        n_results=n_results,
    )

def rag_stats() -> dict:
    collection = _get_collection()

    return {
        "collection": COLLECTION_NAME,
        "path": str(RAG_DIR),
        "chunks": collection.count(),
        "embedding_model": EMBEDDING_MODEL_NAME,
    }

# ============================================================
# SECURE_NAMESPACE_QUERY_V2
# ============================================================

def query_rag(
    query: str,
    n_results: int = 2,
    profile=None,
    agent_id=None,
    namespaces=None,
) -> list[str]:

    query = str(
        query
        or ""
    ).strip()


    if not query:

        return []


    normalized_profile = (
        _normalize_profile(
            profile
        )
    )


    # Quando um perfil e fornecido,
    # namespace torna-se obrigatorio.
    if normalized_profile:

        allowed = tuple(
            str(item)
            for item in (
                namespaces
                or ()
            )
            if item
        )


        if not allowed:

            return []


        collection = (
            _get_collection()
        )


        if (
            collection.count()
            == 0
        ):

            return []


        query_embedding = (
            _embed_query(
                query
            )
        )


        if len(allowed) == 1:

            where = {
                "namespace":
                    allowed[0]
            }

        else:

            where = {
                "$or": [
                    {
                        "namespace":
                            namespace
                    }
                    for namespace
                    in allowed
                ]
            }


        try:

            result = (
                collection.query(
                    query_embeddings=[
                        query_embedding
                    ],

                    n_results=min(
                        int(
                            n_results
                        ),
                        collection.count(),
                    ),

                    where=where,

                    include=[
                        "documents",
                        "metadatas",
                        "distances",
                    ],
                )
            )


        except Exception:

            # FAIL CLOSED:
            # nunca faz busca global
            # se o filtro de privacidade falhar.
            return []


        documents = (
            result.get(
                "documents",
                [[]],
            )[0]
            or []
        )


        return [
            str(document)
            for document in documents
            if document
        ]


    # Sem profile, chamadores internos legados
    # nao recebem RAG global por seguranca.
    return []

