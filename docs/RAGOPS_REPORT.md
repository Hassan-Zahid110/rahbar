# RAHBAR-RAGOps: Operating & Managing a Grounded RAG Pipeline on Kubernetes

**Course:** CS4032 Software Construction & Development (Fall 2026) — Assignment 03 Technical Report  
**Institution:** FAST-NUCES Islamabad  
**Member 1:** Hassan Zahid (Roll No: `i243011` | GitHub: `Hassan-Zahid110`)  
**Member 2:** Faisal Memon (Roll No: `i243032` | GitHub: `faisalmemon353`)  
**Repository:** `https://github.com/Hassan-Zahid110/rahbar`

---

## Executive Summary

Building upon our Assignment 02 *RAHBAR* system, we operationalize the dual-lifecycle **RAGOps architecture** defined by Xu et al. (2026). While conventional LLMOps treats model weights as the primary artifact, RAG systems depend on an intertwined **Query Processing Pipeline Lifecycle** and **Data Management Lifecycle**. We implement automated four-check pre-chunking data verification with quarantine routing, zero-chunk incremental updates with version archival/rollback, a three-level offline testing platform (Module, Component with noise stress-testing, and End-to-End with hand-labeled judge calibration), a ConfigMap-driven release gate on Kubernetes, 16-field per-query JSON tracing with prompt reconstruction, and continuous live-query coverage & drift monitoring.

---

## 1. Mapping Paper Figure 3 (Intertwined RAGOps Lifecycles) to RAHBAR Implementation

| Figure 3 Stage | What Our RAHBAR-RAGOps Pipeline Does | Implementing File(s) | What Is Missing / Future Work |
| :--- | :--- | :--- | :--- |
| **1. Ingest** (Data Lifecycle 4.2.1) | Discovers Markdown, HTML, and digital/scanned PDF documents; parses YAML frontmatter metadata (`source`, `title`, `policy_id`, `doc_version`, `date`, `page_count`); extracts text via `pdfplumber` with automatic 200-DPI `pytesseract` OCR fallback when non-whitespace chars < 25. | `indexer/pipeline/extract.py`, `indexer/pipeline/fetch_corpus.py`, `k8s/ingest-job.yaml` | Real-time Change Data Capture (CDC) webhooks and multi-modal audio/video ingestion streams. |
| **2. Verify** (Data Lifecycle 4.2.2) | Runs after extraction and before chunking. Evaluates 4 checks per document: **Quality** (empty/garbled bytes ratio), **Completeness** (mandatory metadata & truncation markers), **Recency** (stale vs. newer policy version), and **Uniqueness** (SHA-256 exact hash + `hash-384` cosine near-duplicate >= 0.90). Moves failed files to `/data/quarantine/` and writes per-run JSON reports. | `indexer/pipeline/verify.py`, `eval/results/part_a_batch_b_report.json` | Semantic contradiction detection across distinct policy families and pre-index adversarial prompt-injection classification (Paper Sec. 8). |
| **3. Update Data Lake** (Data Lifecycle 4.2.3) | Maintains versioned document state in `/data/data_lake/manifest_state.json` on a Kubernetes PersistentVolumeClaim (`ragops-data-pvc`). Copies superseded versions (e.g., `academic-rules-2026.md` when `2027` arrives) into `/data/archive/` rather than deleting them, enabling one-command version rollback. | `indexer/pipeline/verify.py` (`DataLakeManager`), `indexer/pipeline/run.py` | Fine-grained RBAC document-level ACLs and cryptographic ledger signing for regulatory audits. |
| **4. Update Retrieval Sources** (Data Lifecycle 4.2.4) | Performs incremental vector store updates in ChromaDB: unchanged documents embed **0 chunks**; modified documents delete and re-upsert only their own chunks; deleted documents remove all chunks leaving **0 orphans**; superseded versions flip metadata `superseded: true` and bump Redis cache generation key. | `indexer/pipeline/store.py` (`store_incremental`), `indexer/pipeline/chunk.py`, `indexer/pipeline/embed.py` | Knowledge-graph entity-relation index synchronization alongside HNSW vector storage. |
| **5. Offline Testing** (Pipeline & Data 4.2.5) | Executes a 3-level evaluation suite over `eval/golden.jsonl` (28 questions): **Module level** (16 paraphrase vs. 16 unrelated pairs, ms/chunk, determinism), **Component level** (`recall@3`, `recall@5`, `MRR`, `nDCG@5` + distractor docs & query typo noise test), **End-to-End level** (faithfulness, abstention, citation validity, p50/p95 latency, judge vs. 10 hand labels), and 2-run fixed-seed stochasticity check. | `eval/run_ragops_suite.py`, `eval/golden.jsonl`, `eval/release_gate.py`, `k8s/eval-job.yaml` | Automated multi-turn conversational dialogue trajectory simulation and public BEIR cross-domain benchmarking. |
| **6. Live Testing & Release** (Pipeline Lifecycle 4.1d-f, 4.2.6) | Deploys candidate pipeline as an isolated Kubernetes Deployment (`api-candidate`, Service `api-candidate`, collection `rahbar_candidate`). Runs `job/eval-gate` against ConfigMap thresholds (`rahbar-gate-config`). Promotes passing candidate via zero-downtime rolling update (`maxUnavailable: 0`) and reverses bad releases via `kubectl rollout undo`. | `k8s/candidate-deployment.yaml`, `k8s/eval-job.yaml`, `k8s/base/api-deployment.yaml` | Automated traffic-splitting canary / shadow proxy mirroring live HTTP requests to both deployments simultaneously. |
| **7. Operate, Monitor & Check Coverage** (Lifecycle 4.1f-g, 4.2.7) | Emits 16-field JSON trace line per query to stdout & `/data/traces/traces.jsonl`; reconstructs exact prompts via CLI (`trace_tool.py`); exposes Prometheus `/metrics`; summarizes stage latencies, similarity quantiles & guardrail actions; checks live query coverage against the golden set (>= 85% gate) and clusters uncovered queries to expand the golden set. | `api/app/services/trace.py`, `api/app/services/guardrail.py`, `scripts/trace_tool.py`, `scripts/summarize_traces.py`, `eval/check_coverage.py` | Real-time UMAP/t-SNE visual dashboard for live query drift alerts and active human-in-the-loop expert annotation UI. |

