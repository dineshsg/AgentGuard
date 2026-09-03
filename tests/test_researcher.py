"""Tests for src/agents/researcher.py."""
from __future__ import annotations

from src.agents.researcher import ResearcherAgent
from src.retriever import Retriever
from src.state import SubQuestion


def test_research_returns_retrieved_docs_for_plain_search():
    researcher = ResearcherAgent()
    sub_question = SubQuestion(text="robotic arm warehouse automation", mode="search")

    results = researcher.research(sub_question, k=3)

    assert len(results) > 0
    assert results[0].doc_id == "acme-products"


def test_research_uses_entity_hint_and_doc_type_hint_as_filters():
    researcher = ResearcherAgent()
    sub_question = SubQuestion(
        text="solar battery storage",
        mode="targeted",
        entity_hint="Meridian Energy",
        doc_type_hint="Products",
    )

    results = researcher.research(sub_question, k=5)

    assert len(results) == 1
    assert results[0].doc_id == "meridian-products"


def test_research_respects_k():
    researcher = ResearcherAgent()
    sub_question = SubQuestion(text="revenue company", mode="search")

    results = researcher.research(sub_question, k=2)

    assert len(results) <= 2


def test_research_uses_injected_retriever_not_the_default(tmp_path):
    kb_path = tmp_path / "mini_kb.json"
    kb_path.write_text(
        '[{"doc_id": "x-1", "company": "X Corp", "doc_type": "Products", '
        '"text": "X Corp sells widgets."}]',
        encoding="utf-8",
    )
    researcher = ResearcherAgent(retriever=Retriever(kb_path=kb_path))
    sub_question = SubQuestion(text="widgets", mode="search")

    results = researcher.research(sub_question, k=3)

    assert len(results) == 1
    assert results[0].doc_id == "x-1"
