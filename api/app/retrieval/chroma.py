"""ChromaDB read-only retriever and embedding-pin inspector (sections 3.2 and 4.4)."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..config import Settings
from ..schemas import Passage
from .embedder import embed_query

log = logging.getLogger("rahbar.retrieval.chroma")

OLDER_VERSION_INTENT_RE = re.compile(
    r"\b(?:2019|2020|2021|2022|2023)\b|"
    r"\b(?:old|older|previous|earlier|former|prior|superseded|repealed|historical)\s+"
    r"(?:version|edition|policy|rules?|handbook|regulation)",
    re.IGNORECASE,
)


def asks_for_historical_version(question: str) -> bool:
    """Return True only when the user explicitly asks about an older/superseded policy."""
    return bool(OLDER_VERSION_INTENT_RE.search(question))


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        # chromadb.HttpClient() makes a network call in its constructor. Creating it lazily
        # keeps the API process alive (and /healthz green) while Chroma is still starting;
        # /readyz then reports the outage instead of the pod crash-looping.
        self._client: Any | None = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def inspect_index(self) -> tuple[bool, str, dict[str, object]]:
        """Verify Chroma reachability, non-empty collection, and embedding-model pin (4.3, 4.4)."""
        try:
            collection = self.client.get_collection(name=self.settings.collection)
        except Exception as exc:
            return False, f"chroma: collection {self.settings.collection!r} unavailable ({exc})", {}

        try:
            doc_count = int(collection.count())
        except Exception as exc:
            return False, f"chroma: count failed ({exc})", {}

        if doc_count <= 0:
            return False, f"chroma: collection {self.settings.collection!r} is empty (0 chunks)", {
                "chunks": 0
            }

        meta = getattr(collection, "metadata", None) or {}
        indexed_model = str(meta.get("embed_model", ""))
        indexed_dim = meta.get("dimension")

        if indexed_model != self.settings.embed_model:
            msg = (
                f"embed_model mismatch: collection {self.settings.collection!r} was indexed with "
                f"{indexed_model!r} (dimension={indexed_dim}), which does not match configured "
                f"EMBED_MODEL={self.settings.embed_model!r}"
            )
            log.error("embedding pin conflict", extra={"detail": msg})
            return False, msg, {
                "chunks": doc_count,
                "indexed_embed_model": indexed_model,
                "configured_embed_model": self.settings.embed_model,
                "dimension": indexed_dim,
            }

        return True, "ok", {
            "chunks": doc_count,
            "embed_model": indexed_model,
            "dimension": indexed_dim,
        }

    def retrieve(self, question: str, k: int, query_vector: list[float] | None = None) -> list[Passage]:
        """Embed the question with `settings.embed_model`, query top-k, exclude `superseded`
        documents unless the user explicitly asks about an older version, and convert Chroma
        cosine distance to similarity (`1 - distance`)."""
        vec = query_vector if query_vector is not None else embed_query(question, self.settings)
        collection = self.client.get_collection(name=self.settings.collection)

        meta = getattr(collection, "metadata", None) or {}
        indexed_dim = meta.get("dimension")
        if isinstance(indexed_dim, int) and indexed_dim != len(vec):
            raise RuntimeError(
                f"embedding dimension mismatch: query vector has {len(vec)} dims, "
                f"collection expects {indexed_dim}"
            )

        where_filter: dict[str, object] | None = None
        if self.settings.filter_superseded and not asks_for_historical_version(question):
            where_filter = {"superseded": False}

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [vec],
            "n_results": max(1, k),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter is not None:
            query_kwargs["where"] = where_filter

        raw = collection.query(**query_kwargs)
        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]

        passages: list[Passage] = []
        for cid, text, md, dist in zip(ids, docs, metas, dists):
            md = md or {}
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))
            raw_page = md.get("page")
            page_val = int(raw_page) if isinstance(raw_page, (int, float)) else None
            passages.append(
                Passage(
                    chunk_id=str(cid),
                    text=str(text or ""),
                    source=str(md.get("source", "unknown")),
                    section=str(md.get("section", "Overview")),
                    page=page_val,
                    score=round(similarity, 6),
                )
            )

        passages.sort(key=lambda p: p.score, reverse=True)
        return passages
