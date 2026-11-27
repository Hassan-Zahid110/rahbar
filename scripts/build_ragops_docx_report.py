"""Builds a pure black-and-white Word (.docx) document of the Assignment 03 RAGOps Report
including all tables, analytical Q&A, and the 14 embedded terminal screenshots (A1..F4),
using only Python standard library + PIL (zero external docx dependency required).
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
MD_PATH = REPO_ROOT / "docs" / "RAGOPS_REPORT.md"
SS_DIR = REPO_ROOT / "docs" / "screenshots"

SCREENSHOT_ITEMS = [
    ("A1", "Part A1 — Batch A (Clean Baseline Corpus) Verification & Indexing Report", "A1.png"),
    ("A2", "Part A2 — Second Ingestion Run on Unchanged Corpus Showing 0 Chunks Re-Embedded", "A2.png"),
    ("A3", "Part A1 & A2 — Batch B Verification Report (7 Planted Defects Quarantined + Version Update + 0-Orphan Delete)", "A3.png"),
    ("B1", "Part B (B1–B3) — Three-Level Offline Evaluation Suite Summary (Module, Component + Noise, End-to-End)", "B1.png"),
    ("B2", "Part B4 — Fixed-Seed Stochasticity Verification (Seed = 42, Run 1 vs. Run 2)", "B2.png"),
    ("C1", "Part C2 — Release Gate Failing on Degraded Candidate (Decision: FAIL, Exit Code 1)", "C1.png"),
    ("C2", "Part C2 — Release Gate Passing on Hybrid-512 + Reranker Candidate (Decision: PASS, Exit Code 0)", "C2.png"),
    ("D1", "Part D1 & D3 — Trace Summary Across 57 Traces + One Full 16-Field JSON Trace Record", "D1.png"),
    ("D2", "Part D2 & D4 — Trace CLI Rebuilding Context & Prompt + Retrieval Guardrail Stripping Prompt Injection", "D2.png"),
    ("E1", "Part E2 & E4 — Live Query Coverage & Drift Output (Before Expansion = 69.05% vs. After Adding 8 Golden Questions = 100.00%)", "E1.png"),
    ("F1", "Part F1 — Kubernetes Cluster Resources (kubectl get pods,svc,jobs,cronjobs,pvc,cm -n rahbar)", "F1.png"),
    ("F2", "Part F2 — Completed Kubernetes Ingestion Job Logs (kubectl logs job/ragops-ingest -n rahbar)", "F2.png"),
    ("F3", "Part F2 — Completed Kubernetes Evaluation & Release Gate Job Logs (kubectl logs job/eval-gate -n rahbar)", "F3.png"),
    ("F4", "Part F2 — Release Gate Result Changing to FAIL After Editing ConfigMap Threshold Without Image Rebuild", "F4.png"),
]


def _runs_from_markdown_inline(text: str, base_sz: int = 18, force_bold: bool = False) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`) into WordprocessingML <w:r> elements."""
    text = text.replace("<br/>", " / ").replace("<br>", " / ")
    tokens = re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)", text)
    runs: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        bold = force_bold
        italic = False
        font = "Times New Roman"
        sz = base_sz
        content = tok
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            bold = True
            content = tok[2:-2]
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            font = "Courier New"
            sz = max(14, base_sz - 2)
            content = tok[1:-1]
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            italic = True
            content = tok[1:-1]

        rpr = [
            f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>',
            '<w:color w:val="000000"/>',
            f'<w:sz w:val="{sz}"/>',
            f'<w:szCs w:val="{sz}"/>',
        ]
        if bold:
            rpr.append("<w:b/>")
        if italic:
            rpr.append("<w:i/>")
        runs.append(
            f'<w:r><w:rPr>{"".join(rpr)}</w:rPr><w:t xml:space="preserve">{escape(content)}</w:t></w:r>'
        )
    return "".join(runs)


def _para(text: str, sz: int = 18, bold: bool = False, space_before: int = 60, space_after: int = 80, border_bottom: bool = False) -> str:
    bdr = (
        '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>'
        if border_bottom
        else ""
    )
    ppr = f'<w:pPr><w:spacing w:before="{space_before}" w:after="{space_after}"/>{bdr}</w:pPr>'
    return f"<w:p>{ppr}{_runs_from_markdown_inline(text, base_sz=sz, force_bold=bold)}</w:p>"


