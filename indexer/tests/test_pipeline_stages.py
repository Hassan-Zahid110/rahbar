"""Unit tests for all five indexing pipeline stages (extract, clean, chunk, embed, store).

Runs completely offline with no external network, Chroma server, or LLM needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.chunk import chunk
from pipeline.clean import clean
from pipeline.config import IndexerSettings
from pipeline.embed import embed, hash_embed
from pipeline.extract import extract
from pipeline.models import Document, Page
from pipeline.store import store


class FakeCollection:
    def __init__(self, name: str, metadata: dict) -> None:
        self.name = name
        self.metadata = metadata
        self.rows: dict[str, tuple[str, list[float], dict]] = {}

    def add(self, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        for i, d, e, m in zip(ids, documents, embeddings, metadatas):
            self.rows[i] = (d, e, m)

    def upsert(self, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        self.add(ids, documents, embeddings, metadatas)

    def get(self, include: list[str] | None = None) -> dict[str, list[str]]:
        return {"ids": list(self.rows.keys())}

    def delete(self, ids: list[str]) -> None:
        for i in ids:
            self.rows.pop(i, None)

    def count(self) -> int:
        return len(self.rows)


class FakeChromaClient:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def get_collection(self, name: str) -> FakeCollection:
        if name not in self.collections:
            raise ValueError(f"missing collection {name}")
        return self.collections[name]

    def delete_collection(self, name: str) -> None:
        self.collections.pop(name, None)

    def create_collection(self, name: str, metadata: dict) -> FakeCollection:
        col = FakeCollection(name, metadata)
        self.collections[name] = col
        return col


def test_extract_html_preserves_headings_and_tables(tmp_path: Path) -> None:
    html_file = tmp_path / "fees.html"
    html_file.write_text(
        """
        <html><body>
          <nav>Ignore navigation</nav>
          <h2>1. Tuition Fee</h2>
          <p>Undergraduate tuition applies per credit hour.</p>
          <table>
            <tr><th>Programme</th><th>Fee (PKR)</th></tr>
            <tr><td>BS Computer Science</td><td>11,000</td></tr>
          </table>
          <footer>Copyright footer</footer>
        </body></html>
        """,
        encoding="utf-8",
    )
    doc = extract(str(html_file), doc_version="2026", superseded=False)
    assert len(doc.pages) == 1
    text = doc.pages[0].text
    assert "## 1. Tuition Fee" in text
    assert "| BS Computer Science | 11,000 |" in text
    assert "Ignore navigation" not in text


def test_clean_strips_repeating_headers_but_keeps_clauses() -> None:
    pages = [
        Page(
            source="handbook.pdf",
            page=i,
            text=f"FAST-NUCES Academic Handbook 2026\n{i}.1 Clause content with prereq-\nuisite rule.\nPage {i} of 10",
        )
        for i in range(1, 5)
    ]
    doc = Document(source="handbook.pdf", doc_version="2026-06", superseded=False, pages=pages)
    cleaned = clean(doc)
    for idx, p in enumerate(cleaned.pages, start=1):
        assert "FAST-NUCES Academic Handbook 2026" not in p.text
        assert f"Page {idx} of 10" not in p.text
        assert f"{idx}.1 Clause content with prerequisite rule." in p.text


def test_chunk_preserves_fixture_sections_and_metadata() -> None:
    fixture_md = Path(__file__).resolve().parents[2] / "eval" / "fixtures" / "academic-rules-2026.md"
    doc = clean(extract(str(fixture_md), doc_version="2026", superseded=False))
    chunks = chunk(doc, size=200, overlap=30)
    sections = {c.section for c in chunks}
    assert {"1. Attendance", "2. Academic warning", "3. Repeating a course"} <= sections
    for c in chunks:
        meta = c.metadata()
        assert meta["source"] == "academic-rules-2026.md"
        assert meta["doc_version"] == "2026"
        assert meta["superseded"] is False
        assert isinstance(meta["page"], int)


def test_chunk_applies_overlap_within_long_section() -> None:
    long_para_1 = " ".join(f"alpha{i}" for i in range(60)) + "."
    long_para_2 = " ".join(f"beta{i}" for i in range(60)) + "."
    doc = Document(
        source="long.md",
        doc_version="2026",
        superseded=False,
        pages=[Page(source="long.md", page=1, text=f"## 4. Long Policy\n\n{long_para_1}\n\n{long_para_2}")],
    )
    chunks = chunk(doc, size=80, overlap=15)
    assert len(chunks) >= 2
    assert "alpha59." in chunks[1].text
    assert chunks[1].section == "4. Long Policy"


def test_store_records_pin_and_removes_stale_chunks_without_emptying(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = IndexerSettings(
        embed_model="hash-64",
        chroma_host="localhost",
        chroma_port=8000,
        collection="rahbar",
        corpus_dir="/tmp",
        chunk_size=200,
        chunk_overlap=30,
        ollama_url="http://localhost:11434",
        redis_host="",
    )
    client = FakeChromaClient()
    doc1 = Document(
        source="rules.md",
        doc_version="2026",
        superseded=False,
        pages=[Page(source="rules.md", page=1, text="## 1. Rule\n\nFirst rule.\n\n## 2. Old\n\nSecond rule.")],
    )
    c1 = chunk(doc1, size=20, overlap=5)
    v1 = embed([c.text for c in c1], settings)
    assert store(c1, v1, settings, client=client) == len(c1)
    assert client.collections["rahbar"].metadata["embed_model"] == "hash-64"
    assert client.collections["rahbar"].metadata["dimension"] == 64

    # Re-index with fewer chunks; stale chunk IDs should be cleaned up while keeping pin metadata
    c2 = c1[:1]
    v2 = [hash_embed(c2[0].text, dim=64)]
    assert store(c2, v2, settings, client=client) == 1
    assert set(client.collections["rahbar"].rows.keys()) == {c2[0].id}

