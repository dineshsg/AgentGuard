"""
src/retriever.py

A lightweight, dependency-free document retriever over the local
knowledge base (data/kb_docs.json). Scores documents against a query
using TF-IDF-weighted term overlap — pure stdlib (re + collections +
math), no numpy/sklearn/embeddings — consistent with this project's
zero-new-third-party-dependency design for anything that isn't the LLM
call itself (see src/llm_backend.py).

Retrieval supports the three SubQuestion.mode values defined in
src/state.py:
  - "search":    free-text relevance ranking over the whole corpus
  - "targeted":  filters to one company (entity_hint) and/or doc_type
                 (doc_type_hint) before ranking
  - "aggregate": same filtering as "targeted", but callers (the
                 Researcher agent, in a later stage) are expected to
                 pass a larger k, since synthesizing an aggregate
                 answer typically needs more than one supporting doc
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "kb_docs.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class RetrievedDoc:
    doc_id: str
    score: float
    text: str
    company: str
    doc_type: str


class Retriever:
    """Loads data/kb_docs.json once and serves TF-IDF-ranked retrieval
    over it. A fresh instance can be pointed at any kb_path, which the
    red-team corpus (a later stage) uses to score poisoned documents
    without touching the base knowledge base file."""

    def __init__(self, kb_path: str | Path = DEFAULT_KB_PATH) -> None:
        self.kb_path = Path(kb_path)
        self._docs: list[dict] = json.loads(self.kb_path.read_text(encoding="utf-8"))
        self._doc_tokens: dict[str, list[str]] = {
            d["doc_id"]: _tokenize(d["text"]) for d in self._docs
        }
        self._doc_freq: Counter[str] = Counter()
        for tokens in self._doc_tokens.values():
            self._doc_freq.update(set(tokens))
        self._n_docs = len(self._docs)

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        # +1 smoothing: an unseen query term contributes a small non-zero
        # weight instead of raising or dominating the score.
        return math.log((self._n_docs + 1) / (df + 1)) + 1.0

    def _score(self, query_tokens: list[str], doc_id: str) -> float:
        doc_tokens = self._doc_tokens[doc_id]
        if not doc_tokens or not query_tokens:
            return 0.0
        doc_tf = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        score = 0.0
        for term in query_tokens:
            tf = doc_tf.get(term, 0)
            if tf == 0:
                continue
            score += (tf / doc_len) * self._idf(term)
        return score

    def retrieve(
        self,
        query: str,
        k: int = 3,
        company: str | None = None,
        doc_type: str | None = None,
    ) -> list[RetrievedDoc]:
        """Rank documents by TF-IDF overlap with `query`, optionally
        restricted to one `company` and/or `doc_type` first. Documents
        that score 0 (no query term appears in them at all) are dropped
        rather than returned as noise."""
        query_tokens = _tokenize(query)
        candidates = self._docs
        if company:
            candidates = [d for d in candidates if d["company"] == company]
        if doc_type:
            candidates = [d for d in candidates if d["doc_type"] == doc_type]

        scored = [(self._score(query_tokens, d["doc_id"]), d) for d in candidates]
        scored = [(s, d) for s, d in scored if s > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [
            RetrievedDoc(
                doc_id=d["doc_id"],
                score=round(s, 6),
                text=d["text"],
                company=d["company"],
                doc_type=d["doc_type"],
            )
            for s, d in scored[:k]
        ]

    def all_docs(self) -> list[RetrievedDoc]:
        """Every document in the corpus as RetrievedDoc, score=0.0 (no
        query was involved). Used by evaluation/red-team code (a later
        stage) that needs to sample real, non-poisoned documents."""
        return [
            RetrievedDoc(
                doc_id=d["doc_id"], score=0.0, text=d["text"],
                company=d["company"], doc_type=d["doc_type"],
            )
            for d in self._docs
        ]


_default_retriever: Retriever | None = None


def get_default_retriever() -> Retriever:
    """Lazily-constructed singleton over the base knowledge base, so
    repeated calls to the module-level retrieve() below don't re-read
    and re-index data/kb_docs.json every time."""
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = Retriever()
    return _default_retriever


def retrieve(
    query: str,
    k: int = 3,
    company: str | None = None,
    doc_type: str | None = None,
) -> list[RetrievedDoc]:
    """Module-level convenience wrapper around the default Retriever."""
    return get_default_retriever().retrieve(query, k=k, company=company, doc_type=doc_type)
