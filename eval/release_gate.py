# ruff: noqa: E402
"""Part C1 & C2 (RAGOps 4.1(d), 4.2.5, 4.2.6): Change Experiment Runner & Release Gate CLI.

Usage:
  # Run full Part C experiment (Baseline vs Passing Candidate vs Failing Candidate):
  python -m eval.release_gate --run-experiment

  # Evaluate a specific candidate report against baseline using thresholds from YAML or env/ConfigMap:
  python -m eval.release_gate --baseline eval/results/part_b_baseline_latest.json \
                              --candidate eval/results/part_b_candidate_pass_latest.json \
                              --config eval/release_gate.yaml
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "api"))
sys.path.insert(0, str(REPO_ROOT / "indexer"))

from eval.run_ragops_suite import run_three_level_suite


def _parse_simple_yaml(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.endswith(":"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            try:
                out[k.strip()] = float(v.strip())
            except ValueError:
                pass
    return out


def load_thresholds(config_path: Path) -> dict[str, float]:
    raw_txt = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if yaml is not None and raw_txt:
        data = yaml.safe_load(raw_txt) or {}
        t = dict(data.get("gate_thresholds") or data)
    else:
        t = _parse_simple_yaml(raw_txt)
    # Allow ConfigMap environment variable overrides for Kubernetes Part F2 demonstration
    if "GATE_MAX_RECALL5_DROP" in os.environ:
        t["max_recall5_drop"] = float(os.environ["GATE_MAX_RECALL5_DROP"])
    if "GATE_MIN_RECALL5_ABSOLUTE" in os.environ:
        t["min_recall5_absolute"] = float(os.environ["GATE_MIN_RECALL5_ABSOLUTE"])
    if "GATE_MIN_FAITHFULNESS" in os.environ:
        t["min_faithfulness"] = float(os.environ["GATE_MIN_FAITHFULNESS"])
    if "GATE_MIN_ABSTENTION" in os.environ:
        t["min_abstention_correctness"] = float(os.environ["GATE_MIN_ABSTENTION"])
    if "GATE_MIN_CITATION_VALIDITY" in os.environ:
        t["min_citation_validity"] = float(os.environ["GATE_MIN_CITATION_VALIDITY"])
    if "GATE_MAX_P95_LATENCY_MS" in os.environ:
        t["max_p95_latency_ms"] = float(os.environ["GATE_MAX_P95_LATENCY_MS"])
    return {k: float(v) for k, v in t.items()}


def evaluate_release_gate(
    baseline_rep: dict[str, Any],
    candidate_rep: dict[str, Any],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    b_r1 = baseline_rep["run_1"]
    c_r1 = candidate_rep["run_1"]

    b_r5 = float(b_r1["component_level"]["clean"]["recall@5"])
    c_r5 = float(c_r1["component_level"]["clean"]["recall@5"])
    r5_drop = round(b_r5 - c_r5, 4)

    b_abstain = float(b_r1["end_to_end_level"]["abstention_correctness"])
    c_abstain = float(c_r1["end_to_end_level"]["abstention_correctness"])

    c_faith = float(c_r1["end_to_end_level"]["faithfulness"])
    c_cite = float(c_r1["end_to_end_level"]["citation_validity"])
    c_p95 = float(c_r1["end_to_end_level"]["latency_p95_ms"])

    min_abstain_req = max(thresholds.get("min_abstention_correctness", b_abstain), b_abstain)

    checks = [
        {
            "metric": "recall@5_drop_vs_baseline",
            "baseline": b_r5,
            "candidate": c_r5,
            "measured": r5_drop,
            "operator": "<=",
            "threshold": thresholds["max_recall5_drop"],
            "passed": r5_drop <= thresholds["max_recall5_drop"] + 1e-9,
        },
        {
            "metric": "recall@5_absolute",
            "baseline": b_r5,
            "candidate": c_r5,
            "measured": c_r5,
            "operator": ">=",
            "threshold": thresholds.get("min_recall5_absolute", 0.88),
            "passed": c_r5 + 1e-9 >= thresholds.get("min_recall5_absolute", 0.88),
        },
        {
            "metric": "faithfulness",
            "baseline": float(b_r1["end_to_end_level"]["faithfulness"]),
            "candidate": c_faith,
            "measured": c_faith,
            "operator": ">=",
            "threshold": thresholds["min_faithfulness"],
            "passed": c_faith + 1e-9 >= thresholds["min_faithfulness"],
        },
        {
            "metric": "abstention_correctness",
            "baseline": b_abstain,
            "candidate": c_abstain,
            "measured": c_abstain,
            "operator": ">=",
            "threshold": min_abstain_req,
            "passed": c_abstain + 1e-9 >= min_abstain_req,
        },
        {
            "metric": "citation_validity",
            "baseline": float(b_r1["end_to_end_level"]["citation_validity"]),
            "candidate": c_cite,
            "measured": c_cite,
            "operator": ">=",
            "threshold": thresholds.get("min_citation_validity", 0.80),
            "passed": c_cite + 1e-9 >= thresholds.get("min_citation_validity", 0.80),
        },
        {
            "metric": "latency_p95_ms",
            "baseline": float(b_r1["end_to_end_level"]["latency_p95_ms"]),
            "candidate": c_p95,
            "measured": c_p95,
            "operator": "<=",
            "threshold": thresholds["max_p95_latency_ms"],
            "passed": c_p95 <= thresholds["max_p95_latency_ms"] + 1e-9,
        },
    ]

    overall_pass = all(c["passed"] for c in checks)
    return {
        "candidate_name": candidate_rep.get("config_name", "candidate"),
        "baseline_name": baseline_rep.get("config_name", "baseline"),
        "overall_decision": "PASS" if overall_pass else "FAIL",
        "thresholds_applied": thresholds,
        "checks": checks,
        "three_level_comparison": {
            "module_similarity_gap": {
                "baseline": b_r1["module_level"]["similarity_gap"],
                "candidate": c_r1["module_level"]["similarity_gap"],
                "delta": round(c_r1["module_level"]["similarity_gap"] - b_r1["module_level"]["similarity_gap"], 4),
            },
            "component_recall@3": {
                "baseline": b_r1["component_level"]["clean"]["recall@3"],
                "candidate": c_r1["component_level"]["clean"]["recall@3"],
                "delta": round(c_r1["component_level"]["clean"]["recall@3"] - b_r1["component_level"]["clean"]["recall@3"], 4),
            },
            "component_recall@5": {
                "baseline": b_r5,
                "candidate": c_r5,
                "delta": round(c_r5 - b_r5, 4),
            },
            "component_mrr": {
                "baseline": b_r1["component_level"]["clean"]["mrr"],
                "candidate": c_r1["component_level"]["clean"]["mrr"],
                "delta": round(c_r1["component_level"]["clean"]["mrr"] - b_r1["component_level"]["clean"]["mrr"], 4),
            },
            "component_ndcg@5": {
                "baseline": b_r1["component_level"]["clean"]["ndcg@5"],
                "candidate": c_r1["component_level"]["clean"]["ndcg@5"],
                "delta": round(c_r1["component_level"]["clean"]["ndcg@5"] - b_r1["component_level"]["clean"]["ndcg@5"], 4),
            },
            "component_typo_noise_recall@5": {
                "baseline": b_r1["component_level"]["noise_query_typos"]["recall@5"],
                "candidate": c_r1["component_level"]["noise_query_typos"]["recall@5"],
                "delta": round(c_r1["component_level"]["noise_query_typos"]["recall@5"] - b_r1["component_level"]["noise_query_typos"]["recall@5"], 4),
            },
            "e2e_faithfulness": {
                "baseline": b_r1["end_to_end_level"]["faithfulness"],
                "candidate": c_faith,
                "delta": round(c_faith - b_r1["end_to_end_level"]["faithfulness"], 4),
            },
            "e2e_abstention_correctness": {
                "baseline": b_abstain,
                "candidate": c_abstain,
                "delta": round(c_abstain - b_abstain, 4),
            },
            "e2e_citation_validity": {
                "baseline": b_r1["end_to_end_level"]["citation_validity"],
                "candidate": c_cite,
                "delta": round(c_cite - b_r1["end_to_end_level"]["citation_validity"], 4),
            },
            "e2e_latency_p95_ms": {
                "baseline": b_r1["end_to_end_level"]["latency_p95_ms"],
                "candidate": c_p95,
                "delta": round(c_p95 - b_r1["end_to_end_level"]["latency_p95_ms"], 3),
            },
        },
    }


def format_gate_table(gate_res: dict[str, Any]) -> str:
    lines = [
        "=" * 106,
        f"RAGOPS PART C2 RELEASE GATE EVALUATION | Candidate: {gate_res['candidate_name']:<18} | Decision: {gate_res['overall_decision']}",
        "-" * 106,
        f"{'Gate Check Metric':<28} | {'Baseline':<10} | {'Candidate':<10} | {'Measured':<10} | {'Rule':<14} | {'Status'}",
        "-" * 106,
    ]
    for chk in gate_res["checks"]:
        rule = f"{chk['operator']} {chk['threshold']:.4f}"
        status = "PASS" if chk["passed"] else "FAIL (BLOCKED)"
        lines.append(
            f"{chk['metric']:<28} | {chk['baseline']:<10.4f} | {chk['candidate']:<10.4f} | "
            f"{chk['measured']:<10.4f} | {rule:<14} | {status}"
        )
    lines.append("=" * 106)
    return "\n".join(lines)


def run_part_c_experiments(config_path: Path) -> dict[str, Any]:
    default_res = "/data/eval_results" if Path("/data").exists() and os.access("/data", os.W_OK) else str(REPO_ROOT / "eval" / "results")
    results_dir = Path(os.environ.get("EVAL_RESULTS_DIR", default_res))
    results_dir.mkdir(parents=True, exist_ok=True)
    thresholds = load_thresholds(config_path)

    print(">>> Running Baseline Pipeline (hash-384, chunk=300, overlap=50, reranker=off)...")
    base_rep = run_three_level_suite(
        config_name="baseline",
        embed_model="hash-384",
        chunk_size=300,
        chunk_overlap=50,
        top_k=5,
        relevance_floor=0.22,
        reranker_enabled=False,
        print_summary=False,
    )

    print(">>> Running Candidate 1 (FAILING Candidate: hash-64, chunk=75, overlap=0, top_k=2)...")
    fail_rep = run_three_level_suite(
        config_name="candidate_fail",
        embed_model="hash-64",
        chunk_size=75,
        chunk_overlap=0,
        top_k=2,
        relevance_floor=0.32,
        reranker_enabled=False,
        print_summary=False,
    )
    gate_fail = evaluate_release_gate(base_rep, fail_rep, thresholds)
    print(format_gate_table(gate_fail), flush=True)

    print("\n>>> Running Candidate 2 (PASSING Candidate: hybrid-512 + stem/c4 + lexical reranker, chunk=250, overlap=50)...")
    pass_rep = run_three_level_suite(
        config_name="candidate_pass",
        embed_model="hybrid-512",
        chunk_size=250,
        chunk_overlap=50,
        top_k=5,
        relevance_floor=0.26,
        reranker_enabled=True,
        print_summary=False,
    )
    gate_pass = evaluate_release_gate(base_rep, pass_rep, thresholds)
    print(format_gate_table(gate_pass), flush=True)

    summary = {
        "thresholds": thresholds,
        "failing_candidate_gate": gate_fail,
        "passing_candidate_gate": gate_pass,
    }
    out_path = results_dir / "part_c_release_gate_experiments.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    default_res = "/data/eval_results" if Path("/data").exists() and os.access("/data", os.W_OK) else str(REPO_ROOT / "eval" / "results")
    parser = argparse.ArgumentParser(description="RAGOps Part C Release Gate Evaluator.")
    parser.add_argument("--run-experiment", action="store_true", help="run both failing and passing candidate experiments")
    parser.add_argument("--eval-candidate-mode", choices=["pass", "fail", "env", ""], default="", help="evaluate candidate dynamically in K8s Job")
    parser.add_argument("--baseline", type=str, default=str(Path(default_res) / "part_b_baseline_latest.json"))
    parser.add_argument("--candidate", type=str, default=str(Path(default_res) / "part_b_candidate_pass_latest.json"))
    parser.add_argument("--config", type=str, default=str(REPO_ROOT / "eval" / "release_gate.yaml"))
    args = parser.parse_args()

    cfg_path = Path(args.config)
    mode = args.eval_candidate_mode or os.environ.get("CANDIDATE_MODE", "")
    if mode in {"pass", "fail", "env"}:
        thresholds = load_thresholds(cfg_path)
        base_rep = run_three_level_suite(
            config_name="baseline",
            embed_model="hash-384",
            chunk_size=300,
            chunk_overlap=50,
            top_k=5,
            relevance_floor=0.22,
            reranker_enabled=False,
            print_summary=True,
        )
        if mode == "fail":
            cand_rep = run_three_level_suite(
                config_name="candidate_fail",
                embed_model="hash-64",
                chunk_size=75,
                chunk_overlap=0,
                top_k=2,
                relevance_floor=0.32,
                reranker_enabled=False,
                print_summary=True,
            )
        else:
            cand_rep = run_three_level_suite(
                config_name="candidate_pass",
                embed_model=os.environ.get("CANDIDATE_EMBED_MODEL", "hybrid-512"),
                chunk_size=int(os.environ.get("CANDIDATE_CHUNK_SIZE", "250")),
                chunk_overlap=int(os.environ.get("CANDIDATE_CHUNK_OVERLAP", "50")),
                top_k=int(os.environ.get("CANDIDATE_TOP_K", "5")),
                relevance_floor=float(os.environ.get("CANDIDATE_RELEVANCE_FLOOR", "0.26")),
                reranker_enabled=os.environ.get("CANDIDATE_RERANKER", "true").lower() in {"1", "true", "yes"},
                print_summary=True,
            )
        gate_res = evaluate_release_gate(base_rep, cand_rep, thresholds)
        print(format_gate_table(gate_res), flush=True)
        res_dir = Path(default_res)
        res_dir.mkdir(parents=True, exist_ok=True)
        (res_dir / f"gate_result_{cand_rep['config_name']}.json").write_text(json.dumps(gate_res, indent=2), encoding="utf-8")
        return 0 if gate_res["overall_decision"] == "PASS" else 1

    if args.run_experiment:
        summary = run_part_c_experiments(cfg_path)
        assert summary["failing_candidate_gate"]["overall_decision"] == "FAIL"
        assert summary["passing_candidate_gate"]["overall_decision"] == "PASS"
        return 0

    b_path = Path(args.baseline)
    c_path = Path(args.candidate)
    if not b_path.exists():
        run_three_level_suite(config_name="baseline", print_summary=False)
    if not c_path.exists():
        c_name = "candidate_fail" if "fail" in c_path.name else "candidate_pass"
        if c_name == "candidate_fail":
            run_three_level_suite(config_name="candidate_fail", embed_model="hash-64", chunk_size=75, chunk_overlap=0, top_k=2, relevance_floor=0.32, print_summary=False)
        else:
            run_three_level_suite(config_name="candidate_pass", embed_model="hybrid-512", chunk_size=250, chunk_overlap=50, top_k=5, relevance_floor=0.26, reranker_enabled=True, print_summary=False)

    base_rep = json.loads(b_path.read_text(encoding="utf-8"))
    cand_rep = json.loads(c_path.read_text(encoding="utf-8"))
    thresholds = load_thresholds(cfg_path)
    gate_res = evaluate_release_gate(base_rep, cand_rep, thresholds)
    print(format_gate_table(gate_res), flush=True)
    return 0 if gate_res["overall_decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
