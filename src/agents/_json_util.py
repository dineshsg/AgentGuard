"""
src/agents/_json_util.py

Shared helper for agents that ask the LLM to respond with structured
JSON (planner.py, critic.py). Local/small models in particular tend to
wrap JSON in markdown code fences or add a sentence of prose before or
after it despite being told not to -- extract_json() tolerates both by
locating the first balanced {...} or [...] value in the text (tracking
string boundaries so braces inside quoted strings don't confuse the
bracket count) rather than assuming the whole response is clean JSON.
"""
from __future__ import annotations

import json
from typing import Any


class LLMResponseParseError(ValueError):
    """Raised when an LLM response can't be read as the expected JSON
    value. Callers are expected to catch this and degrade gracefully
    (see planner.py/critic.py) rather than let a single malformed
    response fail the whole request."""


def extract_json(text: str) -> Any:
    """Find and parse the first JSON object or array in `text`.

    Locates the first '{' or '[' , then scans forward counting bracket
    depth (ignoring brackets inside quoted strings) until it finds the
    matching close, so it recovers cleanly from markdown fences and
    leading/trailing prose around the JSON -- both common with LLMs
    that were asked for "only JSON" but didn't fully comply.
    """
    start = None
    open_char = None
    close_char = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            open_char = ch
            close_char = "}" if ch == "{" else "]"
            break

    if start is None:
        raise LLMResponseParseError(f"No JSON value found in LLM response: {text!r}")

    depth = 0
    in_string = False
    escape = False
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = i
                break

    if end is None:
        raise LLMResponseParseError(f"Unterminated JSON value in LLM response: {text!r}")

    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMResponseParseError(f"Malformed JSON in LLM response: {exc}") from exc
