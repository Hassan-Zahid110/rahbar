# RAHBAR — RAGOps: Operating and Managing Retrieval-Augmented Generation Pipelines on Kubernetes

![CI Status](https://img.shields.io/github/actions/workflow/status/Hassan-Zahid110/rahbar/ci.yml?branch=main&label=CI%20Gate&logo=github)
![Kubernetes](https://img.shields.io/badge/kubernetes-1.36-blue?logo=kubernetes)
![ChromaDB](https://img.shields.io/badge/chromadb-1.0.12-orange)
![RAGOps](https://img.shields.io/badge/RAGOps-Xu%20et%20al.%202026-purple)

**Course**: Software Construction and Development (CS4032) — FAST-NUCES Islamabad  
**Assignment**: Assignment 03 — RAGOps (Building on Assignment 02 RAHBAR)  
**Reference Paper**: Xu, Weytjens, Zhang, Lu, Weber, and Zhu, *RAGOps: Operating and Managing Retrieval-Augmented Generation Pipelines* (2026).

## Team Members
- **Hassan Zahid** (`i243011`) — `Hassan-Zahid110`
- **Faisal Memon** (`i243032`) — `faisalmemon353`

---

## Exact Commands to Run Each Part (Parts A to F)

### Part A: Data Management — Verify and Incremental Update (Paper Sections 4.2.1–4.2.4)
Runs the four-check verification gate (`quality`, `completeness`, `recency`, `uniqueness`) after extraction and before chunking, moves failed documents to `quarantine/`, demonstrates 0-chunk embedding on an unchanged corpus re-run, single-document update, zero-orphan deletion, and superseded version archival + rollback:

```bash
# Run the complete Part A suite (Batch A -> Unchanged Re-run -> Batch B -> Update -> Delete -> Rollback):
python -m eval.run_part_a

# Or invoke the indexer CLI directly on a specific batch:
PYTHONPATH=indexer python -m pipeline.run --verify --batch-dir corpus/batch_a --data-dir data_store --report-out eval/results/part_a_batch_a_report.json
PYTHONPATH=indexer python -m pipeline.run --verify --batch-dir corpus/batch_b --data-dir data_store --report-out eval/results/part_a_batch_b_report.json

# Delete a document and verify 0 orphan chunks remain:
PYTHONPATH=indexer python -m pipeline.run --delete-doc course-registration-add-drop-2026.md --data-dir data_store

# Roll back / restore an archived superseded version (e.g. restore academic-rules 2026):
PYTHONPATH=indexer python -m pipeline.run --restore-version academic-rules 2026 --data-dir data_store
```

### Part B: Offline Testing at Three Levels (Paper Section 4.2.5, Table 1)
One command runs Module-level (16 paraphrase vs 16 unrelated pairs, similarity gap, ms/chunk, determinism), Component-level (`recall@3`, `recall@5`, `MRR`, `nDCG@5` + 3 distractor docs & query typo noise test), End-to-End level (`faithfulness`, `abstention_correctness`, `citation_validity`, `p50`/`p95` latency, LLM-judge vs 10 hand-labeled answers agreement), and Stochasticity (2 fixed-seed runs):

```bash
# Run the full 3-level offline testing suite and write timestamped JSON to eval/results/:
python -m eval.run_ragops_suite
```

### Part C: Change Experiment and Release Gate (Paper Sections 4.1(d), 4.2.5, 4.2.6)
Compares the Baseline pipeline (`hash-384`, chunk=300, overlap=50, reranker=off) against a Failing Candidate (`hash-64`, chunk=75, overlap=0, top_k=2) and our Passing Candidate (`hybrid-512` + morphological stem/4-gram features + hybrid lexical-semantic reranker, chunk=250, overlap=50) against `eval/release_gate.yaml`:

```bash
# Run both candidate experiments (Failing Candidate & Passing Candidate):
python -m eval.release_gate --run-experiment

# Evaluate a specific candidate against the release gate (exits 1 on FAIL, 0 on PASS):
python -m eval.release_gate --baseline eval/results/part_b_baseline_latest.json --candidate eval/results/part_b_candidate_fail_latest.json --config eval/release_gate.yaml
python -m eval.release_gate --baseline eval/results/part_b_baseline_latest.json --candidate eval/results/part_b_candidate_pass_latest.json --config eval/release_gate.yaml
```

### Part D: Observability, Traceability, Guardrails & Root-Cause Analysis (Paper Sections 3.2.3, 5.1, Table 2)
Inspects full 16-field JSON query traces (`traces/traces.jsonl`), reconstructs the exact context and prompt for any `trace_id`, summarizes metrics over a time window, logs retrieval guardrail sanitization on Batch B's injected document, and diagnoses an abstained answer from its trace alone:

```bash
# D1 & D2: Print a full JSON trace record and reconstruct its exact context & prompt:
python -m scripts.trace_tool --show-sample-d1-d2

# Reconstruct prompt for a specific trace_id:
python -m scripts.trace_tool --trace-id <TRACE_ID>

# D3, D4 & D5: Summarize trace log metrics, guardrail actions, and 5-line root-cause diagnosis:
python -m scripts.summarize_traces --trace-file traces/traces.jsonl --window last_24h
```

### Part E: Drift and Coverage Checking (Paper Section 4.2.7)
Evaluates 42 live user queries (`eval/live_queries.jsonl`) against `eval/golden.jsonl`, flags uncovered topic clusters when coverage falls below 85%, measures data drift after ingesting Batch B, and closes the coverage gap by expanding the golden set with 8 new questions (`eval/golden_expanded.jsonl`):

```bash
# Run full Part E suite (Coverage before expansion -> Data drift on Batch B -> Coverage after expansion):
python -m eval.check_coverage --run-all

# Enforce coverage gate (exits 1 before expansion at 69.05%, exits 0 after expansion at 100.00%):
python -m eval.check_coverage --golden eval/golden.jsonl --enforce-gate
python -m eval.check_coverage --golden eval/golden_expanded.jsonl --enforce-gate
```

### Part F: Run Everything on Kubernetes (Paper Sections 4.1(e)-(f), 5.1 Reliability)

```bash
# F1: Deploy PersistentVolumeClaim, ConfigMap, Services, Chroma StatefulSet, Redis, and API Deployment
kubectl apply -f k8s/base/namespace.yaml -f k8s/base/serviceaccounts.yaml -f k8s/base/services.yaml
kubectl apply -f k8s/ragops-pvc.yaml -f k8s/base/configmap.yaml -f k8s/base/chroma-statefulset.yaml -f k8s/base/redis.yaml
kubectl apply -f k8s/base/api-deployment.yaml -f k8s/candidate-deployment.yaml -f k8s/base/reindex-cronjob.yaml

# F2: Run Ingestion + Verification Job and Three-Level Evaluation + Release Gate Job
kubectl apply -f k8s/ingest-job.yaml
kubectl wait --for=condition=complete job/ragops-ingest -n rahbar --timeout=120s
kubectl logs job/ragops-ingest -n rahbar

kubectl apply -f k8s/eval-job.yaml
kubectl wait --for=condition=complete job/eval-gate -n rahbar --timeout=90s
kubectl logs job/eval-gate -n rahbar

# F2 ConfigMap Threshold Edit (changes gate outcome without rebuilding image):
kubectl patch configmap rahbar-gate-config -n rahbar --type merge -p '{"data":{"GATE_MAX_P95_LATENCY_MS":"0.10"}}'
kubectl delete job eval-gate -n rahbar && kubectl apply -f k8s/eval-job.yaml

# F3: Controlled Release & Rollback
kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 EMBED_VERSION=2.0-hybrid COLLECTION_VERSION=v2-candidate RERANKER_ENABLED=true RELEVANCE_FLOOR=0.26
kubectl rollout status deployment/api -n rahbar
kubectl rollout undo deployment/api -n rahbar
kubectl rollout status deployment/api -n rahbar

# F4 & F5: Cluster Observability, Trace Logs, Metrics, and Resource Utilization
kubectl get all,pvc,configmap,cronjob,job -n rahbar
kubectl logs -l app=api -n rahbar --tail=20
kubectl port-forward svc/api 8000:8000 -n rahbar &
curl -s http://127.0.0.1:8000/metrics | grep rahbar_
```
