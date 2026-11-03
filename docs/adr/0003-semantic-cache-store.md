# ADR 0003: Redis Persistence over a Second Chroma Collection for the Semantic Cache

## Status
Accepted · 2026-11-04

## Context
Section 3.3 requires a semantic cache that returns previously validated grounded answers when a new standalone question's embedding has cosine similarity `>= CACHE_THRESHOLD` (`ConfigMap`), while enforcing two strict correctness invariants:
1. **Never cache unsafe turns**: Follow-up questions, abstentions (`answered_from_context=False`), citationless answers, and schema-validation fallbacks must never be cached, because a cached mistake is served to every subsequent student.
2. **Invalidate on re-index**: Whenever `Job/indexer` or `CronJob/reindex` updates the corpus, stale cached answers must expire immediately; otherwise newly indexed rules are shadowed by old cached responses.

We evaluated two backing stores permitted by the specification: **Redis with AOF persistence** versus **a second ChromaDB collection**.

## Decision
We use **Redis (`redis:7.4.2-alpine` Deployment backed by the `cache-data` ReadWriteOnce PVC with `--appendonly yes`)** via `api/app/services/cache.py` and `indexer/pipeline/store.py`:

- **Generation-scoped keys for O(1) atomic invalidation**: Cached entries live under `rahbar:cache:gen:<generation_id>:<sha256>` and are registered in `rahbar:cache:keys`. When `store()` finishes writing to Chroma, it executes `INCR rahbar:cache:generation` and deletes old keys. Even if key deletion is mid-flight, API pods immediately read the new `generation_id` and see zero stale entries.
- **Native per-key TTL (`EX 86400`)**: Entries automatically expire after 24 hours without background compaction scripts.
- **Decoupled failure domain & write isolation**: Keeping the API strictly read-only against ChromaDB (`allow-chroma` permits connections, while code-level discipline ensures `api/` never calls `.add` or `.upsert` on Chroma) preserves the central architectural invariant from ADR 0001: **Chroma has one writer (the indexer Job); API replicas only write ephemeral cache keys to Redis**.

## Options Considered
1. **Second ChromaDB collection (`rahbar_cache`)** — Rejected for three reasons:
   - ChromaDB has no native per-document TTL expiration.
   - Having 3–8 API replicas concurrently calling `collection.add()` on Chroma re-introduces multi-writer load onto the single-node Chroma `StatefulSet` that ADR 0001 eliminated.
   - Dropping `rahbar_cache` during re-indexing can race with in-flight API cache writes, whereas Redis `INCR rahbar:cache:generation` is single-threaded and atomic.
2. **In-process Python LRU dictionary per API pod** — Rejected because cache entries would not be shared across the 3–8 API replicas, would vanish on pod restarts, and could not be invalidated cleanly by the external `Job/indexer` pod.

## Consequences
- **Easier**: Sub-millisecond cache lookups over active question embeddings, atomic cross-pod invalidation from the indexer Job, AOF persistence across Redis pod restarts, and clean `/readyz` health verification via `PING`.
- **Harder / Watch-fors**: Client-side cosine scan in Python scales linearly up to a few thousand active 24h entries (well within campus QA volume, <2 ms for 500 entries); at 100k+ concurrent entries, Redis Stack (`FT.SEARCH` HNSW) would be needed. Threshold selection is sensitive to false hits between numerically adjacent clauses and must be calibrated empirically (`docs/PIPELINE.md`).