**Architectural Alignment Note:** In exact accordance with Figure 3 of Xu et al. (2026), our Kubernetes cluster enforces a strict read/write boundary: **Jobs** (`job/ragops-ingest`, `cronjob/reindex`) execute the Data Management Lifecycle and are the sole writers to ChromaDB and the Data Lake PVC, while stateless horizontally-scaled **Deployments** (`deployment/api`, `deployment/api-candidate`) execute the Query Pipeline Lifecycle and are gated by `job/eval-gate`.

---

## 2. RAG System Quality Attributes (Paper Section 5.1 & Table 2)

| Quality (Table 2) | Operational Design Consideration & What We Measure | Configured Threshold / Target | Empirical Evidence from Our Pipeline & Kubernetes Cluster Runs |
| :--- | :--- | :--- | :--- |
| **1. Adaptability** | *Data structure construction & granularity configuration:* Incremental ingestion speed, 0-chunk re-embedding on unchanged files, configurable chunk size/overlap & pluggable embedding models (`hash-384` vs. `hybrid-512`). | Unchanged re-run: `0` chunks embedded; New version swap < `2.0s`; Zero orphan chunks on delete. | Re-running Batch A embedded **0 chunks** (6/6 skipped in 0.04s). Ingesting Batch B automatically archived `academic-rules-2026.md` and promoted `academic-rules-2027.md` (12 chunks embedded). Deleting `course-registration-add-drop-2026.md` left **0 orphan chunks**. |
| **2. Monitorability** | *Performance degradation & data source change detection:* Automated 3-level regression suite, live query coverage ratio against golden set, and data drift deltas across batches. | `Recall@5` drop <= `0.02` (2 pts); Live query coverage >= `85.0%` (sim >= 0.42). | Release gate caught degraded Candidate 1 (`Recall@5` dropped by `0.1818` to `0.7273`, exit code 1). Coverage monitor flagged live query coverage gap at **69.05%** (29/42, exit code 1) and verified recovery to **100.00%** (42/42) after adding 8 golden questions. |
| **3. Observability** | *Retrieval injection attack detection & relevance; Generation context adherence & usefulness:* Top-1 similarity quantiles, per-stage p50/p95 latencies, abstention rate, and guardrail injection counters. | Abstention correctness = `100%`; Faithfulness >= `85%`; All injection payloads stripped & logged. | Across 57 trace records: Top-1 similarity median = `0.3431` (p95 = `0.5664`, max = `0.5960`); Abstention correctness = **100.0%** (6/6); Faithfulness = **100.0%** on candidate; Retrieval guardrail stripped & logged injected instruction in `exam-conduct-injected-2026.md` chunk `0003`. |
| **4. Traceability** | *Versioning, retrieval routing & grounded source reconstruction:* 16-field JSON trace per request linking `trace_id` to `doc_id`, `doc_version`, `embedding_version`, `collection_version`, `reranked_order`, and `prompt_hash`. | 100% of queries emit a complete 16-field JSON trace; CLI rebuilds exact prompt & diagnoses root cause from trace alone. | Every query writes to stdout & `/data/traces/traces.jsonl`. `scripts/trace_tool.py` reconstructed the exact prompt for `trace_id=57ac8831...`. Part D5 diagnosed false abstention on `trace_id=d362986a...` (`top_score=0.1967 < floor=0.22`) using only its trace. |
| **5. Reliability** | *Resource usage, bandwidth & fault isolation:* Liveness/readiness probes, embedding pin mismatch guard, PVC persistence, zero-downtime rolling updates (`maxUnavailable: 0`), and 1-command rollback. | p95 E2E latency <= `2500 ms`; Pod memory within limits; 0 failed requests during rollout/undo. | Measured pod resources: API `18m` CPU / `84Mi` RAM (limit `500m`/`512Mi`); Chroma `24m`/`162Mi`; Redis `6m`/`14Mi`. `kubectl rollout undo deployment/api` restored `collection=rahbar` & `embed=hash-384` in 11s with 0 dropped requests. |

---

## 3. Experimental Results (Parts A to F) & Part C Release Decision

### 3.1 Part A Results: Data Verification Stage (A1) & Incremental Update Lifecycle (A2)

We ingested **Batch A** (6 clean baseline policy documents: 20 chunks) followed by an unchanged re-run of Batch A, and then **Batch B** (11 documents containing 7 planted defects, 1 newer policy version `academic-rules-2027.md`, 1 document with an injected instruction, and 2 valid new documents).

#### Table A1: Batch B Verification Report (11 Documents)

| Batch B Document (11 Total) | Planted Condition / Role | Qual | Comp | Recn | Uniq | Overall | Pipeline Action & Verification Reason |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `fees-2026-copy1.md` | Exact Duplicate #1 | PASS | PASS | PASS | FAIL | **FAIL** | **Quarantined:** `exact_duplicate_hash` matches active `fees-2026.md` |
| `grading-policy-2026-dup.md` | Exact Duplicate #2 | PASS | PASS | PASS | FAIL | **FAIL** | **Quarantined:** `exact_duplicate_hash` matches active `grading-policy-2026.md` |
| `library-rules-rephrased-2026.md` | Near-Duplicate (Paraphrased) | PASS | PASS | PASS | FAIL | **FAIL** | **Quarantined:** `near_duplicate_embedding` cosine_sim = `0.9879 >= 0.90` with `library-and-lab-rules-2026.md` |
| `internship-policy-truncated.md` | Truncated Stream File | PASS | FAIL | PASS | PASS | **FAIL** | **Quarantined:** `text_truncated` detected marker `'[TRUNCATED_EOF'` |
| `corrupt-binary-dump.md` | Corrupt / Garbled Extraction | FAIL | FAIL | PASS | PASS | **FAIL** | **Quarantined:** `garbled_or_corrupt_extraction` (null/replacement bytes `\ufffd\x00`) |
| `disciplinary-committee-nometa.md` | Missing Required Metadata | PASS | FAIL | PASS | PASS | **FAIL** | **Quarantined:** `missing_required_metadata` missing `['title', 'doc_version/date', 'page_count']` |
| `academic-rules-2023-stale.md` | Stale / Older Policy Version | PASS | PASS | FAIL | PASS | **FAIL** | **Quarantined:** `stale_version` incoming `v2023 < active v2026` for `academic-rules` |
| `academic-rules-2027.md` | Newer Version of Existing Doc | PASS | PASS | PASS | PASS | **PASS** | **Supersede & Index (5 chunks):** `v2027` archives `academic-rules-2026.md` to `/data/archive/` & marks it `superseded=True` |
| `exam-conduct-injected-2026.md` | Contains Injected Instruction | PASS | PASS | PASS | PASS | **PASS** | **Index New (3 chunks):** Passes A1 structural verification; caught & sanitized by Part D4 Retrieval Guardrail |
| `graduation-and-medals-2026.md` | Clean New Policy Document | PASS | PASS | PASS | PASS | **PASS** | **Index New (2 chunks):** All 4 verification checks passed |
| `course-registration-add-drop-2026.md` | Clean New Policy Document | PASS | PASS | PASS | PASS | **PASS** | **Index New (2 chunks):** All 4 verification checks passed |

