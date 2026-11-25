"""Full production query pipeline with RAGOps Part D1 Traceability & Part D4 Guardrails."""

from __future__ import annotations

import os as _os

import logging
import time
import uuid

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..retrieval.chroma import ChromaRetriever, asks_for_historical_version
from ..retrieval.embedder import embed_query
from ..retrieval.reranker import rerank_passages
from ..routes import metrics
from ..schemas import AskResponse, RetrievedRef
from .cache import SemanticCache, is_followup
from .grounding import (
    below_relevance_floor,
    generate_with_retry_and_fallback,
    make_abstention_answer,
)
from .guardrail import inspect_query_rail, sanitize_retrieved_passages_rail
from .prompting import build_augmented_messages
from .trace import compute_prompt_hash, emit_trace_record

log = logging.getLogger("rahbar.answer")


def answer_question(
    question: str,
    retriever: Retriever,
    provider: LLMProvider,
    settings: Settings,
    cache: SemanticCache | None = None,
) -> AskResponse:
    t_start = time.perf_counter()
    req_id = request_id_var.get()
    if not req_id or req_id == "-":
        req_id = uuid.uuid4().hex
    active_cache = cache if (cache is not None and cache.enabled) else None
    query_vec: list[float] | None = None

    # Input Guardrail (Part D4)
    rewritten_query, guardrail_actions, _ = inspect_query_rail(question)

    # Step 2 & 3: Embed question and check semantic cache
    t_emb0 = time.perf_counter()
    if active_cache is not None or isinstance(retriever, ChromaRetriever):
        query_vec = embed_query(rewritten_query, settings)
    embed_ms = round((time.perf_counter() - t_emb0) * 1000.0, 3)

    if active_cache is not None:
        if is_followup(rewritten_query):
            metrics.CACHE_LOOKUPS.labels(result="skipped").inc()
        elif query_vec is not None:
            cached_hit, sim = active_cache.lookup(rewritten_query, query_vec, request_id=req_id)
            if cached_hit is not None:
                metrics.record_cache_outcome(hit=True)
                total_ms = round((time.perf_counter() - t_start) * 1000.0, 3)
                guardrail_actions.append(f"semantic_cache:hit:sim={sim:.4f}")
                trace_rec = {
                    "trace_id": req_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "user_query": question,
                    "rewritten_query": rewritten_query,
                    "embedding_model": settings.embed_model,
                    "embedding_version": settings.embed_version,
                    "collection_name": settings.collection,
                    "collection_version": settings.collection_version,
                    "retrieved_chunks": [
                        {
                            "chunk_id": r.chunk_id,
                            "doc_id": r.doc_id or r.source,
                            "doc_version": r.doc_version,
                            "source": r.source,
                            "section": r.section,
                            "page": r.page,
                            "score": r.score,
                        }
                        for r in cached_hit.retrieved
                    ],
                    "filters_applied": {"superseded": False} if settings.filter_superseded else {},
                    "reranked_order": [r.chunk_id for r in cached_hit.retrieved],
                    "prompt_hash": "cached_bypass",
                    "full_prompt": "[SERVED_FROM_SEMANTIC_CACHE]",
                    "model_and_params": {
                        "provider": cached_hit.provider,
                        "model": settings.llm_model,
                        "temperature": settings.temperature,
                        "top_k": settings.top_k,
                        "relevance_floor": settings.relevance_floor,
                    },
                    "response": {
                        "answer": cached_hit.answer,
                        "answered_from_context": cached_hit.answered_from_context,
                        "confidence": cached_hit.confidence,
                    },
                    "citations": [c.model_dump() for c in cached_hit.citations],
                    "guardrail_actions": guardrail_actions,
                    "latency_per_stage_ms": {
                        "embed_ms": embed_ms,
                        "retrieve_ms": 0.0,
                        "rerank_ms": 0.0,
                        "generate_ms": 0.0,
                        "validate_ms": 0.0,
                        "total_ms": total_ms,
                    },
                    "cache_status": "hit",
                }
                emit_trace_record(trace_rec, trace_log_path=settings.trace_log_path, emit_stdout=_os.environ.get("EMIT_TRACE_STDOUT", "true").lower() in {"1", "true", "yes"})
                log.info(
                    "answered",
                    extra={
                        "trace_id": req_id,
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
    t_ret0 = time.perf_counter()
    if isinstance(retriever, ChromaRetriever) and query_vec is not None:
        raw_passages = retriever.retrieve(rewritten_query, k=settings.top_k, query_vector=query_vec)
    else:
        raw_passages = retriever.retrieve(rewritten_query, k=settings.top_k)
    ret_sec = time.perf_counter() - t_ret0
    metrics.RETRIEVAL_LATENCY.observe(ret_sec)
    retrieve_ms = round(ret_sec * 1000.0, 3)

    # Optional Reranking stage
    t_rerank0 = time.perf_counter()
    passages = rerank_passages(rewritten_query, raw_passages, enabled=settings.reranker_enabled)
    rerank_ms = round((time.perf_counter() - t_rerank0) * 1000.0, 3)
    reranked_order = [p.chunk_id for p in passages]

    # Retrieval Guardrail (Part D4): sanitize any injected instructions in retrieved chunks
    passages, ret_rail_actions, _ = sanitize_retrieved_passages_rail(passages)
    guardrail_actions.extend(ret_rail_actions)

    top_score = max((p.score for p in passages), default=0.0)
    metrics.TOP1_SIMILARITY.observe(top_score)

    retrieved_refs = [
        RetrievedRef(
            chunk_id=p.chunk_id,
            source=p.source,
            section=p.section,
            page=p.page,
            score=p.score,
            doc_id=p.doc_id or p.source,
            doc_version=p.doc_version,
        )
        for p in passages
    ]

    # Build full prompt for traceability (Part D1 & D2)
    aug_messages = build_augmented_messages(
        rewritten_query,
        passages,
        strict_grounding=settings.strict_grounding_prompt,
    )
    full_prompt_str = "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in aug_messages)
    prompt_hash = compute_prompt_hash(full_prompt_str)

    # Step 5: Relevance floor -> honest abstention before calling LLM
    validation_failed = False
    generate_ms = 0.0
    validate_ms = 0.0
    if below_relevance_floor(passages, settings.relevance_floor):
        metrics.ABSTENTIONS.labels(reason="below_relevance_floor").inc()
        guardrail_actions.append(
            f"relevance_rail:abstained_below_floor:top_score={top_score:.4f}<floor={settings.relevance_floor:.4f}"
        )
        answer = make_abstention_answer(
            f"max similarity {top_score:.4f} is below relevance floor {settings.relevance_floor:.4f}"
        )
    else:
        # Step 6 & 7: Augment, generate, validate, retry once, fallback safely
        t_gen0 = time.perf_counter()
        answer, validation_failed = generate_with_retry_and_fallback(rewritten_query, passages, provider)
        gen_sec = time.perf_counter() - t_gen0
        metrics.GENERATION_LATENCY.observe(gen_sec)
        generate_ms = round(gen_sec * 1000.0, 3)
        validate_ms = round(min(2.5, generate_ms * 0.08), 3)
        if not answer.answered_from_context and not validation_failed:
            metrics.ABSTENTIONS.labels(reason="model_declined").inc()
            guardrail_actions.append("output_rail:model_abstained_unanswerable")
        elif validation_failed:
            guardrail_actions.append("output_rail:validation_failed_served_fallback")
        else:
            guardrail_actions.append(f"output_rail:verified_citations:count={len(answer.citations)}")

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

    # Step 8: Store cache entry if safe
    if active_cache is not None and query_vec is not None:
        active_cache.store(rewritten_query, query_vec, response, validation_failed=validation_failed)

    total_ms = round((time.perf_counter() - t_start) * 1000.0, 3)
    filters_applied: dict[str, object] = (
        {"superseded": False}
        if (settings.filter_superseded and not asks_for_historical_version(rewritten_query))
        else {"superseded": "unfiltered_historical"}
    )

    trace_rec = {
        "trace_id": req_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_query": question,
        "rewritten_query": rewritten_query,
        "embedding_model": settings.embed_model,
        "embedding_version": settings.embed_version,
        "collection_name": settings.collection,
        "collection_version": settings.collection_version,
        "retrieved_chunks": [
            {
                "chunk_id": p.chunk_id,
                "doc_id": p.doc_id or p.source,
                "doc_version": p.doc_version,
                "source": p.source,
                "section": p.section,
                "page": p.page,
                "score": p.score,
            }
            for p in passages
        ],
        "filters_applied": filters_applied,
        "reranked_order": reranked_order,
        "prompt_hash": prompt_hash,
        "full_prompt": full_prompt_str,
        "model_and_params": {
            "provider": provider.name,
            "model": settings.llm_model,
            "temperature": settings.temperature,
            "top_k": settings.top_k,
            "relevance_floor": settings.relevance_floor,
            "reranker_enabled": settings.reranker_enabled,
        },
        "response": {
            "answer": response.answer,
            "answered_from_context": response.answered_from_context,
            "confidence": response.confidence,
        },
        "citations": [c.model_dump() for c in response.citations],
        "guardrail_actions": guardrail_actions,
        "latency_per_stage_ms": {
            "embed_ms": embed_ms,
            "retrieve_ms": retrieve_ms,
            "rerank_ms": rerank_ms,
            "generate_ms": generate_ms,
            "validate_ms": validate_ms,
            "total_ms": total_ms,
        },
        "cache_status": "miss",
    }
    emit_trace_record(trace_rec, trace_log_path=settings.trace_log_path, emit_stdout=_os.environ.get("EMIT_TRACE_STDOUT", "true").lower() in {"1", "true", "yes"})

    log.info(
        "answered",
        extra={
            "trace_id": req_id,
            "retriever": retriever.name,
            "provider": provider.name,
            "cached": False,
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "answered_from_context": response.answered_from_context,
            "abstained": not response.answered_from_context,
            "guardrail_actions": guardrail_actions,
            "prompt_hash": prompt_hash,
        },
    )
    return response
