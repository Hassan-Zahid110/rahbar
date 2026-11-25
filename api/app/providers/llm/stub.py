"""A deterministic offline provider (no model, no network).

Synthesizes grounded answers directly from the top retrieved passages that match
query terms, citing their exact metadata, so offline tests and CI evaluations are
deterministic and faithful to the retrieved evidence.
"""

from __future__ import annotations

import re

from ...schemas import Answer, Citation, Passage

WORD_RE = re.compile(r"[a-z0-9]+")
STOP = {
    "what", "is", "the", "a", "an", "of", "to", "in", "for", "on", "and", "or",
    "by", "with", "from", "at", "be", "are", "how", "many", "much", "when", "which",
}


class StubProvider:
    name = "stub"

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        if not passages:
            return Answer(
                reasoning="stub: nothing was retrieved",
                answer="No passages were retrieved for this question.",
                citations=[],
                answered_from_context=False,
                confidence="low",
            )

        q_words = {w for w in WORD_RE.findall(question.lower()) if w not in STOP and len(w) > 1}
        # Score each passage by keyword overlap + retrieval score
        scored_passages: list[tuple[float, Passage]] = []
        for idx, p in enumerate(passages):
            p_words = set(WORD_RE.findall(f"{p.section} {p.text}".lower()))
            overlap = len(q_words & p_words) / max(1, len(q_words))
            rank_bonus = 0.15 if idx == 0 else (0.05 if idx == 1 else 0.0)
            scored_passages.append((overlap + 0.5 * p.score + rank_bonus, p))

        scored_passages.sort(key=lambda x: x[0], reverse=True)
        chosen: list[Passage] = [scored_passages[0][1]]
        # Include second passage if it comes from the same document or has strong overlap (for multi-chunk synthesis)
        if len(scored_passages) > 1 and scored_passages[1][0] >= scored_passages[0][0] * 0.72:
            chosen.append(scored_passages[1][1])

        excerpts: list[str] = []
        citations: list[Citation] = []
        seen_cites: set[tuple[str, str]] = set()
        for p in chosen:
            clean_txt = re.sub(r"^\[[^\]]+\]\s*", "", p.text.strip())
            excerpts.append(f"{clean_txt} [{p.source} / {p.section}]")
            key = (p.source, p.section)
            if key not in seen_cites:
                seen_cites.add(key)
                citations.append(Citation(source=p.source, section=p.section, page=p.page))

        return Answer(
            reasoning=f"stub: synthesized from {len(chosen)} retrieved passage(s)",
            answer=" ".join(excerpts),
            citations=citations,
            answered_from_context=True,
            confidence="high",
        )
