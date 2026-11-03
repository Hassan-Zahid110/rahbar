#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails. CI relies on that exit code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4.
MAX_RECALL5_DROP = 0.05        # recall@5 may fall at most 5 points below the baseline
MIN_CITATION_VALIDITY = 0.95   # at least 95% of citations must match retrieved passages
REQUIRED_ABSTENTION = 1.0      # every must-abstain question must be declined


def load_golden(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    return list(questions)


def ask(client: httpx.Client, api: str, question: str) -> dict[str, Any]:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py)."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    return dict(response.json())


def _section_matches(expected_sec: str, actual_sec: str) -> bool:
    exp = " ".join(expected_sec.strip().lower().split())
    act = " ".join(actual_sec.strip().lower().split())
    if not exp:
        return True
    if exp == act:
        return True
    # Allow prefix/clause match (e.g. golden section "5.4" matching chunk "5.4 Academic Warning")
    if act.startswith(exp + " ") or act.startswith(exp + ":") or act.startswith(exp + "."):
        return True
    if exp.startswith(act + " ") and len(act) >= 3:
        return True
    return False


def _passage_matches(rel: dict[str, Any], ret: dict[str, Any]) -> bool:
    if "chunk_id" in rel and rel["chunk_id"]:
        return str(rel["chunk_id"]).strip() == str(ret.get("chunk_id", "")).strip()
    exp_src = str(rel.get("source", "")).strip().lower()
    act_src = str(ret.get("source", "")).strip().lower()
    if exp_src != act_src:
        return False
    exp_sec = str(rel.get("section", ""))
    act_sec = str(ret.get("section", ""))
    return _section_matches(exp_sec, act_sec)


def recall_at_k(
    relevant: list[dict[str, Any]], retrieved: list[dict[str, Any]], k: int
) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Returns None when the question has no relevant passages (must-abstain questions)."""
    if not relevant:
        return None
    top_k = (retrieved or [])[: max(0, k)]
    hits = sum(1 for rel in relevant if any(_passage_matches(rel, ret) for ret in top_k))
    return round(hits / len(relevant), 6)


def citation_validity(response: dict[str, Any]) -> float | None:
    """Fraction of the response's citations that match a passage in response['retrieved'].
    Returns None when there are no citations."""
    citations = response.get("citations") or []
    if not citations:
        return None
    retrieved = response.get("retrieved") or []
    valid = 0
    for cite in citations:
        cite_src = str(cite.get("source", "")).strip().lower()
        cite_sec = str(cite.get("section", ""))
        if any(
            str(r.get("source", "")).strip().lower() == cite_src
            and _section_matches(cite_sec, str(r.get("section", "")))
            for r in retrieved
        ):
            valid += 1
    return round(valid / len(citations), 6)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall recall@3, recall@5, citation validity, abstention correctness,
    and recall@3 / recall@5 broken down by question type."""
    r3_all: list[float] = []
    r5_all: list[float] = []
    r3_by_type: dict[str, list[float]] = {}
    r5_by_type: dict[str, list[float]] = {}

    total_citations = 0
    valid_citations = 0
    abstain_cases = 0
    abstain_correct = 0
    per_question: list[dict[str, Any]] = []

    for row in rows:
        qtype = str(row.get("type", "ordinary"))
        must_abstain = bool(row.get("must_abstain", False))
        relevant = row.get("relevant") or []
        resp = row.get("response") or {}
        retrieved = resp.get("retrieved") or []
        answered = bool(resp.get("answered_from_context", False))

        r3 = None if must_abstain else recall_at_k(relevant, retrieved, 3)
        r5 = None if must_abstain else recall_at_k(relevant, retrieved, 5)
        c_val = citation_validity(resp)

        if r3 is not None:
            r3_all.append(r3)
            r3_by_type.setdefault(qtype, []).append(r3)
        if r5 is not None:
            r5_all.append(r5)
            r5_by_type.setdefault(qtype, []).append(r5)

        cites = resp.get("citations") or []
        if cites and c_val is not None:
            total_citations += len(cites)
            valid_citations += round(c_val * len(cites))

        if must_abstain:
            abstain_cases += 1
            if not answered:
                abstain_correct += 1

        per_question.append(
            {
                "id": row.get("id"),
                "type": qtype,
                "must_abstain": must_abstain,
                "answered_from_context": answered,
                "recall_at_3": r3,
                "recall_at_5": r5,
                "citation_validity": c_val,
                "seconds": row.get("seconds", 0.0),
            }
        )

    overall_cite_val = (
        round(valid_citations / total_citations, 4) if total_citations > 0 else 1.0
    )
    overall_abstain = (
        round(abstain_correct / abstain_cases, 4) if abstain_cases > 0 else 1.0
    )

    return {
        "recall_at_3": _mean(r3_all),
        "recall_at_5": _mean(r5_all),
        "citation_validity": overall_cite_val,
        "abstention_correctness": overall_abstain,
        "recall_at_3_by_type": {k: _mean(v) for k, v in sorted(r3_by_type.items())},
        "recall_at_5_by_type": {k: _mean(v) for k, v in sorted(r5_by_type.items())},
        "per_question": per_question,
    }


def gate(results: dict[str, Any], baseline: dict[str, Any] | None) -> list[str]:
    """Return one message per failed CI gate (section 5.4); an empty list means pass."""
    failures: list[str] = []

    r5 = float(results.get("recall_at_5", 0.0))
    if baseline and "recall_at_5" in baseline:
        base_r5 = float(baseline["recall_at_5"])
        if r5 < base_r5 - MAX_RECALL5_DROP - 1e-9:
            failures.append(
                f"recall@5 dropped to {r5:.4f}, more than {MAX_RECALL5_DROP:.2f} below baseline {base_r5:.4f}"
            )

    abstain = float(results.get("abstention_correctness", 0.0))
    if abstain < REQUIRED_ABSTENTION - 1e-9:
        failures.append(
            f"abstention_correctness is {abstain:.4f} (required {REQUIRED_ABSTENTION:.2f}: "
            "a must-abstain question was answered from context)"
        )

    cite_val = float(results.get("citation_validity", 0.0))
    if cite_val < MIN_CITATION_VALIDITY - 1e-9:
        failures.append(
            f"citation_validity is {cite_val:.4f}, below minimum {MIN_CITATION_VALIDITY:.2f}"
        )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--golden", type=Path, default=HERE / "golden.yaml")
    parser.add_argument("--baseline", type=Path, default=HERE / "baseline.json")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="write these results as the new baseline",
    )
    args = parser.parse_args()

    questions = load_golden(args.golden)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        for q in questions:
            started = time.perf_counter()
            response = ask(client, args.api, q["question"])
            rows.append(
                {
                    "id": q["id"],
                    "type": q.get("type", "ordinary"),
                    "must_abstain": bool(q.get("must_abstain", False)),
                    "relevant": q.get("relevant") or [],
                    "expect": q.get("expect"),
                    "response": response,
                    "seconds": round(time.perf_counter() - started, 2),
                }
            )
            print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")

    results = summarise(rows)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.exists() else None
    failures = gate(results, baseline)

    results["golden"] = str(args.golden)
    results["questions"] = len(rows)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nresults written to {args.out}")
    if args.update_baseline:
        args.baseline.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"baseline updated: {args.baseline}")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
