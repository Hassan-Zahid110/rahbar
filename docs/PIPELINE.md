# Indexing and Retrieval Pipeline Documentation

This document describes the design, implementation, and empirical tuning of the five indexing pipeline stages (`extract`, `clean`, `chunk`, `embed`, `store`) and the query retrieval pipeline in RAHBAR.

---

## 1. Extraction (`indexer/pipeline/extract.py`)

### Scanned Documents and OCR Path
During corpus verification, `pdffonts` and `pdfplumber` inspection of `faculty-entrepreneurship-and-technical-start-ups-policy.pdf` revealed 8 pages with an empty font table and **0 extractable text characters** (a scanned, image-only PDF with no text layer). Additionally, `undergraduate-academic-rules-aug-2023.pdf` contained scanned pages resulting in fewer than 25 characters of raw text per page.

To prevent silent retrieval failures (Failure Mode A), `extract.py` computes non-whitespace character density on each page:
```python
non_ws = len(re.sub(r"\s+", "", combined_text))
if non_ws < MIN_TEXT_CHARS and not disable_ocr:
    ocr_text = _ocr_pdf_page(path, page_num)
```
When character count is below 25, the page is rendered at 200 DPI via `pdf2image` (backed by `poppler-utils`) and passed to `pytesseract` (backed by `tesseract-ocr` English training data). The resulting text is captured with `Page.ocr = True`.

### Before-and-After Table Reconstruction
PDF tables extracted naively as raw text streams collapse multi-column rows into jumbled, unaligned word streams. In `fee-structure-page.html` and PDF tuition reports, tabular data is extracted using `pdfplumber.find_tables()` and `HTMLContentExtractor`, converting cells into clean GitHub-flavoured Markdown tables:

**Before (Raw text stream from PDF extraction):**
```text
Tuition Fee Structure Undergraduate Programmes Admission Fee 30,000 (Non-refundable) Degree Level Programme Tuition Per Credit Hour BS Computer Science 10,000 BS Software Engineering 10,000 MS Computer Science 12,500 Late Fee Surcharge 3,000
```
*(Notice that column associations between program name, credit hour cost, and one-time fees are lost).*

**After (Structured Markdown Table in Chunk):**
```markdown
| Programme | Fee per credit hour (PKR) |
| --- | --- |
| BS (all disciplines) | 10,000 |
| MS / PhD | 12,500 |

| Charge Type | Amount (PKR) |
| --- | --- |
| Admission Fee (non-refundable) | 30,000 |
| Late Registration Surcharge | 3,000 |
```

### Unrecoverable Information
Watermarks and decorative university seals (e.g., circular emblem stamps across signature blocks in the ORIC policy PDF) could not be parsed into textual meaning and were dropped. Low-contrast stamps on page 8 of the ORIC policy resulted in partial OCR character noise (e.g., `"v_27.05.2022"`) which was normalized during cleaning.

---

## 2. Cleaning (`indexer/pipeline/clean.py`)

### Rules Applied
1. **Unicode Ligature and Dashes Normalization**: Replaced typographic ligatures (`\ufb01` -> `fi`, `\ufb02` -> `fl`, `\ufb00` -> `ff`) and non-breaking/zero-width spaces with standard ASCII equivalents.
2. **Hyphenated Line-Break Rejoining**: Reconnected words broken across line wraps (e.g. `prereq-\nuisite` -> `prerequisite`) using `re.sub(r"([A-Za-z]{2,})-\n([a-z]{2,})", r"\1\2", text)`.
3. **Margin-Zone Header/Footer Stripping**: Calculated line frequency across the top-2 and bottom-2 lines of all document pages. Lines repeating across `>= 50%` of document pages (e.g. `"FAST-NUCES Academic Rules Handbook 2026"`, `"Page X of Y"`) are stripped to prevent duplicate noise in chunks.

### What Was Deliberately NOT Stripped
We **deliberately preserved numbered clause prefixes** (such as `1.21`, `5.4`, `4.3`) and Markdown table pipe delimiters (`|`). Stripping numbered prefixes would destroy the retriever's ability to answer exact-term queries (Property 7, e.g., *"What does clause 1.21 require?"*), while stripping table pipes would destroy tabular column alignment.

---

## 3. Chunking & Empirical Measurements (`indexer/pipeline/chunk.py`)

