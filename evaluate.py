"""
evaluate.py

Runs the full research pipeline (src/orchestrator.py's
ResearchOrchestrator) over every question in data/eval_set.json and
writes real, aggregate metrics to reports/eval_report.json:

  keyword_recall     - average fraction of an eval item's
                        expected_keywords found (case-insensitive
                        substring match) in that run's final answer
  citation_coverage   - average of each run's latest CritiqueResult
                        .citation_coverage
  groundedness         - average of each run's latest CritiqueResult
                        .groundedness
  approval_rate         - fraction of eval items where state.approved
                        is True

Run directly: `python evaluate.py`. Uses whatever LLM_PROVIDER/.env is
configured (see .env.example) -- there is no mock mode here by design;
the whole point of this script is to produce real numbers from a real
model, unlike every agent's own test suite (which fakes the LLM
entirely). run_evaluation() takes an optional pre-built orchestrator so
tests can still exercise the aggregation logic without a live model.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src.agents.critic import CriticAgent
from src.agents.planner import PlannerAgent
from src.agents.researcher import ResearcherAgent
from src.agents.writer import WriterAgent
from src.orchestrator import ResearchOrchestrator
from src.state import ResearchState
from src.tools import latest_critique_scores

EVAL_SET_PATH = Path(__file__).resolve().parent / "data" / "eval_set.json"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "eval_report.json"


def _keyword_recall(state: ResearchState, expected_keywords: list[str]) -> float:
    """Fraction of expected_keywords that appear, case-insensitively, as
    a substring of the final answer. A question with no expected
    keywords trivially scores 1.0 rather than dividing by zero."""
    if not expected_keywords:
        return 1.0
    haystack = state.final_answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in haystack)
    return hits / len(expected_keywords)


def _default_orchestrator() -> ResearchOrchestrator:
    return ResearchOrchestrator(
        planner=PlannerAgent(),
        researcher=ResearcherAgent(),
        writer=WriterAgent(),
        critic=CriticAgent(),
    )


def run_evaluation(
    eval_set_path: Path = EVAL_SET_PATH,
    orchestrator: ResearchOrchestrator | None = None,
) -> dict:
    """Run every eval_set.json item through `orchestrator` (a real,
    LLM-backed one by default) and return the full report dict. Accepts
    a pre-built orchestrator so tests can inject one wired to a fake
    LLM backend and verify the aggregation math without a live model."""
    eval_items = json.loads(Path(eval_set_path).read_text(encoding="utf-8"))
    orchestrator = orchestrator or _default_orchestrator()

    per_item_results = []
    for item in eval_items:
        start = time.monotonic()
        state = orchestrator.run(item["question"])
        elapsed = time.monotonic() - start

        scores = latest_critique_scores(state)
        keyword_recall = _keyword_recall(state, item.get("expected_keywords", []))

        per_item_results.append(
            {
                "id": item["id"],
                "question": item["question"],
                "approved": state.approved,
                "iterations_used": state.iteration + 1,
                "keyword_recall": round(keyword_recall, 4),
                "groundedness": round(scores["groundedness"], 4),
                "citation_coverage": round(scores["citation_coverage"], 4),
                "citations": state.citations,
                "elapsed_seconds": round(elapsed, 3),
            }
        )

    n = len(per_item_results)

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in per_item_results) / n, 4) if n else 0.0

    summary = {
        "n_questions": n,
        "keyword_recall": _avg("keyword_recall"),
        "citation_coverage": _avg("citation_coverage"),
        "groundedness": _avg("groundedness"),
        "approval_rate": round(sum(1 for r in per_item_results if r["approved"]) / n, 4)
        if n
        else 0.0,
        "mean_latency_seconds": _avg("elapsed_seconds"),
    }

    return {"summary": summary, "results": per_item_results}


def main() -> None:
    report = run_evaluation()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
