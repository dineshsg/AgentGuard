"""Tests for build_research_graph / ResearchOrchestrator (src/orchestrator.py)
wired up with the real four agents, run against the real data/kb_docs.json
retriever, with only the LLM calls faked (via tests/conftest.py::FakeBackend)."""
from __future__ import annotations

from src.agents.critic import CriticAgent
from src.agents.planner import PlannerAgent
from src.agents.researcher import ResearcherAgent
from src.agents.writer import WriterAgent
from src.orchestrator import ResearchOrchestrator
from src.state import MAX_ITERATIONS
from tests.conftest import FakeBackend

_PLAN_ONE_TARGETED = (
    '[{"text": "What does Acme Robotics sell?", "mode": "targeted", '
    '"entity_hint": "Acme Robotics", "doc_type_hint": "Products"}]'
)
_WRITER_RESPONSE_WITH_CITATION = "Acme Robotics sells robotic arms and warehouse software [acme-products]."


def _build_orchestrator(planner_backend, writer_backend, critic_backend) -> ResearchOrchestrator:
    return ResearchOrchestrator(
        planner=PlannerAgent(backend=planner_backend),
        researcher=ResearcherAgent(),  # real retriever, real data/kb_docs.json
        writer=WriterAgent(backend=writer_backend),
        critic=CriticAgent(backend=critic_backend),
    )


def test_happy_path_approves_on_first_pass():
    orchestrator = _build_orchestrator(
        planner_backend=FakeBackend(_PLAN_ONE_TARGETED),
        writer_backend=FakeBackend(_WRITER_RESPONSE_WITH_CITATION),
        critic_backend=FakeBackend('{"groundedness": 0.9, "feedback": "well supported"}'),
    )

    state = orchestrator.run("What does Acme Robotics sell?")

    assert state.approved is True
    assert state.iteration == 0
    assert len(state.sub_questions) == 1
    assert len(state.sub_answers) == 1
    assert state.sub_answers[0].cited_doc_ids == ["acme-products"]
    assert state.citations == ["acme-products"]
    assert len(state.critique_history) == 1
    assert state.critique_history[0].approved is True
    assert any("planned 1 sub-question" in entry for entry in state.trace)


def test_revision_loop_retries_then_approves():
    critic_backend = FakeBackend(
        [
            '{"groundedness": 0.3, "feedback": "not enough support"}',
            '{"groundedness": 0.9, "feedback": "now well supported"}',
        ]
    )
    orchestrator = _build_orchestrator(
        planner_backend=FakeBackend(_PLAN_ONE_TARGETED),
        writer_backend=FakeBackend(_WRITER_RESPONSE_WITH_CITATION),
        critic_backend=critic_backend,
    )

    state = orchestrator.run("What does Acme Robotics sell?")

    assert state.approved is True
    assert state.iteration == 1  # revised exactly once
    assert len(state.critique_history) == 2
    assert state.critique_history[0].approved is False
    assert state.critique_history[1].approved is True
    # planner only runs once even though research/write/critique re-ran
    assert len(critic_backend.calls) == 2


def test_exhausts_revision_budget_without_approval():
    # never approves -- exercises the "return best draft anyway" path,
    # NOT the governance layer's stricter human-review routing (a later
    # stage), which is intentionally different behavior.
    critic_backend = FakeBackend('{"groundedness": 0.1, "feedback": "still not supported"}')
    orchestrator = _build_orchestrator(
        planner_backend=FakeBackend(_PLAN_ONE_TARGETED),
        writer_backend=FakeBackend(_WRITER_RESPONSE_WITH_CITATION),
        critic_backend=critic_backend,
    )

    state = orchestrator.run("What does Acme Robotics sell?")

    assert state.approved is False
    assert state.iteration == MAX_ITERATIONS - 1
    assert len(state.critique_history) == MAX_ITERATIONS
    assert all(not c.approved for c in state.critique_history)
    assert state.final_answer != ""  # still returns the best draft, not empty
    assert "out of revision budget" in state.trace[-1]


def test_aggregate_mode_subquestion_gets_larger_retrieval_budget():
    plan_response = (
        '[{"text": "Compare revenue across companies", "mode": "aggregate", '
        '"entity_hint": null, "doc_type_hint": null}]'
    )
    orchestrator = _build_orchestrator(
        planner_backend=FakeBackend(plan_response),
        writer_backend=FakeBackend("A synthesized comparison [acme-financials]."),
        critic_backend=FakeBackend('{"groundedness": 0.8, "feedback": "ok"}'),
    )

    state = orchestrator.run("Compare revenue across companies")

    # base_k defaults to 3; aggregate mode should have retrieved up to
    # base_k * 2 = 6 evidence docs for its one sub-question
    assert len(state.sub_answers) == 1
    assert len(state.sub_answers[0].evidence) <= 6
    assert len(state.sub_answers[0].evidence) > 3


def test_multi_company_comparison_produces_one_subquestion_per_company():
    plan_response = (
        '[{"text": "What is Acme Robotics revenue?", "mode": "targeted", '
        '"entity_hint": "Acme Robotics", "doc_type_hint": "Financial Overview"}, '
        '{"text": "What is Borealis Foods revenue?", "mode": "targeted", '
        '"entity_hint": "Borealis Foods", "doc_type_hint": "Financial Overview"}]'
    )
    orchestrator = _build_orchestrator(
        planner_backend=FakeBackend(plan_response),
        writer_backend=FakeBackend("Revenue was strong [acme-financials]."),
        critic_backend=FakeBackend('{"groundedness": 0.8, "feedback": "ok"}'),
    )

    state = orchestrator.run("Compare Acme Robotics and Borealis Foods revenue")

    assert len(state.sub_questions) == 2
    assert len(state.sub_answers) == 2
    assert state.sub_answers[0].evidence[0].doc_id == "acme-financials"
    assert state.sub_answers[1].evidence[0].doc_id == "borealis-financials"
