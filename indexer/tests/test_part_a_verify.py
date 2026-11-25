"""Unit tests for RAGOps Part A1 (Verification stage) & Part A2 (Incremental update)."""

from __future__ import annotations

from pathlib import Path

from pipeline.models import Document, Page
from pipeline.verify import (
    DataLakeManager,
    check_completeness,
    check_quality,
    verify_batch,
)


def test_verify_quality_catches_empty_and_garbled() -> None:
    empty_doc = Document(source="empty.md", doc_version="2026", superseded=False, pages=[])
    assert check_quality(empty_doc).status == "fail"

    garbled_doc = Document(
        source="corrupt.md",
        doc_version="2026",
        superseded=False,
        pages=[Page(source="corrupt.md", page=1, text="\ufffd\x00corrupt stream")],
    )
    assert check_quality(garbled_doc).status == "fail"


def test_verify_completeness_catches_missing_meta_and_truncation() -> None:
    no_meta = Document(
        source="nometa.md",
        doc_version="unknown",
        superseded=False,
        pages=[Page(source="nometa.md", page=1, text="Valid sentence with more than forty alphanumeric characters.")],
    )
    assert check_completeness(no_meta).status == "fail"

    truncated = Document(
        source="trunc.md",
        doc_version="2026",
        superseded=False,
        title="Truncated Doc",
        date="2026-06-01",
        page_count=1,
        pages=[Page(source="trunc.md", page=1, text="A student must complete the internship before [TRUNCATED_EOF")],
    )
    assert check_completeness(truncated).status == "fail"


def test_verify_batch_quarantines_duplicates_and_tracks_unchanged(tmp_path: Path) -> None:
    dl = DataLakeManager(str(tmp_path / "dl"))
    p1 = tmp_path / "doc1.md"
    p1.write_text("content", encoding="utf-8")
    d1 = Document(
        source="doc1.md",
        doc_version="2026",
        superseded=False,
        policy_id="pol1",
        title="Policy One",
        date="2026-06-01",
        page_count=1,
        pages=[Page(source="doc1.md", page=1, text="Students must attend at least 80 percent of lectures in every course.")],
    )
    res1, sum1 = verify_batch([(p1, d1)], dl)
    assert sum1["passed"] == 1
    assert res1[0].action == "index_new"

    # Duplicate under a different filename fails uniqueness
    p2 = tmp_path / "doc1-copy.md"
    p2.write_text("content", encoding="utf-8")
    d2 = Document(
        source="doc1-copy.md",
        doc_version="2026",
        superseded=False,
        policy_id="pol1-copy",
        title="Policy One Copy",
        date="2026-06-01",
        page_count=1,
        pages=[Page(source="doc1-copy.md", page=1, text="Students must attend at least 80 percent of lectures in every course.")],
    )
    res2, sum2 = verify_batch([(p1, d1), (p2, d2)], dl)
    assert sum2["passed"] == 1
    assert sum2["failed_quarantined"] == 1
    assert res2[1].checks["uniqueness"].status == "fail"
