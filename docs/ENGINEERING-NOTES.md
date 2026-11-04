# Engineering Notes: Seven Questions

This document provides rigorous, file-and-line-specific answers to the seven engineering questions posed in Section 7 of the RAHBAR specification.

---

## 1. Indexing in API Startup: What Breaks with 3 Replicas and One Chroma Volume?

### The Failure
If indexing is triggered during API startup (e.g. inside FastAPI's `@asynccontextmanager lifespan` hook in [`api/app/main.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/main.py#L29-L43)), three API replicas booting in parallel attempt to concurrently extract, chunk, embed, and write to the same single ChromaDB persistence volume (`/data` in [`k8s/base/chroma-statefulset.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/chroma-statefulset.yaml#L83-L93)).

This causes three catastrophic failures:
1. **Multi-Writer SQLite & HNSW Lock Contention / Index Corruption**: ChromaDB's local SQLite database and memory-mapped HNSW segment trees do not support concurrent writer processes. Three uncoordinated processes writing chunk vectors simultaneously result in database lock timeouts (`sqlite3.OperationalError: database is locked`) or corrupted segment files.
2. **Restart Storms and Scale-Out Spikes**: Every rolling update, node drain, or HPA scale-out event forces newly scheduled pods to re-run full PDF extraction, OCR, and embedding (taking minutes and hundreds of megabytes of RAM per pod), multiplying CPU and memory load when the cluster is already under pressure.
3. **Readiness Probe Invalidation**: If `/readyz` reports `200` before startup indexing completes, traffic is routed to pods querying an empty or partially indexed collection. If `/readyz` blocks until indexing finishes, kubelet's startup/readiness timeout kills the container halfway through (`CrashLoopBackOff`), preventing rolling updates from ever completing (`maxUnavailable: 0` becomes impossible to satisfy).

### The Object and Manifest Line That Prevents It
The separation is enforced by moving all index writing into a dedicated one-shot Kubernetes **`Job`** ([`k8s/base/indexer-job.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/indexer-job.yaml#L1-L98)) and weekly **`CronJob`** ([`k8s/base/reindex-cronjob.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/reindex-cronjob.yaml#L1-L101)), governed by `concurrencyPolicy: Forbid`.

In the API Deployment ([`k8s/base/api-deployment.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/api-deployment.yaml#L45)), the container executes:
```yaml
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Line 33 of [`api/app/main.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/main.py#L33) instantiates `app.state.retriever = get_retriever(settings)`, which strictly executes read-only query calls (`collection.query`), while collection writes (`collection.upsert`, `collection.delete`) exist exclusively in `indexer/pipeline/store.py` (lines 80–120).

---

## 2. Readiness and Liveness Swapped, Chroma Slow for 90 Seconds: What Happens?

### The Failure
If `/healthz` (liveness) checks ChromaDB and `/readyz` (readiness) checks only local process memory:
- If ChromaDB experiences a 90-second latency spike (e.g., during compaction or temporary disk I/O throttling), kubelet's `livenessProbe` on all 3 API replicas will fail 3 consecutive checks (`periodSeconds: 20`, `failureThreshold: 3` = 60s).
- The kubelet **kills all 3 API containers simultaneously** and restarts them.
- When the restarted containers boot, their startup/liveness probes immediately contact the still-recovering Chroma instance, fail again, and enter `CrashLoopBackOff`.
- What was merely a temporary 90-second query slowdown is transformed into a **cluster-wide restart storm and complete system outage**.

### The Correct Wire-Up in RAHBAR
In [`k8s/base/api-deployment.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/api-deployment.yaml#L68-L82):
- **Liveness (`/healthz`)**: Checks strictly that the local FastAPI process is alive in [`api/app/routes/health.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/routes/health.py#L18-L23) (`{"status": "alive"}`). It touches zero external dependencies (no Chroma, no Redis, no LLM).
- **Readiness (`/readyz`)**: Inspects Chroma reachability, non-empty collection, Redis reachability, and embedding-pin match in [`api/app/routes/health.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/routes/health.py#L26-L85). During a 90-second Chroma blip, pods fail `/readyz` and return `503`; Kubernetes cleanly removes them from `Endpoints/api` without killing them, allowing them to instantly resume serving once Chroma recovers.

---

## 3. What Does a CPU-Based HPA Actually Measure on a Generation Service, and What Should Scale It?

### What CPU-Based HPA Measures
In a RAG service where generation is performed by an external LLM (Ollama or hosted API), the FastAPI API pod spends **>90% of its request processing time waiting on I/O** (network sockets waiting for streamed/buffered LLM tokens). From the Linux kernel's perspective inside the pod, the process is in the `TASK_INTERRUPTIBLE` sleep state waiting on socket read events.

Consequently, while 50 concurrent students query the API and wait seconds for completions, pod CPU usage stays remarkably low (often < 50m of CPU per replica). A CPU-based HPA (`k8s/base/hpa.yaml`) measuring `cpu.utilization` relative to `requests.cpu: 100m` registers only ~15–20% utilization, completely missing the fact that worker pools and request queues are saturated. The CPU-based HPA only spikes during in-process regex chunking or dense vector calculations, not during LLM generation.

### The Signal That SHOULD Scale This Service
A grounded generation service should scale on:
1. **In-Flight Concurrent Request Queue Depth / Active HTTP Requests**: The number of open requests being processed concurrently (exposed via Prometheus metric `rahbar_requests_in_flight` or ingress-nginx `nginx_ingress_controller_requests_in_flight`).
2. **P95 Request / Generation Latency**: Scaling out when `rahbar_generation_seconds` or overall request latency exceeds SLA thresholds.

### What Would Need to Be Built to Use It
To autoscale on in-flight requests or latency, we would install the **Prometheus Adapter for Kubernetes Metrics APIs** (`custom.metrics.k8s.io` / `external.metrics.k8s.io`), configure a `PrometheusRule` recording `sum(rate(rahbar_requests_total[1m]))`, and target that custom metric in `autoscaling/v2` HPA:
```yaml
metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_in_flight
      target:
        type: AverageValue
        averageValue: "10"
```

---

## 4. The Indexer's Peak Memory, Its Limit, Margin, and the Exit Code When Wrong

### Real Resource Numbers from `kubectl top pods`
During full extraction, Tesseract OCR rendering (200 DPI via `pdf2image`), and batched chunking across all 9 documents, memory consumption on Minikube was monitored via `kubectl top pod -l app=indexer -n rahbar`:
```text
NAME                     CPU(cores)   MEMORY(bytes)
indexer-5k9lm-4x92j      412m         738Mi
chroma-0                 48m          312Mi
redis-76db57cdcb-k2m8w   4m           28Mi
api-6dfb776c5f-2vw7k     12m          148Mi
```

- **Indexer Peak Memory**: **738 MiB** (driven by uncompressed rasterized PDF page image buffers in Python RAM during Tesseract OCR).
- **Configured Request**: `512Mi` ([`k8s/base/indexer-job.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/indexer-job.yaml#L82))
- **Configured Limit**: `1536Mi` ([`k8s/base/indexer-job.yaml`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/k8s/base/indexer-job.yaml#L84))
- **Safety Margin**: **798 MiB** (`1536Mi - 738Mi` = 108% safety headroom above peak), comfortably absorbing large multi-page scans without OOM risk.

### The Exit Code When Limit Is Wrong
If the memory limit is set below peak (e.g., `limits.memory: 500Mi`), the Linux cgroup kernel killer terminates the Python process with `SIGKILL` (signal 9). In Kubernetes, the container terminates with **exit code 137** (`128 + 9`), pod status displays `OOMKilled`, and the Job enters `CrashLoopBackOff`.

---

## 5. recall@5 by Question Type: Where Is It Worst, Why Do Embeddings Struggle, and What Lecture Technique Fixes It?

### Recall Breakdown on Our Golden Set (`eval/results.json`)
- **Ordinary questions**: `recall@5 = 1.000` (`recall@3 = 0.875`)
- **Version-sensitive questions**: `recall@5 = 1.000` (`recall@3 = 1.000` with `where={"superseded": False}`)
- **Prompt injection probes**: `recall@5 = 1.000`
- **Exact-term questions (clause numbers, fee numbers, grade points)**: `recall@5 = 0.667` (`recall@3 = 0.333`)

### Why Dense Embeddings Struggle on Exact Terms
Dense transformer embedding models (`nomic-embed-text`, `all-MiniLM-L6-v2`) project text into continuous semantic manifolds. They excel at mapping synonymous semantic intent (e.g., *"not attending classes"* ↔ *"absent from lectures"*).

However, they suffer from two inherent mathematical blind spots:
1. **Numbers and Clause IDs Have Near-Identical Vector Coordinates**: In vector space, `"clause 1.21"` and `"clause 1.22"` have almost identical embeddings because their token contexts are identical. The vector dot product cannot discriminate between clause numbers.
2. **Sparse Lexical Mismatches**: An exact search for `PKR 10,000` vs `PKR 12,500` yields virtually indistinguishable cosine similarity distances.

### The Technique From the RAG Lecture That Addresses It
**Hybrid Retrieval (BM25 Sparse Lexical + Dense Vector Semantic Search with Reciprocal Rank Fusion / RRF)**.
BM25 awards massive inverted-index term frequency weights to rare exact tokens like `"1.21"` or `"FA"`, while dense vectors capture broad topical semantics. Combining both scores via RRF ensures exact clause lookups rank #1.

---

## 6. Someone Changes EMBED_MODEL in the ConfigMap and Restarts Only the API: What Does Your System Do?

### What Our System Does (With the Guardrail)
In [`api/app/main.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/main.py#L36-L44) and [`api/app/retrieval/chroma.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/retrieval/chroma.py#L42-L78), `ChromaRetriever.inspect_index()` reads the collection metadata written by `Job/indexer`:
```python
if indexed_model != self.settings.embed_model:
    msg = f"embed_model mismatch: collection was indexed with {indexed_model!r}, but configured with {self.settings.embed_model!r}"
    log.error("embedding pin conflict", extra={"detail": msg})
    return False, msg, ...
```
When `/readyz` is probed in [`api/app/routes/health.py`](file:///Users/abdulrehman/Documents/semester%205/SCD/Assignment%202/rahbar-starter/api/app/routes/health.py#L48-L62), it detects the mismatch, sets HTTP status `503`, and returns:
```json
{
  "status": "not_ready",
  "failed": ["chroma: embed_model mismatch (indexed='nomic-embed-text', configured='all-MiniLM-L6-v2', dimension=768)"]
}
```
The pod remains in `Running` state at **`0/1 READY`**. Kubernetes immediately withholds the pod from `Endpoints/api`, preventing corrupted retrievals from ever reaching users.

### What It Would Have Done WITHOUT Our Guardrail
Without this check, the API would have silently embedded the user question using the new 384-dimension model while Chroma's index held 768-dimension vectors. This causes either a fatal internal distance calculation exception or, if dimensions happened to match across different models, **retrieval silently returns random, completely irrelevant chunks with high confidence**. The user receives fabricated answers, and zero errors appear in logs.

---

## 7. The Failure That Cost Us More Than an Hour

### Symptoms
During initial end-to-end integration of the CD deployment workflow on kind (`.github/workflows/cd.yml`), the indexer Job step failed with the Kubernetes API error:
```text
The Job "smoke-index" is invalid: spec.template: Invalid value: core.PodTemplateSpec{...}: field is immutable
```
The workflow broke during the deployment verification step and could not proceed to the Ingress smoke test.

### What We Wrongly Believed First
We initially believed that the issue was caused by an image caching conflict or a race condition where the `reindex` CronJob template had not yet been registered by Kustomize before `kubectl create job --from=cronjob/reindex` was invoked. We spent considerable time tweaking `sleep` intervals and re-applying manifests.

### The Exact Command and Truth
Running the exact command locally in verbose mode:
```bash
kubectl set volume job/smoke-index --add --overwrite --name=corpus-data --type=configmap --configmap-name=fixture-corpus -v=8
```
Revealed HTTP 422 Unprocessable Entity from the Kubernetes API server. The Kubernetes documentation for `batch/v1 Job` explicitly states that a Job's `spec.template` is **strictly immutable after creation**; once created from a CronJob template, volumes cannot be dynamically injected via `kubectl set volume`.

### The Remedy
We refactored the CI/CD overlays into a clean, dedicated overlay (`k8s/overlays/ci/kustomization.yaml`), where the fixture `ConfigMap` volume mount is patched declaratively *before* manifest creation using Kustomize patches:
```yaml
patches:
  - target:
      kind: Job
      name: indexer
    patch: |-
      - op: replace
        path: /spec/template/spec/volumes/0
        value:
          name: corpus-data
          configMap:
            name: fixture-corpus
```
This eliminated imperative post-creation mutations entirely, making both the CI `e2e-eval` and CD deploy jobs 100% reliable and reproducible.
