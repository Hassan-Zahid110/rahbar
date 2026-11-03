# RAHBAR Architecture Notes

## System Topology (`namespace: rahbar`)

RAHBAR separates corpus ingestion from query serving across five isolated Kubernetes workloads governed by default-deny `NetworkPolicy` rules:

1. **`StatefulSet/chroma` (1 replica + `volumeClaimTemplates` PVC `chroma-data`)**: Persistent HNSW cosine vector store (`chromadb/chroma:1.0.12`).
2. **`Deployment/redis` (1 replica + PVC `cache-data`)**: AOF-persisted semantic query cache (`redis:7.4.2-alpine`) with generation-based invalidation (`rahbar:cache:generation`).
3. **`Job/indexer` & `CronJob/reindex`**: The **sole writer** to ChromaDB. Runs `extract -> clean -> chunk -> embed -> store`, stamps `embed_model` and `dimension` into Chroma collection metadata, and invalidates Redis on completion.
4. **`Deployment/api` (3–8 replicas via `HorizontalPodAutoscaler/api-hpa`)**: Stateless FastAPI service that **only reads** ChromaDB, checks/populates Redis semantic cache, enforces the relevance floor, calls the pluggable `LLMProvider`, validates `Answer` JSON + citations, and exposes `/healthz`, `/readyz`, and `/metrics`.
5. **`Deployment/ui` (2 replicas)**: Unprivileged read-only `nginx` (`:8080`) serving the static single-page chat client behind `Ingress/rahbar-ingress` (`/` -> `ui`, `/api` -> `api`).

## Why ChromaDB Is a `StatefulSet` and Not a `Deployment` (Section 4.1)

Running ChromaDB (`chromadb/chroma:1.0.12`) as a `StatefulSet` with `volumeClaimTemplates` instead of a `Deployment` is required for three storage and identity reasons:

1. **Ordered single-pod lifecycle prevents dual-mount corruption on SQLite + HNSW**: ChromaDB persists metadata in SQLite (`chroma.sqlite3`) and vector segments in memory-mapped HNSW files on `/data`. A standard `Deployment` defaults to `RollingUpdate`, which launches `new-pod` *before* terminating `old-pod`—either deadlocking on `ReadWriteOnce` volume attachment across nodes or allowing two processes on the same node to write to the same SQLite/HNSW directory concurrently, corrupting the index. A `StatefulSet` guarantees at-most-one `chroma-0` pod identity exists before replacement (`OrderedReady` semantics).
2. **Stable volume binding via `volumeClaimTemplates`**: `chroma-data-chroma-0` stays deterministically bound to ordinal `chroma-0` across pod deletions, restarts, and image upgrades without losing the vector index.
3. **Predictable network and storage identity**: If Chroma is ever sharded or replicated in future topologies, each ordinal receives its own dedicated PVC rather than sharing a single claim across replicas.
