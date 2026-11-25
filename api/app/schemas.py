"""The API contract (section 3.4 & RAGOps Part D)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """POST /api/ask request body. Reject <3 or >500 chars with HTTP 422 (section 4.2)."""

    question: str = Field(..., min_length=3, max_length=500)


class Citation(BaseModel):
    source: str
    section: str
    page: int | None = None


class Answer(BaseModel):
    """The schema the LLM itself must produce (section 3.4)."""

    reasoning: str = Field(
        default="",
        description="Brief check of which retrieved passage answers the question, or why none does.",
    )
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    answered_from_context: bool
    confidence: Literal["high", "medium", "low"]


class Passage(BaseModel):
    """What a Retriever returns for each top-k hit."""

    chunk_id: str
    text: str
    source: str
    section: str
    page: int | None = None
    score: float
    doc_id: str = ""
    doc_version: str = "2026"


class RetrievedRef(BaseModel):
    """Metadata of a retrieved chunk, echoed in AskResponse for observability."""

    chunk_id: str
    source: str
    section: str
    page: int | None = None
    score: float
    doc_id: str = ""
    doc_version: str = "2026"


class AskResponse(BaseModel):
    """POST /api/ask response body."""

    request_id: str
    answer: str
    citations: list[Citation]
    answered_from_context: bool
    confidence: Literal["high", "medium", "low"]
    retrieved: list[RetrievedRef]
    provider: str
    cached: bool = False
