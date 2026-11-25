"""Stage 5: Store & Incremental Vector Store Manager (Part A2 & Section 4.4)."""

from __future__ import annotations

import json
import time
from typing import Any

from .config import IndexerSettings
from .models import Chunk

WRITE_BATCH_SIZE = 100
CACHE_GEN_KEY = "rahbar:cache:generation"
CACHE_INDEX_KEY = "rahbar:cache:keys"


def _log(msg: str, **fields: object) -> None:
    print(
        json.dumps(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "logger": "rahbar.indexer.store",
                "msg": msg,
                **fields,
            }
        ),
        flush=True,
    )


def get_client(settings: IndexerSettings, attempts: int = 30, delay_s: float = 4.0) -> Any:
    """Connect to Chroma, waiting for it to come up."""
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception as exc:
            last_exc = exc
            _log("chroma not reachable yet, retrying", attempt=attempt, error=str(exc))
            time.sleep(delay_s)
    raise RuntimeError(f"chroma unreachable after {attempts} attempts: {last_exc}")


def invalidate_semantic_cache(settings: IndexerSettings) -> int | None:
    """Bump the Redis semantic cache generation and purge old entries on re-index."""
    if not settings.redis_host:
        return None
    try:
        import redis

        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
        )
        new_gen = int(r.incr(CACHE_GEN_KEY))  # type: ignore[arg-type]
        raw_members: Any = r.smembers(CACHE_INDEX_KEY)
        old_keys = list(raw_members or [])
        if old_keys:
            r.delete(*old_keys)
        r.delete(CACHE_INDEX_KEY)
        _log("semantic cache invalidated", generation=new_gen, purged_entries=len(old_keys))
        return new_gen
    except Exception as exc:
        _log("semantic cache invalidation skipped", reason=str(exc))
        return None


def _ensure_collection(chroma: Any, settings: IndexerSettings, dimension: int) -> Any:
    desired_meta = {
        "hnsw:space": "cosine",
        "embed_model": settings.embed_model,
        "dimension": dimension,
    }
    try:
        existing = chroma.get_collection(name=settings.collection)
        meta = getattr(existing, "metadata", None) or {}
        if meta.get("embed_model") == settings.embed_model and meta.get("dimension") == dimension:
            return existing
        chroma.delete_collection(settings.collection)
    except Exception:
        pass
    return chroma.create_collection(name=settings.collection, metadata=desired_meta)


def store(
    chunks: list[Chunk],
    vectors: list[list[float]],
    settings: IndexerSettings,
    client: Any | None = None,
) -> int:
    """Full replace store (backwards-compatible with Assignment 02 unit tests)."""
    if not chunks or not vectors:
        raise ValueError("store requires non-empty chunks and vectors")
    if len(chunks) != len(vectors):
        raise ValueError(f"chunk count ({len(chunks)}) != vector count ({len(vectors)})")

    dimension = len(vectors[0])
    chroma = client if client is not None else get_client(settings)
    collection = _ensure_collection(chroma, settings, dimension)

    existing_ids: set[str] = set()
    if hasattr(collection, "get"):
        got = collection.get(include=[])
        existing_ids = set(got.get("ids") or [])

    write_fn = getattr(collection, "upsert", None) or collection.add
    for start in range(0, len(chunks), WRITE_BATCH_SIZE):
        batch_c = chunks[start : start + WRITE_BATCH_SIZE]
        batch_v = vectors[start : start + WRITE_BATCH_SIZE]
        write_fn(
            ids=[c.id for c in batch_c],
            documents=[c.text for c in batch_c],
            embeddings=batch_v,
            metadatas=[c.metadata() for c in batch_c],
        )

    new_ids = {c.id for c in chunks}
    stale_ids = sorted(existing_ids - new_ids)
    if stale_ids and hasattr(collection, "delete"):
        collection.delete(ids=stale_ids)

    invalidate_semantic_cache(settings)
    return int(collection.count())


