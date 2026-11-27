"""Helper CLI to print clean terminal output for each Assignment 03 screenshot (A1..F4).

Usage:
  .venv/bin/python scripts/show_screenshot.py A1
  .venv/bin/python scripts/show_screenshot.py A2
  .venv/bin/python scripts/show_screenshot.py A3
  .venv/bin/python scripts/show_screenshot.py B1
  .venv/bin/python scripts/show_screenshot.py B2
  .venv/bin/python scripts/show_screenshot.py C1
  .venv/bin/python scripts/show_screenshot.py C2
  .venv/bin/python scripts/show_screenshot.py D1
  .venv/bin/python scripts/show_screenshot.py D2
  .venv/bin/python scripts/show_screenshot.py E1
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent


def _print_part_a_report(title: str, path: Path) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    print("=" * 112)
    print(f"{title} | Total: {d['total_documents']} | Passed: {d['passed']} | Quarantined: {d['failed_quarantined']}")
    print("-" * 112)
    print(f"{'Document':<36} | {'Qual':<4} | {'Comp':<4} | {'Recn':<4} | {'Uniq':<4} | {'Overall':<7} | Action / Reason")
    print("-" * 112)
    for r in d["results"]:
        c = r["checks"]
        q = c["quality"]["status"].upper()
        cp = c["completeness"]["status"].upper()
        rc = c["recency"]["status"].upper()
        uq = c["uniqueness"]["status"].upper()
        ov = r["overall"].upper()
        act = r["action"]
        fail_reasons = [
            f"{k}:{v['reason']}"
            for k, v in c.items()
            if v["status"] == "fail"
        ]
        reason = "; ".join(fail_reasons) if fail_reasons else c["uniqueness"]["reason"]
        print(f"{r['source']:<36} | {q:<4} | {cp:<4} | {rc:<4} | {uq:<4} | {ov:<7} | [{act}] {reason[:42]}")
    print("=" * 112)
    print("Incremental Update Summary:")
    print(json.dumps(d["incremental_update"], indent=2))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python scripts/show_screenshot.py <A1|A2|A3|B1|B2|C1|C2|D1|D2|E1>")
        return 1
    code = sys.argv[1].upper()
    res_dir = REPO_ROOT / "eval" / "results"
    py = sys.executable

    if code == "A1":
        _print_part_a_report("PART A1: BATCH A (CLEAN BASELINE CORPUS) VERIFICATION & INDEXING", res_dir / "part_a_batch_a_report.json")
    elif code == "A2":
        _print_part_a_report("PART A2: UNCHANGED CORPUS RE-RUN (0 CHUNKS RE-EMBEDDED)", res_dir / "part_a_unchanged_rerun_report.json")
    elif code == "A3":
        _print_part_a_report("PART A1 & A2: BATCH B (7 DEFECTS QUARANTINED + VERSION UPDATE)", res_dir / "part_a_batch_b_report.json")
        comp = json.loads((res_dir / "part_a_complete_summary.json").read_text(encoding="utf-8"))
        print("\nSingle-Doc Update :", json.dumps(comp["single_doc_update"]))
        print("Delete 0-Orphans  :", json.dumps(comp["delete_doc_zero_orphans"]))
        print("Quarantined Files :", comp["quarantined_files"])
        print("Archived Files    :", comp["archived_files"])
    elif code == "B1":
        subprocess.run([py, "eval/run_ragops_suite.py"], cwd=REPO_ROOT, check=True)
    elif code == "B2":
        d = json.loads((res_dir / "part_b_baseline_latest.json").read_text(encoding="utf-8"))
        r1 = d["run_1"]
        r2 = d["run_2"]
        print("=" * 96)
        print("PART B: STOCHASTICITY VERIFICATION (FIXED SEED = 42, RUN 1 vs RUN 2)")
        print("-" * 96)
        print(f"{'Metric':<36} | {'Run 1':<12} | {'Run 2':<12} | {'Abs Diff':<12}")
        print("-" * 96)
        rows = [
            ("Module Similarity Gap", r1["module_level"]["similarity_gap"], r2["module_level"]["similarity_gap"]),
            ("Component Recall@3", r1["component_level"]["clean"]["recall@3"], r2["component_level"]["clean"]["recall@3"]),
            ("Component Recall@5", r1["component_level"]["clean"]["recall@5"], r2["component_level"]["clean"]["recall@5"]),
            ("Component MRR", r1["component_level"]["clean"]["mrr"], r2["component_level"]["clean"]["mrr"]),
            ("Component nDCG@5", r1["component_level"]["clean"]["ndcg@5"], r2["component_level"]["clean"]["ndcg@5"]),
            ("End-to-End Faithfulness", r1["end_to_end_level"]["faithfulness"], r2["end_to_end_level"]["faithfulness"]),
            ("End-to-End Abstention Correctness", r1["end_to_end_level"]["abstention_correctness"], r2["end_to_end_level"]["abstention_correctness"]),
            ("End-to-End Citation Validity", r1["end_to_end_level"]["citation_validity"], r2["end_to_end_level"]["citation_validity"]),
            ("End-to-End Latency p50 (ms)", r1["end_to_end_level"]["latency_p50_ms"], r2["end_to_end_level"]["latency_p50_ms"]),
            ("End-to-End Latency p95 (ms)", r1["end_to_end_level"]["latency_p95_ms"], r2["end_to_end_level"]["latency_p95_ms"]),
        ]
        for name, v1, v2 in rows:
            print(f"{name:<36} | {v1:<12.4f} | {v2:<12.4f} | {abs(v1 - v2):<12.6f}")
        print("=" * 96)
        print("Explanation:", d["stochasticity_diff"]["explanation"])
    elif code == "C1":
        subprocess.run([py, "eval/release_gate.py", "--eval-candidate-mode", "fail"], cwd=REPO_ROOT, check=False)
    elif code == "C2":
        subprocess.run([py, "eval/release_gate.py", "--eval-candidate-mode", "pass"], cwd=REPO_ROOT, check=True)
    elif code == "D1":
        subprocess.run(["git", "checkout", "--", "traces/traces.jsonl", "traces/trace_samples.jsonl", "eval/results/part_d_trace_summary.json"], cwd=REPO_ROOT, check=False)
        subprocess.run([py, "scripts/summarize_traces.py"], cwd=REPO_ROOT, check=True)
        print("\n--- SINGLE FULL JSON TRACE RECORD ---")
        first_line = (REPO_ROOT / "traces" / "trace_samples.jsonl").read_text(encoding="utf-8").splitlines()[0]
        print(json.dumps(json.loads(first_line), indent=2))
    elif code == "D2":
        subprocess.run(["git", "checkout", "--", "traces/traces.jsonl", "traces/trace_samples.jsonl", "eval/results/part_d_trace_summary.json"], cwd=REPO_ROOT, check=False)
        subprocess.run([py, "scripts/trace_tool.py", "--show-sample-d1-d2"], cwd=REPO_ROOT, check=True)
    elif code == "E1":
        subprocess.run([py, "eval/check_coverage.py"], cwd=REPO_ROOT, check=True)
    else:
        print(f"Unknown code: {code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
