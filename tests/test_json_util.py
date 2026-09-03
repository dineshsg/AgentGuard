"""Tests for src/agents/_json_util.py."""
from __future__ import annotations

import pytest

from src.agents._json_util import LLMResponseParseError, extract_json


def test_extract_json_plain_object():
    assert extract_json('{"a": 1, "b": "two"}') == {"a": 1, "b": "two"}


def test_extract_json_plain_array():
    assert extract_json('[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]


def test_extract_json_strips_markdown_fence():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_ignores_leading_and_trailing_prose():
    text = 'Sure, here is the JSON:\n{"a": 1}\nHope that helps!'
    assert extract_json(text) == {"a": 1}


def test_extract_json_handles_nested_braces():
    text = '{"outer": {"inner": [1, 2, 3]}}'
    assert extract_json(text) == {"outer": {"inner": [1, 2, 3]}}


def test_extract_json_handles_braces_inside_strings():
    text = '{"text": "a set like {1, 2} inside a string"}'
    assert extract_json(text) == {"text": "a set like {1, 2} inside a string"}


def test_extract_json_raises_on_no_json_found():
    with pytest.raises(LLMResponseParseError):
        extract_json("no json here at all")


def test_extract_json_raises_on_unterminated_json():
    with pytest.raises(LLMResponseParseError):
        extract_json('{"a": 1')


def test_extract_json_raises_on_malformed_json():
    with pytest.raises(LLMResponseParseError):
        extract_json('{"a": 1,}')  # trailing comma is invalid JSON
