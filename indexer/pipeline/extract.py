"""Stage 1: Extract. PDF, HTML, Markdown, or plain text to structured Pages."""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .models import Document, Page

MIN_TEXT_CHARS = 25


def _format_table_as_markdown(rows: list[list[str | None]]) -> str:
    """Convert a 2D table grid into a clean GitHub-flavoured Markdown table."""
    cleaned: list[list[str]] = []
    for row in rows:
        if not row:
            continue
        cells = [" ".join((cell or "").split()).replace("|", "/") for cell in row]
        if any(cells):
            cleaned.append(cells)
    if not cleaned:
        return ""
    width = max(len(r) for r in cleaned)
    if width < 2 and len(cleaned) < 2:
        return "\n".join(" ".join(r) for r in cleaned)
    padded = [r + [""] * (width - len(r)) for r in cleaned]
    header = "| " + " | ".join(padded[0]) + " |"
    divider = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join([header, divider, *body])


def _outside_bboxes(bboxes: list[tuple[float, float, float, float]]):
    """Return a pdfplumber filter predicate keeping objects outside detected table boxes."""
    def _keep(obj: dict[str, Any]) -> bool:
        ox0 = float(obj.get("x0", 0.0))
        otop = float(obj.get("top", 0.0))
        ox1 = float(obj.get("x1", ox0))
        obottom = float(obj.get("bottom", otop))
        cx = (ox0 + ox1) / 2.0
        cy = (otop + obottom) / 2.0
        for x0, top, x1, bottom in bboxes:
            if x0 <= cx <= x1 and top <= cy <= bottom:
                return False
        return True

    return _keep


def _ocr_pdf_page(path: str, page_number: int) -> str:
    """Render one 1-based PDF page via poppler and run Tesseract OCR."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(path, first_page=page_number, last_page=page_number, dpi=200)
    if not images:
        return ""
    return str(pytesseract.image_to_string(images[0], lang="eng") or "")


def _extract_pdf(path: Path, disable_ocr: bool = False) -> list[Page]:
    import pdfplumber

    pages: list[Page] = []
    with pdfplumber.open(str(path)) as pdf:
        for idx, pdf_page in enumerate(pdf.pages, start=1):
            found_tables = pdf_page.find_tables()
            bboxes = [t.bbox for t in found_tables]
            if bboxes:
                prose = pdf_page.filter(_outside_bboxes(bboxes)).extract_text(x_tolerance=2) or ""
            else:
                prose = pdf_page.extract_text(x_tolerance=2) or ""

            md_tables: list[str] = []
            for tbl in found_tables:
                raw_rows = tbl.extract()
                if raw_rows:
                    rendered = _format_table_as_markdown(raw_rows)
                    if rendered:
                        md_tables.append(rendered)

            combined = "\n\n".join(part for part in [prose.strip(), *md_tables] if part)
            used_ocr = False
            non_ws = len(re.sub(r"\s+", "", combined))
            if non_ws < MIN_TEXT_CHARS and not disable_ocr:
                ocr_text = _ocr_pdf_page(str(path), idx).strip()
                if ocr_text:
                    combined = ocr_text
                    used_ocr = True

            pages.append(Page(source=path.name, page=idx, text=combined, ocr=used_ocr))
    return pages


class _HTMLContentExtractor(HTMLParser):
    """Extract headings, paragraphs, list items, and tables from HTML pages."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}
    HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._heading_prefix: str | None = None
        self._buf: list[str] = []
        self.blocks: list[str] = []

    def _flush_buf(self) -> None:
        text = " ".join("".join(self._buf).split())
        self._buf = []
        if not text:
            return
        if self._heading_prefix:
            self.blocks.append(f"{self._heading_prefix} {text}")
            self._heading_prefix = None
        else:
            self.blocks.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if t in self.HEADING_TAGS:
            self._flush_buf()
            self._heading_prefix = self.HEADING_TAGS[t]
        elif t == "table":
            self._flush_buf()
            self._in_table = True
            self._table_rows = []
        elif t == "tr" and self._in_table:
            self._current_row = []
        elif t in ("td", "th") and self._in_table and self._current_row is not None:
            self._current_cell = []
        elif t in ("p", "div", "section", "article", "li", "br"):
            if not self._in_table:
                self._flush_buf()

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            return
        if t in self.HEADING_TAGS:
            self._flush_buf()
        elif t in ("td", "th") and self._in_table and self._current_cell is not None:
            cell_text = " ".join("".join(self._current_cell).split())
            if self._current_row is not None:
                self._current_row.append(cell_text)
            self._current_cell = None
        elif t == "tr" and self._in_table and self._current_row is not None:
            if any(self._current_row):
                self._table_rows.append(self._current_row)
            self._current_row = None
        elif t == "table" and self._in_table:
            self._in_table = False
            rendered = _format_table_as_markdown(
                [[c for c in r] for r in self._table_rows]
            )
            if rendered:
                self.blocks.append(rendered)
            self._table_rows = []
        elif t in ("p", "div", "section", "article", "li"):
            if not self._in_table:
                self._flush_buf()

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_table and self._current_cell is not None:
            self._current_cell.append(data)
        elif not self._in_table:
            self._buf.append(data)


def _extract_html(path: Path) -> list[Page]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    parser = _HTMLContentExtractor()
    parser.feed(raw)
    parser._flush_buf()
    text = "\n\n".join(parser.blocks)
    return [Page(source=path.name, page=1, text=text, ocr=False)]


def _strip_front_matter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                return "\n".join(lines[idx + 1 :]).lstrip("\n")
    return text


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page, running OCR on image-only PDF pages."""
    file_path = Path(path)
    disable_ocr = os.environ.get("DISABLE_OCR", "").strip().lower() in {"1", "true", "yes", "on"}
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        pages = _extract_pdf(file_path, disable_ocr=disable_ocr)
    elif suffix in {".html", ".htm"}:
        pages = _extract_html(file_path)
    else:
        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".md":
            raw_text = _strip_front_matter(raw_text)
        pages = [Page(source=file_path.name, page=1, text=raw_text, ocr=False)]

    return Document(
        source=file_path.name,
        doc_version=doc_version,
        superseded=superseded,
        pages=pages,
    )