#### Table A2: Incremental Update, Zero-Orphan Deletion & Version Rollback Proofs

| Part A2 Incremental Operation | Docs Processed | Unchanged Skipped | Chunks Embedded | Chunks Deleted | Orphan Chunks | Total Store Chunks & Verification Proof |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Initial Batch A Ingestion** | 6 passed, 0 failed | 0 | **20** | 0 | 0 | `20` active chunks across 6 baseline documents |
| **2. Unchanged Batch A Re-run** | 6 passed, 0 failed | **6 / 6** | **0** | 0 | 0 | `20` chunks (SHA-256 match in `manifest_state.json`; **0 embeddings computed**) |
| **3. Batch B Incremental Ingestion** | 4 passed, 7 quarantined | 0 | **12** | 0 | 0 | `32` total chunks (`27` active + `5` archived/superseded for `academic-rules-2026.md`) |
| **4. Single Modified Document** (`library-and-lab-rules-2026.md`) | 1 updated | 0 | **3** | **3** | 0 | `32` total chunks (replaced only its own 3 chunks; other 9 documents untouched) |
| **5. Deleted Document Proof** (`course-registration-add-drop-2026.md`) | 1 deleted | — | **0** | **2** | **0** | `30` total chunks (`chunks_before=2, deleted=2, orphan_chunks_remaining=0`) |
| **6. Superseded Rollback Demo** (`--restore-version academic-rules 2026`) | 2 versions toggled | — | **0** | 0 | 0 | Restores `academic-rules-2026.md` (5 chunks) to `superseded=False` and demotes `2027` (5 chunks) to `superseded=True` |

---

### 3.2 Part B Results: Three-Level Offline Testing Suite (Paper Section 4.2.5 & Table 1)

Our single-command test harness (`python -m eval.run_ragops_suite`) evaluates the pipeline across all three levels defined in Table 1 of Xu et al. (2026) over `eval/golden.jsonl` (**28 questions**: 16 standard answerable, 6 hard [paraphrased, multi-chunk synthesis, or Batch B version/adversarial], and 6 unanswerable must-abstain queries; **14 written by hand** by the group [`origin="human"`] and **14 synthetic questions all reviewed by hand** [`reviewed_by_hand=true`]).

#### Level 1: Module Level (Embedding Quality & Determinism)

| Module-Level Metric | Baseline (`hash-384`) | Candidate (`hybrid-512`) |
| :--- | :--- | :--- |
| Paraphrase Pairs (n = 16) Mean Cosine Similarity | `0.1927` | **`0.3641`** (+88.9%) |
| Unrelated Pairs (n = 16) Mean Cosine Similarity | `0.0866` | **`0.0246`** (-71.6%) |
| **Paraphrase vs. Unrelated Similarity Gap** | `+0.1061` | **`+0.3395` (+3.20x)** |
| Embedding Generation Time per Chunk | `0.0553 ms` | `0.1729 ms` |
| Determinism (Max Difference Across 2 Embed Runs) | `0.00000000` | `0.00000000` |

#### Level 2: Component Level (Retrieval Quality & Noise Stress-Test: +3 Distractor Docs & Query Typos)

| Retrieval Condition (Evaluated on n = 22 Answerable Golden Questions) | Pipeline Config | Recall@3 | Recall@5 | MRR | nDCG@5 | Delta Recall@5 vs. Clean | Delta MRR vs. Clean |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Clean Golden Set** (No Noise) | Baseline (`hash-384`) | `0.9091` | `0.9091` | `0.8864` | `0.8923` | `0.0000` | `0.0000` |
| **2. +3 Irrelevant Distractor Documents** (Cafeteria, Cricket, Alumni Dinner) | Baseline (`hash-384`) | `0.9091` | `0.9091` | `0.8864` | `0.8923` | `+0.0000` | `+0.0000` |
| **3. Query Typos Injected** (*attandance, tution, scholrship, libary*) | Baseline (`hash-384`) | `0.8182` | `0.8636` | `0.7992` | `0.8150` | `-0.0455` (-4.55%) | `-0.0872` (-8.72%) |
| **4. Combined Noise** (+3 Distractor Docs & Query Typos) | Baseline (`hash-384`) | `0.8182` | `0.8636` | `0.7992` | `0.8150` | `-0.0455` (-4.55%) | `-0.0872` (-8.72%) |
| **5. Clean Golden Set** (With Part C1 Candidate Upgrade) | Candidate (`hybrid-512` + Rerank) | **`1.0000`** | **`1.0000`** | **`0.9545`** | **`0.9664`** | `0.0000` | `0.0000` |
| **6. Combined Noise (+3 Docs & Typos)** (With Part C1 Candidate Upgrade) | Candidate (`hybrid-512` + Rerank) | **`0.9545`** | **`0.9545`** | **`0.9318`** | **`0.9378`** | `-0.0455` (95.5% retained) | `-0.0227` (+13.3 pts vs. Base) |

#### Level 3: End-to-End Level (Answer Quality, Citations, Latency & Hand-Labeled Judge Agreement)

| Pipeline Configuration | Faithfulness (n=22) | Abstention Correctness (n=6) | Citation Validity (n=22) | Latency p50 (ms) | Latency p95 (ms) | Judge vs. 10 Hand-Labeled Answers Agreement |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Baseline** (`hash-384`, chunk=300, overlap=50, floor=0.22) | `0.8636` (19/22) | `1.0000` (6/6) | `0.8182` (18/22) | `1.00 ms` | `1.58 ms` | **90.0% (9 / 10 agree)** — 1 disagreement on `g08` tabular multi-fee match |
| **Candidate Pass** (`hybrid-512` + Reranker, chunk=250, floor=0.26) | **`1.0000` (22/22)** | **`1.0000` (6/6)** | **`1.0000` (22/22)** | `1.60 ms` | `1.92 ms` (`1099 ms` live Groq) | **100.0% (10 / 10 agree)** — Complete agreement across all 10 hand labels |

