"""Stage 4: Embed. One vector per chunk, from the pinned model only."""

from __future__ import annotations

import hashlib
import math
import re

import httpx

from .config import IndexerSettings

BATCH_SIZE = 32
WORD_RE = re.compile(r"[a-z0-9]+")


def hash_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic lexical feature-hash unit vector for offline CI (`hash-384`) when no
    external embedding server is used. Must only be used when EMBED_MODEL explicitly asks for it."""
    vec = [0.0] * dim
    tokens = WORD_RE.findall(text.lower())
    features = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")
    if not features:
        features = ["<empty>"]
    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]:
    """Embed `texts` in batches using `settings.embed_model`."""
    if not texts:
        return []

    model = settings.embed_model.strip()
    if model.startswith("hash-"):
        try:
            dim = int(model.split("-", 1)[1])
        except ValueError:
            dim = 384
        return [hash_embed(t, dim=dim) for t in texts]

    url = f"{settings.ollama_url.rstrip('/')}/api/embed"
    all_vectors: list[list[float]] = []
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            resp = client.post(url, json={"model": model, "input": batch})
            resp.raise_for_status()
            payload = resp.json()
            embeddings = payload.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != len(batch):
                raise RuntimeError(
                    f"Ollama /api/embed returned {type(embeddings).__name__} "
                    f"(expected {len(batch)} vectors for model {model!r})"
                )
            all_vectors.extend([[float(x) for x in vec] for vec in embeddings])
    return all_vectors
