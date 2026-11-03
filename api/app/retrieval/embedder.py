"""Query-side embedding helper. Must use the exact pinned EMBED_MODEL (sections 3.2, 4.4)."""

from __future__ import annotations

import hashlib
import math
import re

import httpx

from ..config import Settings

WORD_RE = re.compile(r"[a-z0-9]+")


def _dummy_vector(text: str, dim: int = 768) -> list[float]:
    values: list[float] = []
    seed = text.encode("utf-8")
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        values.extend((b - 127.5) / 127.5 for b in seed)
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _hash_vector(text: str, dim: int = 384) -> list[float]:
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


def embed_query(text: str, settings: Settings) -> list[float]:
    """Embed a single user question using `settings.embed_model`."""
    model = settings.embed_model.strip()
    if model.startswith("dummy-"):
        try:
            dim = int(model.split("-", 1)[1])
        except ValueError:
            dim = 768
        return _dummy_vector(text, dim=dim)

    if model.startswith("hash-"):
        try:
            dim = int(model.split("-", 1)[1])
        except ValueError:
            dim = 384
        return _hash_vector(text, dim=dim)

    url = f"{settings.ollama_url.rstrip('/')}/api/embed"
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        resp = client.post(url, json={"model": model, "input": [text]})
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise RuntimeError(f"Ollama /api/embed returned invalid payload for model {model!r}")
        return [float(x) for x in embeddings[0]]
