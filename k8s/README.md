# Kubernetes Deployment & RAGOps Operations Guide (`k8s/`)

This directory contains all Kubernetes manifests for **Assignment 03 (RAGOps)** building on the **RAHBAR** pipeline.

## Manifest Inventory
- `k8s/base/namespace.yaml`: Dedicated `rahbar` namespace.
- `k8s/ragops-pvc.yaml` (`k8s/base/ragops-pvc.yaml`): `PersistentVolumeClaim` (`ragops-data-pvc`, 1Gi) backing `/data/data_lake`, `/data/quarantine`, `/data/archive`, `/data/eval_results`, and `/data/traces`.
- `k8s/base/chroma-statefulset.yaml`: Vector store `StatefulSet` with persistent `chroma-data` volume.
- `k8s/base/redis.yaml`: Semantic cache `Deployment` with AOF persistence on `cache-data` PVC.
- `k8s/base/configmap.yaml`: Shared runtime configuration (`rahbar-config`).
- `k8s/ingest-job.yaml`: **Part F2 Ingestion + Part A Verification & Incremental Update Job** (`job/ragops-ingest`).
- `k8s/base/reindex-cronjob.yaml`: Scheduled weekly CronJob (`cronjob/reindex`) running incremental verified ingestion.
- `k8s/eval-job.yaml`: **Part F2 Release Gate ConfigMap (`rahbar-gate-config`) + Three-Level Offline Evaluation Job (`job/eval-gate`)**.
- `k8s/base/api-deployment.yaml`: Live 3-replica `Deployment` (`api`) with zero-downtime rolling update (`maxSurge: 1, maxUnavailable: 0`).
- `k8s/candidate-deployment.yaml`: **Part F3 Candidate Deployment (`api-candidate`) + Service (`api-candidate`)** running against collection `rahbar_candidate` with `EMBED_MODEL=hybrid-512` and hybrid lexical-semantic reranking.

## Fresh Cluster Apply Order

```bash
# 1. Build images
docker build -t rahbar-api:ragops-v1 -t rahbar-api:dev api
docker build -t rahbar-indexer:ragops-v1 -t rahbar-indexer:dev indexer
docker build -t rahbar-ui:dev ui

# 2. Create namespace, Secret, PVCs, ConfigMap, Services, and Data Tier
kubectl apply -f k8s/base/namespace.yaml
kubectl create secret generic rahbar-secret -n rahbar --from-literal=LLM_API_KEY="$LLM_API_KEY" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/base/serviceaccounts.yaml -f k8s/base/services.yaml -f k8s/ragops-pvc.yaml -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/chroma-statefulset.yaml -f k8s/base/redis.yaml
kubectl rollout status statefulset/chroma -n rahbar --timeout=120s
kubectl rollout status deployment/redis -n rahbar --timeout=120s

# 3. Run Ingestion + Verification Job (Part A & F2)
kubectl apply -f k8s/ingest-job.yaml -f k8s/base/reindex-cronjob.yaml
kubectl wait --for=condition=complete job/ragops-ingest -n rahbar --timeout=120s
kubectl logs job/ragops-ingest -n rahbar

# 4. Deploy Live API, Candidate API, and UI (Part F1 & F3)
kubectl apply -f k8s/base/api-deployment.yaml -f k8s/candidate-deployment.yaml -f k8s/base/ui-deployment.yaml
kubectl rollout status deployment/api -n rahbar --timeout=90s
kubectl rollout status deployment/api-candidate -n rahbar --timeout=90s

# 5. Run Three-Level Evaluation & Release Gate Job (Part B, C2 & F2)
kubectl apply -f k8s/eval-job.yaml
kubectl wait --for=condition=complete job/eval-gate -n rahbar --timeout=90s
kubectl logs job/eval-gate -n rahbar

# 6. Controlled Release & Rollback (Part C3 & F3)
kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 EMBED_VERSION=2.0-hybrid COLLECTION_VERSION=v2-candidate RERANKER_ENABLED=true
kubectl rollout status deployment/api -n rahbar
kubectl rollout undo deployment/api -n rahbar
kubectl rollout status deployment/api -n rahbar
```