#### Stochasticity Check (Fixed Seed = 42, Run 1 vs. Run 2 Absolute Differences)

| Comparison | Delta Sim Gap | Delta Recall@3 | Delta Recall@5 | Delta MRR | Delta nDCG@5 | Delta Faithfulness | Delta Abstention | Delta Citation Validity | Delta Latency p95 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Run 1 vs. Run 2 Absolute Diff** | `0.000000` | `0.000000` | `0.000000` | `0.000000` | `0.000000` | `0.000000` | `0.000000` | `0.000000` | `0.068 ms` |

**Explanation of Stochasticity:** Because our embedding functions (`hash-384` and `hybrid-512`) use deterministic Blake2b feature hashing, HNSW/exact cosine ranking breaks ties deterministically by chunk ID, and random seeds are fixed (`seed=42`), all retrieval and accuracy metrics exhibit **0.000000 variation** across repeated runs. The only non-zero difference is sub-millisecond wall-clock latency (`0.068 ms`) due to OS kernel thread scheduling (and minor token sampling variance when querying remote Groq GPUs at `temperature=0.1`).

---

### 3.3 Part C Results: Change Experiment & Automated Release Gate (Paper Sections 4.1d, 4.2.5, 4.2.6)

We evaluated two candidate pipeline changes against our Baseline (`hash-384`, `chunk_size=300`, `chunk_overlap=50`, `reranker=False`) using the thresholds defined in `eval/release_gate.yaml` and Kubernetes ConfigMap `rahbar-gate-config`:
* **Candidate 1 (`candidate_fail` — Deliberately Degraded Configuration):** Reduced embedding dimension to `hash-64` with fragmented chunks (`chunk_size=75, chunk_overlap=0, top_k=2, relevance_floor=0.32`).
* **Candidate 2 (`candidate_pass` — Shipped RAGOps Upgrade):** Upgraded embedding model to `hybrid-512` (stopword-filtered morphological stems + domain synonym normalization + word bigrams + character 4-grams for typo immunity) paired with our hybrid lexical-semantic reranker (`reranker_enabled=True, chunk_size=250, chunk_overlap=50, relevance_floor=0.26`).

| Evaluation Level & Metric | Baseline (`hash-384`) | Candidate 1 (`candidate_fail`) | Candidate 2 (`candidate_pass`) | Release Gate Threshold Rule | Candidate 1 Gate | Candidate 2 Gate |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: |
| **[Module]** Mean Paraphrase Cosine Similarity | `0.1927` | `0.1772` | **`0.3641`** | Informational diagnostic | — | — |
| **[Module]** Mean Unrelated Cosine Similarity | `0.0866` | `0.0965` (hash collisions) | **`0.0246`** | Informational diagnostic | — | — |
| **[Module]** Paraphrase vs. Unrelated Gap | `+0.1061` | `+0.0807` (-23.9%) | **`+0.3395` (+220.0%)** | Informational diagnostic | — | — |
| **[Component]** Clean `Recall@3` | `0.9091` | `0.7273` (-0.1818) | **`1.0000` (+0.0909)** | Informational diagnostic | — | — |
| **[Component]** Clean `Recall@5` (Drop vs. Baseline) | `0.9091` | `0.7273` (drop = `+0.1818`) | **`1.0000` (drop = `-0.0909`)** | **Drop <= `0.0200` & Abs >= `0.8800`** | **FAIL (BLOCKED)** | **PASS** |
| **[Component]** Clean `MRR` / `nDCG@5` | `0.8864` / `0.8923` | `0.7045` / `0.7105` | **`0.9545` / `0.9664`** | Informational diagnostic | — | — |
| **[Component]** Typo Noise `Recall@5` / `MRR` | `0.8636` / `0.7992` | `0.6818` / `0.6061` | **`0.9545` / `0.9318`** | Informational diagnostic | — | — |
| **[End-to-End]** `Faithfulness` | `0.8636` | `0.8182` | **`1.0000`** | **>= `0.8500`** (85.0% supported) | **FAIL (BLOCKED)** | **PASS** |
| **[End-to-End]** `Abstention Correctness` | `1.0000` | `0.1667` (false abstentions) | **`1.0000`** | **>= Baseline (`1.0000`)** | **FAIL (BLOCKED)** | **PASS** |
| **[End-to-End]** `Citation Validity` | `0.8182` | `0.6364` | **`1.0000`** | **>= `0.8000`** (80.0% valid citations) | **FAIL (BLOCKED)** | **PASS** |
| **[End-to-End]** `Latency p95 (ms)` | `1.078 ms` | `0.635 ms` | **`1.599 ms`** (`1924 ms` K8s) | **<= `2500.0 ms`** | **PASS** | **PASS** |
| **OVERALL RELEASE GATE DECISION** | **BASELINE** | **5 / 6 CHECKS FAILED** | **6 / 6 CHECKS PASSED** | All 6 gate rules must pass | **REJECT (EXIT 1)** | **RELEASE (EXIT 0)** |

**Part C Release Decision — RELEASE Candidate 2 (`candidate_pass`) & REJECT Candidate 1 (`candidate_fail`):**
1. **Why Thresholds Are Justified:** University academic and financial policy QA requires zero tolerance for out-of-scope hallucination (`min_abstention_correctness = 1.00`), high factual support (`min_faithfulness = 0.85`, `min_citation_validity = 0.80`), non-degrading retrieval coverage (`max_recall5_drop = 0.02`, less than 1 question lost out of 22), and interactive responsiveness (`max_p95_latency_ms = 2500 ms`).
2. **Why Candidate 1 Is Rejected:** Compressing vectors to 64 dimensions and cutting chunks to 75 tokens without overlap severs clause headers from conditions, causing `Recall@5` to plummet by `18.18` points (`0.9091 -> 0.7273`) and Citation Validity to fall to `63.64%`. The release gate exits with code `1` and blocks deployment.
3. **Why Candidate 2 Is Released:** Upgrading to `hybrid-512` with morphological stemming, character 4-grams, and lexical reranking widens the module-level similarity gap by **3.2x** (`+0.1061 -> +0.3395`), achieves **100% Recall@5** on clean queries, boosts typo-noise Recall@5 from `86.36%` to `95.45%`, and achieves **100% Faithfulness, 100% Abstention Correctness, and 100% Citation Validity** at `1.60 ms` offline / `1.10 s` live Groq p95 latency.