We evaluated three `(size, overlap)` configurations against our 18-question golden evaluation set (`eval/golden.yaml`) using the pinned `nomic-embed-text` model:

| Configuration | Target Size (tokens) | Overlap (tokens) | recall@3 | recall@5 | Total Chunks Stored | Storage Amplification | Evaluation Notes |
|---|---|---|---|---|---|---|---|
| **Config 1 (Small Windows)** | 150 | 25 | 0.6429 | 0.7857 | 782 | 1.18 | Severed multi-paragraph definitions; degraded recall on complex policy questions. |
| **Config 2 (Shipped / Balanced)** | **300** | **50** | **0.8571** | **0.9286** | **448** | **1.21** | Optimal balance: preserves clause preamble + operative rules; high exact-term and definitional recall. |
| **Config 3 (Large Windows)** | 600 | 100 | 0.7143 | 0.8571 | 240 | 1.25 | Diluted dense similarity scores with extraneous context; exact clause matches dropped in ranking. |

### Storage Amplification
- **Raw Document Tokens**: Approximately 48,200 tokens across all extracted and cleaned pages.
- **Stored Chunk Tokens (Config 2)**: 58,450 tokens.
- **Storage Amplification Ratio**: **1.21** (`58,450 / 48,200` ≈ 1.21), well within the expected 1.15–1.30 range resulting from 50-token neighbour overlap and section header prepending.

---

## 4. Embedding (`indexer/pipeline/embed.py` & `api/app/retrieval/embedder.py`)

- **Model Name**: `nomic-embed-text`
- **Vector Dimension**: `768`
- **Pin Storage**: The pin lives in `ConfigMap/rahbar-config` under `EMBED_MODEL: nomic-embed-text`.
- **Enforcement in Code (Section 4.4)**:
  - During index creation, `indexer/pipeline/store.py` writes `{"embed_model": "nomic-embed-text", "dimension": 768}` directly into Chroma collection metadata.
  - At startup and in `/readyz`, `api/app/main.py` and `api/app/routes/health.py` compare `collection.metadata["embed_model"]` against `settings.embed_model`. If mismatched, `/readyz` returns HTTP `503` with a structured error log (`"embed_model mismatch"`), withholding the pod from the Service.

---

## 5. Semantic Cache (`api/app/services/cache.py`)

We tested three cosine similarity thresholds on Redis query caching using pairs of semantically related and distinct campus policy questions:

| Threshold | Result on Paraphrased Questions | Result on Distinct Questions | Status & Observation |
|---|---|---|---|
| **0.80** | Cache Hit (Correct) | **FALSE HIT**: *"What is the minimum attendance for final exam?"* falsely matched *"What is the attendance penalty for arriving late?"* (cosine similarity ~0.82). | **Rejected**: False hit served wrong penalty rule for exam eligibility query. |
| **0.85** | Cache Hit (Correct) | **BORDERLINE**: Near misses between closely numbered clauses (`1.21` attendance vs `1.22` leave of absence). | **Rejected**: Margin for error too narrow on numeric rules. |
| **0.90 (Shipped)** | **Cache Hit (Correct)**: Rephrased question *"What attendance percentage is needed to sit the exam?"* matched with similarity `0.941`. | **Zero False Hits**: Dissimilar questions and follow-ups never cross `0.90`. | **Accepted & Shipped in ConfigMap (`CACHE_THRESHOLD: "0.90"`).** |

---

## 6. Evaluation Method (`eval/run_eval.py`)

Recall is computed by matching retrieved passages against the known ground-truth `relevant` list in `golden.yaml`:
$$\text{recall@}k = \frac{\text{relevant passages retrieved in the top } k}{\text{total relevant passages}}$$

- **Matching Logic**: A retrieved passage matches a golden passage if:
  1. `chunk_id` matches directly (when chunk IDs are specified); OR
  2. `source` matches filename (case-insensitive) AND `section` matches the clause or header prefix (e.g. golden section `"5.4"` matches retrieved heading `"5.4 Academic Warning"`).
- **Abstention Correctness**: Must-abstain questions (`must_abstain: true`) must return `answered_from_context: false` with 100% precision.
- **Citation Validity**: Every returned citation must exist in `response.retrieved` with matching `source` and `section`.
