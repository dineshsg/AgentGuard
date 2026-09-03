"""
src/agents/critic.py

CriticAgent reviews a draft final answer against the evidence used to
produce it and decides whether it's good enough to stop revising.

citation_coverage is computed deterministically from the sub-answers'
own citation lists -- it's a plain counting problem, not something to
ask an LLM to judge. groundedness is LLM-judged: assessing whether prose
is actually supported by its cited evidence needs semantic
understanding a citation count alone can't give.

GROUNDEDNESS_THRESHOLD is this agent's OWN approval bar -- "good enough
for the agent to stop revising itself". This is deliberately looser than
the governance layer's HUMAN_REVIEW_GROUNDEDNESS_THRESHOLD (a much later
stage), which gates "good enough to hand to an end user without a human
in the loop".
"""
from __future__ import annotations

from src.agents._json_util import LLMResponseParseError, extract_json
from src.llm_backend import LLMBackend, get_backend
from src.state import CritiqueResult, SubAnswer

GROUNDEDNESS_THRESHOLD = 0.6

_SYSTEM_PROMPT = (
    "You are a strict fact-checking critic reviewing a research answer "
    "against the evidence it cites. Judge only whether the answer's "
    "claims are actually supported by the evidence -- not writing style.\n\n"
    "Respond with ONLY a JSON object, no prose before or after it, with "
    "these fields:\n"
    '  "groundedness": a number from 0.0 to 1.0, where 1.0 means every '
    "claim in the answer is directly supported by the cited evidence and "
    "0.0 means the answer is unsupported or contradicts the evidence\n"
    '  "feedback": one or two sentences explaining the score, specific '
    "enough to guide a revision"
)


class CriticAgent:
    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend = backend or get_backend()

    def critique(
        self,
        sub_answers: list[SubAnswer],
        final_answer: str,
        citations: list[str],
    ) -> CritiqueResult:
        citation_coverage = _compute_citation_coverage(sub_answers)

        prompt = self._build_prompt(sub_answers, final_answer, citations)
        raw_response = self.backend.generate(prompt=prompt, system=_SYSTEM_PROMPT)
        groundedness, feedback = self._parse_response(raw_response)

        return CritiqueResult(
            approved=groundedness >= GROUNDEDNESS_THRESHOLD,
            citation_coverage=citation_coverage,
            groundedness=groundedness,
            feedback=feedback,
        )

    @staticmethod
    def _parse_response(raw_response: str) -> tuple[float, str]:
        try:
            parsed = extract_json(raw_response)
        except LLMResponseParseError:
            return 0.0, f"Could not parse critic response as JSON: {raw_response[:200]!r}"

        if not isinstance(parsed, dict):
            return 0.0, f"Critic response was not a JSON object: {raw_response[:200]!r}"

        try:
            groundedness = float(parsed.get("groundedness", 0.0))
        except (TypeError, ValueError):
            groundedness = 0.0
        groundedness = max(0.0, min(1.0, groundedness))  # clamp, don't trust the model's range

        feedback = str(parsed.get("feedback") or "No feedback provided.")
        return groundedness, feedback

    @staticmethod
    def _build_prompt(
        sub_answers: list[SubAnswer], final_answer: str, citations: list[str]
    ) -> str:
        evidence_block = "\n\n".join(
            f"[{doc.doc_id}]: {doc.text}" for sa in sub_answers for doc in sa.evidence
        )
        return (
            f"Final answer to review:\n{final_answer}\n\n"
            f"Citations used: {citations}\n\n"
            f"Evidence available:\n{evidence_block}"
        )


def _compute_citation_coverage(sub_answers: list[SubAnswer]) -> float:
    """Fraction of sub-answers that cite at least one document. Exact
    and reproducible -- deliberately not an LLM judgment."""
    if not sub_answers:
        return 0.0
    cited_count = sum(1 for sa in sub_answers if sa.cited_doc_ids)
    return cited_count / len(sub_answers)
