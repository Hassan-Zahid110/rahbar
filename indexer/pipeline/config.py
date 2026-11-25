"""Indexer configuration, from the same ConfigMap the API reads (section 4.1 & RAGOps Part A/F)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class IndexerSettings:
    embed_model: str        # EMBED_MODEL: must equal the API's value (section 4.4)
    chroma_host: str
    chroma_port: int
    collection: str
    corpus_dir: str         # where the incoming batch documents sit
    chunk_size: int
    chunk_overlap: int
    ollama_url: str
    redis_host: str = ""
    redis_port: int = 6379
    chunk_strategy: str = "structure"
    disable_ocr: bool = False
    data_dir: str = "/tmp/rahbar_data"       # persistent volume root for data_lake, quarantine, archive
    near_dup_threshold: float = 0.90


def get_settings() -> IndexerSettings:
    return IndexerSettings(
        embed_model=os.environ.get("EMBED_MODEL", "hash-384"),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=int(os.environ.get("CHROMA_PORT", 8000)),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        corpus_dir=os.environ.get("CORPUS_DIR", "/corpus"),
        chunk_size=int(os.environ.get("CHUNK_SIZE", 300)),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", 50)),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        redis_host=os.environ.get("REDIS_HOST", ""),
        redis_port=int(os.environ.get("REDIS_PORT", 6379)),
        chunk_strategy=os.environ.get("CHUNK_STRATEGY", "structure"),
        disable_ocr=_bool("DISABLE_OCR", False),
        data_dir=os.environ.get("DATA_DIR", "/tmp/rahbar_data"),
        near_dup_threshold=float(os.environ.get("NEAR_DUP_THRESHOLD", 0.90)),
    )
