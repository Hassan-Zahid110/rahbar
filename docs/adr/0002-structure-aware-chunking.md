# ADR 0002: Structure-Aware Chunking with Section Metadata and Superseded Filtering

## Status
Accepted · 2026-11-04

## Context
University regulatory documents (the FAST-NUCES Academic Rules Handbook, Student Handbook, Prospectus, and Fee Schedules) exhibit three structural properties that break naive fixed-window character/token chunkers:
1. **Numbered clauses and long definitions**: Splitting blindly every `N` tokens severs clause headings (e.g., `1.21 Attendance` or `5.4 Academic Warning`) from their operative thresholds (`80%`, `CGPA 2.00`), causing both retrieval misses (Failure Mode B) and broken citations.
2. **Multi-column tables**: Fee schedules and grading scales lose row-to-header alignment if flattened as raw text streams (Failure Mode A).
3. **Coexisting policy versions**: When both a superseded 2023 rulebook and the current 2026 handbook live in the corpus, both share nearly identical vocabulary; dense cosine similarity alone retrieves repealed thresholds (`75%` attendance or `1.75` CGPA) alongside or ahead of current ones (Failure Mode E). Prompts cannot reliably adjudicate version precedence if only the repealed chunk makes the top-`k`.

## Decision
1. **Markdown-preserving table extraction (`indexer/pipeline/extract.py`)**: Both `pdfplumber` PDF tables and HTML `<table>` elements are converted into GitHub-flavoured Markdown tables (`| col | ... |`) while excluding table bounding boxes from prose extraction so rows remain intact and un-duplicated.
2. **Hierarchical structure-aware splitter (`indexer/pipeline/chunk.py`)**:
   - First detect structural section boundaries (Markdown `#`–`####`, numbered section titles such as `5.4 Academic Warning`, and named `Section`/`Chapter` headers) while distinguishing short headings from prose sentences ending in `.`.
   - Pack complete paragraphs under `CHUNK_SIZE` whitespace tokens within each section, falling back to sentence boundaries (`(?<=[.!?])\s+`) only when a single paragraph exceeds `CHUNK_SIZE`.
   - Share `CHUNK_OVERLAP` trailing tokens across adjacent chunks within the same section, and prepend `[<section>]` when the heading is not already in the chunk body so dense embeddings retain topical context.
3. **Graded chunk metadata & query-time filtering**: Every chunk writes `source`, `section`, `page`, `doc_version`, and `superseded: bool` to ChromaDB. `ChromaRetriever.retrieve` applies `where={"superseded": False}` by default, lifting that filter only when `asks_for_historical_version(question)` detects explicit historical intent (e.g., `"in 2023"` or `"previous edition"`).

## Options Considered
1. **Fixed-size token windows (`CHUNK_STRATEGY=fixed`)** — Tested empirically in our Stage B failure analysis (`100` tokens, `0` overlap): severed clause headers from conditions, erased meaningful `section` labels, and degraded `recall@5`.
2. **Relying on prompt instructions to ignore outdated policies** — Rejected because if `top_k` fills with chunks from an older edition, the current edition may never enter the prompt context at all. Metadata filtering enforces version correctness deterministically at the retrieval layer.
3. **Parent-document / recursive multi-vector indexing** — Rejected as unnecessary operational complexity for a 50–150 page corpus once section-header prepending and tuned `(CHUNK_SIZE, CHUNK_OVERLAP)` were measured on our golden set.

## Consequences
- **Easier**: Every retrieved chunk carries a human-verifiable `(source, section, page)` citation; repealed policies never contaminate answers to present-tense student questions; table rows remain readable to the LLM.
- **Harder / Watch-fors**: Heading heuristics must avoid misclassifying numbered list sentences as section titles (guarded by length `<= 85` chars and trailing-period checks, verified by unit tests in `indexer/tests/test_pipeline_stages.py`).
