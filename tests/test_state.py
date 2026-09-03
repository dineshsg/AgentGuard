"""Tests for src/state.py."""
from __future__ import annotations

from src.retriever import RetrievedDoc
from src.state import (
    MAX_ITERATIONS,
    CritiqueResult,
    ResearchState,
    SubAnswer,
    SubQuestion,
)


def test_max_iterations_constant():
    assert MAX_ITERATIONS == 3


def test_subquestion_defaults():
    sq = SubQuestion(text="What products does Acme Robotics sell?")
    assert sq.mode == "search"
    assert sq.entity_hint is None
    assert sq.doc_type_hint is None


def test_subquestion_explicit_fields():
    sq = SubQuestion(
        text="Compare revenue across all companies",
        mode="aggregate",
        entity_hint="Acme Robotics",
        doc_type_hint="Financial Overview",
    )
    assert sq.mode == "aggregate"
    assert sq.entity_hint == "Acme Robotics"
    assert sq.doc_type_hint == "Financial Overview"


def test_subanswer_defaults_are_independent_per_instance():
    """Mutable dataclass defaults must use default_factory, not a shared
    list/instance — this is the classic dataclass footgun this test
    guards against."""
    sq = SubQuestion(text="q")
    a1 = SubAnswer(sub_question=sq, text="answer one")
    a2 = SubAnswer(sub_question=sq, text="answer two")

    a1.cited_doc_ids.append("doc-1")
    a1.evidence.append(
        RetrievedDoc(doc_id="doc-1", score=1.0, text="t", company="Acme Robotics", doc_type="Products")
    )

    assert a2.cited_doc_ids == []
    assert a2.evidence == []


def test_critique_result_fields():
    result = CritiqueResult(
        approved=True, citation_coverage=0.9, groundedness=0.8, feedback="looks good"
    )
    assert result.approved is True
    assert result.citation_coverage == 0.9
    assert result.groundedness == 0.8
    assert result.feedback == "looks good"


def test_research_state_defaults():
    state = ResearchState(question="What does Acme Robotics sell?")
    assert state.sub_questions == []
    assert state.sub_answers == []
    assert state.final_answer == ""
    assert state.citations == []
    assert state.critique_history == []
    assert state.iteration == 0
    assert state.approved is False
    assert state.trace == []


def test_research_state_instances_do_not_share_mutable_defaults():
    s1 = ResearchState(question="q1")
    s2 = ResearchState(question="q2")

    s1.sub_questions.append(SubQuestion(text="x"))
    s1.trace.append("s1 only")

    assert s2.sub_questions == []
    assert s2.trace == []


def test_log_appends_to_trace_in_order():
    state = ResearchState(question="q")
    state.log("planning started")
    state.log("research complete")

    assert state.trace == ["planning started", "research complete"]
