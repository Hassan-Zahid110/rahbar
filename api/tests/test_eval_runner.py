"""Unit tests for eval/run_eval.py metrics and CI gate logic."""

from __future__ import annotations

import importlib.util
from pathlib import Path

EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"
spec = importlib.util.spec_from_file_location("run_eval", EVAL_PATH)
assert spec and spec.loader
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)


def test_recall_at_k_and_citation_validity() -> None:
    relevant = [{"source": "rules.pdf", "section": "5.4"}]
    retrieved = [
        {"chunk_id": "1", "source": "rules.pdf", "section": "1.21 Attendance", "page": 2, "score": 0.9},
        {"chunk_id": "2", "source": "rules.pdf", "section": "5.4 Academic Warning", "page": 18, "score": 0.85},
    ]
    assert run_eval.recall_at_k(relevant, retrieved, 1) == 0.0
    assert run_eval.recall_at_k(relevant, retrieved, 3) == 1.0
    assert run_eval.recall_at_k([], retrieved, 5) is None

    good_resp = {
        "citations": [{"source": "rules.pdf", "section": "5.4 Academic Warning", "page": 18}],
        "retrieved": retrieved,
    }
    bad_resp = {
        "citations": [{"source": "fabricated.pdf", "section": "9.9", "page": 1}],
        "retrieved": retrieved,
    }
    assert run_eval.citation_validity(good_resp) == 1.0
    assert run_eval.citation_validity(bad_resp) == 0.0


def test_summarise_and_gate_detect_regressions() -> None:
    rows = [
        {
            "id": "q1",
            "type": "ordinary",
            "must_abstain": False,
            "relevant": [{"source": "rules.pdf", "section": "5.4"}],
            "response": {
                "answered_from_context": True,
                "citations": [{"source": "rules.pdf", "section": "5.4 Academic Warning"}],
                "retrieved": [{"source": "rules.pdf", "section": "5.4 Academic Warning"}],
            },
            "seconds": 0.2,
        },
        {
            "id": "q2",
            "type": "abstain",
            "must_abstain": True,
            "relevant": [],
            "response": {"answered_from_context": False, "citations": [], "retrieved": []},
            "seconds": 0.1,
        },
    ]
    summary = run_eval.summarise(rows)
    assert summary["recall_at_5"] == 1.0
    assert summary["citation_validity"] == 1.0
    assert summary["abstention_correctness"] == 1.0
    assert run_eval.gate(summary, {"recall_at_5": 1.0}) == []

    # Simulate regression: recall drops by 10 points and abstention fails
    bad_summary = {
        "recall_at_5": 0.85,
        "citation_validity": 0.90,
        "abstention_correctness": 0.50,
    }
    failures = run_eval.gate(bad_summary, {"recall_at_5": 0.95})
    assert len(failures) == 3

