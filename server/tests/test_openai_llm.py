"""Tests for server.pipelines.openai_llm — OpenAILLM (mocked client)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.pipelines.openai_llm import (
    OpenAILLM,
    _spoken_error_for,
    max_tokens_for,
    parse_prefix,
)

# ─── parse_prefix ─────────────────────────────────────────────────────


def test_parse_prefix_no_prefix_returns_default() -> None:
    model, content = parse_prefix("hello world", default="gpt-5-mini")
    assert model == "gpt-5-mini"
    assert content == "hello world"


def test_parse_prefix_gpt_routes_to_default_gpt() -> None:
    model, content = parse_prefix("/gpt hello", default="gpt-5-mini")
    assert model == "gpt-5"
    assert content == "hello"


def test_parse_prefix_codex_routes_to_codex_model() -> None:
    model, content = parse_prefix("/codex add a test", default="gpt-5-mini")
    assert model == "gpt-5-codex"
    assert content == "add a test"


def test_parse_prefix_unknown_passes_through() -> None:
    model, content = parse_prefix("/banana split", default="gpt-5-mini")
    assert model == "gpt-5-mini"
    assert content == "/banana split"


def test_parse_prefix_case_insensitive() -> None:
    """Match the dispatcher's case-folding so /CODEX and /Gpt route correctly."""
    model, content = parse_prefix("/CODEX fix tests", default="gpt-5-mini")
    assert model == "gpt-5-codex"
    assert content == "fix tests"

    model, content = parse_prefix("/Gpt explain", default="gpt-5-mini")
    assert model == "gpt-5"
    assert content == "explain"


# ─── max_tokens_for ───────────────────────────────────────────────────


def test_max_tokens_scales_with_tier() -> None:
    # Mirrors the Claude scaling pattern: deeper models get more headroom.
    assert max_tokens_for("gpt-5-mini", base=1024) == 1024
    assert max_tokens_for("gpt-5", base=1024) == 2048
    assert max_tokens_for("gpt-5-codex", base=1024) == 4096
    assert max_tokens_for("unknown-id", base=1024) == 1024


# ─── _spoken_error_for ────────────────────────────────────────────────


def test_spoken_error_rate_limit() -> None:
    import openai
    exc = openai.RateLimitError(
        "rate", response=_fake_resp(429), body=None,
    )
    assert _spoken_error_for(exc) == "Rate limit. Try again shortly."


def test_spoken_error_auth() -> None:
    import openai
    exc = openai.AuthenticationError(
        "auth", response=_fake_resp(401), body=None,
    )
    assert _spoken_error_for(exc) == "API key is invalid."


def test_spoken_error_unknown_falls_back_to_generic() -> None:
    import openai
    exc = openai.APIError("?", request=_fake_req(), body=None)
    msg = _spoken_error_for(exc)
    assert "API" in msg


# ─── OpenAILLM.stream ─────────────────────────────────────────────────


class _FakeDelta:
    def __init__(self, text: str) -> None:
        self.content = text


class _FakeChoice:
    def __init__(self, text: str) -> None:
        self.delta = _FakeDelta(text)


class _FakeChunk:
    def __init__(self, text: str) -> None:
        self.choices = [_FakeChoice(text)]


class _FakeStream:
    """Async iterator that yields `_FakeChunk` instances."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = list(deltas)

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> _FakeChunk:
        if not self._deltas:
            raise StopAsyncIteration
        return _FakeChunk(self._deltas.pop(0))


class _FakeCompletions:
    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas
        self.captured_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.captured_kwargs = kwargs
        return _FakeStream(self._deltas)


class _FakeChat:
    def __init__(self, deltas: list[str]) -> None:
        self.completions = _FakeCompletions(deltas)


class _FakeClient:
    def __init__(self, deltas: list[str]) -> None:
        self.chat = _FakeChat(deltas)


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_openai_llm_streams_concatenates_deltas() -> None:
    client = _FakeClient(["Hel", "lo,", " Max."])
    llm = OpenAILLM(default_model="gpt-5-mini", max_tokens=1024, client=client)
    out = await _collect(
        llm.stream(history=[{"role": "user", "content": "hi"}], user_text="hi")
    )
    assert "".join(out) == "Hello, Max."


@pytest.mark.asyncio
async def test_openai_llm_uses_prefix_model_and_strips_content() -> None:
    client = _FakeClient(["ok"])
    llm = OpenAILLM(default_model="gpt-5-mini", max_tokens=1024, client=client)
    await _collect(
        llm.stream(
            history=[{"role": "user", "content": "/codex write a test"}],
            user_text="/codex write a test",
        )
    )
    captured = client.chat.completions.captured_kwargs
    assert captured["model"] == "gpt-5-codex"
    assert captured["max_tokens"] == 4096  # deep tier scaling
    # Last user message has the prefix stripped.
    last = captured["messages"][-1]
    assert last == {"role": "user", "content": "write a test"}


@pytest.mark.asyncio
async def test_openai_llm_extra_context_concatenates_to_system() -> None:
    client = _FakeClient(["ok"])
    llm = OpenAILLM(
        default_model="gpt-5-mini",
        max_tokens=1024,
        system_prompt="base sys",
        client=client,
    )
    await _collect(
        llm.stream(
            history=[{"role": "user", "content": "hi"}],
            user_text="hi",
            extra_context="memory: yesterday we shipped X.",
        )
    )
    captured = client.chat.completions.captured_kwargs
    sys_msgs = [m for m in captured["messages"] if m["role"] == "system"]
    assert any("base sys" in m["content"] for m in sys_msgs)
    assert any("memory" in m["content"] for m in sys_msgs)


# ─── helpers ──────────────────────────────────────────────────────────


def _fake_req():
    import httpx
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def _fake_resp(status: int):
    import httpx
    return httpx.Response(status_code=status, request=_fake_req())