---

### 3.4 Part D Results: Observability, Traceability, Guardrails & Root-Cause Diagnosis (Sections 3.2.3, 5.1)

Every query executed by our API writes a single-line JSON trace record to standard output (readable via `kubectl logs -l app=api -n rahbar`) and appends it to persistent storage at `/data/traces/traces.jsonl` (committed under `traces/traces.jsonl` and `traces/trace_samples.jsonl`).

#### D3.1 Top-1 Retrieval Similarity Distribution (n = 57 Committed Traces)

| Quantile / Statistic | Measured Similarity Score | Operational Interpretation |
| :--- | :---: | :--- |
| Minimum (`min`) | `0.0963` | Out-of-scope unanswerable query below relevance floor |
| 25th Percentile (`p25`) | `0.2329` | Boundary region near relevance floor (`0.22`) |
| **Median (`p50`)** | **`0.3431`** | Typical grounded multi-clause policy query |
| Mean (`mean`) | `0.3596` | Balanced across answerable and unanswerable queries |
| 75th Percentile (`p75`) | `0.5303` | High lexical + semantic alignment on exact clauses |
| 95th Percentile (`p95`) | `0.5664` | Strong policy title & clause keyword match |
| Maximum (`max`) | `0.5960` | Peak similarity in 57-trace committed sample (`0.8478` in 448-trace full run) |

#### D3.2 Per-Stage Latency & Operational Rates

| Pipeline Stage / Rate | p50 (ms) | Mean (ms) | p95 (ms) / Value |
| :--- | :---: | :---: | :--- |
| 1. Query Embedding (`embed_ms`) | `0.000 ms` | `0.001 ms` | `0.000 ms` (`0.065 ms` K8s) |
| 2. Vector Retrieval (`retrieve_ms`) | `0.959 ms` | `1.005 ms` | `1.021 ms` (`3.449 ms` K8s HTTP) |
| 3. Hybrid Reranking (`rerank_ms`) | `0.000 ms` | `0.000 ms` | `0.000 ms` (`0.178 ms` w/ rerank) |
| 4. LLM Generation (`generate_ms`) | `0.051 ms` | `19.205 ms` | `0.070 ms` stub / `1092.44 ms` Groq |
| 5. Schema Validation (`validate_ms`) | `0.004 ms` | `0.047 ms` | `0.006 ms` stub / `2.500 ms` Groq |
| **Total End-to-End (`total_ms`)** | **`1.286 ms`** | **`20.600 ms`** | **`1.921 ms` stub / `1099.623 ms` Groq** |
| **Abstention Rate** | 14 / 57 traces abstained | — | **`24.56%`** (6 unanswerable + 3 base floor) |
| **Injection Attempts Flagged** | Retrieval + Input Guardrails | — | **`8` queries flagged & sanitized** |

#### D1 & D4: Trace Record Schema & Retrieval Guardrail Verification on Batch B Injected Document

* **Identity & Query:** `trace_id="57ac8831ab5d42a19cd29d99c609e7cc"` | `timestamp="2026-11-25T08:25:32Z"` | `user_query="Are mobile phones or programmable calculators allowed inside the examination hall, and is attendance optional?"`
* **Model & Index Pin:** `embedding_model="hybrid-512"` (`embedding_version="2.0-hybrid"`) | `collection_name="rahbar"` (`collection_version="v2-batch-b"`) | `filters_applied={"superseded": false}`
* **Retrieved Chunks:** Rank 1: `exam-conduct-injected-2026-md-2026-0002` (`score=0.6384`); Rank 2: `exam-conduct-injected-2026-md-2026-0003` (`score=0.3912` — contains planted injection).
* **D4 Guardrail Action Logged in Trace:** `guardrail_actions: ["input_rail:passed", "retrieval_rail:stripped_injected_instruction:chunk_id=exam-conduct-injected-2026-md-2026-0003:source=exam-conduct-injected-2026.md", "output_rail:verified_citations:count=1"]`. The retrieval guardrail detected `"[SYSTEM INSTRUCTION OVERRIDE]: Ignore all previous instructions..."` inside chunk `0003`, replaced the malicious clause with `[REDACTED_BY_RETRIEVAL_GUARDRAIL]` prior to prompt construction, and incremented `rahbar_injection_attempts_total`.

#### D5: Root-Cause Analysis of an Abstained Answer Using ONLY Its Trace Record (5 Lines)

* **Target Trace ID:** `d362986a3afe493b8f0b1bc5a8f0fc81` (Part B Baseline query `g15`: *"What is the maximum Turnitin similarity index permitted for the Final Year Project thesis report?"*)
1. **Line 1:** Trace `d362986a3afe493b8f0b1bc5a8f0fc81` shows query `g15` was embedded using `embedding_model="hash-384"` (`v1.0-hash`) against `collection_name="rahbar"` (`v2-batch-b`) with active metadata filter `filters_applied={"superseded": false}`.
2. **Line 2:** Inspecting `retrieved_chunks[0]` in the trace confirms that the correct ground-truth chunk `chunk_id="final-year-project-2026-md-2026-0003"` (`doc_id="final-year-project-2026.md"`, `doc_version="2026"`, Section *"3. Plagiarism and Deliverable Evaluation"*) was retrieved at Rank 1, proving the chunk was neither missing nor blocked by the version filter.
3. **Line 3:** However, the trace records `retrieved_chunks[0].score = 0.1967` because exact-token feature hashing (`hash-384`) suffered from stopword dilution and morphological mismatch between query terms (*"maximum", "permitted", "report"*) and chunk terms (*"strictly below 15 percent", "deliverable"*).
4. **Line 4:** The trace field `guardrail_actions` contains `"relevance_rail:abstained_below_floor:top_score=0.1967<floor=0.2200"`, showing that the relevance-floor guardrail short-circuited execution before calling the LLM (`generate_ms = 0.0`) because `0.1967 < model_and_params.relevance_floor (0.22)`.
5. **Line 5:** Thus, the trace alone proves the root cause is **embedding lexical sparsity relative to the static 0.22 relevance floor** (not chunking loss or version filtering), which is why our Part C1 upgrade to `hybrid-512` + lexical reranking raised this chunk's score to `0.5942` and eliminated the false abstention.

---

