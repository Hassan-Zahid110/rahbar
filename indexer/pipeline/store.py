"""Stage 5: Store. The only code in the whole system that writes to Chroma."""

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
    """Connect to Chroma, waiting for it to come up (the Job and StatefulSet start together).

    Without this, an indexer pod that starts before Chroma is serving exhausts the Job's
    backoffLimit on connection-refused errors instead of simply waiting.
    """
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception as exc:  # connection refused / DNS not ready yet
            last_exc = exc
            _log("chroma not reachable yet, retrying", attempt=attempt, error=str(exc))
            time.sleep(delay_s)
    raise RuntimeError(f"chroma unreachable after {attempts} attempts: {last_exc}")


def invalidate_semantic_cache(settings: IndexerSettings) -> int | None:
    """Bump the Redis semantic cache generation and purge old entries on re-index (section 3.3)."""
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


def store(
    chunks: list[Chunk],
    vectors: list[list[float]],
    settings: IndexerSettings,
    client: Any | None = None,
) -> int:
    """Write every chunk with its vector and metadata, record `embed_model` and `dimension`
    in the Chroma collection metadata (section 4.4), and invalidate the semantic cache.

    Zero-downtime re-index strategy (documented in ADR 0001):
    - When an existing collection already has matching `embed_model` and `dimension`, we
      upsert all new/updated chunks first and then delete stale chunk IDs, so concurrent
      API pods never observe an empty or missing collection.
    - When `embed_model` or `dimension` changes (or no collection exists), Chroma requires
      recreating the collection with the new vector dimension metadata.
    """
    if not chunks or not vectors:
        raise ValueError("store requires non-empty chunks and vectors")
    if len(chunks) != len(vectors):
        raise ValueError(f"chunk count ({len(chunks)}) != vector count ({len(vectors)})")

    dimension = len(vectors[0])
    chroma = client if client is not None else get_client(settings)
    desired_meta = {
        "hnsw:space": "cosine",
        "embed_model": settings.embed_model,
        "dimension": dimension,
    }

    collection = None
    existing_ids: set[str] = set()
    try:
        existing = chroma.get_collection(name=settings.collection)
        meta = getattr(existing, "metadata", None) or {}
        if meta.get("embed_model") == settings.embed_model and meta.get("dimension") == dimension:
            collection = existing
            if hasattr(collection, "get"):
                got = collection.get(include=[])
                existing_ids = set(got.get("ids") or [])
        else:
            chroma.delete_collection(settings.collection)
    except Exception:
        collection = None

    if collection is None:
        collection = chroma.create_collection(name=settings.collection, metadata=desired_meta)

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