def _table_xml(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    tbl_pr = """
    <w:tblPr>
      <w:tblW w:w="5000" w:type="pct"/>
      <w:tblBorders>
        <w:top w:val="single" w:sz="6" w:space="0" w:color="000000"/>
        <w:left w:val="single" w:sz="6" w:space="0" w:color="000000"/>
        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>
        <w:right w:val="single" w:sz="6" w:space="0" w:color="000000"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>
        <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>
      </w:tblBorders>
      <w:tblCellMar>
        <w:top w:w="40" w:type="dxa"/>
        <w:left w:w="80" w:type="dxa"/>
        <w:bottom w:w="40" w:type="dxa"/>
        <w:right w:w="80" w:type="dxa"/>
      </w:tblCellMar>
    </w:tblPr>
    """
    tr_list: list[str] = []
    for r_idx, row in enumerate(rows):
        is_hdr = (r_idx == 0)
        tc_list: list[str] = []
        for cell in row:
            p = f'<w:p><w:pPr><w:spacing w:before="20" w:after="20"/></w:pPr>{_runs_from_markdown_inline(cell.strip(), base_sz=15, force_bold=is_hdr)}</w:p>'
            tc_list.append(f"<w:tc><w:tcPr></w:tcPr>{p}</w:tc>")
        tr_list.append(f"<w:tr>{''.join(tc_list)}</w:tr>")
    return f"<w:tbl>{tbl_pr}{''.join(tr_list)}</w:tbl>"


def _image_para(rel_id: str, doc_pr_id: int, cx_emu: int, cy_emu: int) -> str:
    return f"""
    <w:p>
      <w:pPr><w:jc w:val="center"/><w:spacing w:before="80" w:after="120"/></w:pPr>
      <w:r>
        <w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0"
                     xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
            <wp:extent cx="{cx_emu}" cy="{cy_emu}"/>
            <wp:docPr id="{doc_pr_id}" name="Picture {doc_pr_id}"/>
            <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:nvPicPr>
                    <pic:cNvPr id="{doc_pr_id}" name="Screenshot_{doc_pr_id}.png"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="{rel_id}"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
    """


def build_docx(out_path: Path) -> None:
    md_lines = MD_PATH.read_text(encoding="utf-8").splitlines()
    body_elements: list[str] = []
    table_buffer: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_buffer
        if table_buffer:
            body_elements.append(_table_xml(table_buffer))
            body_elements.append(_para("", sz=10, space_before=10, space_after=20))
            table_buffer = []

    for line in md_lines:
        s = line.strip()
        if s.startswith("## Appendix: Terminal Screenshots"):
            flush_table()
            break
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= {":", "-", " "} for c in cells):
                continue
            table_buffer.append(cells)
            continue
        else:
            flush_table()

        if not s or s == "---":
            continue
        if s.startswith("# "):
            body_elements.append(_para(s[2:], sz=26, bold=True, space_before=40, space_after=80, border_bottom=True))
        elif s.startswith("## "):
            body_elements.append(_para(s[3:], sz=22, bold=True, space_before=140, space_after=60, border_bottom=True))
        elif s.startswith("### "):
            body_elements.append(_para(s[4:], sz=19, bold=True, space_before=100, space_after=40))
        elif s.startswith("#### "):
            body_elements.append(_para(s[5:], sz=18, bold=True, space_before=80, space_after=40))
        else:
            body_elements.append(_para(s, sz=17, bold=False, space_before=30, space_after=50))

    flush_table()

    # Add Appendix with all 14 screenshots embedded
    rels_items: list[str] = []
    media_files: list[tuple[str, Path]] = []
    max_w_emu = 6200000  # ~6.78 inches on A4

    for idx, (code, title, fname) in enumerate(SCREENSHOT_ITEMS, start=1):
        img_path = SS_DIR / fname
        if not img_path.exists():
            continue
        rel_id = f"rIdImg{idx}"
        media_name = f"media/{fname}"
        rels_items.append(
            f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{media_name}"/>'
        )
        media_files.append((f"word/{media_name}", img_path))

        with Image.open(img_path) as im:
            w_px, h_px = im.size
        cx = max_w_emu
        cy = int(max_w_emu * (h_px / max(1, w_px)))

        body_elements.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        body_elements.append(_para(f"APPENDIX SCREENSHOT {idx} OF {len(SCREENSHOT_ITEMS)} — ITEM [{code}]", sz=18, bold=True, space_before=20, space_after=20))
        body_elements.append(_para(title, sz=20, bold=True, space_before=20, space_after=80, border_bottom=True))
        body_elements.append(_image_para(rel_id, idx, cx, cy))

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {"".join(body_elements)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

    doc_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rels_items)}
</Relationships>
"""

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for arcname, fpath in media_files:
            zf.write(fpath, arcname)

    print(f"Created Word document: {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    out1 = REPO_ROOT / "docs" / "RAHBAR_Assignment_03_RAGOps_Report.docx"
    out2 = REPO_ROOT.parent / "RAHBAR_Assignment_03_RAGOps_Report.docx"
    out3 = REPO_ROOT.parent / "i243032_i243011_Assignment_03.docx"
    build_docx(out1)
    out2.write_bytes(out1.read_bytes())
    out3.write_bytes(out1.read_bytes())
    print(f"Copied to {out2} and {out3}")
