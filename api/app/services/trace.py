"""Part D1 (RAGOps 3.2.3, 5.1, Table 2): Structured End-to-End Query Trace Emitter.

Every query writes one JSON line to stdout AND to the persistent trace file (`traces/traces.jsonl`)
containing all required RAGOps traceability fields:
- trace_id, timestamp, user_query, rewritten_query
- embedding_model, embedding_version, collection_name, collection_version
- retrieved_chunks (with chunk_id, doc_id, doc_version, source, section, page, score)
- filters_applied, reranked_order
- prompt_hash, full_prompt
- model_and_params, response, citations
- guardrail_actions, latency_per_stage_ms, cache_status
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def compute_prompt_hash(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:24]


def emit_trace_record(
    trace_record: dict[str, Any],
    trace_log_path: str = "traces/traces.jsonl",
    emit_stdout: bool = True,
) -> None:
    line = json.dumps(trace_record, ensure_ascii=False)
    if emit_stdout:
        print(line, flush=True)
    if trace_log_path:
        try:
            path = Path(trace_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
