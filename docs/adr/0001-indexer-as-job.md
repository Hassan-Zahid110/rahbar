# ADR 0001: Run Corpus Indexing as a Kubernetes Job Instead of API Startup

## Status
Accepted · 2026-11-04

## Context
RAHBAR serves grounded answers over a multi-document university policy corpus from a horizontally scaled FastAPI Deployment (`replicas: 3`, autoscaled up to `8` by an HPA) backed by a persistent ChromaDB vector store (`StatefulSet/chroma` with a `ReadWriteOnce` PVC).

Extracting PDFs, running Tesseract OCR on scanned pages, chunking, and computing vector embeddings over 100+ pages takes tens of seconds to several minutes and peaks at several hundred megabytes of RAM. In contrast, answering a single user query requires embedding one short string, reading `top_k` vectors, and calling the LLM. A naive prototype runs indexing inside FastAPI's `lifespan` startup hook, which fails catastrophically on a multi-replica cluster:

1. **Concurrent write races on one vector store**: Three API replicas booting simultaneously all write chunks into the same `rahbar` Chroma collection at different speeds, interleaving partial updates or colliding on `delete_collection` / `create_collection` calls.
2. **Repeated extraction and embedding on every lifecycle event**: Every rolling update, HPA scale-out from 3 to 4 pods, node drain, or OOMKill re-runs full PDF extraction, OCR, and embedding—turning a 2-second pod scale-out into a multi-minute CPU/memory spike.
3. **Readiness probe dilemma**: If `/readyz` returns `200` before indexing finishes, Kubernetes routes user traffic to pods querying an empty or half-built collection. If `/readyz` waits minutes for indexing, probe `failureThreshold` expires and kubelet kills or withholds every replacement pod during a rolling update.
4. **Coupling data refresh to code deployment**: Updating a revised university policy PDF would require restarting or redeploying API pods rather than triggering a clean data job.

## Decision
We separate the write path and read path into distinct Kubernetes workloads that never share a process:

- **Single writer (`Job/indexer` and weekly `CronJob/reindex` with `concurrencyPolicy: Forbid`)**: Runs `python -m pipeline.run` once to extract, clean, chunk, embed, write the Chroma collection (recording `embed_model` and `dimension` in collection metadata), bump the Redis semantic cache generation (`rahbar:cache:generation`), and exit `0` (`restartPolicy: OnFailure`, `backoffLimit: 3`). Manual re-indexing requires zero API pod restarts:
  ```bash
  kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
  ```
- **Read-only servers (`Deployment/api`, 3–8 replicas)**: Never import or execute extraction/indexing code. `/healthz` checks only process liveness (touching no dependencies), while `/readyz` checks Chroma reachability, `collection.count() > 0`, Redis reachability, and `embed_model` agreement—withholding pods from `Service/api` until a valid index exists.
- **Zero-downtime live re-index behaviour (`indexer/pipeline/store.py`)**: While the API is actively serving traffic during a `CronJob` run, deleting the collection upfront would cause transient `503` readiness failures and empty query results. Instead, when `embed_model` and vector `dimension` match the live collection, `store()` **upserts** all new and updated chunks in batches first and deletes stale chunk IDs (`existing_ids - new_ids`) only afterward, then atomically increments `rahbar:cache:generation` in Redis. Only when `EMBED_MODEL` (and thus vector geometry) intentionally changes does `store()` recreate the collection.

## Options Considered
1. **Index inside FastAPI `lifespan` startup** — Rejected due to 3-replica write races, slow HPA scale-out, OOM risk on serving pods, and inability to re-index independently of deployments.
2. **Leader-elected startup indexing among API replicas (e.g. Redis distributed lock)** — Rejected because API pods would still require heavy OCR binaries (`tesseract-ocr`, `poppler-utils`) and high memory limits bloated for a task that runs once per week, violating least-privilege container sizing.
3. **Drop-and-recreate Chroma collection on every re-index** — Rejected for same-model updates because dropping the collection leaves a multi-second window where concurrent API queries fail or return empty results; batch `upsert` + stale-ID pruning keeps the index continuously readable.

## Consequences
- **Easier**: API image stays small and low-memory (no OCR packages); HPA scales out in seconds; rolling updates maintain `maxUnavailable: 0`; policy updates re-index on demand or weekly without touching `Deployment/api`.
- **Harder / Watch-fors**: On a brand-new cluster, `Deployment/api` pods intentionally sit at `0/1 READY` (`Running`, not crashing) until `Job/indexer` completes. Operators and CI scripts must wait for `job/indexer` completion before expecting `deployment/api` rollout readiness.

