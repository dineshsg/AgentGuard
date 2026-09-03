"""Tests for src/agents/writer.py."""
from __future__ import annotations

from src.agents.writer import WriterAgent
from src.retriever import RetrievedDoc
from src.state import SubAnswer, SubQuestion
from tests.conftest import FakeBackend


def _doc(doc_id: str, text: str = "some evidence text") -> RetrievedDoc:
    return RetrievedDoc(
        doc_id=doc_id, score=1.0, text=text, company="Acme Robotics", doc_type="Products"
    )


def test_write_sub_answer_extracts_only_real_citations():
    evidence = [_doc("acme-products"), _doc("acme-financials")]
    response = (
        "Acme Robotics sells robotic arms [acme-products]. "
        "It also made up a citation [not-a-real-doc]."
    )
    writer = WriterAgent(backend=FakeBackend(response))
    sub_question = SubQuestion(text="What does Acme Robotics sell?")

    sub_answer = writer.write_sub_answer(sub_question, evidence)

    assert sub_answer.text == response
    assert sub_answer.cited_doc_ids == ["acme-products"]
    assert sub_answer.evidence == evidence


def test_write_sub_answer_with_no_evidence_still_returns_subanswer():
    writer = WriterAgent(backend=FakeBackend("No evidence was available to answer this."))
    sub_question = SubQuestion(text="unanswerable question")

    sub_answer = writer.write_sub_answer(sub_question, evidence=[])

    assert sub_answer.cited_doc_ids == []
    assert sub_answer.evidence == []


def test_compose_final_answer_extracts_citations_from_final_text():
    evidence = [_doc("acme-products"), _doc("borealis-products")]
    sub_answers = [
        SubAnswer(
            sub_question=SubQuestion(text="q1"),
            text="Acme Robotics sells arms [acme-products].",
            cited_doc_ids=["acme-products"],
            evidence=[evidence[0]],
        ),
        SubAnswer(
            sub_question=SubQuestion(text="q2"),
            text="Borealis Foods sells snacks [borealis-products].",
            cited_doc_ids=["borealis-products"],
            evidence=[evidence[1]],
        ),
    ]
    final_text = (
        "Acme Robotics sells robotic arms [acme-products] and Borealis Foods "
        "sells snacks [borealis-products]."
    )
    writer = WriterAgent(backend=FakeBackend(final_text))

    answer, citations = writer.compose_final_answer(
        "Compare Acme and Borealis products", sub_answers
    )

    assert answer == final_text
    assert citations == ["acme-products", "borealis-products"]


def test_compose_final_answer_falls_back_to_subanswer_citations_when_final_text_has_none():
    sub_answers = [
        SubAnswer(
            sub_question=SubQuestion(text="q1"),
            text="answer with citation [acme-products]",
            cited_doc_ids=["acme-products"],
            evidence=[_doc("acme-products")],
        )
    ]
    # final answer text doesn't repeat the bracketed citation verbatim
    writer = WriterAgent(backend=FakeBackend("A terser final answer with no brackets."))

    answer, citations = writer.compose_final_answer("q", sub_answers)

    assert citations == ["acme-products"]


def test_compose_final_answer_deduplicates_citations():
    sub_answers = [
        SubAnswer(
            sub_question=SubQuestion(text="q1"),
            text="a [acme-products]",
            cited_doc_ids=["acme-products"],
            evidence=[_doc("acme-products")],
        ),
        SubAnswer(
            sub_question=SubQuestion(text="q2"),
            text="b [acme-products]",
            cited_doc_ids=["acme-products"],
            evidence=[_doc("acme-products")],
        ),
    ]
    final_text = "Both sub-answers point to [acme-products] and [acme-products] again."
    writer = WriterAgent(backend=FakeBackend(final_text))

    _, citations = writer.compose_final_answer("q", sub_answers)

    assert citations == ["acme-products"]
