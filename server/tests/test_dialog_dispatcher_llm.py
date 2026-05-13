"""Tests for server.dialog.dispatcher.LLMBackedDispatcher."""

from __future__ import annotations

from typing import Any

import pytest

from server.dialog.dispatcher import LLMBackedDispatcher
from server.dialog.types import DialogState

# ── Fake Anthropic client ─────────────────────────────────────────────


class _FakeBlock:
    def __init__(self, *, btype: str, input: dict[str, Any] | None = None) -> None:
        self.type = btype
        self.input = input or {}


class _FakeMessage:
    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.return_msg = return_msg
        self.raise_on_create = raise_on_create
        self.captured_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeMessage:
        self.captured_kwargs = kwargs
        if self.raise_on_create:
            raise self.raise_on_create
        assert self.return_msg is not None
        return self.return_msg


class _FakeClient:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.messages = _FakeMessages(
            return_msg=return_msg, raise_on_create=raise_on_create,
        )


def _plan_tool_use(segments: list[dict[str, Any]], rationale: str) -> _FakeMessage:
    return _FakeMessage(
        content=[
            _FakeBlock(
                btype="tool_use",
                input={"segments": segments, "rationale": rationale},
            ),
        ],
    )


# ── Fast path (no LLM call) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_path_name_at_start_skips_llm() -> None:
    client = _FakeClient(return_msg=_plan_tool_use([], "should not be called"))
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Pepper, run the tests", DialogState())
    assert plan.segments[0].speaker == "pepper"
    # Fast path: LLM wasn't called.
    assert client.messages.captured_kwargs == {}


@pytest.mark.asyncio
async def test_fast_path_with_domain_keyword_invokes_llm() -> None:
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "balanced", "mode": "chat",
                 "intent": "design", "handoff_style": "soft"},
                {"speaker": "pepper", "tier": "deep", "mode": "chat",
                 "intent": "implement"},
            ],
            "design then implement",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch(
        "Jarvis, design and then implement the CSV exporter",
        DialogState(),
    )
    # LLM was called (domain keywords detected).
    assert client.messages.captured_kwargs != {}
    assert len(plan.segments) == 2


# ── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_call_returns_valid_plan() -> None:
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "balanced", "mode": "chat",
                 "intent": "compare A and B"},
            ],
            "ambiguous comparison",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we ship Monday or Wednesday?", DialogState())
    assert len(plan.segments) == 1
    assert plan.segments[0].tier == "balanced"
    assert "compare" in plan.segments[0].intent


# ── Fallback paths ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falls_back_on_llm_error() -> None:
    import anthropic
    import httpx

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(status_code=500, request=req)
    client = _FakeClient(
        raise_on_create=anthropic.APIStatusError("server error", response=resp, body=None),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    # Fell back to rule-based: default speaker (Jarvis), single segment.
    assert len(plan.segments) == 1
    assert plan.segments[0].speaker == "jarvis"
    assert "fallback" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_falls_back_on_invalid_schema() -> None:
    """If the LLM returns segments that don't validate (e.g. unknown speaker),
    the dispatcher falls back to the rule-based path."""
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [{"speaker": "bob", "tier": "fast", "mode": "chat", "intent": "x"}],
            "bad output",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert plan.segments[0].speaker == "jarvis"
    assert "fallback" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_falls_back_when_no_tool_use_block() -> None:
    """LLM returned text but didn't invoke the plan tool — fall back."""
    msg = _FakeMessage(content=[_FakeBlock(btype="text")])
    client = _FakeClient(return_msg=msg)
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert "fallback" in plan.rationale.lower()


# ── Slash prefix preserved through LLM path ───────────────────────────


@pytest.mark.asyncio
async def test_slash_prefix_uses_fast_path() -> None:
    """`/codex …` should always use the rule-based fast path so it never
    misroutes due to a quirky LLM output."""
    client = _FakeClient(return_msg=_plan_tool_use([], "should not be called"))
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("/codex add a test", DialogState())
    assert client.messages.captured_kwargs == {}
    assert plan.segments[0].speaker == "pepper"
    assert plan.segments[0].mode == "codex_agent"


# ── Cap enforcement ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falls_back_when_llm_returns_too_many_segments() -> None:
    """Plan schema caps at 3 — anything more is treated as malformed."""
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "fast", "mode": "chat", "intent": "a"},
                {"speaker": "pepper", "tier": "fast", "mode": "chat", "intent": "b"},
                {"speaker": "jarvis", "tier": "fast", "mode": "chat", "intent": "c"},
                {"speaker": "pepper", "tier": "fast", "mode": "chat", "intent": "d"},
            ],
            "too many",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert "fallback" in plan.rationale.lower()
