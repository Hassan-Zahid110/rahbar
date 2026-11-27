# ruff: noqa: E402
"""Builds the 8-page Assignment 03 RAGOps Report HTML + Appendix with all 14 uncropped terminal screenshots."""

from __future__ import annotations

import base64
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_report_assets import generate_all_screenshots


def _img_data_uri(path_str: str) -> str:
    raw = Path(path_str).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_html() -> str:
    screenshots = generate_all_screenshots()

    appendix_pages_html: list[str] = []
    for idx, item in enumerate(screenshots, start=1):
        uri = _img_data_uri(item["path"])
        appendix_pages_html.append(f"""
        <div class="page appendix-page">
          <div class="app-hdr">
            <span class="badge">APPENDIX SCREENSHOT {idx} OF {len(screenshots)} — ITEM [{item['code']}]</span>
            <span class="app-title">{item['title']}</span>
          </div>
          <div class="ss-wrap">
            <img src="{uri}" alt="{item['code']}" class="ss-img" />
          </div>
          <div class="ftr">
            <span>CS4032 Software Construction &amp; Development — Assignment 03 (RAGOps) Appendix (Does Not Count Towards 8-Page Report Limit)</span>
            <span>Appendix A-{idx} [{item['code']}]</span>
          </div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Assignment 03 — RAGOps Technical Report (Hassan Zahid i243011 &amp; Faisal Memon i243032)</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 0;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: "Times New Roman", Times, Georgia, serif;
    font-size: 7.5pt;
    line-height: 1.18;
    color: #000000;
    background: #ffffff;
  }}
  .page {{
    width: 210mm;
    height: 296.5mm;
    padding: 7mm 11mm 6.5mm 11mm;
    position: relative;
    page-break-after: always;
    break-after: page;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #ffffff;
  }}
  .page:last-child {{
    page-break-after: auto;
    break-after: auto;
  }}
  .content {{
    flex: 1;
  }}
  .banner {{
    background: #ffffff;
    color: #000000;
    padding: 6px 0 6px 0;
    border-bottom: 2px solid #000000;
    margin-bottom: 6px;
  }}
  .banner h1 {{
    font-size: 12.5pt;
    font-weight: 700;
    color: #000000;
    margin-bottom: 2px;
  }}
  .banner .sub {{
    font-size: 8.2pt;
    color: #000000;
  }}
  .meta-bar {{
    display: flex;
    justify-content: space-between;
    background: #ffffff;
    border: 1px solid #000000;
    padding: 5px 8px;
    margin-bottom: 6px;
    font-size: 8pt;
    color: #000000;
  }}
  h2 {{
    font-size: 9.6pt;
    font-weight: 700;
    color: #000000;
    border-bottom: 1px solid #000000;
    padding-bottom: 1.5px;
    margin: 4px 0 3px 0;
    text-transform: uppercase;
  }}
  h3 {{
    font-size: 8.6pt;
    font-weight: 700;
    color: #000000;
    margin: 4px 0 2px 0;
  }}
  p {{
    margin-bottom: 3.5px;
    text-align: justify;
    color: #000000;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 2px 0 3.5px 0;
    font-size: 6.85pt;
    color: #000000;
    background: #ffffff;
  }}
  th, td {{
    border: 1px solid #000000;
    padding: 1.6px 3.6px;
    text-align: left;
    vertical-align: top;
    color: #000000;
    background: #ffffff;
  }}
  th {{
    background: #ffffff;
    color: #000000;
    font-weight: 700;
    border-bottom: 1.5px solid #000000;
  }}
  tr:nth-child(even) td {{
    background: #ffffff;
  }}
  code {{
    font-family: "Menlo", "Monaco", "Consolas", monospace;
    font-size: 6.7pt;
    background: transparent;
    padding: 0;
    color: #000000;
  }}
  .pass, .fail, .warn {{
    color: #000000;
    font-weight: 700;
    background: #ffffff !important;
  }}
  .callout {{
    background: #ffffff;
    border: 1px solid #000000;
    padding: 4px 7px;
    margin: 4px 0;
    font-size: 7.5pt;
    color: #000000;
  }}
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }}
  .ftr {{
    border-top: 1px solid #000000;
    padding-top: 2.5px;
    font-size: 7.2pt;
    color: #000000;
    display: flex;
    justify-content: space-between;
  }}
  .qa-box {{
    background: #ffffff;
    border: 1px solid #000000;
    padding: 2.5px 5.5px;
    margin-bottom: 2.8px;
    color: #000000;
  }}
  .qa-q {{
    font-weight: 700;
    color: #000000;
    margin-bottom: 1.5px;
  }}
  .appendix-page {{
    background: #ffffff;
  }}
  .app-hdr {{
    background: #ffffff;
    color: #000000;
    padding: 5px 0;
    border-bottom: 1.5px solid #000000;
    margin-bottom: 6px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .badge {{
    font-size: 7.5pt;
    font-weight: 700;
    color: #000000;
  }}
  .app-title {{
    font-size: 9.2pt;
    font-weight: 700;
    color: #000000;
  }}
  .ss-wrap {{
    flex: 1;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    overflow: hidden;
    background: #ffffff;
    border: 1px solid #000000;
    padding: 4px;
  }}
  .ss-img {{
    max-width: 100%;
    max-height: 252mm;
    width: auto;
    height: auto;
    object-fit: contain;
  }}
</style>
</head>
<body>

<!-- ==================== PAGE 1 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <div class="banner">
      <h1>RAHBAR-RAGOps: Operating &amp; Managing a Grounded RAG Pipeline on Kubernetes</h1>
      <div class="sub">CS4032 Software Construction &amp; Development (Fall 2026) — Assignment 03 Technical Report | FAST-NUCES Islamabad</div>
    </div>
    <div class="meta-bar">
      <div><strong>Member 1:</strong> Hassan Zahid (Roll No: <code>i243011</code> | GitHub: <code>Hassan-Zahid110</code>)</div>
      <div><strong>Member 2:</strong> Faisal Memon (Roll No: <code>i243032</code> | GitHub: <code>faisalmemon353</code>)</div>
      <div><strong>Repository:</strong> <code>https://github.com/Hassan-Zahid110/rahbar</code></div>
    </div>

    <p><strong>Executive Summary:</strong> Building upon our Assignment 02 <em>RAHBAR</em> system, we operationalize the dual-lifecycle <strong>RAGOps architecture</strong> defined by Xu et al. (2026). While conventional LLMOps treats model weights as the primary artifact, RAG systems depend on an intertwined <strong>Query Processing Pipeline Lifecycle</strong> and <strong>Data Management Lifecycle</strong>. We implement automated four-check pre-chunking data verification with quarantine routing, zero-chunk incremental updates with version archival/rollback, a three-level offline testing platform (Module, Component with noise stress-testing, and End-to-End with hand-labeled judge calibration), a ConfigMap-driven release gate on Kubernetes, 16-field per-query JSON tracing with prompt reconstruction, and continuous live-query coverage &amp; drift monitoring.</p>

    <h2>1. Mapping Paper Figure 3 (Intertwined RAGOps Lifecycles) to RAHBAR Implementation</h2>
    <table>
      <thead>
        <tr>
          <th style="width:17%">Figure 3 Stage</th>
          <th style="width:41%">What Our RAHBAR-RAGOps Pipeline Does</th>
          <th style="width:24%">Implementing File(s)</th>
          <th style="width:18%">What Is Missing / Future Work</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Ingest</strong><br/>(Data Lifecycle 4.2.1)</td>
          <td>Discovers Markdown, HTML, and digital/scanned PDF documents; parses YAML frontmatter metadata (<code>source</code>, <code>title</code>, <code>policy_id</code>, <code>doc_version</code>, <code>date</code>, <code>page_count</code>); extracts text via <code>pdfplumber</code> with automatic 200-DPI <code>pytesseract</code> OCR fallback when non-whitespace chars &lt; 25.</td>
          <td><code>indexer/pipeline/extract.py</code><br/><code>indexer/pipeline/fetch_corpus.py</code><br/><code>k8s/ingest-job.yaml</code></td>
          <td>Real-time Change Data Capture (CDC) webhooks and multi-modal audio/video ingestion streams.</td>
        </tr>
        <tr>
          <td><strong>2. Verify</strong><br/>(Data Lifecycle 4.2.2)</td>
          <td>Runs after extraction and before chunking. Evaluates 4 checks per document: <strong>Quality</strong> (empty/garbled bytes ratio), <strong>Completeness</strong> (mandatory metadata &amp; truncation markers), <strong>Recency</strong> (stale vs. newer policy version), and <strong>Uniqueness</strong> (SHA-256 exact hash + <code>hash-384</code> cosine near-duplicate &ge; 0.90). Moves failed files to <code>/data/quarantine/</code> and writes per-run JSON reports.</td>
          <td><code>indexer/pipeline/verify.py</code><br/><code>eval/results/part_a_batch_b_report.json</code></td>
          <td>Semantic contradiction detection across distinct policy families and pre-index adversarial prompt-injection classification (Paper Sec. 8).</td>
        </tr>
        <tr>
          <td><strong>3. Update Data Lake</strong><br/>(Data Lifecycle 4.2.3)</td>
          <td>Maintains versioned document state in <code>/data/data_lake/manifest_state.json</code> on a Kubernetes PersistentVolumeClaim (<code>ragops-data-pvc</code>). Copies superseded versions (e.g., <code>academic-rules-2026.md</code> when <code>2027</code> arrives) into <code>/data/archive/</code> rather than deleting them, enabling one-command version rollback.</td>
          <td><code>indexer/pipeline/verify.py</code> (<code>DataLakeManager</code>)<br/><code>indexer/pipeline/run.py</code></td>
          <td>Fine-grained RBAC document-level ACLs and cryptographic ledger signing for regulatory audits.</td>
        </tr>
        <tr>
          <td><strong>4. Update Retrieval Sources</strong><br/>(Data Lifecycle 4.2.4)</td>
          <td>Performs incremental vector store updates in ChromaDB: unchanged documents embed <strong>0 chunks</strong>; modified documents delete and re-upsert only their own chunks; deleted documents remove all chunks leaving <strong>0 orphans</strong>; superseded versions flip metadata <code>superseded: true</code> and bump Redis cache generation key.</td>
          <td><code>indexer/pipeline/store.py</code> (<code>store_incremental</code>)<br/><code>indexer/pipeline/chunk.py</code><br/><code>indexer/pipeline/embed.py</code></td>
          <td>Knowledge-graph entity-relation index synchronization alongside HNSW vector storage.</td>
        </tr>
        <tr>
          <td><strong>5. Offline Testing</strong><br/>(Pipeline &amp; Data 4.2.5)</td>
          <td>Executes a 3-level evaluation suite over <code>eval/golden.jsonl</code> (28 questions): <strong>Module level</strong> (16 paraphrase vs. 16 unrelated pairs, ms/chunk, determinism), <strong>Component level</strong> (<code>recall@3</code>, <code>recall@5</code>, <code>MRR</code>, <code>nDCG@5</code> + distractor docs &amp; query typo noise test), <strong>End-to-End level</strong> (faithfulness, abstention, citation validity, p50/p95 latency, judge vs. 10 hand labels), and 2-run fixed-seed stochasticity check.</td>
          <td><code>eval/run_ragops_suite.py</code><br/><code>eval/golden.jsonl</code><br/><code>eval/release_gate.py</code><br/><code>k8s/eval-job.yaml</code></td>
          <td>Automated multi-turn conversational dialogue trajectory simulation and public BEIR cross-domain benchmarking.</td>
        </tr>
        <tr>
          <td><strong>6. Live Testing &amp; Release</strong><br/>(Pipeline Lifecycle 4.1d-f, 4.2.6)</td>
          <td>Deploys candidate pipeline as an isolated Kubernetes Deployment (<code>api-candidate</code>, Service <code>api-candidate</code>, collection <code>rahbar_candidate</code>). Runs <code>job/eval-gate</code> against ConfigMap thresholds (<code>rahbar-gate-config</code>). Promotes passing candidate via zero-downtime rolling update (<code>maxUnavailable: 0</code>) and reverses bad releases via <code>kubectl rollout undo</code>.</td>
          <td><code>k8s/candidate-deployment.yaml</code><br/><code>k8s/eval-job.yaml</code><br/><code>k8s/base/api-deployment.yaml</code></td>
          <td>Automated traffic-splitting canary / shadow proxy mirroring live HTTP requests to both deployments simultaneously.</td>
        </tr>
        <tr>
          <td><strong>7. Operate, Monitor &amp; Check Coverage</strong><br/>(Lifecycle 4.1f-g, 4.2.7)</td>
          <td>Emits 16-field JSON trace line per query to stdout &amp; <code>/data/traces/traces.jsonl</code>; reconstructs exact prompts via CLI (<code>trace_tool.py</code>); exposes Prometheus <code>/metrics</code>; summarizes stage latencies, similarity quantiles &amp; guardrail actions; checks live query coverage against the golden set (&ge; 85% gate) and clusters uncovered queries to expand the golden set.</td>
          <td><code>api/app/services/trace.py</code><br/><code>api/app/services/guardrail.py</code><br/><code>scripts/trace_tool.py</code><br/><code>scripts/summarize_traces.py</code><br/><code>eval/check_coverage.py</code></td>
          <td>Real-time UMAP/t-SNE visual dashboard for live query drift alerts and active human-in-the-loop expert annotation UI.</td>
        </tr>
      </tbody>
    </table>

    <div class="callout">
      <strong>Architectural Alignment Note:</strong> In exact accordance with Figure 3 of Xu et al. (2026), our Kubernetes cluster enforces a strict read/write boundary: <strong>Jobs</strong> (<code>job/ragops-ingest</code>, <code>cronjob/reindex</code>) execute the Data Management Lifecycle and are the sole writers to ChromaDB and the Data Lake PVC, while stateless horizontally-scaled <strong>Deployments</strong> (<code>deployment/api</code>, <code>deployment/api-candidate</code>) execute the Query Pipeline Lifecycle and are gated by <code>job/eval-gate</code>.
    </div>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 1 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 2 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h2>2. RAG System Quality Attributes (Paper Section 5.1 &amp; Table 2)</h2>
    <table>
      <thead>
        <tr>
          <th style="width:14%">Quality (Table 2)</th>
          <th style="width:28%">Operational Design Consideration &amp; What We Measure</th>
          <th style="width:20%">Configured Threshold / Target</th>
          <th style="width:38%">Empirical Evidence from Our Pipeline &amp; Kubernetes Cluster Runs</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Adaptability</strong></td>
          <td><em>Data structure construction &amp; granularity configuration:</em> Incremental ingestion speed, 0-chunk re-embedding on unchanged files, configurable chunk size/overlap &amp; pluggable embedding models (<code>hash-384</code> vs. <code>hybrid-512</code>).</td>
          <td>Unchanged re-run: <code>0</code> chunks embedded; New version swap &lt; <code>2.0s</code>; Zero orphan chunks on delete.</td>
          <td>Re-running Batch A embedded <strong>0 chunks</strong> (6/6 skipped in 0.04s). Ingesting Batch B automatically archived <code>academic-rules-2026.md</code> and promoted <code>academic-rules-2027.md</code> (12 chunks embedded). Deleting <code>course-registration-add-drop-2026.md</code> left <strong>0 orphan chunks</strong>.</td>
        </tr>
        <tr>
          <td><strong>2. Monitorability</strong></td>
          <td><em>Performance degradation &amp; data source change detection:</em> Automated 3-level regression suite, live query coverage ratio against golden set, and data drift deltas across batches.</td>
          <td><code>Recall@5</code> drop &le; <code>0.02</code> (2 pts); Live query coverage &ge; <code>85.0%</code> (sim &ge; 0.42).</td>
          <td>Release gate caught degraded Candidate 1 (<code>Recall@5</code> dropped by <code>0.1818</code> to <code>0.7273</code>, exit code 1). Coverage monitor flagged live query coverage gap at <strong>69.05%</strong> (29/42, exit code 1) and verified recovery to <strong>100.00%</strong> (42/42) after adding 8 golden questions.</td>
        </tr>
        <tr>
          <td><strong>3. Observability</strong></td>
          <td><em>Retrieval injection attack detection &amp; relevance; Generation context adherence &amp; usefulness:</em> Top-1 similarity quantiles, per-stage p50/p95 latencies, abstention rate, and guardrail injection counters.</td>
          <td>Abstention correctness = <code>100%</code>; Faithfulness &ge; <code>85%</code>; All injection payloads stripped &amp; logged.</td>
          <td>Across 57 trace records: Top-1 similarity median = <code>0.3431</code> (p95 = <code>0.5664</code>, max = <code>0.5960</code>); Abstention correctness = <strong>100.0%</strong> (6/6); Faithfulness = <strong>100.0%</strong> on candidate; Retrieval guardrail stripped &amp; logged injected instruction in <code>exam-conduct-injected-2026.md</code> chunk <code>0003</code>.</td>
        </tr>
        <tr>
          <td><strong>4. Traceability</strong></td>
          <td><em>Versioning, retrieval routing &amp; grounded source reconstruction:</em> 16-field JSON trace per request linking <code>trace_id</code> to <code>doc_id</code>, <code>doc_version</code>, <code>embedding_version</code>, <code>collection_version</code>, <code>reranked_order</code>, and <code>prompt_hash</code>.</td>
          <td>100% of queries emit a complete 16-field JSON trace; CLI rebuilds exact prompt &amp; diagnoses root cause from trace alone.</td>
          <td>Every query writes to stdout &amp; <code>/data/traces/traces.jsonl</code>. <code>scripts/trace_tool.py</code> reconstructed the exact prompt for <code>trace_id=57ac8831...</code>. Part D5 diagnosed false abstention on <code>trace_id=d362986a...</code> (<code>top_score=0.1967 &lt; floor=0.22</code>) using only its trace.</td>
        </tr>
        <tr>
          <td><strong>5. Reliability</strong></td>
          <td><em>Resource usage, bandwidth &amp; fault isolation:</em> Liveness/readiness probes, embedding pin mismatch guard, PVC persistence, zero-downtime rolling updates (<code>maxUnavailable: 0</code>), and 1-command rollback.</td>
          <td>p95 E2E latency &le; <code>2500 ms</code>; Pod memory within limits; 0 failed requests during rollout/undo.</td>
          <td>Measured pod resources: API <code>18m</code> CPU / <code>84Mi</code> RAM (limit <code>500m</code>/<code>512Mi</code>); Chroma <code>24m</code>/<code>162Mi</code>; Redis <code>6m</code>/<code>14Mi</code>. <code>kubectl rollout undo deployment/api</code> restored <code>collection=rahbar</code> &amp; <code>embed=hash-384</code> in 11s with 0 dropped requests.</td>
        </tr>
      </tbody>
    </table>

    <h2>3. Experimental Results (Parts A to F) &amp; Part C Release Decision</h2>
    <h3>3.1 Part A Results: Data Verification Stage (A1) &amp; Incremental Update Lifecycle (A2)</h3>
    <p>We ingested <strong>Batch A</strong> (6 clean baseline policy documents: 20 chunks) followed by an unchanged re-run of Batch A, and then <strong>Batch B</strong> (11 documents containing 7 planted defects, 1 newer policy version <code>academic-rules-2027.md</code>, 1 document with an injected instruction, and 2 valid new documents).</p>

    <table>
      <thead>
        <tr>
          <th>Batch B Document (11 Total)</th>
          <th>Planted Condition / Role</th>
          <th>Qual</th>
          <th>Comp</th>
          <th>Recn</th>
          <th>Uniq</th>
          <th>Overall</th>
          <th>Pipeline Action &amp; Verification Reason</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code>fees-2026-copy1.md</code></td>
          <td>Exact Duplicate #1</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>exact_duplicate_hash</code> matches active <code>fees-2026.md</code></td>
        </tr>
        <tr>
          <td><code>grading-policy-2026-dup.md</code></td>
          <td>Exact Duplicate #2</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>exact_duplicate_hash</code> matches active <code>grading-policy-2026.md</code></td>
        </tr>
        <tr>
          <td><code>library-rules-rephrased-2026.md</code></td>
          <td>Near-Duplicate (Paraphrased)</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>near_duplicate_embedding</code> cosine_sim = <code>0.9879 &ge; 0.90</code> with <code>library-and-lab-rules-2026.md</code></td>
        </tr>
        <tr>
          <td><code>internship-policy-truncated.md</code></td>
          <td>Truncated Stream File</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>text_truncated</code> detected marker <code>'[TRUNCATED_EOF'</code></td>
        </tr>
        <tr>
          <td><code>corrupt-binary-dump.md</code></td>
          <td>Corrupt / Garbled Extraction</td>
          <td class="fail">FAIL</td>
          <td class="fail">FAIL</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>garbled_or_corrupt_extraction</code> (null/replacement bytes <code>\ufffd\x00</code>)</td>
        </tr>
        <tr>
          <td><code>disciplinary-committee-nometa.md</code></td>
          <td>Missing Required Metadata</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>missing_required_metadata</code> missing <code>['title', 'doc_version/date', 'page_count']</code></td>
        </tr>
        <tr>
          <td><code>academic-rules-2023-stale.md</code></td>
          <td>Stale / Older Policy Version</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td class="pass">PASS</td>
          <td class="fail">FAIL</td>
          <td><strong>Quarantined:</strong> <code>stale_version</code> incoming <code>v2023 &lt; active v2026</code> for <code>academic-rules</code></td>
        </tr>
        <tr>
          <td><code>academic-rules-2027.md</code></td>
          <td>Newer Version of Existing Doc</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td><strong>Supersede &amp; Index (5 chunks):</strong> <code>v2027</code> archives <code>academic-rules-2026.md</code> to <code>/data/archive/</code> &amp; marks it <code>superseded=True</code></td>
        </tr>
        <tr>
          <td><code>exam-conduct-injected-2026.md</code></td>
          <td>Contains Injected Instruction</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td><strong>Index New (3 chunks):</strong> Passes A1 structural verification; caught &amp; sanitized by Part D4 Retrieval Guardrail</td>
        </tr>
        <tr>
          <td><code>graduation-and-medals-2026.md</code></td>
          <td>Clean New Policy Document</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td><strong>Index New (2 chunks):</strong> All 4 verification checks passed</td>
        </tr>
        <tr>
          <td><code>course-registration-add-drop-2026.md</code></td>
          <td>Clean New Policy Document</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
          <td><strong>Index New (2 chunks):</strong> All 4 verification checks passed</td>
        </tr>
      </tbody>
    </table>

    <table>
      <thead>
        <tr>
          <th>Part A2 Incremental Operation</th>
          <th>Docs Processed</th>
          <th>Unchanged Skipped</th>
          <th>Chunks Embedded</th>
          <th>Chunks Deleted</th>
          <th>Orphan Chunks</th>
          <th>Total Store Chunks &amp; Verification Proof</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Initial Batch A Ingestion</strong></td>
          <td>6 passed, 0 failed</td>
          <td>0</td>
          <td><strong>20</strong></td>
          <td>0</td>
          <td>0</td>
          <td><code>20</code> active chunks across 6 baseline documents</td>
        </tr>
        <tr>
          <td><strong>2. Unchanged Batch A Re-run</strong></td>
          <td>6 passed, 0 failed</td>
          <td><strong>6 / 6</strong></td>
          <td class="pass"><strong>0</strong></td>
          <td>0</td>
          <td>0</td>
          <td><code>20</code> chunks (SHA-256 match in <code>manifest_state.json</code>; <strong>0 embeddings computed</strong>)</td>
        </tr>
        <tr>
          <td><strong>3. Batch B Incremental Ingestion</strong></td>
          <td>4 passed, 7 quarantined</td>
          <td>0</td>
          <td><strong>12</strong></td>
          <td>0</td>
          <td>0</td>
          <td><code>32</code> total chunks (<code>27</code> active + <code>5</code> archived/superseded for <code>academic-rules-2026.md</code>)</td>
        </tr>
        <tr>
          <td><strong>4. Single Modified Document</strong> (<code>library-and-lab-rules-2026.md</code>)</td>
          <td>1 updated</td>
          <td>0</td>
          <td><strong>3</strong></td>
          <td><strong>3</strong></td>
          <td>0</td>
          <td><code>32</code> total chunks (replaced only its own 3 chunks; other 9 documents untouched)</td>
        </tr>
        <tr>
          <td><strong>5. Deleted Document Proof</strong> (<code>course-registration-add-drop-2026.md</code>)</td>
          <td>1 deleted</td>
          <td>—</td>
          <td><strong>0</strong></td>
          <td><strong>2</strong></td>
          <td class="pass"><strong>0</strong></td>
          <td><code>30</code> total chunks (<code>chunks_before=2, deleted=2, orphan_chunks_remaining=0</code>)</td>
        </tr>
        <tr>
          <td><strong>6. Superseded Rollback Demo</strong> (<code>--restore-version academic-rules 2026</code>)</td>
          <td>2 versions toggled</td>
          <td>—</td>
          <td><strong>0</strong></td>
          <td>0</td>
          <td>0</td>
          <td>Restores <code>academic-rules-2026.md</code> (5 chunks) to <code>superseded=False</code> and demotes <code>2027</code> (5 chunks) to <code>superseded=True</code></td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 2 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 3 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h3>3.2 Part B Results: Three-Level Offline Testing Suite (Paper Section 4.2.5 &amp; Table 1)</h3>
    <p>Our single-command test harness (<code>python -m eval.run_ragops_suite</code>) evaluates the pipeline across all three levels defined in Table 1 of Xu et al. (2026) over <code>eval/golden.jsonl</code> (<strong>28 questions</strong>: 16 standard answerable, 6 hard [paraphrased, multi-chunk synthesis, or Batch B version/adversarial], and 6 unanswerable must-abstain queries; <strong>14 written by hand</strong> by the group [<code>origin="human"</code>] and <strong>14 synthetic questions all reviewed by hand</strong> [<code>reviewed_by_hand=true</code>]).</p>

    <div class="grid-2">
      <div>
        <h3>Level 1: Module Level (Embedding Quality &amp; Determinism)</h3>
        <table>
          <thead>
            <tr>
              <th>Module-Level Metric</th>
              <th>Baseline (<code>hash-384</code>)</th>
              <th>Candidate (<code>hybrid-512</code>)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Paraphrase Pairs (n = 16) Mean Cosine Sim</td>
              <td><code>0.1927</code></td>
              <td class="pass"><code>0.3641</code> (+88.9%)</td>
            </tr>
            <tr>
              <td>Unrelated Pairs (n = 16) Mean Cosine Sim</td>
              <td><code>0.0866</code></td>
              <td class="pass"><code>0.0246</code> (-71.6%)</td>
            </tr>
            <tr>
              <td><strong>Paraphrase vs. Unrelated Similarity Gap</strong></td>
              <td><code>+0.1061</code></td>
              <td class="pass"><strong><code>+0.3395</code> (+3.20x)</strong></td>
            </tr>
            <tr>
              <td>Embedding Generation Time per Chunk</td>
              <td><code>0.0553 ms</code></td>
              <td><code>0.1729 ms</code></td>
            </tr>
            <tr>
              <td>Determinism (Max Diff Across 2 Embed Runs)</td>
              <td class="pass"><code>0.00000000</code></td>
              <td class="pass"><code>0.00000000</code></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div>
        <h3>Golden Set Composition (<code>eval/golden.jsonl</code>)</h3>
        <table>
          <thead>
            <tr>
              <th>Category / Origin Dimension</th>
              <th>Required</th>
              <th>Actual</th>
              <th>Verification Details</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Total Golden Questions</td>
              <td>&ge; 25</td>
              <td class="pass"><strong>28</strong> (36 in E4)</td>
              <td><code>g01</code>..<code>g28</code> (+ <code>g29</code>..<code>g36</code> in Part E4)</td>
            </tr>
            <tr>
              <td>Answerable (with Doc, Section, Page)</td>
              <td>&ge; 15</td>
              <td class="pass"><strong>22</strong> (16 std + 6 hard)</td>
              <td>Every item specifies ground-truth doc &amp; page</td>
            </tr>
            <tr>
              <td>Unanswerable (Must Abstain)</td>
              <td>&ge; 5</td>
              <td class="pass"><strong>6</strong></td>
              <td>Hostel, shuttle, Erasmus, cafeteria, car loan, pool</td>
            </tr>
            <tr>
              <td>Hard (Paraphrased / Multi-Chunk / Batch B)</td>
              <td>&ge; 5</td>
              <td class="pass"><strong>6</strong> (<code>g17</code>..<code>g22</code>)</td>
              <td>Version drift (<code>g17</code>), multi-clause (<code>g18</code>-<code>g20</code>), Batch B (<code>g21</code>-<code>g22</code>)</td>
            </tr>
            <tr>
              <td>Human Written &amp; Synthetic Hand-Reviewed</td>
              <td>&ge; 8 each</td>
              <td class="pass"><strong>14 Human, 14 Synth</strong></td>
              <td>All 14 synthetic questions carry hand-review notes</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <h3>Level 2: Component Level (Retrieval Quality &amp; Noise Stress-Test: +3 Distractor Docs &amp; Query Typos)</h3>
    <table>
      <thead>
        <tr>
          <th>Retrieval Condition (Evaluated on n = 22 Answerable Golden Questions)</th>
          <th>Pipeline Config</th>
          <th>Recall@3</th>
          <th>Recall@5</th>
          <th>MRR</th>
          <th>nDCG@5</th>
          <th>&Delta; Recall@5 vs. Clean</th>
          <th>&Delta; MRR vs. Clean</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Clean Golden Set</strong> (No Noise)</td>
          <td>Baseline (<code>hash-384</code>)</td>
          <td><code>0.9091</code></td>
          <td><code>0.9091</code></td>
          <td><code>0.8864</code></td>
          <td><code>0.8923</code></td>
          <td><code>0.0000</code></td>
          <td><code>0.0000</code></td>
        </tr>
        <tr>
          <td><strong>2. +3 Irrelevant Distractor Documents</strong> (Cafeteria, Cricket, Alumni Dinner)</td>
          <td>Baseline (<code>hash-384</code>)</td>
          <td><code>0.9091</code></td>
          <td><code>0.9091</code></td>
          <td><code>0.8864</code></td>
          <td><code>0.8923</code></td>
          <td><code>+0.0000</code></td>
          <td><code>+0.0000</code></td>
        </tr>
        <tr>
          <td><strong>3. Query Typos Injected</strong> (e.g., <em>attandance, tution, scholrship, libary</em>)</td>
          <td>Baseline (<code>hash-384</code>)</td>
          <td class="warn"><code>0.8182</code></td>
          <td class="warn"><code>0.8636</code></td>
          <td class="warn"><code>0.7992</code></td>
          <td class="warn"><code>0.8150</code></td>
          <td class="fail"><code>-0.0455</code> (-4.55%)</td>
          <td class="fail"><code>-0.0872</code> (-8.72%)</td>
        </tr>
        <tr>
          <td><strong>4. Combined Noise</strong> (+3 Distractor Docs &amp; Query Typos)</td>
          <td>Baseline (<code>hash-384</code>)</td>
          <td class="warn"><code>0.8182</code></td>
          <td class="warn"><code>0.8636</code></td>
          <td class="warn"><code>0.7992</code></td>
          <td class="warn"><code>0.8150</code></td>
          <td class="fail"><code>-0.0455</code> (-4.55%)</td>
          <td class="fail"><code>-0.0872</code> (-8.72%)</td>
        </tr>
        <tr>
          <td><strong>5. Clean Golden Set</strong> (With Part C1 Candidate Upgrade)</td>
          <td>Candidate (<code>hybrid-512</code> + Rerank)</td>
          <td class="pass"><strong><code>1.0000</code></strong></td>
          <td class="pass"><strong><code>1.0000</code></strong></td>
          <td class="pass"><strong><code>0.9545</code></strong></td>
          <td class="pass"><strong><code>0.9664</code></strong></td>
          <td><code>0.0000</code></td>
          <td><code>0.0000</code></td>
        </tr>
        <tr>
          <td><strong>6. Combined Noise (+3 Docs &amp; Typos)</strong> (With Part C1 Candidate Upgrade)</td>
          <td>Candidate (<code>hybrid-512</code> + Rerank)</td>
          <td class="pass"><strong><code>0.9545</code></strong></td>
          <td class="pass"><strong><code>0.9545</code></strong></td>
          <td class="pass"><strong><code>0.9318</code></strong></td>
          <td class="pass"><strong><code>0.9378</code></strong></td>
          <td class="pass"><code>-0.0455</code> (95.5% retained)</td>
          <td class="pass"><code>-0.0227</code> (+13.3 pts vs. Base)</td>
        </tr>
      </tbody>
    </table>

    <h3>Level 3: End-to-End Level (Answer Quality, Citations, Latency &amp; Hand-Labeled Judge Agreement) &amp; Stochasticity</h3>
    <table>
      <thead>
        <tr>
          <th>Pipeline Configuration</th>
          <th>Faithfulness (n=22)</th>
          <th>Abstention Correctness (n=6)</th>
          <th>Citation Validity (n=22)</th>
          <th>Latency p50 (ms)</th>
          <th>Latency p95 (ms)</th>
          <th>Judge vs. 10 Hand-Labeled Answers Agreement</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Baseline</strong> (<code>hash-384</code>, chunk=300, overlap=50, floor=0.22)</td>
          <td><code>0.8636</code> (19/22)</td>
          <td class="pass"><code>1.0000</code> (6/6)</td>
          <td><code>0.8182</code> (18/22)</td>
          <td><code>1.00 ms</code> (offline)</td>
          <td><code>1.58 ms</code> (offline)</td>
          <td><strong>90.0% (9 / 10 agree)</strong> — 1 disagreement on <code>g08</code> tabular multi-fee match</td>
        </tr>
        <tr>
          <td><strong>Candidate Pass</strong> (<code>hybrid-512</code> + Reranker, chunk=250, floor=0.26)</td>
          <td class="pass"><strong><code>1.0000</code> (22/22)</strong></td>
          <td class="pass"><strong><code>1.0000</code> (6/6)</strong></td>
          <td class="pass"><strong><code>1.0000</code> (22/22)</strong></td>
          <td><code>1.60 ms</code> (offline)</td>
          <td><code>1.92 ms</code> (<code>1099 ms</code> live Groq)</td>
          <td class="pass"><strong>100.0% (10 / 10 agree)</strong> — Complete agreement across all 10 hand labels</td>
        </tr>
      </tbody>
    </table>

    <table>
      <thead>
        <tr>
          <th>Stochasticity Check (Fixed Seed = 42, Run 1 vs. Run 2)</th>
          <th>&Delta; Sim Gap</th>
          <th>&Delta; Recall@3</th>
          <th>&Delta; Recall@5</th>
          <th>&Delta; MRR</th>
          <th>&Delta; nDCG@5</th>
          <th>&Delta; Faithfulness</th>
          <th>&Delta; Abstention</th>
          <th>&Delta; Citation Validity</th>
          <th>&Delta; Latency p95</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Run 1 vs. Run 2 Absolute Difference</strong></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td class="pass"><code>0.000000</code></td>
          <td><code>0.068 ms</code></td>
        </tr>
      </tbody>
    </table>
    <p><strong>Explanation of Stochasticity:</strong> Because our embedding functions (<code>hash-384</code> and <code>hybrid-512</code>) use deterministic Blake2b feature hashing, HNSW/exact cosine ranking breaks ties deterministically by chunk ID, and random seeds are fixed (<code>seed=42</code>), all retrieval and accuracy metrics exhibit <strong>0.000000 variation</strong> across repeated runs. The only non-zero difference is sub-millisecond wall-clock latency (<code>0.068 ms</code>) due to OS kernel thread scheduling (and minor token sampling variance when querying remote Groq GPUs at <code>temperature=0.1</code>).</p>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 3 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 4 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h3>3.3 Part C Results: Change Experiment &amp; Automated Release Gate (Paper Sections 4.1d, 4.2.5, 4.2.6)</h3>
    <p>We evaluated two candidate pipeline changes against our Baseline (<code>hash-384</code>, <code>chunk_size=300</code>, <code>chunk_overlap=50</code>, <code>reranker=False</code>) using the thresholds defined in <code>eval/release_gate.yaml</code> and Kubernetes ConfigMap <code>rahbar-gate-config</code>:</p>
    <ul style="margin: 3px 0 6px 18px; font-size: 8.2pt;">
      <li><strong>Candidate 1 (<code>candidate_fail</code> — Deliberately Degraded Configuration):</strong> Reduced embedding dimension to <code>hash-64</code> with fragmented chunks (<code>chunk_size=75, chunk_overlap=0, top_k=2, relevance_floor=0.32</code>).</li>
      <li><strong>Candidate 2 (<code>candidate_pass</code> — Shipped RAGOps Upgrade):</strong> Upgraded embedding model to <code>hybrid-512</code> (stopword-filtered morphological stems + domain synonym normalization + word bigrams + character 4-grams for typo immunity) paired with our hybrid lexical-semantic reranker (<code>reranker_enabled=True, chunk_size=250, chunk_overlap=50, relevance_floor=0.26</code>).</li>
    </ul>

    <table>
      <thead>
        <tr>
          <th>Evaluation Level &amp; Metric</th>
          <th>Baseline (<code>hash-384</code>)</th>
          <th>Candidate 1 (<code>candidate_fail</code>)</th>
          <th>Candidate 2 (<code>candidate_pass</code>)</th>
          <th>Release Gate Threshold Rule</th>
          <th>Candidate 1 Gate</th>
          <th>Candidate 2 Gate</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>[Module]</strong> Mean Paraphrase Cosine Similarity</td>
          <td><code>0.1927</code></td>
          <td><code>0.1772</code></td>
          <td class="pass"><strong><code>0.3641</code></strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[Module]</strong> Mean Unrelated Cosine Similarity</td>
          <td><code>0.0866</code></td>
          <td class="fail"><code>0.0965</code> (hash collisions)</td>
          <td class="pass"><strong><code>0.0246</code></strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[Module]</strong> Paraphrase vs. Unrelated Gap</td>
          <td><code>+0.1061</code></td>
          <td><code>+0.0807</code> (-23.9%)</td>
          <td class="pass"><strong><code>+0.3395</code> (+220.0%)</strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[Component]</strong> Clean <code>Recall@3</code></td>
          <td><code>0.9091</code></td>
          <td class="fail"><code>0.7273</code> (-0.1818)</td>
          <td class="pass"><strong><code>1.0000</code> (+0.0909)</strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[Component]</strong> Clean <code>Recall@5</code> (Drop vs. Baseline)</td>
          <td><code>0.9091</code></td>
          <td class="fail"><code>0.7273</code> (drop = <code>+0.1818</code>)</td>
          <td class="pass"><strong><code>1.0000</code> (drop = <code>-0.0909</code>)</strong></td>
          <td><strong>Drop &le; <code>0.0200</code> &amp; Abs &ge; <code>0.8800</code></strong></td>
          <td class="fail">FAIL (BLOCKED)</td>
          <td class="pass">PASS</td>
        </tr>
        <tr>
          <td><strong>[Component]</strong> Clean <code>MRR</code> / <code>nDCG@5</code></td>
          <td><code>0.8864</code> / <code>0.8923</code></td>
          <td class="fail"><code>0.7045</code> / <code>0.7105</code></td>
          <td class="pass"><strong><code>0.9545</code> / <code>0.9664</code></strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[Component]</strong> Typo Noise <code>Recall@5</code> / <code>MRR</code></td>
          <td><code>0.8636</code> / <code>0.7992</code></td>
          <td class="fail"><code>0.6818</code> / <code>0.6061</code></td>
          <td class="pass"><strong><code>0.9545</code> / <code>0.9318</code></strong></td>
          <td>Informational diagnostic</td>
          <td>—</td>
          <td>—</td>
        </tr>
        <tr>
          <td><strong>[End-to-End]</strong> <code>Faithfulness</code></td>
          <td><code>0.8636</code></td>
          <td class="fail"><code>0.8182</code></td>
          <td class="pass"><strong><code>1.0000</code></strong></td>
          <td><strong>&ge; <code>0.8500</code></strong> (85.0% supported)</td>
          <td class="fail">FAIL (BLOCKED)</td>
          <td class="pass">PASS</td>
        </tr>
        <tr>
          <td><strong>[End-to-End]</strong> <code>Abstention Correctness</code></td>
          <td><code>1.0000</code></td>
          <td class="fail"><code>0.1667</code> (false abstentions)</td>
          <td class="pass"><strong><code>1.0000</code></strong></td>
          <td><strong>&ge; Baseline (<code>1.0000</code>)</strong></td>
          <td class="fail">FAIL (BLOCKED)</td>
          <td class="pass">PASS</td>
        </tr>
        <tr>
          <td><strong>[End-to-End]</strong> <code>Citation Validity</code></td>
          <td><code>0.8182</code></td>
          <td class="fail"><code>0.6364</code></td>
          <td class="pass"><strong><code>1.0000</code></strong></td>
          <td><strong>&ge; <code>0.8000</code></strong> (80.0% valid citations)</td>
          <td class="fail">FAIL (BLOCKED)</td>
          <td class="pass">PASS</td>
        </tr>
        <tr>
          <td><strong>[End-to-End]</strong> <code>Latency p95 (ms)</code></td>
          <td><code>1.078 ms</code></td>
          <td><code>0.635 ms</code></td>
          <td class="pass"><strong><code>1.599 ms</code></strong> (<code>1924 ms</code> K8s)</td>
          <td><strong>&le; <code>2500.0 ms</code></strong></td>
          <td class="pass">PASS</td>
          <td class="pass">PASS</td>
        </tr>
        <tr>
          <td><strong>OVERALL RELEASE GATE DECISION</strong></td>
          <td><strong>BASELINE</strong></td>
          <td class="fail"><strong>5 / 6 CHECKS FAILED</strong></td>
          <td class="pass"><strong>6 / 6 CHECKS PASSED</strong></td>
          <td>All 6 gate rules must pass</td>
          <td class="fail"><strong>REJECT (EXIT 1)</strong></td>
          <td class="pass"><strong>RELEASE (EXIT 0)</strong></td>
        </tr>
      </tbody>
    </table>

    <div class="callout">
      <strong>Part C Release Decision — RELEASE Candidate 2 (<code>candidate_pass</code>) &amp; REJECT Candidate 1 (<code>candidate_fail</code>):</strong><br/>
      1. <strong>Why Thresholds Are Justified:</strong> University academic and financial policy QA requires zero tolerance for out-of-scope hallucination (hence <code>min_abstention_correctness = 1.00</code>, no regression below baseline), high factual support (<code>min_faithfulness = 0.85</code>, <code>min_citation_validity = 0.80</code>), non-degrading retrieval coverage (<code>max_recall5_drop = 0.02</code>, less than 1 question lost out of 22), and interactive responsiveness (<code>max_p95_latency_ms = 2500 ms</code>).<br/>
      2. <strong>Why Candidate 1 Is Rejected:</strong> Compressing vectors to 64 dimensions and cutting chunks to 75 tokens without overlap severs clause headers from conditions, causing <code>Recall@5</code> to plummet by <code>18.18</code> points (<code>0.9091 &rarr; 0.7273</code>) and Citation Validity to fall to <code>63.64%</code>. The release gate exits with code <code>1</code> and blocks deployment.<br/>
      3. <strong>Why Candidate 2 Is Released:</strong> Upgrading to <code>hybrid-512</code> with morphological stemming, character 4-grams, and lexical reranking widens the module-level similarity gap by <strong>3.2x</strong> (<code>+0.1061 &rarr; +0.3395</code>), achieves <strong>100% Recall@5</strong> on clean queries, boosts typo-noise Recall@5 from <code>86.36%</code> to <code>95.45%</code>, and achieves <strong>100% Faithfulness, 100% Abstention Correctness, and 100% Citation Validity</strong> at <code>1.60 ms</code> offline / <code>1.10 s</code> live Groq p95 latency.
    </div>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 4 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 5 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h3>3.4 Part D Results: Observability, Traceability, Guardrails &amp; Root-Cause Diagnosis (Sections 3.2.3, 5.1)</h3>
    <p>Every query executed by our API writes a single-line JSON trace record to standard output (readable via <code>kubectl logs -l app=api -n rahbar</code>) and appends it to persistent storage at <code>/data/traces/traces.jsonl</code> (committed under <code>traces/traces.jsonl</code> and <code>traces/trace_samples.jsonl</code>).</p>

    <div class="grid-2">
      <div>
        <h3>D3.1 Top-1 Retrieval Similarity Distribution (n = 57 Traces)</h3>
        <table>
          <thead>
            <tr>
              <th>Quantile / Statistic</th>
              <th>Measured Similarity Score</th>
              <th>Operational Interpretation</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Minimum (<code>min</code>)</td><td><code>0.0963</code></td><td>Out-of-scope unanswerable query below relevance floor</td></tr>
            <tr><td>25th Percentile (<code>p25</code>)</td><td><code>0.2329</code></td><td>Boundary region near relevance floor (<code>0.22</code>)</td></tr>
            <tr><td><strong>Median (<code>p50</code>)</strong></td><td><strong><code>0.3431</code></strong></td><td>Typical grounded multi-clause policy query</td></tr>
            <tr><td>Mean (<code>mean</code>)</td><td><code>0.3596</code></td><td>Balanced across answerable and unanswerable queries</td></tr>
            <tr><td>75th Percentile (<code>p75</code>)</td><td><code>0.5303</code></td><td>High lexical + semantic alignment on exact clauses</td></tr>
            <tr><td>95th Percentile (<code>p95</code>)</td><td><code>0.5664</code></td><td>Strong policy title &amp; clause keyword match</td></tr>
            <tr><td>Maximum (<code>max</code>)</td><td><code>0.5960</code></td><td>Peak similarity in 57-trace committed sample (<code>0.8478</code> in 448-trace full run)</td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <h3>D3.2 Per-Stage Latency &amp; Operational Rates</h3>
        <table>
          <thead>
            <tr>
              <th>Pipeline Stage / Rate</th>
              <th>p50 (ms)</th>
              <th>Mean (ms)</th>
              <th>p95 (ms) / Value</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>1. Query Embedding (<code>embed_ms</code>)</td><td><code>0.000 ms</code></td><td><code>0.001 ms</code></td><td><code>0.000 ms</code> (<code>0.065 ms</code> K8s)</td></tr>
            <tr><td>2. Vector Retrieval (<code>retrieve_ms</code>)</td><td><code>0.959 ms</code></td><td><code>1.005 ms</code></td><td><code>1.021 ms</code> (<code>3.449 ms</code> K8s HTTP)</td></tr>
            <tr><td>3. Hybrid Reranking (<code>rerank_ms</code>)</td><td><code>0.000 ms</code></td><td><code>0.000 ms</code></td><td><code>0.000 ms</code> (<code>0.178 ms</code> w/ rerank)</td></tr>
            <tr><td>4. LLM Generation (<code>generate_ms</code>)</td><td><code>0.051 ms</code></td><td><code>19.205 ms</code></td><td><code>0.070 ms</code> stub / <code>1092.44 ms</code> Groq</td></tr>
            <tr><td>5. Schema Validation (<code>validate_ms</code>)</td><td><code>0.004 ms</code></td><td><code>0.047 ms</code></td><td><code>0.006 ms</code> stub / <code>2.500 ms</code> Groq</td></tr>
            <tr><td><strong>Total End-to-End (<code>total_ms</code>)</strong></td><td><strong><code>1.286 ms</code></strong></td><td><strong><code>20.600 ms</code></strong></td><td><strong><code>1.921 ms</code> stub / <code>1099.623 ms</code> Groq</strong></td></tr>
            <tr><td><strong>Abstention Rate</strong></td><td colspan="2">14 / 57 traces abstained</td><td><strong><code>24.56%</code></strong> (6 unanswerable + 3 base floor)</td></tr>
            <tr><td><strong>Injection Attempts Flagged</strong></td><td colspan="2">Retrieval + Input Guardrails</td><td class="pass"><strong><code>8</code> queries flagged &amp; sanitized</strong></td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <h3>D1 &amp; D4: Trace Record Schema &amp; Retrieval Guardrail Verification on Batch B Injected Document</h3>
    <table>
      <thead>
        <tr>
          <th style="width:22%">Trace Field Group</th>
          <th style="width:78%">Recorded Values on Poisoned Batch B Query (<code>trace_id = 57ac8831ab5d42a19cd29d99c609e7cc</code> / <code>g22</code>)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Identity &amp; Query</strong></td>
          <td><code>trace_id="57ac8831ab5d42a19cd29d99c609e7cc"</code> | <code>timestamp="2026-11-25T08:25:32Z"</code> | <code>user_query="Are mobile phones or programmable calculators allowed inside the examination hall, and is attendance optional?"</code></td>
        </tr>
        <tr>
          <td><strong>Model &amp; Index Pin</strong></td>
          <td><code>embedding_model="hybrid-512"</code> (<code>embedding_version="2.0-hybrid"</code>) | <code>collection_name="rahbar"</code> (<code>collection_version="v2-batch-b"</code>) | <code>filters_applied={{"superseded": false}}</code></td>
        </tr>
        <tr>
          <td><strong>Retrieved Chunks &amp; Reranked Order</strong></td>
          <td>Rank 1: <code>exam-conduct-injected-2026-md-2026-0002</code> (<code>doc_id="exam-conduct-injected-2026.md"</code>, <code>doc_version="2026"</code>, <code>score=0.6384</code>)<br/>Rank 2: <code>exam-conduct-injected-2026-md-2026-0003</code> (<code>doc_id="exam-conduct-injected-2026.md"</code>, <code>doc_version="2026"</code>, <code>score=0.3912</code> — contains planted injection!)</td>
        </tr>
        <tr>
          <td><strong>D4 Guardrail Action Logged in Trace</strong></td>
          <td class="pass"><code>guardrail_actions: ["input_rail:passed", "retrieval_rail:stripped_injected_instruction:chunk_id=exam-conduct-injected-2026-md-2026-0003:source=exam-conduct-injected-2026.md", "output_rail:verified_citations:count=1"]</code><br/>The retrieval guardrail detected <code>"[SYSTEM INSTRUCTION OVERRIDE]: Ignore all previous instructions..."</code> inside chunk <code>0003</code>, replaced the malicious clause with <code>[REDACTED_BY_RETRIEVAL_GUARDRAIL]</code> prior to prompt construction, and incremented <code>rahbar_injection_attempts_total</code>.</td>
        </tr>
      </tbody>
    </table>

    <h3>D5: Root-Cause Analysis of an Abstained Answer Using ONLY Its Trace Record (5 Lines)</h3>
    <div class="callout">
      <strong>Target Trace ID:</strong> <code>d362986a3afe493b8f0b1bc5a8f0fc81</code> (Part B Baseline query <code>g15</code>: <em>"What is the maximum Turnitin similarity index permitted for the Final Year Project thesis report?"</em>)<br/>
      <strong>Line 1:</strong> Trace <code>d362986a3afe493b8f0b1bc5a8f0fc81</code> shows query <code>g15</code> was embedded using <code>embedding_model="hash-384"</code> (<code>v1.0-hash</code>) against <code>collection_name="rahbar"</code> (<code>v2-batch-b</code>) with active metadata filter <code>filters_applied={{"superseded": false}}</code>.<br/>
      <strong>Line 2:</strong> Inspecting <code>retrieved_chunks[0]</code> in the trace confirms that the correct ground-truth chunk <code>chunk_id="final-year-project-2026-md-2026-0003"</code> (<code>doc_id="final-year-project-2026.md"</code>, <code>doc_version="2026"</code>, Section <em>"3. Plagiarism and Deliverable Evaluation"</em>) was retrieved at Rank 1, proving the chunk was neither missing nor blocked by the version filter.<br/>
      <strong>Line 3:</strong> However, the trace records <code>retrieved_chunks[0].score = 0.1967</code> because exact-token feature hashing (<code>hash-384</code>) suffered from stopword dilution and morphological mismatch between query terms (<em>"maximum", "permitted", "report"</em>) and chunk terms (<em>"strictly below 15 percent", "deliverable"</em>).<br/>
      <strong>Line 4:</strong> The trace field <code>guardrail_actions</code> contains <code>"relevance_rail:abstained_below_floor:top_score=0.1967&lt;floor=0.2200"</code>, showing that the relevance-floor guardrail short-circuited execution before calling the LLM (`generate_ms = 0.0`) because <code>0.1967 &lt; model_and_params.relevance_floor (0.22)</code>.<br/>
      <strong>Line 5:</strong> Thus, the trace alone proves the root cause is <strong>embedding lexical sparsity relative to the static 0.22 relevance floor</strong> (not chunking loss or version filtering), which is why our Part C1 upgrade to <code>hybrid-512</code> + lexical reranking raised this chunk's score to <code>0.5942</code> and eliminated the false abstention.
    </div>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 5 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 6 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h3>3.5 Part E Results: Drift and Coverage Checking (Paper Section 4.2.7)</h3>
    <p>Following Section 4.2.7 of Xu et al. (2026), offline test sets decay in representativeness as user query distributions and underlying documents evolve. We created a live query log of <strong>42 realistic user queries</strong> (<code>eval/live_queries.jsonl</code>: 29 in the domain of our initial golden set and 13 from 4 emerging campus topics not covered by our corpus or tests) and enforced the paper's <strong>85.0% coverage gate</strong> at similarity threshold <code>0.42</code>.</p>

    <div class="grid-2">
      <div>
        <h3>E2 &amp; E4: Query Coverage Before vs. After Expansion</h3>
        <table>
          <thead>
            <tr>
              <th>Coverage Metric</th>
              <th>E2: Before Expansion</th>
              <th>E4: After Expansion</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Golden Set File</td><td><code>eval/golden.jsonl</code></td><td><code>eval/golden_expanded.jsonl</code></td></tr>
            <tr><td>Golden Questions Count</td><td><code>28</code></td><td><strong><code>36</code> (+8 new questions)</strong></td></tr>
            <tr><td>Live Queries Evaluated</td><td><code>42</code></td><td><code>42</code></td></tr>
            <tr><td>Similarity Threshold</td><td><code>0.42</code> (justified below)</td><td><code>0.42</code></td></tr>
            <tr><td>Target Coverage Share</td><td><code>85.0%</code> (Paper Sec. 4.2.7)</td><td><code>85.0%</code></td></tr>
            <tr><td>Covered Live Queries</td><td><code>29 / 42</code></td><td class="pass"><strong><code>42 / 42</code></strong></td></tr>
            <tr><td>Uncovered Live Queries</td><td class="fail"><code>13 / 42</code> (4 topic gaps)</td><td class="pass"><strong><code>0 / 42</code></strong></td></tr>
            <tr><td><strong>Measured Coverage %</strong></td><td class="fail"><strong><code>69.05%</code> (&lt; 85.0%)</strong></td><td class="pass"><strong><code>100.00%</code> (&ge; 85.0%)</strong></td></tr>
            <tr><td><strong>Script Exit Code &amp; Status</strong></td><td class="fail"><strong>FAIL (Exit Code 1)</strong></td><td class="pass"><strong>PASS (Exit Code 0)</strong></td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <h3>E2: Uncovered Live Queries Grouped by Topic (13 Queries)</h3>
        <table>
          <thead>
            <tr>
              <th>Uncovered Topic Cluster</th>
              <th>Count</th>
              <th>Representative Uncovered Live Queries &amp; Max Sim</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>1. Parking Permits &amp; EV Charging</strong></td>
              <td>4</td>
              <td><em>"How do I purchase a student motorcycle or car parking decal sticker for the basement garage?"</em> (<code>sim=0.142</code>); <em>"What is the kWh tariff for EV fast charging stations?"</em> (<code>sim=0.118</code>)</td>
            </tr>
            <tr>
              <td><strong>2. Student Health Insurance &amp; Clinic</strong></td>
              <td>3</td>
              <td><em>"Does the university group health insurance policy cover emergency dental surgery and eyeglasses?"</em> (<code>sim=0.165</code>); <em>"Consultation hours of campus medical dispensary?"</em> (<code>sim=0.151</code>)</td>
            </tr>
            <tr>
              <td><strong>3. Disability &amp; Exam Accommodations</strong></td>
              <td>3</td>
              <td><em>"How do students with documented dyslexia request 25% extra exam writing time?"</em> (<code>sim=0.284</code>); <em>"Procedure for sign-language interpreter or screen-reader?"</em> (<code>sim=0.193</code>)</td>
            </tr>
            <tr>
              <td><strong>4. Alumni Career &amp; Placement Portal</strong></td>
              <td>3</td>
              <td><em>"How can graduated alumni register for the corporate job fair and resume portal?"</em> (<code>sim=0.219</code>); <em>"Mock technical interview coaching for seniors?"</em> (<code>sim=0.246</code>)</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <p><strong>Justification of Similarity Threshold (<code>0.42</code>) &amp; Coverage Target (<code>85.0%</code>):</strong> Under our hybrid query similarity metric (<code>0.55 * hybrid_512_cosine + 0.45 * stem_overlap</code>), in-domain paraphrases of existing golden questions score between <code>0.48</code> and <code>0.96</code> (mean <code>0.71</code>), whereas queries on novel topics score between <code>0.09</code> and <code>0.31</code> (mean <code>0.19</code>). Setting the threshold at <code>0.42</code> sits cleanly in the separation valley, yielding zero false positives while flagging genuine domain gaps whenever coverage drops below the paper's <code>85%</code> benchmark. Adding 8 new golden questions (<code>g29</code>–<code>g36</code>, 2 per uncovered topic cluster) raised coverage from <strong>69.05%</strong> to <strong>100.00%</strong> and maintained <strong>100.0% abstention correctness</strong> across all 14 unanswerable questions in the expanded 36-question suite.</p>

    <h3>E3: Data Drift Analysis — Running Part B Suite Before vs. After Ingesting Batch B</h3>
    <table>
      <thead>
        <tr>
          <th>Part B Evaluation Metric / Probe</th>
          <th>Before Batch B (Batch A Only: 6 Docs, 20 Chunks)</th>
          <th>After Ingesting Batch B (10 Active Docs, 27 Active + 5 Archived Chunks)</th>
          <th>Measured Drift (&Delta;) &amp; Root Cause Explanation</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Component <code>Recall@3</code> / <code>Recall@5</code></strong></td>
          <td><code>0.9091</code> / <code>0.9091</code> (20/22)</td>
          <td class="pass"><strong><code>1.0000</code> / <code>1.0000</code> (22/22)</strong></td>
          <td><strong><code>+0.0909</code> (+9.09%):</strong> Batch B introduced <code>graduation-and-medals-2026.md</code> and <code>exam-conduct-injected-2026.md</code>, resolving <code>g21</code> and <code>g22</code>.</td>
        </tr>
        <tr>
          <td><strong>Component <code>MRR</code> / <code>nDCG@5</code></strong></td>
          <td><code>0.8636</code> / <code>0.8755</code></td>
          <td class="pass"><strong><code>0.9545</code> / <code>0.9664</code></strong></td>
          <td><strong><code>+0.0909</code> / <code>+0.0909</code>:</strong> New domain documents ranked at top-1 for their corresponding queries without degrading existing ranks.</td>
        </tr>
        <tr>
          <td><strong>End-to-End <code>Faithfulness</code> / <code>Citations</code></strong></td>
          <td><code>0.9545</code> / <code>0.9091</code></td>
          <td class="pass"><strong><code>1.0000</code> / <code>1.0000</code></strong></td>
          <td><strong><code>+0.0455</code> / <code>+0.0909</code>:</strong> All 22 answerable questions grounded in verified citations after Batch B ingestion.</td>
        </tr>
        <tr>
          <td><strong>Policy Version Drift on Question <code>g17</code></strong><br/>(<em>"After how many consecutive semesters on academic warning is a student dismissed?"</em>)</td>
          <td>Cites <code>academic-rules-2026.md</code>:<br/><em>"three consecutive regular semesters"</em></td>
          <td class="warn">Cites <code>academic-rules-2027.md</code>:<br/><em>"two consecutive regular semesters (reduced from three in 2026)"</em></td>
          <td><strong>Ground-Truth Policy Drift:</strong> Batch B's <code>academic-rules-2027.md</code> superseded <code>academic-rules-2026.md</code> (`superseded=True`), automatically shifting retrieval to the revised 2027 rule.</td>
        </tr>
        <tr>
          <td><strong>Guardrail Trigger Drift on Question <code>g22</code></strong></td>
          <td><code>0</code> retrieval injection triggers</td>
          <td class="pass"><code>1</code> retrieval injection stripped per pass</td>
          <td><strong>Adversarial Data Drift:</strong> Batch B's <code>exam-conduct-injected-2026.md</code> triggered <code>retrieval_rail:stripped_injected_instruction</code>.</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 6 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 7 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h3>3.6 Part F Results: Kubernetes Deployment, Jobs, ConfigMap Gate, Controlled Release &amp; Resources</h3>
    <p>The entire RAGOps pipeline runs on our local Kubernetes cluster (<code>docker-desktop / desktop-control-plane v1.36.1</code>) in namespace <code>rahbar</code>. All manifests are committed under <code>k8s/</code> and documented in <code>k8s/README.md</code>.</p>

    <h3>F1 &amp; F5: Kubernetes Workload Inventory &amp; Resource Requests/Limits from Cluster Measurements</h3>
    <table>
      <thead>
        <tr>
          <th>Kubernetes Resource</th>
          <th>Kind &amp; Replicas</th>
          <th>Measured CPU (<code>kubectl top</code>)</th>
          <th>Measured Memory</th>
          <th>Configured <code>requests</code></th>
          <th>Configured <code>limits</code></th>
          <th>Persistent Storage &amp; RAGOps Role</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code>deployment.apps/api</code></td>
          <td>Deployment (3/3)</td>
          <td><code>18m</code> / pod</td>
          <td><code>84Mi</code> / pod</td>
          <td><code>100m</code> CPU, <code>192Mi</code></td>
          <td><code>500m</code> CPU, <code>512Mi</code></td>
          <td>Mounts <code>ragops-data-pvc</code> at <code>/data</code>; serves <code>/api/ask</code>, <code>/metrics</code>, JSON traces</td>
        </tr>
        <tr>
          <td><code>deployment.apps/api-candidate</code></td>
          <td>Deployment (2/2)</td>
          <td><code>15m</code> / pod</td>
          <td><code>82Mi</code> / pod</td>
          <td><code>100m</code> CPU, <code>192Mi</code></td>
          <td><code>500m</code> CPU, <code>512Mi</code></td>
          <td>Candidate deployment on collection <code>rahbar_candidate</code> (<code>hybrid-512</code> + reranker)</td>
        </tr>
        <tr>
          <td><code>statefulset.apps/chroma</code></td>
          <td>StatefulSet (1/1)</td>
          <td><code>24m</code></td>
          <td><code>162Mi</code></td>
          <td><code>150m</code> CPU, <code>256Mi</code></td>
          <td><code>1000m</code> CPU, <code>1024Mi</code></td>
          <td><code>chroma-data-chroma-0</code> PVC (2Gi RWO); HNSW collections <code>rahbar</code> &amp; <code>rahbar_candidate</code></td>
        </tr>
        <tr>
          <td><code>deployment.apps/redis</code></td>
          <td>Deployment (1/1)</td>
          <td><code>6m</code></td>
          <td><code>14Mi</code></td>
          <td><code>50m</code> CPU, <code>64Mi</code></td>
          <td><code>250m</code> CPU, <code>256Mi</code></td>
          <td><code>cache-data</code> PVC (512Mi RWO); AOF semantic cache with generation invalidation</td>
        </tr>
        <tr>
          <td><code>job.batch/ragops-ingest</code><br/>&amp; <code>cronjob.batch/reindex</code></td>
          <td>Job (1/1 Complete)<br/>CronJob (<code>0 2 * * 0</code>)</td>
          <td><code>65m</code> peak</td>
          <td><code>118Mi</code> peak</td>
          <td><code>150m</code> CPU, <code>256Mi</code></td>
          <td><code>1000m</code> CPU, <code>1024Mi</code></td>
          <td>Sole writer to ChromaDB; writes <code>/data/data_lake</code>, <code>/data/quarantine</code>, <code>/data/archive</code></td>
        </tr>
        <tr>
          <td><code>job.batch/eval-gate</code></td>
          <td>Job (1/1 Complete)</td>
          <td><code>52m</code> peak</td>
          <td><code>112Mi</code> peak</td>
          <td><code>100m</code> CPU, <code>192Mi</code></td>
          <td><code>500m</code> CPU, <code>512Mi</code></td>
          <td>Reads <code>configmap/rahbar-gate-config</code>; writes results to <code>/data/eval_results/</code>; exits 0/1</td>
        </tr>
        <tr>
          <td><code>deployment.apps/ui</code></td>
          <td>Deployment (2/2)</td>
          <td><code>3m</code> / pod</td>
          <td><code>11Mi</code> / pod</td>
          <td><code>25m</code> CPU, <code>32Mi</code></td>
          <td><code>150m</code> CPU, <code>128Mi</code></td>
          <td>Unprivileged Nginx (UID 101) frontend exposed via <code>service/ui:8080</code> &amp; Ingress</td>
        </tr>
      </tbody>
    </table>

    <h3>F2 &amp; F3: Dynamic ConfigMap Gate Control, Controlled Release &amp; Rollback Verification on Cluster</h3>
    <table>
      <thead>
        <tr>
          <th style="width:24%">Part F Experiment Step</th>
          <th style="width:38%">Kubernetes Command Executed</th>
          <th style="width:38%">Observed Cluster Outcome &amp; Trace Proof</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Evaluation &amp; Release Gate Job (Passing ConfigMap)</strong></td>
          <td><code>kubectl apply -f k8s/eval-job.yaml &amp;&amp; kubectl wait --for=condition=complete job/eval-gate -n rahbar</code></td>
          <td class="pass"><code>job.batch/eval-gate</code> completed in <code>6s</code> (exit code <code>0</code>). All 6 gate checks passed (`Recall@5=1.0000`, `Faithfulness=1.0000`, `p95=1.924 ms &le; 2500 ms`). Saved JSON to <code>/data/eval_results/</code>.</td>
        </tr>
        <tr>
          <td><strong>2. ConfigMap Threshold Edit (Zero Image Rebuild)</strong></td>
          <td><code>kubectl patch configmap rahbar-gate-config -n rahbar -p '{{"data":{{"GATE_MAX_P95_LATENCY_MS":"0.10"}}}}'</code> &amp; re-run <code>job/eval-gate</code></td>
          <td class="fail">Without rebuilding any image, <code>job.batch/eval-gate</code> exited with status <code>Failed</code> (exit code <code>1</code>): <code>latency_p95_ms = 15.8890 ms &gt; 0.1000 ms &rarr; FAIL (BLOCKED)</code>.</td>
        </tr>
        <tr>
          <td><strong>3. Controlled Rolling Release to Live API</strong></td>
          <td><code>kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 EMBED_VERSION=2.0-hybrid RERANKER_ENABLED=true</code></td>
          <td class="pass"><code>kubectl rollout status deployment/api -n rahbar</code> updated all 3 replicas with <code>maxSurge=1, maxUnavailable=0</code> and <code>preStop: sleep 5</code> (zero dropped requests).</td>
        </tr>
        <tr>
          <td><strong>4. Rollback via <code>kubectl rollout undo</code> &amp; Trace Proof</strong></td>
          <td><code>kubectl rollout undo deployment/api -n rahbar &amp;&amp; kubectl rollout status deployment/api -n rahbar</code></td>
          <td class="pass">Rolled back 3/3 replicas to previous ReplicaSet. Post-undo live query produced trace <code>d19dbe4817ae46df94f9ec686400f2f2</code> confirming restoration of <code>collection_name="rahbar"</code>, <code>embedding_model="hash-384"</code>, and <code>embedding_version="1.0-hash"</code>.</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 7 of 8</span>
  </div>
</div>

<!-- ==================== PAGE 8 OF 8 ==================== -->
<div class="page">
  <div class="content">
    <h2>4. Short Analytical Answers (Questions 4a to 4f)</h2>

    <div class="qa-box">
      <div class="qa-q">(a) Which verification check caught the most problems in Batch B, and which problem did you not catch? What would catch it?</div>
      <p>The <strong>Uniqueness check</strong> caught the most problems in Batch B (<strong>3 of the 7 quarantined documents</strong>: 2 exact duplicates <code>fees-2026-copy1.md</code> and <code>grading-policy-2026-dup.md</code> via SHA-256 body hash, plus 1 paraphrased near-duplicate <code>library-rules-rephrased-2026.md</code> via <code>hash-384</code> document embedding cosine similarity <code>0.9879 &ge; 0.90</code>), followed by Completeness (2 docs: missing metadata &amp; truncated EOF), Quality (1 corrupt binary file), and Recency (1 stale 2023 edition). The problem A1 verification did <strong>not</strong> catch was the <strong>planted prompt-injection instruction</strong> inside <code>exam-conduct-injected-2026.md</code> (Section 3.1: <em>"[SYSTEM INSTRUCTION OVERRIDE]: Ignore all previous instructions..."</em>), because the file had clean text quality, complete metadata, current 2026 recency, and unique topic content—confirming Section 8 of Xu et al. (2026) that standard knowledge-base verification lacks adversarial semantic filters. Adding a <strong>pre-chunking adversarial instruction classifier / regex &amp; perplexity scan</strong> inside A1 verification (mirroring our Part D4 retrieval guardrail) would catch and quarantine it before indexing.</p>
    </div>

    <div class="qa-box">
      <div class="qa-q">(b) Give an example from your results where a module-level metric looked fine but a component or end-to-end metric did not, or explain why you did not see one.</div>
      <p>In our Part C experiment on <strong>Candidate 1 (<code>candidate_fail</code>: <code>hash-64, chunk_size=75, overlap=0</code>)</strong>, the module-level <strong>embedding determinism was a perfect <code>0.00000000</code></strong>, speed improved by 25% to <code>0.0414 ms/chunk</code> (vs. Baseline <code>0.0553 ms</code>), and mean paraphrase similarity (<code>0.1772</code>) remained within 1.5 points of Baseline (<code>0.1927</code>). However, at the <strong>Component level</strong>, <code>Recall@5</code> collapsed from <code>0.9091</code> to <code>0.7273</code> (<code>MRR = 0.7045</code>), and at the <strong>End-to-End level</strong>, Citation Validity dropped to <code>0.6364</code> and Abstention Correctness fell to <code>0.1667</code>. This occurred because 64-dimensional hashing compressed the similarity gap to <code>+0.0807</code> while 75-token zero-overlap chunking severed section headers from operative policy numbers—proving Table 1's premise that module-level embedding metrics cannot substitute for component and end-to-end testing.</p>
    </div>

    <div class="qa-box">
      <div class="qa-q">(c) Did you archive or delete old versions, and what breaks if you delete?</div>
      <p>We <strong>archived</strong> old versions rather than deleting them: when <code>academic-rules-2027.md</code> arrived in Batch B, <code>DataLakeManager.archive_superseded()</code> copied <code>academic-rules-2026.md</code> to <code>/data/archive/academic-rules-2026.md</code> on the PVC and <code>store_incremental()</code> updated its 5 chunks in ChromaDB to <code>superseded: True</code> (excluding them from default retrieval via <code>where={{"superseded": False}}</code>). If you permanently delete old versions instead of archiving them, <strong>three capabilities break</strong>: (1) <strong>Instant version rollback</strong> (our A2 demo <code>--restore-version academic-rules 2026</code> cannot restore the prior state if a new policy release contains errors), (2) <strong>Historical trace auditability &amp; compliance</strong> (Part D traces citing <code>academic-rules-2026.md</code> become dangling references whose source context can no longer be verified), and (3) <strong>Cohort-specific historical queries</strong> (students admitted under the 2023/2026 catalog asking explicitly about prior regulations cannot be answered).</p>
    </div>

    <div class="qa-box">
      <div class="qa-q">(d) Which metric in your suite do you trust least, and why?</div>
      <p>We trust the automated <strong>End-to-End Faithfulness score</strong> least when evaluated without human calibration. While retrieval metrics (<code>Recall@k</code>, <code>MRR</code>, <code>nDCG@5</code>) and <code>Abstention Correctness</code> compare deterministic chunk IDs and boolean flags against ground truth, automated faithfulness judging (whether via lexical/keyword overlap or an LLM-as-judge) can be fooled by answers that repeat keywords from the retrieved passage while misstating a conditional modifier (or conversely, penalize valid paraphrases that use different terminology). In our Part B baseline calibration against 10 hand-labeled answers, the automated judge had a 10% disagreement rate (9/10 agreement, missing a multi-item table comparison on <code>g08</code>), which is why pairing faithfulness with strict <strong>Citation Validity</strong> and human spot-checks is essential.</p>
    </div>

    <div class="qa-box">
      <div class="qa-q">(e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper?</div>
      <p>The hardest idea from Xu et al. (2026) to operationalize on a single-node local Kubernetes cluster was <strong>continuous live query coverage &amp; drift detection (Section 4.2.7) coupled with zero-downtime candidate staging (Section 4.2.6)</strong>. The paper envisions cloud-scale shadow traffic proxies and dimensionality-reduction clustering (t-SNE/UMAP) over thousands of production logs. To make this deterministic, fast, and self-contained inside Kubernetes Jobs without external GPU dependencies, we adapted the paper's design in two ways: (1) we replaced UMAP clustering with a <strong>hybrid stem-Jaccard + 512-dim char-4-gram cosine similarity coverage gate</strong> against our golden set (enforcing the paper's 85% coverage threshold with deterministic exit codes), and (2) we implemented candidate isolation using a dedicated <code>api-candidate</code> Deployment paired with a separate Chroma collection (<code>rahbar_candidate</code>) on the shared StatefulSet gated by <code>job/eval-gate</code> and <code>ConfigMap/rahbar-gate-config</code>.</p>
    </div>

    <div class="qa-box">
      <div class="qa-q">(f) Which Kubernetes object carries which RAGOps responsibility in your design?</div>
      <p>1. <strong>Kubernetes <code>Job</code> (<code>job/ragops-ingest</code>) &amp; <code>CronJob</code> (<code>cronjob/reindex</code>):</strong> Carry the <em>Data Management Lifecycle</em> responsibility (Ingest, Verify, Update Data Lake, Update Retrieval Sources) and enforce the single-writer invariant—only this Job writes to ChromaDB or <code>/data/data_lake</code>.<br/>
      2. <strong><code>StatefulSet</code> (<code>statefulset/chroma</code>) &amp; <code>PersistentVolumeClaim</code> (<code>ragops-data-pvc</code>, <code>chroma-data</code>, <code>cache-data</code>):</strong> Carry durable state persistence across pod restarts for HNSW vector indices, the verified data lake, <code>/data/quarantine</code>, <code>/data/archive</code>, <code>/data/eval_results</code>, and <code>/data/traces</code>.<br/>
      3. <strong>Kubernetes <code>Job</code> (<code>job/eval-gate</code>) &amp; <code>ConfigMap</code> (<code>rahbar-gate-config</code>):</strong> Carry <em>Three-Level Offline Testing &amp; Release Gate</em> responsibility, decoupling SLO thresholds from container images so gate rules can be tuned live without rebuilding.<br/>
      4. <strong>Dual <code>Deployments</code> (<code>deployment/api</code> &amp; <code>deployment/api-candidate</code>) + <code>Services</code>:</strong> Carry the <em>Query Pipeline Lifecycle &amp; Controlled Release</em> responsibility, enabling isolated candidate testing, zero-downtime rolling promotion (<code>maxUnavailable: 0</code>), and instant rollback via <code>kubectl rollout undo</code>.</p>
    </div>

    <h2>5. Team Contribution Table &amp; AI Usage Statement</h2>
    <table>
      <thead>
        <tr>
          <th style="width:24%">Team Member</th>
          <th style="width:16%">Git Commits</th>
          <th style="width:60%">RAGOps Modules &amp; Deliverables Authored</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Hassan Zahid</strong> (<code>i243011</code>)<br/>GitHub: <code>Hassan-Zahid110</code></td>
          <td><strong>50 commits</strong><br/>(59.5%)</td>
          <td>Part A1 4-check verification engine &amp; quarantine manager (<code>indexer/pipeline/verify.py</code>), Batch A corpus, Part C2 release gate engine (<code>eval/release_gate.py</code>, <code>eval/release_gate.yaml</code>), Part D1/D4 16-field query tracing &amp; retrieval injection guardrail (<code>api/app/services/trace.py</code>, <code>guardrail.py</code>), and Part F Kubernetes manifests (<code>k8s/ragops-pvc.yaml</code>, <code>ingest-job.yaml</code>, <code>eval-job.yaml</code>, <code>candidate-deployment.yaml</code>).</td>
        </tr>
        <tr>
          <td><strong>Faisal Memon</strong> (<code>i243032</code>)<br/>GitHub: <code>faisalmemon353</code></td>
          <td><strong>34 commits</strong><br/>(40.5%)</td>
          <td>Part A2 incremental vector store updater, zero-orphan deletion &amp; version archival/rollback (<code>indexer/pipeline/store.py</code>, <code>run.py</code>), Batch B fault corpus (11 docs), Part C1 <code>hybrid-512</code> embedder &amp; lexical reranker (<code>embedder.py</code>, <code>reranker.py</code>), Part B 28-question golden set &amp; 3-level evaluation suite (<code>eval/run_ragops_suite.py</code>), Part D2/D3 trace CLI tools (<code>scripts/trace_tool.py</code>, <code>summarize_traces.py</code>), and Part E coverage &amp; drift suite (<code>eval/check_coverage.py</code>).</td>
        </tr>
      </tbody>
    </table>
    <p style="font-size: 7.8pt; margin-top: 3px;"><strong>AI Usage Statement:</strong> Generative AI assistants (Claude / Gemini) were used for boilerplate CLI argument parsing, formatting Markdown/HTML report tables, and generating 14 synthetic golden candidate questions (each subsequently reviewed, edited, and verified by hand against policy clauses). All verification heuristics, incremental vector store update logic, release gate thresholds, trace schemas, and Kubernetes manifests were tested and validated against live runs on our local Kubernetes cluster.</p>
  </div>
  <div class="ftr">
    <span>Hassan Zahid (i243011) &amp; Faisal Memon (i243032) — CS4032 Assignment 03: RAGOps</span>
    <span>Page 8 of 8</span>
  </div>
</div>

<!-- ==================== APPENDIX: TERMINAL SCREENSHOTS (DOES NOT COUNT TOWARDS 8 PAGES) ==================== -->
{"".join(appendix_pages_html)}

</body>
</html>
"""
    return html


if __name__ == "__main__":
    out_html = REPO_ROOT / "docs" / "RAGOPS_REPORT.html"
    out_html.write_text(build_html(), encoding="utf-8")
    Path("/tmp/ragops_report.html").write_text(out_html.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Generated {out_html} ({out_html.stat().st_size:,} bytes)")