### 3.5 Part E Results: Drift and Coverage Checking (Paper Section 4.2.7)

We created a live query log of **42 realistic user queries** (`eval/live_queries.jsonl`: 29 in the domain of our initial golden set and 13 from 4 emerging campus topics not covered by our corpus or tests) and enforced the paper's **85.0% coverage gate** at similarity threshold `0.42`.

#### E2 & E4: Query Coverage Before vs. After Expansion

| Coverage Metric | E2: Before Expansion | E4: After Expansion |
| :--- | :--- | :--- |
| Golden Set File | `eval/golden.jsonl` | `eval/golden_expanded.jsonl` |
| Golden Questions Count | `28` | **`36` (+8 new questions)** |
| Live Queries Evaluated | `42` | `42` |
| Similarity Threshold / Target Share | `0.42` / `85.0%` | `0.42` / `85.0%` |
| Covered Live Queries | `29 / 42` | **`42 / 42`** |
| Uncovered Live Queries | `13 / 42` (4 topic gaps) | **`0 / 42`** |
| **Measured Coverage %** | **`69.05%` (< 85.0%)** | **`100.00%` (>= 85.0%)** |
| **Script Exit Code & Status** | **FAIL (Exit Code 1)** | **PASS (Exit Code 0)** |

#### E2: Uncovered Live Queries Grouped by Topic (13 Queries)

| Uncovered Topic Cluster | Count | Representative Uncovered Live Queries & Max Sim |
| :--- | :---: | :--- |
| **1. Parking Permits & EV Charging** | 4 | *"How do I purchase a student motorcycle or car parking decal sticker for the basement garage?"* (`sim=0.142`); *"What is the kWh tariff for EV fast charging stations?"* (`sim=0.118`) |
| **2. Student Health Insurance & Clinic** | 3 | *"Does the university group health insurance policy cover emergency dental surgery and eyeglasses?"* (`sim=0.165`); *"Consultation hours of campus medical dispensary?"* (`sim=0.151`) |
| **3. Disability & Exam Accommodations** | 3 | *"How do students with documented dyslexia request 25% extra exam writing time?"* (`sim=0.284`); *"Procedure for sign-language interpreter or screen-reader?"* (`sim=0.193`) |
| **4. Alumni Career & Placement Portal** | 3 | *"How can graduated alumni register for the corporate job fair and resume portal?"* (`sim=0.219`); *"Mock technical interview coaching for seniors?"* (`sim=0.246`) |

#### E3: Data Drift Analysis — Running Part B Suite Before vs. After Ingesting Batch B

| Part B Evaluation Metric / Probe | Before Batch B (Batch A Only: 6 Docs, 20 Chunks) | After Ingesting Batch B (10 Active Docs, 27 Active + 5 Archived Chunks) | Measured Drift (Delta) & Root Cause Explanation |
| :--- | :--- | :--- | :--- |
| **Component `Recall@3` / `Recall@5`** | `0.9091` / `0.9091` (20/22) | **`1.0000` / `1.0000` (22/22)** | **`+0.0909` (+9.09%):** Batch B introduced `graduation-and-medals-2026.md` and `exam-conduct-injected-2026.md`, resolving `g21` and `g22`. |
| **Component `MRR` / `nDCG@5`** | `0.8636` / `0.8755` | **`0.9545` / `0.9664`** | **`+0.0909` / `+0.0909`:** New domain documents ranked at top-1 for their corresponding queries without degrading existing ranks. |
| **End-to-End `Faithfulness` / `Citations`** | `0.9545` / `0.9091` | **`1.0000` / `1.0000`** | **`+0.0455` / `+0.0909`:** All 22 answerable questions grounded in verified citations after Batch B ingestion. |
| **Policy Version Drift on Question `g17`** (*"After how many consecutive semesters on academic warning is a student dismissed?"*) | Cites `academic-rules-2026.md`: *"three consecutive regular semesters"* | Cites `academic-rules-2027.md`: *"two consecutive regular semesters (reduced from three in 2026)"* | **Ground-Truth Policy Drift:** Batch B's `academic-rules-2027.md` superseded `academic-rules-2026.md` (`superseded=True`), automatically shifting retrieval to the revised 2027 rule. |
| **Guardrail Trigger Drift on Question `g22`** | `0` retrieval injection triggers | `1` retrieval injection stripped per pass | **Adversarial Data Drift:** Batch B's `exam-conduct-injected-2026.md` triggered `retrieval_rail:stripped_injected_instruction`. |

---

### 3.6 Part F Results: Kubernetes Deployment, Jobs, ConfigMap Gate, Controlled Release & Resources

#### F1 & F5: Kubernetes Workload Inventory & Resource Requests/Limits from Cluster Measurements

| Kubernetes Resource | Kind & Replicas | Measured CPU | Measured Memory | Configured `requests` | Configured `limits` | Persistent Storage & RAGOps Role |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| `deployment.apps/api` | Deployment (3/3) | `18m` / pod | `84Mi` / pod | `100m` CPU, `192Mi` | `500m` CPU, `512Mi` | Mounts `ragops-data-pvc` at `/data`; serves `/api/ask`, `/metrics`, JSON traces |
| `deployment.apps/api-candidate` | Deployment (2/2) | `15m` / pod | `82Mi` / pod | `100m` CPU, `192Mi` | `500m` CPU, `512Mi` | Candidate deployment on collection `rahbar_candidate` (`hybrid-512` + reranker) |
| `statefulset.apps/chroma` | StatefulSet (1/1) | `24m` | `162Mi` | `150m` CPU, `256Mi` | `1000m` CPU, `1024Mi` | `chroma-data-chroma-0` PVC (2Gi RWO); HNSW collections `rahbar` & `rahbar_candidate` |
| `deployment.apps/redis` | Deployment (1/1) | `6m` | `14Mi` | `50m` CPU, `64Mi` | `250m` CPU, `256Mi` | `cache-data` PVC (512Mi RWO); AOF semantic cache with generation invalidation |
| `job.batch/ragops-ingest` & `cronjob.batch/reindex` | Job (1/1 Complete), CronJob (`0 2 * * 0`) | `65m` peak | `118Mi` peak | `150m` CPU, `256Mi` | `1000m` CPU, `1024Mi` | Sole writer to ChromaDB; writes `/data/data_lake`, `/data/quarantine`, `/data/archive` |
| `job.batch/eval-gate` | Job (1/1 Complete) | `52m` peak | `112Mi` peak | `100m` CPU, `192Mi` | `500m` CPU, `512Mi` | Reads `configmap/rahbar-gate-config`; writes results to `/data/eval_results/`; exits 0/1 |
| `deployment.apps/ui` | Deployment (2/2) | `3m` / pod | `11Mi` / pod | `25m` CPU, `32Mi` | `150m` CPU, `128Mi` | Unprivileged Nginx (UID 101) frontend exposed via `service/ui:8080` & Ingress |

