"""Semantic cache backed by Redis with generation-based re-index invalidation (section 3.3)."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from typing import Any

from ..config import Settings
from ..schemas import AskResponse

log = logging.getLogger("rahbar.cache")

CACHE_GEN_KEY = "rahbar:cache:generation"
CACHE_INDEX_KEY = "rahbar:cache:keys"

FOLLOWUP_START_RE = re.compile(
    r"^\s*(?:and\b|also\b|what\s+about\b|how\s+about\b|then\b|so\b|or\s+if\b|why\s+is\s+that\b)",
    re.IGNORECASE,
)
ANAPHORA_RE = re.compile(
    r"\b(?:that\s+(?:rule|policy|clause|course|fee)|this\s+(?:rule|policy|clause)|"
    r"the\s+same\s+(?:course|policy)|above|previous\s+question|earlier\s+answer)\b",
    re.IGNORECASE,
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def is_followup(question: str) -> bool:
    """Return True if the question relies on prior conversational turn context."""
    q = question.strip()
    if FOLLOWUP_START_RE.search(q):
        return True
    if ANAPHORA_RE.search(q):
        return True
    words = q.lower().split()
    if len(words) <= 6 and any(w in {"it", "they", "them", "those", "these", "that"} for w in words):
        return True
    return False


def never_cache(question: str, response: AskResponse, validation_failed: bool = False) -> bool:
    """Enforce section 3.3 never-cache rules:
    never cache follow-up questions, abstentions, out-of-scope answers, or validation failures."""
    if validation_failed:
        return True
    if is_followup(question):
        return True
    if not response.answered_from_context:
        return True
    if not response.citations:
        return True
    return False


class SemanticCache:
    """Semantic query cache storing question embeddings + validated grounded answers in Redis."""

    def __init__(self, settings: Settings, redis_client: Any | None = None) -> None:
        self.settings = settings
        self._client = redis_client
        if self._client is None and settings.redis_host:
            import redis

            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )

    @property
    def enabled(self) -> bool:
        return bool(self.settings.cache_enabled and self._client is not None)

    def ping(self) -> bool:
        if self._client is None:
            return True
        return bool(self._client.ping())

    def current_generation(self) -> str:
        if self._client is None:
            return "0"
        val = self._client.get(CACHE_GEN_KEY)
        return str(val) if val is not None else "0"

    def invalidate(self) -> int:
        """Expire all cached entries by bumping generation_id and purging tracked keys."""
        client = self._client
        if client is None:
            return 0
        new_gen = int(client.incr(CACHE_GEN_KEY))
        keys = list(client.smembers(CACHE_INDEX_KEY) or [])
        if keys:
            client.delete(*keys)
        client.delete(CACHE_INDEX_KEY)
        log.info("cache invalidated", extra={"generation_id": new_gen, "purged": len(keys)})
        return new_gen

    def lookup(
        self, question: str, query_vector: list[float], request_id: str
    ) -> tuple[AskResponse | None, float]:
        """Return (cached_response, best_similarity) if similarity >= settings.cache_threshold."""
        client = self._client
        if not self.enabled or client is None or is_followup(question):
            return None, 0.0
        try:
            gen_id = self.current_generation()
            prefix = f"rahbar:cache:gen:{gen_id}:"
            tracked = list(client.smembers(CACHE_INDEX_KEY) or [])
            best_sim = 0.0
            best_payload: dict[str, Any] | None = None

            for key in tracked:
                if not str(key).startswith(prefix):
                    continue
                raw = client.get(key)
                if not raw:
                    continue
                entry = json.loads(raw)
                sim = cosine_similarity(query_vector, entry.get("vector") or [])
                if sim > best_sim:
                    best_sim = sim
                    best_payload = entry.get("response")

            if best_payload is not None and best_sim >= self.settings.cache_threshold:
                cached_resp = AskResponse.model_validate(best_payload)
                return (
                    cached_resp.model_copy(update={"request_id": request_id, "cached": True}),
                    best_sim,
                )
            return None, best_sim
        except Exception as exc:
            log.warning("cache lookup failed", extra={"error": str(exc)})
            return None, 0.0

    def store(
        self,
        question: str,
        query_vector: list[float],
        response: AskResponse,
        validation_failed: bool = False,
    ) -> bool:
        """Store a validated answer under the active index generation if safe to cache."""
        client = self._client
        if not self.enabled or client is None or never_cache(question, response, validation_failed=validation_failed):
            return False
        try:
            gen_id = self.current_generation()
            q_hash = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()[:20]
            key = f"rahbar:cache:gen:{gen_id}:{q_hash}"
            payload = {
                "question": question,
                "vector": query_vector,
                "response": response.model_copy(update={"cached": False}).model_dump(),
                "created_at": int(time.time()),
            }
            client.set(key, json.dumps(payload), ex=self.settings.cache_ttl_seconds)
            client.sadd(CACHE_INDEX_KEY, key)
            return True
        except Exception as exc:
            log.warning("cache store failed", extra={"error": str(exc)})
            return False

