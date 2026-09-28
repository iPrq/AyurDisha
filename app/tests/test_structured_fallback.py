"""structured_invoke falls back to JSON prompting when provider structured output fails."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from graph.models import Section3Clause, Section3Results
from llm.structured import structured_invoke


class FakeChat:
    """Chat model whose provider-side structured output always fails."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def with_structured_output(self, schema):
        class _Broken:
            def invoke(self, messages):
                raise RuntimeError("[400] unknown field `guided_json`")

        return _Broken()

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.replies.pop(0))


VALID = {"provisions": [{"clause": "3(k)", "triggered": False, "evidence_source_ids": ["s1"]}],
         "summary": "ok"}


def test_fallback_parses_plain_json():
    out = structured_invoke(FakeChat([json.dumps(VALID)]), Section3Results, system="s", user="u")
    assert out.provisions[0].clause == Section3Clause.K


def test_fallback_strips_think_blocks_and_code_fences():
    reply = "<think>reasoning here</think>\n```json\n" + json.dumps(VALID) + "\n```"
    out = structured_invoke(FakeChat([reply]), Section3Results, system="s", user="u")
    assert out.summary == "ok"


def test_fallback_finds_json_after_prose():
    out = structured_invoke(FakeChat(["Here you go: " + json.dumps(VALID)]), Section3Results, system="s", user="u")
    assert out.summary == "ok"


def test_fallback_keeps_schema_validators():
    data = {"provisions": [{"clause": "3(g)", "triggered": True}], "summary": "x"}
    out = structured_invoke(FakeChat([json.dumps(data)]), Section3Results, system="s", user="u")
    assert out.provisions == [] and out.rejected_clauses == ["3(g)"]


def test_fallback_retries_once_with_the_validation_error():
    bad = json.dumps({"provisions": [{"clause": "3(k)", "triggered": "maybe"}]})
    fake = FakeChat([bad, json.dumps(VALID)])
    out = structured_invoke(fake, Section3Results, system="s", user="u")
    assert out.summary == "ok" and len(fake.calls) == 2
    assert "not valid for the schema" in fake.calls[1][-1].content


def test_fallback_gives_up_after_two_invalid_replies():
    with pytest.raises(ValueError, match="did not return valid Section3Results"):
        structured_invoke(FakeChat(["no json", "still none"]), Section3Results, system="s", user="u")


def test_structured_path_used_when_it_works():
    class Good(FakeChat):
        def with_structured_output(self, schema):
            class _Ok:
                def invoke(self, messages):
                    return Section3Results.model_validate(VALID)

            return _Ok()

    fake = Good([])
    assert structured_invoke(fake, Section3Results, system="s", user="u").summary == "ok"
    assert fake.calls == []