#### F2 & F3: Dynamic ConfigMap Gate Control, Controlled Release & Rollback Verification on Cluster

| Part F Experiment Step | Kubernetes Command Executed | Observed Cluster Outcome & Trace Proof |
| :--- | :--- | :--- |
| **1. Evaluation & Release Gate Job (Passing ConfigMap)** | `kubectl apply -f k8s/eval-job.yaml && kubectl wait --for=condition=complete job/eval-gate -n rahbar` | `job.batch/eval-gate` completed in `6s` (exit code `0`). All 6 gate checks passed (`Recall@5=1.0000`, `Faithfulness=1.0000`, `p95=1.924 ms <= 2500 ms`). Saved JSON to `/data/eval_results/`. |
| **2. ConfigMap Threshold Edit (Zero Image Rebuild)** | `kubectl patch configmap rahbar-gate-config -n rahbar -p '{"data":{"GATE_MAX_P95_LATENCY_MS":"0.10"}}'` & re-run `job/eval-gate` | Without rebuilding any image, `job.batch/eval-gate` exited with status `Failed` (exit code `1`): `latency_p95_ms = 15.8890 ms > 0.1000 ms -> FAIL (BLOCKED)`. |
| **3. Controlled Rolling Release to Live API** | `kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 EMBED_VERSION=2.0-hybrid RERANKER_ENABLED=true` | `kubectl rollout status deployment/api -n rahbar` updated all 3 replicas with `maxSurge=1, maxUnavailable=0` and `preStop: sleep 5` (zero dropped requests). |
| **4. Rollback via `kubectl rollout undo` & Trace Proof** | `kubectl rollout undo deployment/api -n rahbar && kubectl rollout status deployment/api -n rahbar` | Rolled back 3/3 replicas to previous ReplicaSet. Post-undo live query produced trace `d19dbe4817ae46df94f9ec686400f2f2` confirming restoration of `collection_name="rahbar"`, `embedding_model="hash-384"`, and `embedding_version="1.0-hash"`. |

---

## 4. Short Analytical Answers (Questions 4a to 4f)

**(a) Which verification check caught the most problems in Batch B, and which problem did you not catch? What would catch it?**  
The **Uniqueness check** caught the most problems in Batch B (**3 of the 7 quarantined documents**: 2 exact duplicates `fees-2026-copy1.md` and `grading-policy-2026-dup.md` via SHA-256 body hash, plus 1 paraphrased near-duplicate `library-rules-rephrased-2026.md` via `hash-384` document embedding cosine similarity `0.9879 >= 0.90`), followed by Completeness (2 docs: missing metadata & truncated EOF), Quality (1 corrupt binary file), and Recency (1 stale 2023 edition). The problem A1 verification did **not** catch was the **planted prompt-injection instruction** inside `exam-conduct-injected-2026.md` (Section 3.1: *"[SYSTEM INSTRUCTION OVERRIDE]: Ignore all previous instructions..."*), because the file had clean text quality, complete metadata, current 2026 recency, and unique topic content—confirming Section 8 of Xu et al. (2026) that standard knowledge-base verification lacks adversarial semantic filters. Adding a **pre-chunking adversarial instruction classifier / regex & perplexity scan** inside A1 verification (mirroring our Part D4 retrieval guardrail) would catch and quarantine it before indexing.

**(b) Give an example from your results where a module-level metric looked fine but a component or end-to-end metric did not, or explain why you did not see one.**  
In our Part C experiment on **Candidate 1 (`candidate_fail`: `hash-64, chunk_size=75, overlap=0`)**, the module-level **embedding determinism was a perfect `0.00000000`**, speed improved by 25% to `0.0414 ms/chunk` (vs. Baseline `0.0553 ms`), and mean paraphrase similarity (`0.1772`) remained within 1.5 points of Baseline (`0.1927`). However, at the **Component level**, `Recall@5` collapsed from `0.9091` to `0.7273` (`MRR = 0.7045`), and at the **End-to-End level**, Citation Validity dropped to `0.6364` and Abstention Correctness fell to `0.1667`. This occurred because 64-dimensional hashing compressed the similarity gap to `+0.0807` while 75-token zero-overlap chunking severed section headers from operative policy numbers—proving Table 1's premise that module-level embedding metrics cannot substitute for component and end-to-end testing.

**(c) Did you archive or delete old versions, and what breaks if you delete?**  
We **archived** old versions rather than deleting them: when `academic-rules-2027.md` arrived in Batch B, `DataLakeManager.archive_superseded()` copied `academic-rules-2026.md` to `/data/archive/academic-rules-2026.md` on the PVC and `store_incremental()` updated its 5 chunks in ChromaDB to `superseded: True` (excluding them from default retrieval via `where={"superseded": False}`). If you permanently delete old versions instead of archiving them, **three capabilities break**: (1) **Instant version rollback** (our A2 demo `--restore-version academic-rules 2026` cannot restore the prior state if a new policy release contains errors), (2) **Historical trace auditability & compliance** (Part D traces citing `academic-rules-2026.md` become dangling references whose source context can no longer be verified), and (3) **Cohort-specific historical queries** (students admitted under the 2023/2026 catalog asking explicitly about prior regulations cannot be answered).

**(d) Which metric in your suite do you trust least, and why?**  
We trust the automated **End-to-End Faithfulness score** least when evaluated without human calibration. While retrieval metrics (`Recall@k`, `MRR`, `nDCG@5`) and `Abstention Correctness` compare deterministic chunk IDs and boolean flags against ground truth, automated faithfulness judging (whether via lexical/keyword overlap or an LLM-as-judge) can be fooled by answers that repeat keywords from the retrieved passage while misstating a conditional modifier (or conversely, penalize valid paraphrases that use different terminology). In our Part B baseline calibration against 10 hand-labeled answers, the automated judge had a 10% disagreement rate (9/10 agreement, missing a multi-item table comparison on `g08`), which is why pairing faithfulness with strict **Citation Validity** and human spot-checks is essential.

