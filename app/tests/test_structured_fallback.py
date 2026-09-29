"""structured_invoke falls back to JSON prompting when provider structured output fails."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from graph.models import Section3Clause, Section3Results
from llm import structured
from llm.structured import is_transient_llm_error, structured_invoke


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


def test_fallback_repairs_malformed_json():
    reply = """{
      // model commentary
      'provisions': [{"clause": "3(k)", "triggered": false, "evidence_source_ids": ["s1"],},],
      summary: "ok",
    }"""
    fake = FakeChat([reply])
    out = structured_invoke(fake, Section3Results, system="s", user="u")
    assert out.summary == "ok" and out.provisions[0].clause == Section3Clause.K
    assert len(fake.calls) == 1


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


class Overloaded(FakeChat):
    """Structured output works, but the first ``failures`` calls hit a 503."""

    def __init__(self, failures):
        super().__init__([])
        self.failures = failures
        self.attempts = 0

    def with_structured_output(self, schema):
        outer = self

        class _Flaky:
            def invoke(self, messages):
                outer.attempts += 1
                if outer.attempts <= outer.failures:
                    raise RuntimeError("[503] {'message': 'Service temporarily overloaded'}")
                return Section3Results.model_validate(VALID)

        return _Flaky()


def test_transient_errors_are_retried(monkeypatch):
    monkeypatch.setattr(structured, "_sleep", lambda _s: None)
    fake = Overloaded(failures=2)
    assert structured_invoke(fake, Section3Results, system="s", user="u").summary == "ok"
    assert fake.attempts == 3 and fake.calls == []


def test_transient_errors_raise_after_retries_without_json_fallback(monkeypatch):
    monkeypatch.setattr(structured, "_sleep", lambda _s: None)
    fake = Overloaded(failures=99)
    with pytest.raises(RuntimeError, match="503"):
        structured_invoke(fake, Section3Results, system="s", user="u")
    assert fake.calls == []
    assert is_transient_llm_error(RuntimeError("[503] overloaded"))
    assert not is_transient_llm_error(RuntimeError("[400] unknown field `guided_json`"))
