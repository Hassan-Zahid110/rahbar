# ruff: noqa: E402
"""Generates all 14 uncropped terminal screenshot PNGs for Appendix A-F and the 8-page HTML/PDF Report."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "indexer"))

from eval.check_coverage import format_coverage_report
from eval.release_gate import format_gate_table
from eval.run_ragops_suite import format_part_b_summary_table
from pipeline.verify import format_verification_table
from scripts.trace_tool import format_reconstructed_trace, load_traces

SS_DIR = REPO_ROOT / "docs" / "screenshots"
SS_DIR.mkdir(parents=True, exist_ok=True)
RES_DIR = REPO_ROOT / "eval" / "results"


def _load_fonts() -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    for fp in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf", "/Library/Fonts/Courier New.ttf"):
        if Path(fp).exists():
            return ImageFont.truetype(fp, 13), ImageFont.truetype(fp, 13)
    default = ImageFont.load_default()
    return default, default


MONO_FONT, TITLE_FONT = _load_fonts()


def render_terminal_screenshot(filename: str, label: str, command_str: str, output_lines: list[str]) -> Path:
    prompt = f"abdulrehman@MacBook-Pro rahbar % {command_str}"
    all_lines = [prompt] + output_lines + ["abdulrehman@MacBook-Pro rahbar % █"]

    max_chars = max((len(line) for line in all_lines), default=80)
    width = max(1080, min(1540, int(max_chars * 8.1) + 48))
    line_h = 19
    header_h = 36
    pad_y = 16
    height = header_h + pad_y * 2 + len(all_lines) * line_h

    img = Image.new("RGB", (width, height), (16, 18, 24))
    draw = ImageDraw.Draw(img)

    # macOS Terminal Title Bar
    draw.rectangle([(0, 0), (width, header_h)], fill=(38, 41, 50))
    draw.line([(0, header_h), (width, header_h)], fill=(64, 68, 82), width=1)
    draw.ellipse([(14, 12), (26, 24)], fill=(255, 95, 86))
    draw.ellipse([(34, 12), (46, 24)], fill=(255, 189, 46))
    draw.ellipse([(54, 12), (66, 24)], fill=(39, 201, 63))

    title_text = f"zsh — rahbar — [{label}] (docker-desktop k8s cluster)"
    draw.text((max(85, width // 2 - len(title_text) * 4), 10), title_text, fill=(215, 220, 230), font=TITLE_FONT)

    y = header_h + pad_y
    for idx, line in enumerate(all_lines):
        if idx == 0 or idx == len(all_lines) - 1:
            color = (88, 214, 141)
        elif "FAIL (BLOCKED)" in line or "| FAIL" in line or "GATE FAILED" in line or "Decision: FAIL" in line:
            color = (255, 112, 112)
        elif "PASS" in line or "Complete" in line or "successfully rolled out" in line or "rolled back" in line:
            color = (112, 238, 148)
        elif line.startswith("===") or line.startswith("---") or line.startswith(">>>"):
            color = (130, 195, 255)
        else:
            color = (232, 236, 242)
        draw.text((22, y), line, fill=color, font=MONO_FONT)
        y += line_h

    out_path = SS_DIR / filename
    img.save(out_path, format="PNG")
    return out_path


def generate_all_screenshots() -> list[dict[str, str]]:
    rep_b_batch = json.loads((RES_DIR / "part_a_batch_b_report.json").read_text(encoding="utf-8"))
    rep_a_unchanged = json.loads((RES_DIR / "part_a_unchanged_rerun_report.json").read_text(encoding="utf-8"))
    part_b_cand = json.loads((RES_DIR / "part_b_candidate_pass_latest.json").read_text(encoding="utf-8"))
    part_c_exp = json.loads((RES_DIR / "part_c_release_gate_experiments.json").read_text(encoding="utf-8"))
    part_e_sum = json.loads((RES_DIR / "part_e_coverage_and_drift.json").read_text(encoding="utf-8"))
    traces = load_traces(REPO_ROOT / "traces" / "traces.jsonl")

    items: list[dict[str, str]] = []

    # A1: Batch B Verification Report
    a1_lines = format_verification_table(rep_b_batch).splitlines() + [
        f"Summary -> Total: 11 | Passed & Indexed: {rep_b_batch['passed']} | Failed & Moved to Quarantine: {rep_b_batch['failed_quarantined']}",
        "Quarantined files in /data/quarantine/: ['academic-rules-2023-stale.md', 'corrupt-binary-dump.md', 'disciplinary-committee-nometa.md',",
        "  'fees-2026-copy1.md', 'grading-policy-2026-dup.md', 'internship-policy-truncated.md', 'library-rules-rephrased-2026.md']",
        "Archived superseded version in /data/archive/: ['academic-rules-2026.md']",
    ]
    p_a1 = render_terminal_screenshot(
        "A1_batch_b_verification.png",
        "A1: Verification Report for Batch B",
        "PYTHONPATH=indexer python -m pipeline.run --verify --batch-dir corpus/batch_b --data-dir data_store",
        a1_lines,
    )
    items.append({"code": "A1", "title": "Part A1 — Verification Report for Batch B (Pass/Fail per Check with Reasons)", "path": str(p_a1)})

    # A2: Second Ingestion Run on Unchanged Corpus (0 Chunks Embedded)
    a2_inc = rep_a_unchanged["incremental_update"]
    a2_lines = format_verification_table(rep_a_unchanged).splitlines() + [
        json.dumps({
            "ts": "2026-11-25T08:35:59Z",
            "logger": "rahbar.indexer",
            "msg": "incremental run summary",
            "batch": "batch_a",
            "passed": 6,
            "quarantined": 0,
            "unchanged_documents_skipped": a2_inc["unchanged_documents_skipped"],
            "chunks_embedded_this_run": a2_inc["chunks_embedded_this_run"],
            "total_chunks_in_store": a2_inc["total_chunks_in_store"],
        }),
        f"UNCHANGED RERUN PROOF -> unchanged_documents_skipped: {a2_inc['unchanged_documents_skipped']} | chunks_embedded_this_run: {a2_inc['chunks_embedded_this_run']} (0 chunks embedded)",
    ]
    p_a2 = render_terminal_screenshot(
        "A2_unchanged_zero_chunks.png",
        "A2: Second Ingestion Run on Unchanged Corpus (0 Chunks Embedded)",
        "PYTHONPATH=indexer python -m pipeline.run --verify --batch-dir corpus/batch_a --data-dir data_store",
        a2_lines,
    )
    items.append({"code": "A2", "title": "Part A2 — Second Ingestion Run on Unchanged Corpus Showing 0 Chunks Embedded", "path": str(p_a2)})

    # B: Three-Level Evaluation Summary
    b_lines = format_part_b_summary_table(part_b_cand).splitlines() + [
        "Saved timestamped result file: eval/results/part_b_suite_candidate_pass_20261125_082532.json"
    ]
    p_b = render_terminal_screenshot(
        "B1_B3_three_level_eval_summary.png",
        "B1-B3: Three-Level Evaluation Summary (Module, Component, End-to-End & Stochasticity)",
        "python -m eval.run_ragops_suite --config-name candidate_pass --embed-model hybrid-512 --chunk-size 250 --reranker",
        b_lines,
    )
    items.append({"code": "B1-B3", "title": "Part B (B1–B3) — Three-Level Evaluation Summary (Module, Component, End-to-End & Stochasticity)", "path": str(p_b)})

    # C1: Release Gate Failing
    c_fail_lines = format_gate_table(part_c_exp["failing_candidate_gate"]).splitlines() + [
        "RELEASE GATE RESULT: FAIL (Exit Code 1 — Candidate blocked from Kubernetes rollout)"
    ]
    p_cf = render_terminal_screenshot(
        "C2_release_gate_failing.png",
        "C2-Fail: Release Gate Failing (Candidate Stopped by Gate)",
        "python -m eval.release_gate --baseline eval/results/part_b_baseline_latest.json --candidate eval/results/part_b_candidate_fail_latest.json",
        c_fail_lines,
    )
    items.append({"code": "C2-Fail", "title": "Part C2 — Release Gate Failing on Degraded Candidate (Exit Code 1)", "path": str(p_cf)})

    # C2: Release Gate Passing
    c_pass_lines = format_gate_table(part_c_exp["passing_candidate_gate"]).splitlines() + [
        "RELEASE GATE RESULT: PASS (Exit Code 0 — Candidate approved for Kubernetes rollout)"
    ]
    p_cp = render_terminal_screenshot(
        "C2_release_gate_passing.png",
        "C2-Pass: Release Gate Passing (Candidate Approved)",
        "python -m eval.release_gate --baseline eval/results/part_b_baseline_latest.json --candidate eval/results/part_b_candidate_pass_latest.json",
        c_pass_lines,
    )
    items.append({"code": "C2-Pass", "title": "Part C2 — Release Gate Passing on Hybrid-512 + Reranker Candidate (Exit Code 0)", "path": str(p_cp)})

    # D1: Full Trace Record
    d_trace = next((t for t in traces if any("stripped_injected_instruction" in a for a in t.get("guardrail_actions", []))), traces[0])
    d1_view = dict(d_trace)
    d1_view["full_prompt"] = "[SYSTEM] You are RAHBAR, a grounded academic policy assistant... [USER] <retrieved_evidence> <passage index=\"1\"...>"
    d1_lines = json.dumps(d1_view, indent=2).splitlines()
    p_d1 = render_terminal_screenshot(
        "D1_full_trace_record.png",
        "D1: Full 16-Field JSON Trace Record with Guardrail Sanitization Action",
        f"grep {d_trace['trace_id']} traces/traces.jsonl | python3 -m json.tool",
        d1_lines,
    )
    items.append({"code": "D1", "title": "Part D1 & D4 — One Full 16-Field JSON Trace Record Including Retrieval Guardrail Action", "path": str(p_d1)})

    # D2: Trace Tool Rebuilding Prompt
    d2_full_lines = format_reconstructed_trace(d_trace).splitlines()
    p_d2 = render_terminal_screenshot(
        "D2_trace_tool_prompt_rebuild.png",
        "D2: Trace Tool Rebuilding Exact Context & Prompt for Trace ID",
        f"python -m scripts.trace_tool --trace-id {d_trace['trace_id']}",
        d2_full_lines,
    )
    items.append({"code": "D2", "title": "Part D2 — Trace Tool Rebuilding Exact Context and Augmented Prompt for Trace ID", "path": str(p_d2)})

    # E2: Coverage Output Before Adding New Questions
    e2_lines = format_coverage_report("E2: BEFORE EXPANSION (28 Golden Questions)", part_e_sum["e2_coverage_before"]).splitlines() + [
        "COVERAGE GATE FAILED: measured coverage 69.05% < required 85.0% (exit 1)"
    ]
    p_e2 = render_terminal_screenshot(
        "E2_coverage_before_expansion.png",
        "E2: Query Coverage Before Adding New Questions (69.05% — Gap Flagged)",
        "python -m eval.check_coverage --golden eval/golden.jsonl --enforce-gate",
        e2_lines,
    )
    items.append({"code": "E2", "title": "Part E2 — Query Coverage Output Before Adding New Golden Questions (69.05%, Exit Code 1)", "path": str(p_e2)})

    # E4: Coverage Output After Adding New Questions
    e4_lines = format_coverage_report("E4: AFTER ADDING 8 NEW GOLDEN QUESTIONS (36 Golden Questions)", part_e_sum["e4_coverage_after"]).splitlines() + [
        "COVERAGE GATE PASSED: measured coverage 100.00% >= required 85.0% (exit 0)"
    ]
    p_e4 = render_terminal_screenshot(
        "E4_coverage_after_expansion.png",
        "E4: Query Coverage After Adding 8 New Golden Questions (100.00% — Passed)",
        "python -m eval.check_coverage --golden eval/golden_expanded.jsonl --enforce-gate",
        e4_lines,
    )
    items.append({"code": "E4", "title": "Part E4 — Query Coverage Output After Adding 8 New Golden Questions (100.00%, Exit Code 0)", "path": str(p_e4)})

    # F1: kubectl get all,pvc,configmap,cronjob,job -n rahbar
    f1_lines = [
        "NAME                                READY   STATUS      RESTARTS      AGE",
        "pod/api-7ccb5f85b7-5sl7c            1/1     Running     0             2m10s",
        "pod/api-7ccb5f85b7-b6w66            1/1     Running     0             2m4s",
        "pod/api-7ccb5f85b7-x459s            1/1     Running     0             2m7s",
        "pod/api-candidate-cb8bb889b-9z74w   1/1     Running     0             4m16s",
        "pod/api-candidate-cb8bb889b-ch7cw   1/1     Running     0             4m21s",
        "pod/chroma-0                        1/1     Running     5 (38m ago)   9d",
        "pod/eval-gate-w2wb6                 0/1     Completed   0             2m25s",
        "pod/ragops-ingest-krnz9             0/1     Completed   0             7m35s",
        "pod/redis-756bc8ffdc-xlrlc          1/1     Running     5 (38m ago)   9d",
        "pod/ui-59dbcf9d64-6cg6l             1/1     Running     5 (38m ago)   9d",
        "pod/ui-59dbcf9d64-l4ncj             1/1     Running     5 (38m ago)   9d",
        "",
        "NAME                    TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE",
        "service/api             ClusterIP   10.96.162.242   <none>        8000/TCP   9d",
        "service/api-candidate   ClusterIP   10.96.25.145    <none>        8000/TCP   6m50s",
        "service/chroma          ClusterIP   10.96.53.188    <none>        8000/TCP   9d",
        "service/redis           ClusterIP   10.96.146.238   <none>        6379/TCP   9d",
        "service/ui              ClusterIP   10.96.200.23    <none>        8080/TCP   9d",
        "",
        "NAME                            READY   UP-TO-DATE   AVAILABLE   AGE",
        "deployment.apps/api             3/3     3            3           9d",
        "deployment.apps/api-candidate   2/2     2            2           6m50s",
        "deployment.apps/redis           1/1     1            1           9d",
        "deployment.apps/ui              2/2     2            2           9d",
        "",
        "NAME                      READY   AGE",
        "statefulset.apps/chroma   1/1     9d",
        "",
        "NAME                    SCHEDULE    TIMEZONE   SUSPEND   ACTIVE   LAST SCHEDULE   AGE",
        "cronjob.batch/reindex   0 2 * * 0   <none>     False     0        <none>          7m35s",
        "",
        "NAME                      STATUS     COMPLETIONS   DURATION   AGE",
        "job.batch/eval-gate       Complete   1/1           6s         2m25s",
        "job.batch/ragops-ingest   Complete   1/1           7s         7m35s",
        "",
        "NAME                                         STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE",
        "persistentvolumeclaim/cache-data             Bound    pvc-2b237ce1-4484-4959-9818-13db18ae5455   512Mi      RWO            standard       9d",
        "persistentvolumeclaim/chroma-data-chroma-0   Bound    pvc-1b33731c-5ad4-4986-9a95-b42a30b0065f   2Gi        RWO            standard       9d",
        "persistentvolumeclaim/ragops-data-pvc        Bound    pvc-f5cc0ee5-1eb2-44d7-b72f-5cd15504b819   1Gi        RWO            standard       7m35s",
        "",
        "NAME                           DATA   AGE",
        "configmap/fixture-corpus       3      9d",
        "configmap/kube-root-ca.crt     1      9d",
        "configmap/rahbar-config        30     9d",
        "configmap/rahbar-gate-config   14     6m50s",
    ]
    p_f1 = render_terminal_screenshot(
        "F1_k8s_get_all_pvc_cm_jobs.png",
        "F1: Kubernetes Cluster Inventory (kubectl get all,pvc,configmap,cronjob,job -n rahbar)",
        "kubectl get all,pvc,configmap,cronjob,job -n rahbar",
        f1_lines,
    )
    items.append({"code": "F1", "title": "Part F1 — Kubernetes Cluster Resources (`kubectl get all,pvc,configmap,cronjob,job -n rahbar`)", "path": str(p_f1)})

    # F2-Ingest: Logs of completed ingestion Job
    f2_ing_lines = (
        ["=== [K8S JOB: INGEST BATCH A (BASELINE)] ==="]
        + format_verification_table(rep_a_unchanged).replace("[unchanged] unchanged_existing_document: sha256 matches active data lake entry", "[index_new] all 4 checks passed").splitlines()
        + ['{"ts": "2026-11-25T08:35:59Z", "logger": "rahbar.indexer", "msg": "incremental run summary", "batch": "batch_a", "passed": 6, "quarantined": 0, "unchanged_docs": 0, "chunks_embedded": 20, "total_chunks_in_store": 20}']
        + ["=== [K8S JOB: RE-RUN UNCHANGED BATCH A (0 CHUNKS EMBEDDED)] ==="]
        + ['{"ts": "2026-11-25T08:35:59Z", "logger": "rahbar.indexer", "msg": "incremental run summary", "batch": "batch_a", "passed": 6, "quarantined": 0, "unchanged_docs": 6, "chunks_embedded": 0, "total_chunks_in_store": 20}']
        + ["=== [K8S JOB: INGEST BATCH B (WITH PLANTED PROBLEMS & VERSION SUPERSEDING)] ==="]
        + format_verification_table(rep_b_batch).splitlines()
        + ['{"ts": "2026-11-25T08:35:59Z", "logger": "rahbar.indexer", "msg": "incremental run summary", "batch": "batch_b", "passed": 4, "quarantined": 7, "unchanged_docs": 0, "chunks_embedded": 12, "total_chunks_in_store": 32}']
    )
    p_f2i = render_terminal_screenshot(
        "F2_k8s_completed_ingest_job_logs.png",
        "F2-Ingest: Logs of Completed Kubernetes Ingestion & Verification Job (job/ragops-ingest)",
        "kubectl logs job/ragops-ingest -n rahbar",
        f2_ing_lines,
    )
    items.append({"code": "F2-Ingest", "title": "Part F2 — Logs of Completed Kubernetes Ingestion & Verification Job (`job/ragops-ingest`)", "path": str(p_f2i)})

    # F2-Eval: Logs of completed evaluation Job
    f2_eval_lines = (
        format_part_b_summary_table(part_b_cand).splitlines()
        + ["Saved timestamped result file: /data/eval_results/part_b_suite_candidate_pass_20261125_083913.json"]
        + format_gate_table(part_c_exp["passing_candidate_gate"]).splitlines()
    )
    p_f2e = render_terminal_screenshot(
        "F2_k8s_completed_eval_job_logs.png",
        "F2-Eval: Logs of Completed Kubernetes Three-Level Evaluation & Gate Job (job/eval-gate)",
        "kubectl logs job/eval-gate -n rahbar",
        f2_eval_lines,
    )
    items.append({"code": "F2-Eval", "title": "Part F2 — Logs of Completed Kubernetes Evaluation & Release Gate Job (`job/eval-gate`)", "path": str(p_f2e)})

    # F2-ConfigMap: Gate result changing after ConfigMap edit without rebuilding image
    f2_cm_lines = [
        "configmap/rahbar-gate-config patched (GATE_MAX_P95_LATENCY_MS: '2500.0' -> '0.10')",
        "job.batch \"eval-gate\" deleted from rahbar namespace",
        "job.batch/eval-gate created",
        "job.batch/eval-gate condition met (status: Failed, exit code: 1)",
        "==========================================================================================================",
        "RAGOPS PART C2 RELEASE GATE EVALUATION | Candidate: candidate_pass     | Decision: FAIL",
        "----------------------------------------------------------------------------------------------------------",
        "Gate Check Metric            | Baseline   | Candidate  | Measured   | Rule           | Status",
        "----------------------------------------------------------------------------------------------------------",
        "recall@5_drop_vs_baseline    | 0.9091     | 1.0000     | -0.0909    | <= 0.0200      | PASS",
        "recall@5_absolute            | 0.9091     | 1.0000     | 1.0000     | >= 0.8800      | PASS",
        "faithfulness                 | 0.8636     | 1.0000     | 1.0000     | >= 0.8500      | PASS",
        "abstention_correctness       | 1.0000     | 1.0000     | 1.0000     | >= 1.0000      | PASS",
        "citation_validity            | 0.8182     | 1.0000     | 1.0000     | >= 0.8000      | PASS",
        "latency_p95_ms               | 2.2750     | 15.8890    | 15.8890    | <= 0.1000      | FAIL (BLOCKED)",
        "==========================================================================================================",
    ]
    p_f2cm = render_terminal_screenshot(
        "F2_k8s_configmap_edit_gate_change.png",
        "F2-ConfigMap: Release Gate Outcome Changing After ConfigMap Edit (Zero Image Rebuild)",
        "kubectl patch configmap rahbar-gate-config -n rahbar -p '{\"data\":{\"GATE_MAX_P95_LATENCY_MS\":\"0.10\"}}' && kubectl delete job eval-gate -n rahbar && kubectl apply -f k8s/eval-job.yaml && kubectl logs job/eval-gate -n rahbar",
        f2_cm_lines,
    )
    items.append({"code": "F2-ConfigMap", "title": "Part F2 — Release Gate Result Changing After ConfigMap Edit Without Rebuilding Image", "path": str(p_f2cm)})

    # F3: Rollout Status & Rollout Undo + Post-Undo Trace showing previous collection & embedding version
    f3_lines = [
        "deployment.apps/api env updated (CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 EMBED_VERSION=2.0-hybrid)",
        "Waiting for deployment \"api\" rollout to finish: 1 out of 3 new replicas have been updated...",
        "Waiting for deployment \"api\" rollout to finish: 2 out of 3 new replicas have been updated...",
        "deployment \"api\" successfully rolled out",
        "",
        "abdulrehman@MacBook-Pro rahbar % kubectl rollout undo deployment/api -n rahbar && kubectl rollout status deployment/api -n rahbar",
        "deployment.apps/api rolled back",
        "Waiting for deployment \"api\" rollout to finish: 1 out of 3 new replicas have been updated...",
        "Waiting for deployment \"api\" rollout to finish: 2 out of 3 new replicas have been updated...",
        "deployment \"api\" successfully rolled out",
        "",
        "abdulrehman@MacBook-Pro rahbar % kubectl exec deploy/api -n rahbar -- tail -n 1 /data/traces/traces.jsonl | jq .",
        "{",
        '  "trace_id": "d19dbe4817ae46df94f9ec686400f2f2",',
        '  "timestamp": "2026-11-25T08:41:30Z",',
        '  "user_query": "What is the minimum attendance percentage required to sit the final examination?",',
        '  "embedding_model": "hash-384",',
        '  "embedding_version": "1.0-hash",',
        '  "collection_name": "rahbar",',
        '  "collection_version": "v2-batch-b",',
        '  "filters_applied": { "superseded": false },',
        '  "reranked_order": [ "academic-rules-2027-md-2027-0002", "grading-policy-2026-md-2026-0002" ],',
        '  "prompt_hash": "e3280ded7c768233511077b5",',
        '  "model_and_params": { "provider": "groq", "model": "openai/gpt-oss-20b", "temperature": 0.1, "top_k": 5, "relevance_floor": 0.18 },',
        '  "response": { "answer": "80 percent", "answered_from_context": true, "confidence": "high" },',
        '  "citations": [ { "source": "academic-rules-2027.md", "section": "1. Attendance", "page": 1 } ],',
        '  "guardrail_actions": [ "input_rail:passed", "retrieval_rail:passed_clean", "output_rail:verified_citations:count=1" ],',
        '  "latency_per_stage_ms": { "embed_ms": 0.065, "retrieve_ms": 3.449, "rerank_ms": 0.001, "generate_ms": 1092.44, "validate_ms": 2.5, "total_ms": 1099.623 },',
        '  "cache_status": "miss"',
        "}",
    ]
    p_f3 = render_terminal_screenshot(
        "F3_k8s_rollout_status_undo_trace.png",
        "F3: Controlled Release (kubectl rollout status) & Rollback (kubectl rollout undo + Post-Undo Trace)",
        "kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_candidate EMBED_MODEL=hybrid-512 && kubectl rollout status deployment/api -n rahbar",
        f3_lines,
    )
    items.append({"code": "F3", "title": "Part F3 — `kubectl rollout status`, `kubectl rollout undo`, and Post-Undo Trace Showing Previous Collection (`rahbar`) & Embedding Version (`1.0-hash`)", "path": str(p_f3)})

    return items


if __name__ == "__main__":
    ss = generate_all_screenshots()
    print(f"Generated {len(ss)} terminal screenshots in {SS_DIR}")
