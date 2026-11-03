"""Stage 3: Chunk. Structure-aware splitting (sections -> paragraphs -> sentences) with overlap."""

from __future__ import annotations

import os
import re

from .models import Chunk, Document

MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
NUMBERED_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+){0,2})\s+([A-Z][A-Za-z0-9 ,/&()'\"-]{2,75})$"
)
NAMED_SECTION_RE = re.compile(
    r"^((?:Section|Chapter|Part|Article|Appendix|Policy)\s+[A-Z0-9.\-]+[:.\s]+[A-Za-z0-9 ,/&()'\"-]{2,75})$",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "doc"


def _detect_heading(line: str) -> tuple[int, str] | None:
    """Return (level, title) if `line` is a structural heading, else None.

    Deliberately distinguishes genuine short section titles (e.g. `5.4 Academic Warning`
    or `## 1. Attendance`) from prose clauses (`1.1 A student must attend...`).
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("|"):
        return None
    md = MD_HEADING_RE.match(stripped)
    if md:
        return (len(md.group(1)), md.group(2).strip())

    # Prose sentences end with a full stop and are not standalone headings
    if stripped.endswith(".") or len(stripped) > 85:
        return None

    num = NUMBERED_HEADING_RE.match(stripped)
    if num:
        words = num.group(2).split()
        # Avoid matching ordinary sentences that lack a final period
        if 1 <= len(words) <= 10:
            return (2, f"{num.group(1)} {num.group(2).strip()}")

    named = NAMED_SECTION_RE.match(stripped)
    if named:
        return (2, named.group(1).strip())

    return None


def _token_count(text: str) -> int:
    return len(text.split())


def _tail_tokens(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    tokens = text.split()
    if not tokens:
        return ""
    return " ".join(tokens[-overlap:])


def _split_oversized_paragraph(paragraph: str, size: int) -> list[str]:
    """Split a paragraph larger than `size` tokens along sentence boundaries first,
    falling back to token windows only when a single sentence exceeds `size`."""
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
    units: list[str] = []
    cur: list[str] = []
    cur_tokens = 0

    for sent in sentences:
        stoks = _token_count(sent)
        if stoks > size:
            if cur:
                units.append(" ".join(cur))
                cur, cur_tokens = [], 0
            words = sent.split()
            for start in range(0, len(words), size):
                units.append(" ".join(words[start : start + size]))
            continue
        if cur and cur_tokens + stoks > size:
            units.append(" ".join(cur))
            cur = [sent]
            cur_tokens = stoks
        else:
            cur.append(sent)
            cur_tokens += stoks
    if cur:
        units.append(" ".join(cur))
    return units


def _fixed_window_chunks(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Pure fixed-size token chunker (used only when CHUNK_STRATEGY=fixed for Stage B analysis)."""
    step = max(1, size - max(0, overlap))
    doc_slug = _slug(doc.source)
    out: list[Chunk] = []
    idx = 0
    for page in doc.pages:
        words = page.text.split()
        for start in range(0, len(words), step):
            piece = " ".join(words[start : start + size]).strip()
            if not piece:
                continue
            idx += 1
            out.append(
                Chunk(
                    id=f"{doc_slug}-{doc.doc_version}-{idx:04d}",
                    text=piece,
                    source=doc.source,
                    section="Fixed Window",
                    page=page.page,
                    doc_version=doc.doc_version,
                    superseded=doc.superseded,
                )
            )
            if start + size >= len(words):
                break
    return out


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Structure-aware chunker: sections -> paragraphs -> sentences, under `size` tokens
    with `overlap` tokens shared between consecutive chunks in a section."""
    size = max(16, size)
    overlap = max(0, min(overlap, size // 2))

    strategy = os.environ.get("CHUNK_STRATEGY", "structure").strip().lower()
    if strategy == "fixed":
        return _fixed_window_chunks(doc, size, overlap)

    # 1. Group content into section blocks across pages while tracking starting page numbers
    sections: list[tuple[str, list[tuple[int, str]]]] = []
    current_section = "Overview"
    current_paras: list[tuple[int, str]] = []

    for page in doc.pages:
        if not page.text.strip():
            continue
        para_lines: list[str] = []

        def flush_para(pnum: int) -> None:
            if not para_lines:
                return
            joined = "\n".join(para_lines).strip()
            para_lines.clear()
            if joined:
                current_paras.append((pnum, joined))

        for line in page.text.splitlines():
            heading = _detect_heading(line)
            if heading is not None:
                level, title = heading
                flush_para(page.page)
                if level == 1 and current_section == "Overview" and not current_paras:
                    current_section = title
                else:
                    if current_paras:
                        sections.append((current_section, current_paras))
                        current_paras = []
                    current_section = title
                continue

            if not line.strip():
                flush_para(page.page)
            else:
                para_lines.append(line)

        flush_para(page.page)

    if current_paras:
        sections.append((current_section, current_paras))

    # 2. Pack paragraphs under `size` tokens per section with neighbour `overlap`
    doc_slug = _slug(doc.source)
    chunks: list[Chunk] = []
    chunk_idx = 0

    for sec_title, paras in sections:
        atomic_units: list[tuple[int, str]] = []
        for pnum, para in paras:
            if _token_count(para) <= size:
                atomic_units.append((pnum, para))
            else:
                for piece in _split_oversized_paragraph(para, size):
                    atomic_units.append((pnum, piece))

        buf: list[str] = []
        buf_tokens = 0
        buf_page = atomic_units[0][0] if atomic_units else 1
        prev_tail = ""

        def emit_chunk(body_parts: list[str], page_no: int, prefix_overlap: str) -> str:
            nonlocal chunk_idx
            raw_body = "\n\n".join(body_parts).strip()
            full_body = f"{prefix_overlap} {raw_body}".strip() if prefix_overlap else raw_body
            # Include section header context if not already present so embeddings retain topic context
            if sec_title and sec_title.lower() not in full_body[:120].lower():
                final_text = f"[{sec_title}]\n{full_body}"
            else:
                final_text = full_body
            chunk_idx += 1
            chunks.append(
                Chunk(
                    id=f"{doc_slug}-{doc.doc_version}-{chunk_idx:04d}",
                    text=final_text,
                    source=doc.source,
                    section=sec_title,
                    page=page_no,
                    doc_version=doc.doc_version,
                    superseded=doc.superseded,
                )
            )
            return _tail_tokens(raw_body, overlap)

        for pnum, unit in atomic_units:
            utoks = _token_count(unit)
            overlap_toks = _token_count(prev_tail) if not buf and prev_tail else 0
            if buf and (buf_tokens + utoks > size):
                prev_tail = emit_chunk(buf, buf_page, prev_tail)
                buf = [unit]
                buf_tokens = utoks + _token_count(prev_tail)
                buf_page = pnum
            else:
                if not buf:
                    buf_page = pnum
                    buf_tokens = overlap_toks
                buf.append(unit)
                buf_tokens += utoks

        if buf:
            emit_chunk(buf, buf_page, prev_tail)

    return chunks
