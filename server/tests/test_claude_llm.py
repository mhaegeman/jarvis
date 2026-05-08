"""Unit tests for ClaudeLLM (v0.2 α)."""

from __future__ import annotations

import pytest

from server.pipelines.claude_llm import PREFIX_MAP, parse_prefix


HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-7"


class TestParsePrefix:
    def test_no_prefix_returns_default(self):
        assert parse_prefix("How's the weather", default=HAIKU) == (HAIKU, "How's the weather")

    def test_sonnet_prefix(self):
        assert parse_prefix("/sonnet Explain entanglement", default=HAIKU) == (
            SONNET,
            "Explain entanglement",
        )

    def test_opus_prefix(self):
        assert parse_prefix("/opus Design X", default=HAIKU) == (OPUS, "Design X")

    def test_haiku_prefix_explicit(self):
        assert parse_prefix("/haiku Quick question", default=HAIKU) == (
            HAIKU,
            "Quick question",
        )

    def test_unknown_prefix_passes_through(self):
        # Unknown slash-prefix is not stripped; full text routed to default.
        assert parse_prefix("/unknown foo", default=HAIKU) == (HAIKU, "/unknown foo")

    def test_prefix_with_extra_whitespace(self):
        # Multiple spaces between prefix and content collapse.
        assert parse_prefix("/sonnet   hi there", default=HAIKU) == (SONNET, "hi there")

    def test_empty_content_after_prefix(self):
        # Empty content is passed through; the API will 400, surfacing via §8.2.
        assert parse_prefix("/sonnet", default=HAIKU) == (SONNET, "")

    def test_prefix_map_keys(self):
        assert set(PREFIX_MAP.keys()) == {"/haiku", "/sonnet", "/opus"}


from server.pipelines.claude_llm import JARVIS_SYSTEM_PROMPT, max_tokens_for


class TestMaxTokensFor:
    def test_haiku_uses_base(self):
        assert max_tokens_for(HAIKU, base=1024) == 1024

    def test_sonnet_doubles_base(self):
        assert max_tokens_for(SONNET, base=1024) == 2048

    def test_opus_quadruples_base(self):
        assert max_tokens_for(OPUS, base=1024) == 4096

    def test_unknown_model_uses_base(self):
        # Defensive: never crash on an unfamiliar id.
        assert max_tokens_for("claude-future-99", base=1024) == 1024

    def test_scales_with_base(self):
        assert max_tokens_for(SONNET, base=512) == 1024
        assert max_tokens_for(OPUS, base=512) == 2048


class TestSystemPrompt:
    def test_addresses_max_not_maxime(self):
        assert "Max" in JARVIS_SYSTEM_PROMPT
        assert "Maxime" not in JARVIS_SYSTEM_PROMPT

    def test_voice_friendly_rules_present(self):
        # Spec §6 requires voice-friendly guidance.
        assert "spoken aloud" in JARVIS_SYSTEM_PROMPT
        assert "no markdown" in JARVIS_SYSTEM_PROMPT.lower() or "plain prose" in JARVIS_SYSTEM_PROMPT.lower()


from dataclasses import dataclass, field
from typing import Any


@dataclass
class _FakeDelta:
    type: str
    text: str = ""


@dataclass
class _FakeEvent:
    type: str
    delta: _FakeDelta | None = None


def text_delta(text: str) -> _FakeEvent:
    """Build a content_block_delta event with a text payload."""
    return _FakeEvent(type="content_block_delta", delta=_FakeDelta(type="text_delta", text=text))


def non_text_event() -> _FakeEvent:
    """Build a content_block_start event the consumer should skip."""
    return _FakeEvent(type="content_block_start", delta=None)


@dataclass
class _FakeStream:
    events: list[_FakeEvent]
    aexit_called: bool = False

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.aexit_called = True
        return False  # do not suppress

    def __aiter__(self) -> "_FakeStream":
        return self

    async def __anext__(self) -> _FakeEvent:
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)


@dataclass
class _FakeMessages:
    events: list[_FakeEvent] = field(default_factory=list)
    raise_on_stream: BaseException | None = None
    captured_kwargs: dict[str, Any] = field(default_factory=dict)
    last_stream: _FakeStream | None = None

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.captured_kwargs = kwargs
        if self.raise_on_stream is not None:
            raise self.raise_on_stream
        self.last_stream = _FakeStream(events=list(self.events))
        return self.last_stream


@dataclass
class FakeAnthropic:
    """Minimal fake of `anthropic.AsyncAnthropic` for unit tests."""

    events: list[_FakeEvent] = field(default_factory=list)
    raise_on_stream: BaseException | None = None

    def __post_init__(self) -> None:
        self.messages = _FakeMessages(
            events=self.events, raise_on_stream=self.raise_on_stream
        )


from server.pipelines.claude_llm import ClaudeLLM


class TestStream:
    async def test_yields_text_deltas_in_order(self):
        client = FakeAnthropic(events=[
            text_delta("Hello "),
            text_delta("there, "),
            text_delta("Max."),
        ])
        llm = ClaudeLLM(default_model=HAIKU, client=client)

        chunks = [chunk async for chunk in llm.stream(history=[], user_text="hi")]

        assert chunks == ["Hello ", "there, ", "Max."]

    async def test_skips_non_text_events(self):
        client = FakeAnthropic(events=[
            non_text_event(),
            text_delta("hi"),
            non_text_event(),
        ])
        llm = ClaudeLLM(default_model=HAIKU, client=client)

        chunks = [chunk async for chunk in llm.stream(history=[], user_text="hi")]

        assert chunks == ["hi"]

    async def test_passes_correct_kwargs_to_stream(self):
        client = FakeAnthropic(events=[text_delta("ok")])
        llm = ClaudeLLM(default_model=HAIKU, client=client, max_tokens=1024)

        history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "reply"}]
        async for _ in llm.stream(history=history, user_text="now"):
            pass

        kwargs = client.messages.captured_kwargs
        assert kwargs["model"] == HAIKU
        assert kwargs["max_tokens"] == 1024
        assert kwargs["system"] == JARVIS_SYSTEM_PROMPT
        assert kwargs["messages"] == [
            {"role": "user", "content": "earlier"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "now"},
        ]

    async def test_prefix_routes_to_sonnet_with_doubled_max_tokens(self):
        client = FakeAnthropic(events=[text_delta("ok")])
        llm = ClaudeLLM(default_model=HAIKU, client=client, max_tokens=1024)

        async for _ in llm.stream(history=[], user_text="/sonnet Explain"):
            pass

        kwargs = client.messages.captured_kwargs
        assert kwargs["model"] == SONNET
        assert kwargs["max_tokens"] == 2048
        assert kwargs["messages"] == [{"role": "user", "content": "Explain"}]

    async def test_cancellation_calls_aexit(self):
        """Cancelling the consumer mid-stream invokes the SDK's __aexit__."""
        client = FakeAnthropic(events=[
            text_delta("first "),
            text_delta("second "),
            text_delta("third"),
        ])
        llm = ClaudeLLM(default_model=HAIKU, client=client)

        gen = llm.stream(history=[], user_text="hi")
        first = await anext(gen)
        assert first == "first "

        # Tear down the generator before exhausting events.
        await gen.aclose()

        assert client.messages.last_stream is not None
        assert client.messages.last_stream.aexit_called is True
