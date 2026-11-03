"""Runtime configuration, read once from environment variables.

On the cluster these variables come from your ConfigMap and Secret (section 4.1).
Nothing here is baked into the image, so one image runs in every environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Which implementations to load. "stub" needs no cluster, no model, no network.
    retriever: str = "stub"          # RETRIEVER: stub | chroma
    llm_provider: str = "stub"       # LLM_PROVIDER: stub | ollama-host | ollama-incluster | hosted

    # The embedding pin (section 4.4). The indexer reads the same ConfigMap key.
    embed_model: str = "nomic-embed-text"

    # Vector store
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    collection: str = "rahbar"

    # Semantic cache (Redis)
    redis_host: str = ""
    redis_port: int = 6379
    cache_enabled: bool = True
    cache_threshold: float = 0.90
    cache_ttl_seconds: int = 86400

    # Retrieval, grounding, and generation
    top_k: int = 5
    relevance_floor: float = 0.35
    filter_superseded: bool = True
    strict_grounding_prompt: bool = True
    temperature: float = 0.2
    llm_model: str = "llama3.2:3b"
    llm_timeout_seconds: float = 90.0
    ollama_url: str = "http://host.minikube.internal:11434"
    hosted_base_url: str = ""        # e.g. https://api.groq.com/openai/v1
    llm_api_key: str = field(default="", repr=False)   # from the Secret; never log it

    log_level: str = "INFO"


def get_settings() -> Settings:
    retriever = os.environ.get("RETRIEVER", "stub")
    default_floor = 0.0 if retriever == "stub" else 0.35
    return Settings(
        retriever=retriever,
        llm_provider=os.environ.get("LLM_PROVIDER", "stub"),
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=_int("CHROMA_PORT", 8000),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        redis_host=os.environ.get("REDIS_HOST", ""),
        redis_port=_int("REDIS_PORT", 6379),
        cache_enabled=_bool("CACHE_ENABLED", retriever != "stub"),
        cache_threshold=_float("CACHE_THRESHOLD", 0.90),
        cache_ttl_seconds=_int("CACHE_TTL_SECONDS", 86400),
        top_k=_int("TOP_K", 5),
        relevance_floor=_float("RELEVANCE_FLOOR", default_floor),
        filter_superseded=_bool("FILTER_SUPERSEDED", True),
        strict_grounding_prompt=_bool("STRICT_GROUNDING_PROMPT", True),
        temperature=_float("TEMPERATURE", 0.2),
        llm_model=os.environ.get("LLM_MODEL", "llama3.2:3b"),
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 90.0),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        hosted_base_url=os.environ.get("HOSTED_BASE_URL", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
