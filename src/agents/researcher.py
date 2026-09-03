"""
src/agents/researcher.py

ResearcherAgent retrieves evidence for one SubQuestion. Deliberately has
no LLM dependency at all -- retrieval is the deterministic TF-IDF lookup
in src/retriever.py, scoped by the SubQuestion's entity_hint/
doc_type_hint whenever the Planner set them.
"""
from __future__ import annotations

from src.retriever import RetrievedDoc, Retriever, get_default_retriever
from src.state import SubQuestion


class ResearcherAgent:
    def __init__(self, retriever: Retriever | None = None) -> None:
        self.retriever = retriever or get_default_retriever()

    def research(self, sub_question: SubQuestion, k: int) -> list[RetrievedDoc]:
        return self.retriever.retrieve(
            query=sub_question.text,
            k=k,
            company=sub_question.entity_hint,
            doc_type=sub_question.doc_type_hint,
        )
