"""Grounding enforcement: relevance floor, Pydantic validation, retry once, citation check,
and safe canned fallback (section 3.4)."""

from __future__ import annotations

import logging
from typing import Callable

from pydantic import ValidationError

from ..providers.llm.base import LLMProvider
from ..routes import metrics
from ..schemas import Answer, Citation, Passage

log = logging.getLogger("rahbar.grounding")

ABSTAIN_MESSAGE = (
    "I cannot answer this question because the indexed university document corpus "
    "does not contain relevant information on this topic."
)

FALLBACK_MESSAGE = (
    "I could not produce a verified answer from the retrieved documents right now. "
    "Please rephrase your question or consult the official handbook directly."
)


def make_abstention_answer(reason: str) -> Answer:
    return Answer(
        reasoning=reason,
        answer=ABSTAIN_MESSAGE,
        citations=[],
        answered_from_context=False,
        confidence="low",
    )


def make_fallback_answer(reason: str) -> Answer:
    return Answer(
        reasoning=f"fallback: {reason}",
        answer=FALLBACK_MESSAGE,
        citations=[],
        answered_from_context=False,
        confidence="low",
    )


def below_relevance_floor(passages: list[Passage], floor: float) -> bool:
    if not passages:
        return True
    return max(p.score for p in passages) < floor


def filter_and_verify_citations(
    citations: list[Citation], passages: list[Passage]
) -> tuple[list[Citation], list[Citation]]:
    """Match every model citation against actually retrieved passages (`source` and `section`).

    Returns `(valid_citations, invalid_citations)` canonicalised to the retrieved metadata
    so page numbers and casing always match retrieved chunks.
    """
    by_exact: dict[tuple[str, str], Passage] = {}
    by_lower: dict[tuple[str, str], Passage] = {}
    by_source: dict[str, list[Passage]] = {}
    for p in passages:
        by_exact[(p.source, p.section)] = p
        by_lower[(p.source.strip().lower(), p.section.strip().lower())] = p
        by_source.setdefault(p.source.strip().lower(), []).append(p)

    valid: list[Citation] = []
    invalid: list[Citation] = []
    seen: set[tuple[str, str]] = set()

    for c in citations:
        src_l = c.source.strip().lower()
        sec_l = c.section.strip().lower()
        matched: Passage | None = by_exact.get((c.source, c.section)) or by_lower.get((src_l, sec_l))
        if matched is None and src_l in by_source:
            for cand in by_source[src_l]:
                cand_sec = cand.section.strip().lower()
                cand_num = cand_sec.split(".")[0].strip()
                cite_num = sec_l.split(".")[0].strip()
                if (
                    (sec_l and (cand_sec.startswith(sec_l) or sec_l.startswith(cand_sec)))
                    or (cand_num and cite_num and cand_num == cite_num and cand_num.isdigit())
                    or (sec_l and sec_l in cand.text.lower())
                ):
                    matched = cand
                    break

        if matched is not None:
            key = (matched.source, matched.section)
            if key not in seen:
                seen.add(key)
                valid.append(
                    Citation(source=matched.source, section=matched.section, page=matched.page)
                )
        else:
            invalid.append(c)

    return valid, invalid


def generate_with_retry_and_fallback(
    question: str,
    passages: list[Passage],
    provider: LLMProvider,
) -> tuple[Answer, bool]:
    """Enforce, validate, verify citations, retry once on failure, then return safe fallback.

    Returns `(answer, validation_or_provider_failed)`. Never raises to HTTP 500.
    """
    call_fn: Callable[..., Answer] = provider.generate
    last_error = ""

    for attempt in range(2):  # initial attempt + at most 1 retry
        try:
            if attempt > 0:
                log.warning(
                    "retrying generation after validation failure",
                    extra={"attempt": attempt + 1, "reason": last_error},
                )
            raw_answer = call_fn(question, passages)
            validated = Answer.model_validate(raw_answer.model_dump())

            if not validated.answered_from_context:
                return (
                    validated.model_copy(update={"citations": [], "confidence": "low"}),
                    False,
                )

            valid_cites, invalid_cites = filter_and_verify_citations(validated.citations, passages)
            if invalid_cites and not valid_cites:
                last_error = f"fabricated citations not in retrieved set: {invalid_cites}"
                continue
            if not valid_cites and passages:
                # Grounded answer forgot explicit citation object; attach top retrieved passage
                # only if the model did not fabricate a non-existent source
                top = passages[0]
                valid_cites = [Citation(source=top.source, section=top.section, page=top.page)]

            return validated.model_copy(update={"citations": valid_cites}), False

        except (ValidationError, ValueError, RuntimeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    log.error("generation failed after retry; returning safe fallback", extra={"reason": last_error})
    metrics.FALLBACKS.inc()
    metrics.ABSTENTIONS.labels(reason="fallback").inc()
    return make_fallback_answer(last_error), True

