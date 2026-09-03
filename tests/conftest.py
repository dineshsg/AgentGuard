"""Shared test fixtures. FakeBackend stands in for a real LLMBackend so
agent tests never make live network/LLM calls."""
from __future__ import annotations

from src.llm_backend import LLMBackend


class FakeBackend(LLMBackend):
    """A canned-response LLMBackend for tests.

    Give it one response (returned on every call) or a list of
    responses (returned in order, one per call -- the last one repeats
    if generate() is called more times than there are responses). Every
    call is recorded in `.calls` so tests can assert on the prompt/
    system text an agent actually sent.
    """

    name = "fake"

    def __init__(self, responses: str | list[str]) -> None:
        self._responses = responses if isinstance(responses, list) else [responses]
        self.calls: list[dict] = []

    def generate(self, prompt: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "system": system})
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]
