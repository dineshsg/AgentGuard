"""
src/agents/planner.py

PlannerAgent decomposes a user's research question into one or more
SubQuestion objects the Researcher/Writer/Critic pipeline can act on.
Backed by an LLM (see src/llm_backend.py) -- deciding how to break a
question apart, and recognizing when it needs several targeted
sub-questions instead of one open-ended one, is exactly the kind of
judgment call a heuristic can't make reliably.
"""
from __future__ import annotations

from src.agents._json_util import LLMResponseParseError, extract_json
from src.llm_backend import LLMBackend, get_backend
from src.state import SubQuestion

_VALID_MODES = {"search", "aggregate", "targeted"}

_SYSTEM_PROMPT = (
    "You are the planning stage of a research assistant that answers "
    "questions about companies using a document knowledge base. Given a "
    "user's question, decompose it into one or more focused sub-questions "
    "a retrieval system can act on.\n\n"
    "Respond with ONLY a JSON array, no prose before or after it. Each "
    "element is an object with these fields:\n"
    '  "text": the sub-question, as a self-contained string\n'
    '  "mode": one of "search" (open-ended lookup), "targeted" (about one '
    'named company and/or one document type), or "aggregate" (needs to '
    "synthesize across several documents, e.g. comparisons or "
    "multi-part summaries)\n"
    '  "entity_hint": the exact company name this sub-question is about, '
    "or null if it isn't scoped to one company\n"
    '  "doc_type_hint": one of "Products", "Financial Overview", '
    '"Risk Factors", "Executive Team", "Competitive Landscape", or null '
    "if not scoped to one document type\n\n"
    "A single-company, single-fact question should usually produce exactly "
    "one sub-question. A comparison across companies should produce one "
    "targeted sub-question per company, each with mode set appropriately."
)


class PlannerAgent:
    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend = backend or get_backend()

    def plan(self, question: str) -> list[SubQuestion]:
        raw_response = self.backend.generate(prompt=question, system=_SYSTEM_PROMPT)

        try:
            parsed = extract_json(raw_response)
        except LLMResponseParseError:
            return self._fallback(question)

        if not isinstance(parsed, list) or not parsed:
            return self._fallback(question)

        sub_questions: list[SubQuestion] = []
        for item in parsed:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            mode = item.get("mode") or "search"
            if mode not in _VALID_MODES:
                mode = "search"
            sub_questions.append(
                SubQuestion(
                    text=str(item["text"]),
                    mode=mode,
                    entity_hint=item.get("entity_hint") or None,
                    doc_type_hint=item.get("doc_type_hint") or None,
                )
            )

        return sub_questions or self._fallback(question)

    @staticmethod
    def _fallback(question: str) -> list[SubQuestion]:
        """Degrade to one open-ended sub-question covering the whole
        original question, rather than failing the request outright,
        when the LLM's response can't be read as a usable plan."""
        return [SubQuestion(text=question, mode="search")]
