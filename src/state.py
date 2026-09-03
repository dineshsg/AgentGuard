"""
src/state.py

The core state model for a single research request as it moves through
the agent pipeline (planner -> researcher -> writer -> critic). Every
field here is deliberately plain data (dataclasses only, no behavior
beyond ResearchState.log) so it's trivial for src/orchestrator.py's
generic AgentGraph (a later stage) to pass around, and trivial for
src/governance/governed_orchestrator.py (a much later stage) to wrap in
a GovernedResearchState without needing to understand its internals.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.retriever import RetrievedDoc

MAX_ITERATIONS = 3


@dataclass
class SubQuestion:
    """One decomposed piece of the user's overall question, as produced
    by the Planner agent."""

    text: str
    mode: str = "search"  # "search" | "aggregate" | "targeted"
    entity_hint: str | None = None
    doc_type_hint: str | None = None


@dataclass
class SubAnswer:
    """The Writer agent's answer to one SubQuestion, grounded in the
    evidence the Researcher agent retrieved for it."""

    sub_question: SubQuestion
    text: str
    cited_doc_ids: list[str] = field(default_factory=list)
    evidence: list[RetrievedDoc] = field(default_factory=list)


@dataclass
class CritiqueResult:
    """One pass of the Critic agent's review of the current draft
    answer."""

    approved: bool
    citation_coverage: float
    groundedness: float
    feedback: str


@dataclass
class ResearchState:
    """The full state of one research request as it flows through the
    graph. `trace` is a plain human-readable log of what happened,
    deliberately kept separate from `critique_history` (structured
    scores) so the two read differently in a report: one for a person
    skimming what happened, one for computing metrics."""

    question: str
    sub_questions: list[SubQuestion] = field(default_factory=list)
    sub_answers: list[SubAnswer] = field(default_factory=list)
    final_answer: str = ""
    citations: list[str] = field(default_factory=list)
    critique_history: list[CritiqueResult] = field(default_factory=list)
    iteration: int = 0
    approved: bool = False
    trace: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.trace.append(message)
