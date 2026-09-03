"""
src/llm_backend.py

Provider-agnostic LLM backend for the Multi-Agent Research Assistant's
agents (Planner / Researcher / Writer / Critic). Supports four backends,
selected via the LLM_PROVIDER environment variable:

    openai    - api.openai.com Chat Completions API
    litellm   - a LiteLLM proxy/router (OpenAI-compatible), or the litellm
                SDK directly if no proxy URL is configured
    ollama    - a local Ollama server (native /api/chat)
    lmstudio  - a local LM Studio server (OpenAI-compatible /v1/chat/completions)

Design commitments:
  - No provider SDK is imported unless that provider is actually selected
    (openai/litellm are lazy-imported; ollama/lmstudio need no SDK at all
    since both expose plain HTTP APIs, reached here via `requests`).
  - No key or URL is ever hardcoded. Every credential/endpoint is read from
    os.environ at call time. See .env.example for the full list.
  - Missing required configuration raises a clear, named LLMBackendError
    naming the missing variable, rather than failing deep inside a request.
  - This module is used ONLY by src/agents/*.py. src/governance/* never
    imports it — the governance layer is regex/dataclass-only, per the
    build plan's explicit zero-LLM-dependency design commitment.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

DEFAULT_TIMEOUT_SECONDS = 60


class LLMBackendError(RuntimeError):
    """Raised when a backend is misconfigured or a call fails."""


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMBackend(ABC):
    """Common interface every provider backend implements."""

    name: str

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Send one prompt (plus optional system message) and return the
        model's text response as a plain string."""


def _require_env(var_name: str, provider: str) -> str:
    value = os.environ.get(var_name, "").strip()
    if not value:
        raise LLMBackendError(
            f"LLM_PROVIDER={provider} requires the {var_name} environment "
            f"variable to be set (see .env.example)."
        )
    return value


def _optional_env(var_name: str, default: str = "") -> str:
    return os.environ.get(var_name, default).strip()


def _build_messages(prompt: str, system: str | None) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))
    return messages


class OpenAIBackend(LLMBackend):
    """https://platform.openai.com Chat Completions API."""

    name = "openai"

    def __init__(self) -> None:
        self.api_key = _require_env("OPENAI_API_KEY", self.name)
        self.model = _optional_env("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str, system: str | None = None) -> str:
        try:
            import openai  # lazy import: only needed for this provider
        except ImportError as exc:
            raise LLMBackendError(
                "LLM_PROVIDER=openai requires the `openai` package. "
                "Install it with: pip install openai"
            ) from exc

        client = openai.OpenAI(api_key=self.api_key)
        messages = _build_messages(prompt, system)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return response.choices[0].message.content or ""


class LiteLLMBackend(LLMBackend):
    """A LiteLLM proxy/router — OpenAI-compatible, can front any provider
    LiteLLM supports (OpenAI, Anthropic, Azure, Bedrock, ...). Reached over
    plain HTTP when LITELLM_BASE_URL is set (no `litellm` package needed to
    just call a running proxy); falls back to the `litellm` Python SDK
    directly when only LITELLM_API_KEY is set."""

    name = "litellm"

    def __init__(self) -> None:
        self.base_url = _optional_env("LITELLM_BASE_URL")
        self.api_key = _optional_env("LITELLM_API_KEY")
        self.model = _optional_env("LITELLM_MODEL", "gpt-4o-mini")
        if not self.base_url and not self.api_key:
            raise LLMBackendError(
                "LLM_PROVIDER=litellm requires either LITELLM_BASE_URL "
                "(a running LiteLLM proxy) or LITELLM_API_KEY (to use the "
                "litellm SDK directly). Neither is set (see .env.example)."
            )

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = _build_messages(prompt, system)
        if self.base_url:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
            }
            resp = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""

        try:
            import litellm  # lazy import: only needed without a proxy URL
        except ImportError as exc:
            raise LLMBackendError(
                "LLM_PROVIDER=litellm without LITELLM_BASE_URL requires the "
                "`litellm` package. Install it with: pip install litellm"
            ) from exc

        response = litellm.completion(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            api_key=self.api_key,
        )
        return response["choices"][0]["message"]["content"] or ""


class OllamaBackend(LLMBackend):
    """A local (or remote) Ollama server's native /api/chat endpoint. No
    key required for a local install — OLLAMA_API_KEY only matters for a
    remote/hosted Ollama instance sitting behind auth."""

    name = "ollama"

    def __init__(self) -> None:
        self.base_url = _optional_env("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = _optional_env("OLLAMA_MODEL", "llama3.1")
        self.api_key = _optional_env("OLLAMA_API_KEY")

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = _build_messages(prompt, system)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        resp = requests.post(
            f"{self.base_url.rstrip('/')}/api/chat",
            json=payload,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"] or ""


class LMStudioBackend(LLMBackend):
    """A local LM Studio server's OpenAI-compatible /v1/chat/completions.
    No key required by default; LMSTUDIO_API_KEY exists only in case
    you've configured one on the server."""

    name = "lmstudio"

    def __init__(self) -> None:
        self.base_url = _optional_env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        self.model = _optional_env("LMSTUDIO_MODEL", "local-model")
        self.api_key = _optional_env("LMSTUDIO_API_KEY")

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = _build_messages(prompt, system)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        resp = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


_PROVIDERS: dict[str, type[LLMBackend]] = {
    "openai": OpenAIBackend,
    "litellm": LiteLLMBackend,
    "ollama": OllamaBackend,
    "lmstudio": LMStudioBackend,
}


def get_backend(provider: str | None = None) -> LLMBackend:
    """Factory: returns the configured LLMBackend.

    provider defaults to the LLM_PROVIDER environment variable (falls back
    to "ollama" if unset, since that's the only one that needs no API key
    for a local dev setup). Raises LLMBackendError for an unknown provider
    name or missing required configuration.
    """
    selected = (provider or os.environ.get("LLM_PROVIDER", "ollama")).strip().lower()
    backend_cls = _PROVIDERS.get(selected)
    if backend_cls is None:
        raise LLMBackendError(
            f"Unknown LLM_PROVIDER={selected!r}. Must be one of: "
            f"{', '.join(sorted(_PROVIDERS))}."
        )
    return backend_cls()
