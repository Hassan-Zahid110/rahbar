"""Stage 2: Clean. Remove artefacts without destroying structure."""

from __future__ import annotations

from collections import Counter
import re

from .models import Document, Page

LIGATURES = str.maketrans({
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u00a0": " ",
    "\u200b": "",
    "\u2013": "-",
    "\u2014": "-",
    "\u00ad": "",
})

BARE_PAGE_NUM_RE = re.compile(
    r"^\s*(?:page\s+\d+(?:\s+of\s+\d+)?|-\s*\d+\s*-|\d+\s+of\s+\d+)\s*$",
    re.IGNORECASE,
)
HEADING_GUARD_RE = re.compile(r"^(?:#{1,4}\s+|\d+(?:\.\d+)+\s+\S)")


def _normalise_margin_line(line: str) -> str:
    collapsed = " ".join(line.strip().split())
    return re.sub(r"\b\d+\b", "<NUM>", collapsed).lower()


def _find_repeating_margins(pages: list[Page]) -> set[str]:
    """Identify header/footer lines that repeat across at least half of a multi-page doc."""
    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for p in pages:
        non_empty = [ln.strip() for ln in p.text.splitlines() if ln.strip()]
        candidates = set()
        for ln in non_empty[:2] + non_empty[-2:]:
            if HEADING_GUARD_RE.match(ln) or ln.startswith("|"):
                continue
            norm = _normalise_margin_line(ln)
            if len(norm) >= 4:
                candidates.add(norm)
        for c in candidates:
            counts[c] += 1
    threshold = max(2, len(pages) // 2)
    return {norm for norm, cnt in counts.items() if cnt >= threshold}


def _clean_page_text(text: str, repeating_margins: set[str]) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(LIGATURES)
    # Rejoin words hyphenated across line breaks (e.g., "prereq-\nuisite" -> "prerequisite")
    text = re.sub(r"([A-Za-z]{2,})-\n([a-z]{2,})", r"\1\2", text)

    lines = text.splitlines()
    kept: list[str] = []
    total = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        is_margin_zone = idx < 3 or idx >= total - 3
        if is_margin_zone and BARE_PAGE_NUM_RE.match(stripped):
            continue
        if is_margin_zone and _normalise_margin_line(stripped) in repeating_margins:
            continue
        # Deliberately preserve Markdown table rows, headings, and numbered clauses (e.g. 1.21)
        if stripped.startswith("|"):
            kept.append(stripped)
        else:
            kept.append(re.sub(r"[ \t]{2,}", " ", stripped))

    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def clean(doc: Document) -> Document:
    """Strip repeating headers/footers and encoding artefacts while preserving headings,
    numbered clauses, and Markdown tables."""
    repeating = _find_repeating_margins(doc.pages)
    cleaned_pages = [
        Page(
            source=p.source,
            page=p.page,
            text=_clean_page_text(p.text, repeating),
            ocr=p.ocr,
        )
        for p in doc.pages
    ]
    return Document(
        source=doc.source,
        doc_version=doc.doc_version,
        superseded=doc.superseded,
        pages=cleaned_pages,
    )
