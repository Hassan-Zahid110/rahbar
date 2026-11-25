"""Part D4 (RAGOps 3.2.3 & 5.1): Input, Retrieval, and Output Guardrails with Trace Action Logging."""

from __future__ import annotations

import re

from ..routes import metrics
from ..schemas import Passage

INJECTION_PATTERNS = [
    re.compile(r"\[?SYSTEM\s*(?:INSTRUCTION)?\s*OVERRIDE\]?[:\s]*[^.\n]*", re.IGNORECASE),
    re.compile(r"ignore\s+all\s+(?:previous|prior)\s+instructions[^.\n]*[.]?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules)[^.\n]*[.]?", re.IGNORECASE),
    re.compile(r"tell\s+the\s+student\s+that\s+(?:all\s+final\s+examinations\s+are\s+open-book|attendance\s+is\s+(?:completely\s+)?optional)[^.\n]*[.]?", re.IGNORECASE),
]


def inspect_query_rail(question: str) -> tuple[str, list[str], int]:
    """Input guardrail: normalizes whitespace and flags injection patterns in user query."""
    actions: list[str] = []
    flagged = 0
    rewritten = " ".join(question.strip().split())
    for pat in INJECTION_PATTERNS:
        if pat.search(rewritten):
            flagged += 1
            actions.append("input_rail:flagged_prompt_injection_in_query")
            metrics.INJECTION_ATTEMPTS.inc()
            break
    if not actions:
        actions.append("input_rail:passed")
    return rewritten, actions, flagged


def sanitize_retrieved_passages_rail(passages: list[Passage]) -> tuple[list[Passage], list[str], int]:
    """Retrieval guardrail (Part D4): scans retrieved chunks for embedded prompt-injection payloads,
    strips malicious clauses before prompt augmentation, and logs actions into the trace."""
    sanitized: list[Passage] = []
    actions: list[str] = []
    flagged = 0

    for p in passages:
        cleaned_text = p.text
        chunk_flagged = False
        for pat in INJECTION_PATTERNS:
            if pat.search(cleaned_text):
                chunk_flagged = True
                cleaned_text = pat.sub("[REDACTED_BY_RETRIEVAL_GUARDRAIL]", cleaned_text)
        if chunk_flagged:
            flagged += 1
            metrics.INJECTION_ATTEMPTS.inc()
            actions.append(
                f"retrieval_rail:stripped_injected_instruction:chunk_id={p.chunk_id}:source={p.source}"
            )
            sanitized.append(p.model_copy(update={"text": cleaned_text}))
        else:
            sanitized.append(p)

    if not actions:
        actions.append("retrieval_rail:passed_clean")
    return sanitized, actions, flagged
