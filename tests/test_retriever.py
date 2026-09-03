"""Tests for src/retriever.py, run against the real data/kb_docs.json."""
from __future__ import annotations

import json

import pytest

from src.retriever import DEFAULT_KB_PATH, RetrievedDoc, Retriever, retrieve


@pytest.fixture(scope="module")
def kb_docs_raw():
    return json.loads(DEFAULT_KB_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def retriever():
    return Retriever()


def test_kb_docs_json_shape(kb_docs_raw):
    assert len(kb_docs_raw) == 25  # 5 companies x 5 doc types
    for doc in kb_docs_raw:
        assert set(doc.keys()) == {"doc_id", "company", "doc_type", "text"}
        assert doc["text"].strip() != ""


def test_kb_docs_covers_five_companies_and_five_doc_types(kb_docs_raw):
    companies = {d["company"] for d in kb_docs_raw}
    doc_types = {d["doc_type"] for d in kb_docs_raw}
    assert companies == {
        "Acme Robotics", "Borealis Foods", "Cascade Biotech",
        "Meridian Energy", "Solstice Financial",
    }
    assert doc_types == {
        "Products", "Financial Overview", "Risk Factors",
        "Executive Team", "Competitive Landscape",
    }


def test_doc_ids_are_unique(kb_docs_raw):
    doc_ids = [d["doc_id"] for d in kb_docs_raw]
    assert len(doc_ids) == len(set(doc_ids))


def test_retrieve_ranks_relevant_doc_highest(retriever):
    results = retriever.retrieve("robotic arm warehouse automation products", k=3)
    assert len(results) > 0
    assert results[0].doc_id == "acme-products"
    assert all(isinstance(r, RetrievedDoc) for r in results)
    # scores are sorted descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_respects_k(retriever):
    results = retriever.retrieve("company revenue financial", k=2)
    assert len(results) <= 2


def test_retrieve_company_filter_restricts_to_one_company(retriever):
    results = retriever.retrieve("revenue", k=25, company="Cascade Biotech")
    assert len(results) > 0
    assert all(r.company == "Cascade Biotech" for r in results)


def test_retrieve_doc_type_filter_restricts_to_one_type(retriever):
    results = retriever.retrieve("company", k=25, doc_type="Risk Factors")
    assert len(results) > 0
    assert all(r.doc_type == "Risk Factors" for r in results)


def test_retrieve_company_and_doc_type_combined_targets_one_doc(retriever):
    results = retriever.retrieve(
        "solar battery storage", k=5, company="Meridian Energy", doc_type="Products"
    )
    assert len(results) == 1
    assert results[0].doc_id == "meridian-products"


def test_retrieve_drops_zero_score_documents(retriever):
    # a nonsense query sharing no tokens with the corpus should return
    # nothing rather than k arbitrary documents
    results = retriever.retrieve("zzqxnonexistenttoken", k=5)
    assert results == []


def test_retrieve_unknown_company_filter_returns_empty(retriever):
    results = retriever.retrieve("revenue", k=5, company="Nonexistent Corp")
    assert results == []


def test_all_docs_returns_every_document(retriever, kb_docs_raw):
    all_docs = retriever.all_docs()
    assert len(all_docs) == len(kb_docs_raw)
    assert {d.doc_id for d in all_docs} == {d["doc_id"] for d in kb_docs_raw}


def test_module_level_retrieve_matches_default_retriever_instance():
    results = retrieve("battery storage solar", k=1)
    assert len(results) == 1
    assert results[0].doc_id == "meridian-products"
