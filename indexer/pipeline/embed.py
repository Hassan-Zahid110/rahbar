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



STEM_SYNONYMS = {
    "examinations": "exam", "examination": "exam", "exams": "exam",
    "attending": "attend", "attendance": "attend", "absent": "absence",
    "programmes": "program", "programme": "program", "programs": "program",
    "scholarships": "scholarship", "waiver": "scholarship", "aid": "financial_aid",
    "warnings": "warning", "probation": "warning", "dismissed": "dropped", "dismissal": "dropped",
    "refunded": "refund", "refunds": "refund", "reimbursement": "refund",
    "tuition": "fee", "fees": "fee", "charges": "fee", "charge": "fee", "cost": "fee", "price": "fee",
    "credits": "credit", "hours": "hour",
    "semesters": "semester", "terms": "semester",
    "courses": "course", "classes": "course",
    "grades": "grade", "grading": "grade", "cgpa": "gpa", "sgpa": "gpa",
    "borrowed": "borrow", "borrowing": "borrow", "books": "book", "library": "library_book",
    "fines": "fine", "overdue": "late_fine", "penalty": "fine",
    "calculators": "calculator", "phones": "phone", "mobile": "phone",
    "medals": "medal", "gold": "medal", "graduating": "graduation", "graduate": "graduation",
    "registration": "register", "overload": "credit_load",
}

STOPWORDS = {
    "what", "is", "the", "a", "an", "of", "to", "in", "for", "on", "and", "or",
    "by", "with", "from", "at", "be", "are", "was", "were", "can", "may", "must",
    "how", "many", "much", "when", "where", "which", "who", "does", "do", "if", "that", "this",
}


def _stem_token(tok: str) -> str:
    if tok in STEM_SYNONYMS:
        return STEM_SYNONYMS[tok]
    if len(tok) > 5 and tok.endswith("ing"):
        tok = tok[:-3]
    elif len(tok) > 4 and tok.endswith("ed"):
        tok = tok[:-2]
    elif len(tok) > 4 and tok.endswith("es"):
        tok = tok[:-2]
    elif len(tok) > 3 and tok.endswith("s"):
        tok = tok[:-1]
    return STEM_SYNONYMS.get(tok, tok)


def hybrid_embed(text: str, dim: int = 512) -> list[float]:
    """Enhanced RAGOps candidate embedder (`hybrid-512`): combines stopword-filtered
    morphological stems, domain synonym normalization, word bigrams, and character 4-grams
    for typo resilience and higher paraphrase cosine similarity."""
    vec = [0.0] * dim
    raw_tokens = WORD_RE.findall(text.lower())
    content_tokens = [_stem_token(t) for t in raw_tokens if t not in STOPWORDS]
    if not content_tokens:
        content_tokens = [_stem_token(t) for t in raw_tokens] or ["<empty>"]

    weighted_features: list[tuple[str, float]] = []
    for tok in content_tokens:
        weighted_features.append((f"w:{tok}", 2.0))
        padded = f"^{tok}$"
        for i in range(max(0, len(padded) - 3)):
            weighted_features.append((f"c4:{padded[i:i+4]}", 0.45))

    for i in range(len(content_tokens) - 1):
        weighted_features.append((f"bg:{content_tokens[i]}_{content_tokens[i+1]}", 1.5))

    for feat, weight in weighted_features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

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
    if model.startswith("hybrid-"):
        try:
            dim = int(model.split("-", 1)[1])
        except ValueError:
            dim = 512
        return [hybrid_embed(t, dim=dim) for t in texts]

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
