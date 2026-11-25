"""RAGOps Part C1/D1 Component: Hybrid Lexical-Semantic Reranker."""

from __future__ import annotations

import re

from ..schemas import Passage
from .embedder import STOPWORDS, _stem_token

WORD_RE = re.compile(r"[a-z0-9]+")


def _query_stems(text: str) -> set[str]:
    tokens = WORD_RE.findall(text.lower())
    stems = {_stem_token(t) for t in tokens if t not in STOPWORDS and len(t) > 1}
    return stems or {_stem_token(t) for t in tokens}


def rerank_passages(question: str, passages: list[Passage], enabled: bool = True) -> list[Passage]:
    """Combine vector cosine similarity with BM25-style lexical stem overlap when enabled."""
    if not enabled or len(passages) <= 1:
        return list(passages)

    q_stems = _query_stems(question)
    if not q_stems:
        return list(passages)

    reranked: list[Passage] = []
    for p in passages:
        p_tokens = WORD_RE.findall(f"{p.section} {p.text}".lower())
        p_stems = {_stem_token(t) for t in p_tokens}
        overlap = len(q_stems & p_stems) / max(1, len(q_stems))
        # Exact numbers/acronyms bonus (e.g. 2.00, 80, 10,000, FA, FYP)
        q_nums = {t for t in WORD_RE.findall(question.lower()) if any(c.isdigit() for c in t)}
        p_nums = {t for t in p_tokens if any(c.isdigit() for c in t)}
        num_bonus = 0.08 if (q_nums and (q_nums & p_nums)) else 0.0
        combined = min(1.0, round(0.65 * p.score + 0.35 * overlap + num_bonus, 6))
        reranked.append(p.model_copy(update={"score": combined}))

    reranked.sort(key=lambda x: x.score, reverse=True)
    return reranked
