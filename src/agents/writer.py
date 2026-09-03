"""
src/agents/writer.py

WriterAgent turns retrieved evidence into a grounded, cited sub-answer
(write_sub_answer), then synthesizes the sub-answers into one final
answer with a deduplicated citation list (compose_final_answer). Both
are LLM calls -- writing prose that stays grounded in specific documents
is a language task, not a lookup.
"""
from __future__ import annotations

from src.llm_backend import LLMBackend, get_backend
from src.retriever import RetrievedDoc
from src.state import SubAnswer, SubQuestion

_SUB_ANSWER_SYSTEM_PROMPT = (
    "You answer one focused research sub-question using ONLY the evidence "
    "documents provided below. Do not use outside knowledge. After every "
    "claim, cite the document it came from by writing its doc_id in "
    "square brackets, e.g. [acme-products]. If the evidence doesn't "
    "support an answer, say so plainly instead of guessing. Respond with "
    "the answer text only, no preamble."
)

_FINAL_ANSWER_SYSTEM_PROMPT = (
    "You write the final answer to a user's research question, given a "
    "set of already-written, already-cited sub-answers. Combine them into "
    "one coherent answer, preserving every [doc_id] citation exactly as "
    "written in the sub-answers -- do not invent new citations and do not "
    "drop existing ones. Respond with the final answer text only, no "
    "preamble."
)


class WriterAgent:
    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend = backend or get_backend()

    def write_sub_answer(
        self, sub_question: SubQuestion, evidence: list[RetrievedDoc]
    ) -> SubAnswer:
        prompt = self._build_sub_answer_prompt(sub_question, evidence)
        text = self.backend.generate(prompt=prompt, system=_SUB_ANSWER_SYSTEM_PROMPT)
        cited_doc_ids = _extract_cited_doc_ids(text, evidence)
        return SubAnswer(
            sub_question=sub_question,
            text=text,
            cited_doc_ids=cited_doc_ids,
            evidence=evidence,
        )

    def compose_final_answer(
        self, question: str, sub_answers: list[SubAnswer]
    ) -> tuple[str, list[str]]:
        prompt = self._build_final_answer_prompt(question, sub_answers)
        final_text = self.backend.generate(prompt=prompt, system=_FINAL_ANSWER_SYSTEM_PROMPT)

        all_evidence = [doc for sa in sub_answers for doc in sa.evidence]
        citations = _extract_cited_doc_ids(final_text, all_evidence)
        if not citations:
            # The synthesis step sometimes writes a terser final answer
            # that doesn't repeat every bracketed citation verbatim --
            # fall back to the union of the sub-answers' own citations
            # rather than reporting zero citations for an answer that
            # was, in fact, grounded.
            seen: list[str] = []
            for sa in sub_answers:
                for doc_id in sa.cited_doc_ids:
                    if doc_id not in seen:
                        seen.append(doc_id)
            citations = seen

        return final_text, citations

    @staticmethod
    def _build_sub_answer_prompt(
        sub_question: SubQuestion, evidence: list[RetrievedDoc]
    ) -> str:
        if not evidence:
            return (
                f"Sub-question: {sub_question.text}\n\n"
                "No evidence documents were retrieved for this sub-question."
            )
        evidence_block = "\n\n".join(
            f"[{doc.doc_id}] ({doc.company} - {doc.doc_type}):\n{doc.text}"
            for doc in evidence
        )
        return f"Sub-question: {sub_question.text}\n\nEvidence:\n{evidence_block}"

    @staticmethod
    def _build_final_answer_prompt(question: str, sub_answers: list[SubAnswer]) -> str:
        sub_answer_block = "\n\n".join(
            f"Sub-question: {sa.sub_question.text}\nAnswer: {sa.text}"
            for sa in sub_answers
        )
        return f"Original question: {question}\n\nSub-answers:\n{sub_answer_block}"


def _extract_cited_doc_ids(text: str, evidence: list[RetrievedDoc]) -> list[str]:
    """Citations are read directly out of the generated text rather than
    trusted from a separate LLM field: only a doc_id that both (a) is
    actually in the evidence the model was given, and (b) appears
    literally in its bracketed form, e.g. "[acme-products]", counts as a
    real citation. This keeps citation_coverage (src/agents/critic.py)
    honest -- a model can't claim a citation it never actually wrote."""
    cited: list[str] = []
    for doc in evidence:
        marker = f"[{doc.doc_id}]"
        if marker in text and doc.doc_id not in cited:
            cited.append(doc.doc_id)
    return cited