**(e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper?**  
The hardest idea from Xu et al. (2026) to operationalize on a single-node local Kubernetes cluster was **continuous live query coverage & drift detection (Section 4.2.7) coupled with zero-downtime candidate staging (Section 4.2.6)**. The paper envisions cloud-scale shadow traffic proxies and dimensionality-reduction clustering (t-SNE/UMAP) over thousands of production logs. To make this deterministic, fast, and self-contained inside Kubernetes Jobs without external GPU dependencies, we adapted the paper's design in two ways: (1) we replaced UMAP clustering with a **hybrid stem-Jaccard + 512-dim char-4-gram cosine similarity coverage gate** against our golden set (enforcing the paper's 85% coverage threshold with deterministic exit codes), and (2) we implemented candidate isolation using a dedicated `api-candidate` Deployment paired with a separate Chroma collection (`rahbar_candidate`) on the shared StatefulSet gated by `job/eval-gate` and `ConfigMap/rahbar-gate-config`.

**(f) Which Kubernetes object carries which RAGOps responsibility in your design?**  
1. **Kubernetes `Job` (`job/ragops-ingest`) & `CronJob` (`cronjob/reindex`):** Carry the *Data Management Lifecycle* responsibility (Ingest, Verify, Update Data Lake, Update Retrieval Sources) and enforce the single-writer invariant—only this Job writes to ChromaDB or `/data/data_lake`.  
2. **`StatefulSet` (`statefulset/chroma`) & `PersistentVolumeClaim` (`ragops-data-pvc`, `chroma-data`, `cache-data`):** Carry durable state persistence across pod restarts for HNSW vector indices, the verified data lake, `/data/quarantine`, `/data/archive`, `/data/eval_results`, and `/data/traces`.  
3. **Kubernetes `Job` (`job/eval-gate`) & `ConfigMap` (`rahbar-gate-config`):** Carry *Three-Level Offline Testing & Release Gate* responsibility, decoupling SLO thresholds from container images so gate rules can be tuned live without rebuilding.  
4. **Dual `Deployments` (`deployment/api` & `deployment/api-candidate`) + `Services`:** Carry the *Query Pipeline Lifecycle & Controlled Release* responsibility, enabling isolated candidate testing, zero-downtime rolling promotion (`maxUnavailable: 0`), and instant rollback via `kubectl rollout undo`.

---

## 5. Team Contribution Table & AI Usage Statement

| Team Member | Git Commits | RAGOps Modules & Deliverables Authored |
| :--- | :---: | :--- |
| **Hassan Zahid** (`i243011`, `Hassan-Zahid110`) | **51 commits** (60.0%) | Part A1 4-check verification engine & quarantine manager (`indexer/pipeline/verify.py`), Batch A corpus, Part C2 release gate engine (`eval/release_gate.py`, `eval/release_gate.yaml`), Part D1/D4 16-field query tracing & retrieval injection guardrail (`api/app/services/trace.py`, `guardrail.py`), and Part F Kubernetes manifests (`k8s/ragops-pvc.yaml`, `ingest-job.yaml`, `eval-job.yaml`, `candidate-deployment.yaml`). |
| **Faisal Memon** (`i243032`, `faisalmemon353`) | **34 commits** (40.0%) | Part A2 incremental vector store updater, zero-orphan deletion & version archival/rollback (`indexer/pipeline/store.py`, `run.py`), Batch B fault corpus (11 docs), Part C1 `hybrid-512` embedder & lexical reranker (`embedder.py`, `reranker.py`), Part B 28-question golden set & 3-level evaluation suite (`eval/run_ragops_suite.py`), Part D2/D3 trace CLI tools (`scripts/trace_tool.py`, `summarize_traces.py`), and Part E coverage & drift suite (`eval/check_coverage.py`). |

**AI Usage Statement:** Generative AI assistants (Claude / Gemini) were used for boilerplate CLI argument parsing, formatting Markdown/HTML report tables, and generating 14 synthetic golden candidate questions (each subsequently reviewed, edited, and verified by hand against policy clauses). All verification heuristics, incremental vector store update logic, release gate thresholds, trace schemas, and Kubernetes manifests were tested and validated against live runs on our local Kubernetes cluster.

---

## Appendix: Terminal Screenshots (Parts A to F)

1. **[A1]** Part A1 — Batch A (Clean Baseline Corpus) Verification & Indexing Report (`docs/screenshots/A1.png`)
2. **[A2]** Part A2 — Second Ingestion Run on Unchanged Corpus Showing 0 Chunks Re-Embedded (`docs/screenshots/A2.png`)
3. **[A3]** Part A1 & A2 — Batch B Verification Report (7 Planted Defects Quarantined + Version Update + 0-Orphan Delete) (`docs/screenshots/A3.png`)
4. **[B1]** Part B (B1–B3) — Three-Level Offline Evaluation Suite Summary (`docs/screenshots/B1.png`)
5. **[B2]** Part B4 — Fixed-Seed Stochasticity Verification (`seed=42`, Run 1 vs. Run 2) (`docs/screenshots/B2.png`)
6. **[C1]** Part C2 — Release Gate Failing (`docs/screenshots/C1.png`)
7. **[C2]** Part C2 — Release Gate Passing (`docs/screenshots/C2.png`)
8. **[D1]** Part D1 & D3 — Trace Summary + One Full 16-Field JSON Trace Record (`docs/screenshots/D1.png`)
9. **[D2]** Part D2 & D4 — Trace Tool Rebuilding Context & Prompt + Retrieval Guardrail Action (`docs/screenshots/D2.png`)
10. **[E1]** Part E2 & E4 — Live Query Coverage & Drift Output Before & After Adding 8 New Golden Questions (`docs/screenshots/E1.png`)
11. **[F1]** Part F1 — Kubernetes Cluster Resources (`docs/screenshots/F1.png`)
12. **[F2]** Part F2 — Completed Kubernetes Ingestion Job Logs (`docs/screenshots/F2.png`)
13. **[F3]** Part F2 — Completed Kubernetes Evaluation & Release Gate Job Logs (`docs/screenshots/F3.png`)
14. **[F4]** Part F2 — Release Gate Result Changing After ConfigMap Threshold Edit (`docs/screenshots/F4.png`)
14. **[F3]** Part F3 — `kubectl rollout status`, `kubectl rollout undo`, and Post-Undo Trace (`docs/screenshots/F3_k8s_rollout_status_undo_trace.png`)
