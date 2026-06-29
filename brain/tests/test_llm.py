"""Tests for the tolerant JSON extraction (no Ollama needed)."""

from __future__ import annotations

import pytest

from pueblo.llm import extract_json


def test_plain_json_object():
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_plain_json_array():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_json_in_code_fence():
    raw = "Sure!\n```json\n{\"rating\": 7}\n```\nHope that helps."
    assert extract_json(raw) == {"rating": 7}


def test_json_with_leading_prose():
    raw = 'The answer is: {"plan": ["wake", "work"]} as requested.'
    assert extract_json(raw) == {"plan": ["wake", "work"]}


def test_nested_braces_balanced():
    raw = 'noise {"outer": {"inner": [1, {"k": "v"}]}} tail'
    assert extract_json(raw) == {"outer": {"inner": [1, {"k": "v"}]}}


def test_string_with_braces_not_confused():
    raw = '{"text": "a } b { c"}'
    assert extract_json(raw) == {"text": "a } b { c"}


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json("there is no json here at all")
