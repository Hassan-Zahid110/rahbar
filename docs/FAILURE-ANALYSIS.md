# Failure Analysis: Breaking Five Stages on Purpose

This document records our controlled failure injection experiments across the RAHBAR pipeline (Section 5.5). For each stage, we broke the component in an isolated test, observed the resulting symptoms across metrics and logs, diagnosed the root cause using production observability signals, and verified the remedy.

---

## Stage A · Extraction (Indexing Scanned PDF Without OCR)

### What We Broke
In `indexer/pipeline/extract.py`, we set `DISABLE_OCR=true` (bypassing `pdf2image` and `pytesseract`) and indexed the corpus, including `faculty-entrepreneurship-and-technical-start-ups-policy.pdf` (8 scanned pages).

### Symptom
When asking *"What percentage of equity does the university retain under the technical start-ups policy?"*, the system returned:
```json
{
  "answered_from_context": false,
  "answer": "I cannot answer this question because the indexed university document corpus does not contain relevant information on this topic.",
  "citations": [],
  "confidence": "low"
}
```
The system abstained on a document that is physically present in `corpus/raw/`.

### Diagnosis
1. **Metric**: Prometheus metric `rahbar_abstentions_total{reason="below_relevance_floor"}` incremented.
2. **Log Line**: `rahbar.answer` logged:
   ```json
   {"logger": "rahbar.answer", "msg": "answered", "top_k": 5, "chunk_ids": [], "scores": [], "answered_from_context": false, "abstained": true}
   ```
3. **Command / Investigation**: Inspecting the vector store collection:
   ```bash
   python -c "import chromadb; c = chromadb.HttpClient().get_collection('rahbar'); print(c.get(where={'source': 'faculty-entrepreneurship-and-technical-start-ups-policy.pdf'}))"
   ```
   Returned `{'ids': [], 'documents': [], 'metadatas': []}`. The file had 0 extracted chunks because `pdfplumber.extract_text()` yielded 0 characters on all 8 image-only pages.

### Remedy
Re-enabled OCR in `extract.py` (`DISABLE_OCR=false`) and installed `tesseract-ocr` and `poppler-utils` in the Docker container. Re-ran `Job/indexer`, producing 14 chunks with `ocr=True` in page metadata. Queries now retrieve equity clauses with similarity `> 0.82`.

---

## Stage B · Chunking (Fixed-Size 100-Token Chunks With Zero Overlap)

### What We Broke
In `indexer/pipeline/chunk.py`, we switched `CHUNK_STRATEGY=fixed` with `size=100` and `overlap=0`, disabling section-boundary detection and paragraph packaging.

### Symptom
On golden question `q01` (*"What CGPA does an undergraduate student need to maintain to avoid being placed on academic warning?"*), `recall@5` dropped by 18 percentage points across the golden set. The retrieved chunk contained:
```text
...regular semester is placed on academic warning. 5.5 Academic Dismissal: A student who remains on...
```
The section heading `5.4 Academic Warning` was cut off and placed in the preceding chunk, while the threshold clause was truncated. When the generator answered, it lacked the clause tag and cited an incorrect section title.

### Diagnosis
1. **Metric**: `eval/run_eval.py` reported `recall@5` falling from `0.9286` down to `0.7410` (triggering the `MAX_RECALL5_DROP` CI gate failure).
2. **Log Line**: `rahbar.grounding` logged:
   ```json
   {"logger": "rahbar.grounding", "msg": "retrying generation after validation failure", "reason": "fabricated citations not in retrieved set"}
   ```
   Because section headers were severed, the LLM attempted to infer section titles that did not match the chunk's stored section metadata.

### Remedy
Restored structure-aware chunking (`chunk.py`) with `CHUNK_SIZE=300`, `CHUNK_OVERLAP=50`, and structural section header prepending (`[<section>]`). Chunk boundaries now align with clause headings, restoring `recall@5` to `0.9286`.

---

## Stage C · Retrieval & Embedding Pin (Mismatched Embedding Model on API)

### What We Broke
In `ConfigMap/rahbar-config`, we updated `EMBED_MODEL` to `all-MiniLM-L6-v2` (dimension 384) on the API Deployment without re-indexing ChromaDB (which was indexed with `nomic-embed-text`, dimension 768).

### Symptom
API pods restarted, entered `Running` status, but sat permanently at `0/1 READY`. The service was withheld from `Endpoints/api`, and user traffic through Ingress returned HTTP `503 Service Temporarily Unavailable`.

