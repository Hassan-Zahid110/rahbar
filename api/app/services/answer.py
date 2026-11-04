"""Full eight-step production query pipeline (sections 3.2, 3.3, 3.4, 4.8):

1. Receive & validate question (AskRequest: 3..500 chars)
2. Semantic cache check (skipped for follow-up questions)
3. Embed question with pinned EMBED_MODEL
4. Retrieve top-k chunks from Chroma (filtering superseded unless historical intent)
5. Enforce relevance floor (honest abstention when evidence is absent) & augment prompt
6. Generate schema-constrained Answer at low temperature
7. Validate with Pydantic + citation check, retry once, safe fallback on failure
8. Log structured observability record & cache if safe to cache
"""

from __future__ import annotations

import logging
import time

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..retrieval.chroma import ChromaRetriever
from ..retrieval.embedder import embed_query
from ..routes import metrics
from ..schemas import AskResponse, RetrievedRef
from .cache import SemanticCache, is_followup
from .grounding import (
    below_relevance_floor,
    generate_with_retry_and_fallback,
    make_abstention_answer,
)

log = logging.getLogger("rahbar.answer")


def answer_question(
    question: str,
    retriever: Retriever,
    provider: LLMProvider,
    settings: Settings,
    cache: SemanticCache | None = None,
) -> AskResponse:
    req_id = request_id_var.get()
    active_cache = cache if (cache is not None and cache.enabled) else None
    query_vec: list[float] | None = None

    # Step 2 & 3: Embed once (when using real/cached pipeline) and check semantic cache
    if active_cache is not None or isinstance(retriever, ChromaRetriever):
        query_vec = embed_query(question, settings)

    if active_cache is not None:
        if is_followup(question):
            metrics.CACHE_LOOKUPS.labels(result="skipped").inc()
        elif query_vec is not None:
            cached_hit, sim = active_cache.lookup(question, query_vec, request_id=req_id)
            if cached_hit is not None:
                metrics.record_cache_outcome(hit=True)
                log.info(
                    "answered",
                    extra={
                        "retriever": retriever.name,
                        "provider": cached_hit.provider,
                        "cached": True,
                        "cache_similarity": round(sim, 4),
                        "top_k": settings.top_k,
                        "chunk_ids": [r.chunk_id for r in cached_hit.retrieved],
                        "scores": [round(r.score, 4) for r in cached_hit.retrieved],
                        "answered_from_context": cached_hit.answered_from_context,
                        "abstained": not cached_hit.answered_from_context,
                    },
                )
                return cached_hit
            metrics.record_cache_outcome(hit=False)

    # Step 4: Retrieve top-k passages
    t_ret = time.perf_counter()
    if isinstance(retriever, ChromaRetriever) and query_vec is not None:
        passages = retriever.retrieve(question, k=settings.top_k, query_vector=query_vec)
    else:
        passages = retriever.retrieve(question, k=settings.top_k)
    metrics.RETRIEVAL_LATENCY.observe(time.perf_counter() - t_ret)

    retrieved_refs = [
        RetrievedRef(
            chunk_id=p.chunk_id,
            source=p.source,
            section=p.section,
            page=p.page,
            score=p.score,
        )
        for p in passages
    ]

    # Step 5: Relevance floor -> honest abstention before calling LLM
    validation_failed = False
    if below_relevance_floor(passages, settings.relevance_floor):
        metrics.ABSTENTIONS.labels(reason="below_relevance_floor").inc()
        top_score = max((p.score for p in passages), default=0.0)
        answer = make_abstention_answer(
            f"max similarity {top_score:.4f} is below relevance floor {settings.relevance_floor:.4f}"
        )
    else:
        # Step 6 & 7: Augment, generate, validate, retry once, fallback safely
        t_gen = time.perf_counter()
        answer, validation_failed = generate_with_retry_and_fallback(question, passages, provider)
        metrics.GENERATION_LATENCY.observe(time.perf_counter() - t_gen)
        if not answer.answered_from_context and not validation_failed:
            metrics.ABSTENTIONS.labels(reason="model_declined").inc()

    response = AskResponse(
        request_id=req_id,
        answer=answer.answer,
        citations=answer.citations,
        answered_from_context=answer.answered_from_context,
        confidence=answer.confidence,
        retrieved=retrieved_refs,
        provider=provider.name,
        cached=False,
    )

    # Step 8: Store cache entry if safe (never follow-ups, abstentions, or fallbacks)
    if active_cache is not None and query_vec is not None:
        active_cache.store(question, query_vec, response, validation_failed=validation_failed)

    log.info(
        "answered",
        extra={
            "retriever": retriever.name,
            "provider": provider.name,
            "cached": False,
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "answered_from_context": response.answered_from_context,
            "abstained": not response.answered_from_context,
        },
    )
    return response
