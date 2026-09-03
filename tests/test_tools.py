"""Tests for src/tools.py."""
from __future__ import annotations

from src.retriever import RetrievedDoc
from src.state import CritiqueResult, ResearchState, SubAnswer, SubQuestion
from src.tools import format_final_report, latest_critique_scores, unique_companies_cited


def _doc(doc_id: str, company: str, doc_type: str = "Products") -> RetrievedDoc:
    return RetrievedDoc(doc_id=doc_id, score=1.0, text="t", company=company, doc_type=doc_type)


def _approved_state() -> ResearchState:
    doc = _doc("acme-products", "Acme Robotics")
    sub_answer = SubAnswer(
        sub_question=SubQuestion(text="q"),
        text="a [acme-products]",
        cited_doc_ids=["acme-products"],
        evidence=[doc],
    )
    state = ResearchState(question="What does Acme Robotics sell?")
    state.sub_answers = [sub_answer]
    state.final_answer = "Acme Robotics sells robotic arms [acme-products]."
    state.citations = ["acme-products"]
    state.critique_history = [
        CritiqueResult(approved=True, citation_coverage=1.0, groundedness=0.9, feedback="good")
    ]
    state.approved = True
    return state


def test_format_final_report_includes_key_fields():
    report = format_final_report(_approved_state())

    assert "What does Acme Robotics sell?" in report
    assert "acme-products" in report
    assert "Approved: True" in report
    assert "0.90" in report  # groundedness, formatted to 2 decimals


def test_format_final_report_handles_no_citations():
    report = format_final_report(ResearchState(question="q"))
    assert "(none)" in report


def test_latest_critique_scores_returns_zeros_when_no_critique_yet():
    assert latest_critique_scores(ResearchState(question="q")) == {
        "groundedness": 0.0,
        "citation_coverage": 0.0,
    }


def test_latest_critique_scores_returns_latest_entry():
    assert latest_critique_scores(_approved_state()) == {
        "groundedness": 0.9,
        "citation_coverage": 1.0,
    }


def test_unique_companies_cited_returns_companies_in_citation_order():
    assert unique_companies_cited(_approved_state()) == ["Acme Robotics"]


def test_unique_companies_cited_empty_when_no_citations():
    assert unique_companies_cited(ResearchState(question="q")) == []


def test_unique_companies_cited_deduplicates_across_subanswers():
    doc1 = _doc("acme-products", "Acme Robotics")
    doc2 = _doc("acme-financials", "Acme Robotics", doc_type="Financial Overview")
    state = ResearchState(question="q")
    state.sub_answers = [
        SubAnswer(
            sub_question=SubQuestion(text="q1"), text="a",
            cited_doc_ids=["acme-products"], evidence=[doc1],
        ),
        SubAnswer(
            sub_question=SubQuestion(text="q2"), text="b",
            cited_doc_ids=["acme-financials"], evidence=[doc2],
        ),
    ]
    state.citations = ["acme-products", "acme-financials"]

    assert unique_companies_cited(state) == ["Acme Robotics"]


def test_unique_companies_cited_preserves_citation_order_across_companies():
    doc_borealis = _doc("borealis-products", "Borealis Foods")
    doc_acme = _doc("acme-products", "Acme Robotics")
    state = ResearchState(question="q")
    state.sub_answers = [
        SubAnswer(
            sub_question=SubQuestion(text="q1"), text="a",
            cited_doc_ids=["borealis-products"], evidence=[doc_borealis],
        ),
        SubAnswer(
            sub_question=SubQuestion(text="q2"), text="b",
            cited_doc_ids=["acme-products"], evidence=[doc_acme],
        ),
    ]
    state.citations = ["borealis-products", "acme-products"]

    assert unique_companies_cited(state) == ["Borealis Foods", "Acme Robotics"]
