"""Tests for src/agents/critic.py."""
from __future__ import annotations

from src.agents.critic import GROUNDEDNESS_THRESHOLD, CriticAgent
from src.retriever import RetrievedDoc
from src.state import SubAnswer, SubQuestion
from tests.conftest import FakeBackend


def _sub_answer(cited_doc_ids: list[str]) -> SubAnswer:
    doc = RetrievedDoc(
        doc_id="acme-products", score=1.0, text="t", company="Acme Robotics", doc_type="Products"
    )
    return SubAnswer(
        sub_question=SubQuestion(text="q"), text="a", cited_doc_ids=cited_doc_ids, evidence=[doc]
    )


def test_critique_approves_when_groundedness_meets_threshold():
    response = '{"groundedness": 0.85, "feedback": "Well supported by evidence."}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([_sub_answer(["acme-products"])], "final answer", ["acme-products"])

    assert result.approved is True
    assert result.groundedness == 0.85
    assert result.feedback == "Well supported by evidence."
    assert result.citation_coverage == 1.0


def test_critique_rejects_when_groundedness_below_threshold():
    response = '{"groundedness": 0.4, "feedback": "Several claims are unsupported."}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([_sub_answer(["acme-products"])], "final answer", ["acme-products"])

    assert result.approved is False
    assert result.groundedness == 0.4


def test_critique_approval_boundary_is_inclusive():
    response = f'{{"groundedness": {GROUNDEDNESS_THRESHOLD}, "feedback": "borderline"}}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([_sub_answer(["acme-products"])], "x", ["acme-products"])

    assert result.approved is True


def test_citation_coverage_computed_from_subanswers_not_llm():
    sub_answers = [_sub_answer(["acme-products"]), _sub_answer([])]  # 1 of 2 cited
    response = '{"groundedness": 0.9, "feedback": "ok"}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique(sub_answers, "final", ["acme-products"])

    assert result.citation_coverage == 0.5


def test_citation_coverage_zero_for_empty_subanswers_list():
    response = '{"groundedness": 0.9, "feedback": "ok"}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([], "final", [])

    assert result.citation_coverage == 0.0


def test_critique_handles_unparseable_response_gracefully():
    critic = CriticAgent(backend=FakeBackend("not json at all"))

    result = critic.critique([_sub_answer(["acme-products"])], "final", ["acme-products"])

    assert result.approved is False
    assert result.groundedness == 0.0
    assert "Could not parse" in result.feedback


def test_critique_clamps_out_of_range_groundedness():
    response = '{"groundedness": 1.7, "feedback": "over-confident score"}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([_sub_answer(["acme-products"])], "final", ["acme-products"])

    assert result.groundedness == 1.0


def test_critique_clamps_negative_groundedness():
    response = '{"groundedness": -0.3, "feedback": "negative score"}'
    critic = CriticAgent(backend=FakeBackend(response))

    result = critic.critique([_sub_answer(["acme-products"])], "final", ["acme-products"])

    assert result.groundedness == 0.0
