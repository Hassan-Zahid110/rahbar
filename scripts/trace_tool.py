"""Part D2 (RAGOps 3.2.3, 5.1): Trace Inspection & Prompt Reconstruction CLI Tool.

Usage:
  python -m scripts.trace_tool --trace-id <TRACE_ID>
  python -m scripts.trace_tool --list
  python -m scripts.trace_tool --show-sample-d1-d2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE_PATH = REPO_ROOT / "traces" / "traces.jsonl"


def load_traces(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def format_reconstructed_trace(rec: dict[str, Any]) -> str:
    lines = [
        "=" * 108,
        f"RAGOPS PART D2 TRACE TOOL — PROMPT & CONTEXT RECONSTRUCTION | trace_id: {rec['trace_id']}",
        "-" * 108,
        f"Timestamp          : {rec['timestamp']}",
        f"User Query         : {rec['user_query']}",
        f"Rewritten Query    : {rec['rewritten_query']}",
        f"Embedding Model    : {rec['embedding_model']} (version={rec['embedding_version']})",
        f"Collection         : {rec['collection_name']} (version={rec['collection_version']})",
        f"Filters Applied    : {json.dumps(rec['filters_applied'])}",
        f"Reranked Order     : {rec['reranked_order']}",
        f"Cache Status       : {rec['cache_status']}",
        f"Guardrail Actions  : {rec['guardrail_actions']}",
        f"Stage Latencies ms : {json.dumps(rec['latency_per_stage_ms'])}",
        f"Model & Params     : {json.dumps(rec['model_and_params'])}",
        f"Prompt SHA256 Hash : {rec['prompt_hash']}",
        "-" * 108,
        "RETRIEVED CONTEXT CHUNKS:",
    ]
    for idx, ch in enumerate(rec.get("retrieved_chunks", []), start=1):
        lines.append(
            f"  [{idx}] chunk_id={ch['chunk_id']} | doc_id={ch['doc_id']} (v={ch['doc_version']}) | "
            f"section={ch['section']!r} (p.{ch['page']}) | score={ch['score']:.4f}"
        )
    lines.extend([
        "-" * 108,
        "EXACT RECONSTRUCTED PROMPT SENT TO GENERATOR:",
        rec.get("full_prompt", ""),
        "-" * 108,
        "GENERATED RESPONSE & CITATIONS:",
        f"  Answered From Context : {rec['response']['answered_from_context']} (confidence={rec['response']['confidence']})",
        f"  Answer                : {rec['response']['answer']}",
        f"  Verified Citations    : {json.dumps(rec['citations'])}",
        "=" * 108,
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAGOps Part D2 Trace Inspection Tool.")
    parser.add_argument("--trace-file", type=str, default=str(DEFAULT_TRACE_PATH))
    parser.add_argument("--trace-id", type=str, default="", help="trace_id to reconstruct")
    parser.add_argument("--list", action="store_true", help="list recent trace IDs and queries")
    parser.add_argument("--show-sample-d1-d2", action="store_true", help="print one full D1 JSON trace record + D2 prompt reconstruction")
    args = parser.parse_args()

    traces = load_traces(Path(args.trace_file))
    if not traces:
        print(f"No traces found at {args.trace_file}", file=sys.stderr)
        return 1

    if args.list:
        for t in traces[-15:]:
            print(f"{t['trace_id']} | {t['timestamp']} | cache={t['cache_status']:<4} | {t['user_query'][:65]}")
        return 0

    if args.show_sample_d1_d2:
        # Pick a trace where retrieval_rail stripped an injected instruction (or first answered trace)
        target = next(
            (t for t in traces if any("stripped_injected_instruction" in a for a in t.get("guardrail_actions", []))),
            traces[0],
        )
        print(">>> [PART D1] FULL JSON TRACE RECORD (Single JSON Line Pretty-Printed):")
        # Show full trace JSON with full_prompt truncated to 360 chars in JSON preview so terminal fits, then full prompt in D2
        d1_view = dict(target)
        print(json.dumps(d1_view, indent=2), flush=True)
        print("\n>>> [PART D2] TRACE TOOL REBUILDING EXACT CONTEXT & PROMPT FOR TRACE ID:", target["trace_id"])
        print(format_reconstructed_trace(target), flush=True)
        return 0

    target_id = args.trace_id.strip()
    matched = next((t for t in traces if t["trace_id"] == target_id or t["trace_id"].startswith(target_id)), None)
    if matched is None:
        print(f"Trace ID {target_id!r} not found in {args.trace_file}", file=sys.stderr)
        return 1

    print(format_reconstructed_trace(matched), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