def store_incremental(
    new_or_updated_chunks: list[Chunk],
    vectors: list[list[float]],
    settings: IndexerSettings,
    updated_sources: list[str] | None = None,
    deleted_sources: list[str] | None = None,
    superseded_sources: list[str] | None = None,
    client: Any | None = None,
    default_dim: int = 384,
) -> dict[str, Any]:
    """Part A2 Incremental Vector Store Update:
    - Re-running on unchanged corpus embeds 0 chunks and performs 0 vector writes.
    - A changed document replaces ONLY its own chunks.
    - A deleted document removes all of its chunks, leaving 0 orphans.
    - A superseded version is marked `superseded: True` in metadata (archived, excluded from retrieval).
    """
    if len(new_or_updated_chunks) != len(vectors):
        raise ValueError("chunk count != vector count")

    dimension = len(vectors[0]) if vectors else default_dim
    chroma = client if client is not None else get_client(settings)
    collection = _ensure_collection(chroma, settings, dimension)

    got = collection.get(include=["metadatas", "documents", "embeddings"]) if hasattr(collection, "get") else {}
    all_ids: list[str] = list(got.get("ids") or [])
    all_metas: list[dict[str, Any]] = list(got.get("metadatas") or [])
    all_docs: list[str] = list(got.get("documents") or [])
    raw_embs = got.get("embeddings")
    all_embs: list[ Any ] = list(raw_embs) if raw_embs is not None else []

    deleted_chunk_ids: list[str] = []
    # 1. Remove old chunks of modified documents or deleted documents
    targets_to_remove = set(updated_sources or []) | set(deleted_sources or [])
    if targets_to_remove:
        for cid, meta in zip(all_ids, all_metas):
            if (meta or {}).get("source") in targets_to_remove:
                deleted_chunk_ids.append(cid)
        if deleted_chunk_ids and hasattr(collection, "delete"):
            collection.delete(ids=deleted_chunk_ids)

    # 2. Mark superseded document chunks with superseded=True
    superseded_chunk_count = 0
    if superseded_sources:
        sup_set = set(superseded_sources)
        sup_ids: list[str] = []
        sup_docs: list[str] = []
        sup_embs: list[list[float]] = []
        sup_metas: list[dict[str, Any]] = []
        for idx, (cid, meta) in enumerate(zip(all_ids, all_metas)):
            m = dict(meta or {})
            if m.get("source") in sup_set and cid not in deleted_chunk_ids:
                m["superseded"] = True
                sup_ids.append(cid)
                if idx < len(all_docs):
                    sup_docs.append(all_docs[idx])
                if idx < len(all_embs):
                    sup_embs.append([float(x) for x in all_embs[idx]])
                sup_metas.append(m)
        if sup_ids:
            write_fn = getattr(collection, "upsert", None) or collection.add
            write_fn(
                ids=sup_ids,
                documents=sup_docs,
                embeddings=sup_embs,
                metadatas=sup_metas,
            )
            superseded_chunk_count = len(sup_ids)

    # 3. Upsert only new/changed chunks
    upserted_count = 0
    if new_or_updated_chunks:
        write_fn = getattr(collection, "upsert", None) or collection.add
        for start in range(0, len(new_or_updated_chunks), WRITE_BATCH_SIZE):
            batch_c = new_or_updated_chunks[start : start + WRITE_BATCH_SIZE]
            batch_v = vectors[start : start + WRITE_BATCH_SIZE]
            write_fn(
                ids=[c.id for c in batch_c],
                documents=[c.text for c in batch_c],
                embeddings=batch_v,
                metadatas=[c.metadata() for c in batch_c],
            )
        upserted_count = len(new_or_updated_chunks)

    if upserted_count > 0 or deleted_chunk_ids or superseded_chunk_count > 0:
        invalidate_semantic_cache(settings)

    return {
        "total_chunks_in_store": int(collection.count()),
        "embedded_and_upserted_chunks": upserted_count,
        "deleted_chunks": len(deleted_chunk_ids),
        "superseded_chunks_marked": superseded_chunk_count,
    }


def get_document_chunk_counts(settings: IndexerSettings, client: Any | None = None) -> dict[str, dict[str, Any]]:
    """Return chunk counts grouped by document source & doc_id to prove 0 orphans and show version states."""
    chroma = client if client is not None else get_client(settings)
    try:
        collection = chroma.get_collection(name=settings.collection)
    except Exception:
        return {}
    got = collection.get(include=["metadatas"])
    ids = got.get("ids") or []
    metas = got.get("metadatas") or []
    counts: dict[str, dict[str, Any]] = {}
    for cid, meta in zip(ids, metas):
        m = meta or {}
        src = str(m.get("source", "unknown"))
        entry = counts.setdefault(
            src,
            {
                "doc_id": str(m.get("doc_id", src)),
                "doc_version": str(m.get("doc_version", "unknown")),
                "superseded": bool(m.get("superseded", False)),
                "chunk_count": 0,
            },
        )
        entry["chunk_count"] += 1
        entry["superseded"] = bool(m.get("superseded", False))
    return dict(sorted(counts.items()))
