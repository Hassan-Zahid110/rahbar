"""Liveness and readiness probes (sections 4.3 and 4.4).

`/healthz` checks only that the Python process is alive (touches zero dependencies).
`/readyz` verifies Chroma reachability, non-empty collection (`collection.count() > 0`),
embedding-model pin agreement, and Redis reachability — returning 503 with the exact
failing dependency when any check fails.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from ..retrieval.chroma import ChromaRetriever

router = APIRouter()
log = logging.getLogger("rahbar.health")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, object]:
    """Can this pod serve user traffic right now?"""
    state = request.app.state
    settings = state.settings
    retriever = state.retriever
    cache = getattr(state, "cache", None)
    checks: dict[str, object] = {}
    failures: list[str] = []

    if isinstance(retriever, ChromaRetriever):
        try:
            collection = retriever.client.get_collection(name=settings.collection)
            doc_count = int(collection.count())
            if doc_count <= 0:
                failures.append(f"chroma: collection {settings.collection!r} is empty (0 documents)")
                checks["chroma"] = "empty"
            else:
                meta = getattr(collection, "metadata", None) or {}
                indexed_model = str(meta.get("embed_model", ""))
                indexed_dim = meta.get("dimension")
                if indexed_model != settings.embed_model:
                    conflict = (
                        f"chroma: embed_model mismatch (indexed={indexed_model!r}, "
                        f"configured={settings.embed_model!r}, dimension={indexed_dim})"
                    )
                    log.error("readiness blocked by embedding pin mismatch", extra={"conflict": conflict})
                    failures.append(conflict)
                    checks["chroma"] = "embed_model_mismatch"
                else:
                    checks["chroma"] = "ok"
                    checks["collection_count"] = doc_count
                    checks["embed_model"] = indexed_model
        except Exception as exc:
            failures.append(f"chroma: unreachable or missing collection ({exc})")
            checks["chroma"] = "unreachable"
    else:
        checks["chroma"] = "stub"

    if cache is not None and (settings.redis_host or cache.enabled):
        try:
            if cache.ping():
                checks["redis"] = "ok"
            else:
                failures.append("redis: ping returned false")
                checks["redis"] = "failed"
        except Exception as exc:
            failures.append(f"redis: unreachable ({exc})")
            checks["redis"] = "unreachable"
    else:
        checks["redis"] = "disabled"

    if failures:
        response.status_code = 503
        return {
            "status": "not_ready",
            "failed": failures,
            "checks": checks,
        }

    return {"status": "ready", "checks": checks}
