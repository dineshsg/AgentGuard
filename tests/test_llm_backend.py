"""Tests for src/llm_backend.py.

No live network calls: OpenAI/LiteLLM SDK calls and the Ollama/LM Studio
HTTP requests are all monkeypatched. These tests verify configuration
validation, provider selection, and request/response wiring — not actual
model output.
"""
from __future__ import annotations

import pytest

from src import llm_backend as lb


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Every test starts with none of the provider env vars set, so each
    test controls its own configuration explicitly."""
    for var in [
        "LLM_PROVIDER",
        "OPENAI_API_KEY", "OPENAI_MODEL",
        "LITELLM_BASE_URL", "LITELLM_API_KEY", "LITELLM_MODEL",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_API_KEY",
        "LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "LMSTUDIO_API_KEY",
    ]:
        monkeypatch.delenv(var, raising=False)


class FakeResponse:
    def __init__(self, json_body, status_ok=True):
        self._json = json_body
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise lb.requests.HTTPError("boom")

    def json(self):
        return self._json


# --- get_backend() provider selection --------------------------------------

def test_get_backend_unknown_provider_raises():
    with pytest.raises(lb.LLMBackendError, match="Unknown LLM_PROVIDER"):
        lb.get_backend("not-a-real-provider")


def test_get_backend_defaults_to_ollama_when_unset():
    backend = lb.get_backend()
    assert isinstance(backend, lb.OllamaBackend)
    assert backend.name == "ollama"


def test_get_backend_respects_env_var(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    backend = lb.get_backend()
    assert isinstance(backend, lb.LMStudioBackend)


def test_get_backend_explicit_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    backend = lb.get_backend("ollama")
    assert isinstance(backend, lb.OllamaBackend)


# --- OpenAI ------------------------------------------------------------

def test_openai_backend_requires_api_key():
    with pytest.raises(lb.LLMBackendError, match="OPENAI_API_KEY"):
        lb.OpenAIBackend()


def test_openai_backend_constructs_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    backend = lb.OpenAIBackend()
    assert backend.api_key == "sk-test-123"
    assert backend.model == "gpt-4o-mini"  # default


# --- LiteLLM -------------------------------------------------------------

def test_litellm_backend_requires_base_url_or_api_key():
    with pytest.raises(lb.LLMBackendError, match="LITELLM_BASE_URL"):
        lb.LiteLLMBackend()


def test_litellm_backend_via_proxy_http(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LITELLM_MODEL", "gpt-4o-mini")
    backend = lb.LiteLLMBackend()

    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse({"choices": [{"message": {"content": "hello from litellm proxy"}}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    result = backend.generate("What products does Acme sell?", system="Be concise.")

    assert result == "hello from litellm proxy"
    assert captured["url"] == "http://localhost:4000/chat/completions"
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][1]["content"] == "What products does Acme sell?"


# --- Ollama --------------------------------------------------------------

def test_ollama_backend_needs_no_key_by_default():
    backend = lb.OllamaBackend()  # must not raise
    assert backend.base_url == "http://localhost:11434"
    assert backend.model == "llama3.1"


def test_ollama_backend_generate_calls_native_chat_endpoint(monkeypatch):
    backend = lb.OllamaBackend()
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse({"message": {"content": "hello from ollama"}})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    result = backend.generate("summarize this")

    assert result == "hello from ollama"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["stream"] is False


# --- LM Studio -----------------------------------------------------------

def test_lmstudio_backend_needs_no_key_by_default():
    backend = lb.LMStudioBackend()  # must not raise
    assert backend.base_url == "http://localhost:1234/v1"


def test_lmstudio_backend_generate_calls_openai_compatible_endpoint(monkeypatch):
    backend = lb.LMStudioBackend()
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        return FakeResponse({"choices": [{"message": {"content": "hello from lm studio"}}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    result = backend.generate("summarize this")

    assert result == "hello from lm studio"
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"


def test_lmstudio_backend_sends_bearer_header_when_key_set(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_API_KEY", "local-secret")
    backend = lb.LMStudioBackend()
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    backend.generate("x")

    assert captured["headers"]["Authorization"] == "Bearer local-secret"
