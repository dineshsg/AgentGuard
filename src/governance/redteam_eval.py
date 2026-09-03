"""
src/governance/redteam_eval.py

Runs src/governance/injection_guard.py against
src/governance/redteam_corpus.py's labeled dataset and computes real
precision/recall/F1 for two separate guard surfaces (questions,
documents), plus the pass rate for this project's centerpiece scenario
-- indirect injection via a poisoned retrieved document -- reported as
its OWN named metric, not folded into the general precision/recall
numbers, so a partial pass would be visible on its own rather than
averaged away.

Zero LLM/network dependency: this whole evaluation is deterministic
regex matching against a fixed, labeled corpus, so re-running it always
produces the same numbers -- unlike evaluate.py (the base project's own
eval harness), which depends on whatever LLM backend is configured.

Run directly: `python -m src.governance.redteam_eval`.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.governance.injection_guard import scan_document, scan_question
from src.governance.redteam_corpus import (
    BENIGN_QUESTIONS,
    CLEAN_QUESTION_POISONED_RETRIEVAL_PAIRS,
    DIRECT_ATTACK_QUESTIONS,
    POISONED_DOCUMENTS,
)
from src.retriever import RetrievedDoc, Retriever

REPORT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "reports"
    / "governance"
    / "redteam_eval_report.json"
)


def _real_documents() -> list[RetrievedDoc]:
    """A seam for tests: the module-level function tests monkeypatch
    instead of reaching into Retriever/data/kb_docs.json directly."""
    return Retriever().all_docs()


def _confusion_metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def evaluate_direct_guard() -> dict:
    """scan_question() over DIRECT_ATTACK_QUESTIONS (expected
    flagged=True, label 1) and BENIGN_QUESTIONS (expected flagged=False,
    label 0)."""
    tp = fn = tn = fp = 0

    for question in DIRECT_ATTACK_QUESTIONS:
        if scan_question(question).flagged:
            tp += 1
        else:
            fn += 1

    for question in BENIGN_QUESTIONS:
        if scan_question(question).flagged:
            fp += 1
        else:
            tn += 1

    metrics = _confusion_metrics(tp, fp, tn, fn)
    metrics["n_attack"] = len(DIRECT_ATTACK_QUESTIONS)
    metrics["n_benign"] = len(BENIGN_QUESTIONS)
    return metrics


def evaluate_document_guard() -> dict:
    """scan_document() over POISONED_DOCUMENTS (expected flagged=True,
    label 1) and every real, non-poisoned document in
    data/kb_docs.json (expected flagged=False, label 0)."""
    tp = fn = tn = fp = 0

    for doc in POISONED_DOCUMENTS:
        if scan_document(doc["doc_id"], doc["text"]).flagged:
            tp += 1
        else:
            fn += 1

    real_docs = _real_documents()
    for doc in real_docs:
        if scan_document(doc.doc_id, doc.text).flagged:
            fp += 1
        else:
            tn += 1

    metrics = _confusion_metrics(tp, fp, tn, fn)
    metrics["n_poisoned"] = len(POISONED_DOCUMENTS)
    metrics["n_real_documents_sampled"] = len(real_docs)
    return metrics


def evaluate_indirect_scenario() -> dict:
    """The pass/fail check for this project's centerpiece scenario: for
    every (question, doc_id) pair, the question must scan clean AND its
    paired poisoned document must be flagged. pass_rate is reported on
    its own, separate from the precision/recall metrics above."""
    poisoned_by_id = {doc["doc_id"]: doc for doc in POISONED_DOCUMENTS}
    details = []
    n_passed = 0

    for question, doc_id in CLEAN_QUESTION_POISONED_RETRIEVAL_PAIRS:
        question_flagged = scan_question(question).flagged
        document_flagged = scan_document(doc_id, poisoned_by_id[doc_id]["text"]).flagged
        passed = (not question_flagged) and document_flagged
        if passed:
            n_passed += 1
        details.append(
            {
                "question": question,
                "doc_id": doc_id,
                "question_flagged": question_flagged,
                "document_flagged": document_flagged,
                "passed": passed,
            }
        )

    n_pairs = len(CLEAN_QUESTION_POISONED_RETRIEVAL_PAIRS)
    return {
        "pass_rate": round(n_passed / n_pairs, 4) if n_pairs else 0.0,
        "n_pairs": n_pairs,
        "n_passed": n_passed,
        "details": details,
    }


def run_redteam_eval() -> dict:
    """Runs all three evaluations and returns the combined report dict
    that main() writes to reports/governance/redteam_eval_report.json."""
    return {
        "direct_guard": evaluate_direct_guard(),
        "document_guard": evaluate_document_guard(),
        "indirect_scenario": evaluate_indirect_scenario(),
    }


def main() -> None:
    report = run_redteam_eval()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
