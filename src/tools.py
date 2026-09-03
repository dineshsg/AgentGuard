"""
src/tools.py

Small, dependency-free formatting/reporting helpers shared across the
project's entry points (a future CLI, evaluate.py in a later stage).
Kept separate from orchestrator.py so those entry points don't need to
know anything about AgentGraph or the agents themselves -- they just
hand these functions a finished ResearchState.
"""
from __future__ import annotations

from src.state import ResearchState


def format_final_report(state: ResearchState) -> str:
    """A human-readable summary of a finished research run: the
    question, the final answer, its citations, and whether the critic
    approved it -- the shape a CLI would print to a terminal."""
    lines = [
        f"Question: {state.question}",
        "",
        f"Answer:\n{state.final_answer}",
        "",
        f"Citations: {', '.join(state.citations) if state.citations else '(none)'}",
        f"Approved: {state.approved} (after {state.iteration + 1} iteration(s))",
    ]
    if state.critique_history:
        latest = state.critique_history[-1]
        lines.append(
            f"Groundedness: {latest.groundedness:.2f}  "
            f"Citation coverage: {latest.citation_coverage:.2f}"
        )
    return "\n".join(lines)


def latest_critique_scores(state: ResearchState) -> dict[str, float]:
    """The most recent CritiqueResult's numeric scores, or zeros if the
    state has no critique yet (e.g. inspected mid-run). Used by
    evaluate.py (a later stage) to aggregate scores across an eval set
    without every caller needing to know CritiqueResult's field names."""
    if not state.critique_history:
        return {"groundedness": 0.0, "citation_coverage": 0.0}
    latest = state.critique_history[-1]
    return {"groundedness": latest.groundedness, "citation_coverage": latest.citation_coverage}


def unique_companies_cited(state: ResearchState) -> list[str]:
    """The distinct companies whose documents were actually cited in the
    final answer, in citation order. Useful as a quick sanity check that
    a comparison question actually drew on more than one company."""
    doc_by_id = {
        doc.doc_id: doc for sub_answer in state.sub_answers for doc in sub_answer.evidence
    }
    companies: list[str] = []
    for doc_id in state.citations:
        doc = doc_by_id.get(doc_id)
        if doc and doc.company not in companies:
            companies.append(doc.company)
    return companies