### Diagnosis
1. **Command**:
   ```bash
   kubectl describe pod -l app=api -n rahbar
   ```
   Events reported: `Readiness probe failed: HTTP probe failed with statuscode: 503`.
2. **Log Line**: `rahbar.health` and `rahbar.retrieval.chroma` logged:
   ```json
   {
     "logger": "rahbar.health",
     "level": "ERROR",
     "msg": "readiness blocked by embedding pin mismatch",
     "conflict": "chroma: embed_model mismatch (indexed='nomic-embed-text', configured='all-MiniLM-L6-v2', dimension=768)"
   }
   ```
   Without our Section 4.4 guardrail, Chroma would have either silently failed cosine distance on dimension mismatch or returned nonsensical random vectors without raising an error. The guardrail turned a silent data corruption bug into an explicit, observable deployment block.

### Remedy
Reverted `EMBED_MODEL` in `ConfigMap/rahbar-config` back to `nomic-embed-text` and triggered `kubectl rollout restart deployment/api -n rahbar`. All 3 pods immediately passed `/readyz` within 2 seconds and resumed serving traffic.

---

## Stage E · Source & Version Filtering (Removing the Superseded Filter)

### What We Broke
In `api/app/config.py`, we set `FILTER_SUPERSEDED=false` (disabling `where={"superseded": False}` in `ChromaRetriever.retrieve`), so chunks from both the 2023 and 2026 rulebooks competed purely on dense semantic similarity.

### Symptom
When asking *"What is the minimum attendance required to sit the final exam?"*, the system answered:
```text
A student must attend at least 75 percent of lectures to sit the final examination [undergraduate-academic-rules-aug-2023.pdf / Attendance, p. 4].
```
The model confidently quoted a repealed regulation from 2023 instead of the operative 80% rule from the 2026 handbook!

### Diagnosis
1. **Metric**: Golden question `q09` (type: `version`) failed expectation check (expected `80%`, received `75%`).
2. **Log Line**: `rahbar.answer` logged:
   ```json
   {
     "logger": "rahbar.answer",
     "msg": "answered",
     "chunk_ids": ["undergrad-rules-2023-0012", "academic-rules-2026-0034"],
     "scores": [0.9124, 0.8951]
   }
   ```
   Because the 2023 PDF used the concise phrase *"at least 75 percent of the lectures"*, its dense similarity score slightly edged out the longer 2026 clause, filling `top_1`. Prompts cannot fix this if the retriever serves outdated chunks.

### Remedy
Re-enabled `FILTER_SUPERSEDED=true`. `ChromaRetriever` now applies `where={"superseded": False}` by default, unless `asks_for_historical_version(question)` explicitly detects historical intent (e.g., *"What was the rule in 2023?"*). The system now consistently serves the 2026 rule (80%).

---

## Stage F · Generation (High Temperature = 1.2)

### What We Broke
In `ConfigMap/rahbar-config`, we raised `TEMPERATURE` from `0.1` to `1.2`.

### Symptom
The API experienced severe JSON decoding errors and citation fabrication. On several runs, the model hallucinated non-existent clauses (e.g. `[academic-rules-handbook-jun-2026.pdf / Clause 9.99 Special Exemption]`) and intermittently produced unescaped trailing commas in its JSON output.

### Diagnosis
1. **Metric**: Prometheus metric `rahbar_fallbacks_total` surged from `0` to `4`, and `eval/run_eval.py` reported `citation_validity` plummeting to `76.2%` (failing the `MIN_CITATION_VALIDITY = 0.95` CI gate).
2. **Log Line**: `rahbar.grounding` logged:
   ```json
   {
     "logger": "rahbar.grounding",
     "level": "ERROR",
     "msg": "generation failed after retry; returning safe fallback",
     "reason": "fabricated citations not in retrieved set: [Citation(source='academic-rules-handbook-jun-2026.pdf', section='Clause 9.99 Special Exemption')]"
   }
   ```
3. **Observation**: Notice that stages A through E were healthy (correct chunks were retrieved); only generation failed. As emphasized in the course lecture, **only Stage F is the model's fault; always check A to E first.**

### Remedy
Lowered `TEMPERATURE` back to `0.1` in `ConfigMap/rahbar-config`. Output JSON became deterministic and schema-compliant, with 100% citation validity restored.


<!-- Multi-provider failover: safe fallback prevents uncaught HTTP 500 errors -->
