# Claude conversational pipeline (v0.2 α) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `MockLLM` with a real `ClaudeLLM` that satisfies the existing `LLM` ABC, defaulting to Haiku 4.5 with `/sonnet`, `/opus`, `/haiku` per-turn prefixes.

**Architecture:** New `claude_llm.py` sibling of `mock_llm.py` in `server/server/pipelines/`. A factory in `main.py` chooses the LLM based on `JARVIS_MODEL_NAME`. JARVIS-style butler persona via system prompt. Per-error-class spoken messages.

**Tech Stack:** Python 3.12, `anthropic>=0.40` async SDK, FastAPI, pytest-asyncio (auto mode).

**Spec:** `docs/superpowers/specs/2026-05-08-claude-llm-design.md` — read it before starting.

**Branch:** `alpha/claude-llm` (already created).

**Working directory:** `server/` for all `pytest` commands. `pyproject.toml` lives at `server/pyproject.toml`.

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `server/pyproject.toml` | modify | Add `anthropic>=0.40,<1.0` to runtime deps |
| `server/server/config.py` | modify | Add `llm_max_tokens: int = 1024` to `Settings` |
| `server/server/pipelines/claude_llm.py` | create | `ClaudeLLM`, `parse_prefix`, `max_tokens_for`, `_spoken_error_for`, `JARVIS_SYSTEM_PROMPT`, `PREFIX_MAP` |
| `server/server/main.py` | modify | Add `_build_llm()` factory; replace hard-coded `MockLLM()` |
| `server/tests/test_claude_llm.py` | create | All unit tests for `claude_llm.py` |
| `server/tests/test_main_factory.py` | create | Tests for the `_build_llm()` factory |
| `server/README.md` | modify | Document `ANTHROPIC_API_KEY`, model values, prefixes, smoke recipe |

---

## Task 1: Add `anthropic` dependency and `llm_max_tokens` config field

**Files:**
- Modify: `server/pyproject.toml`
- Modify: `server/server/config.py`

- [ ] **Step 1: Add the dependency**

Edit `server/pyproject.toml`. In the `[project] dependencies` list, append `"anthropic>=0.40,<1.0"`:

```toml
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "websockets>=13",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "psutil>=5.9",
  "google-auth>=2.30",
  "google-auth-oauthlib>=1.2",
  "google-api-python-client>=2.140",
  "anthropic>=0.40,<1.0",
]
```

- [ ] **Step 2: Install the dependency**

Run from `server/`:

```bash
pip install -e '.[dev]'
```

Expected: install succeeds, `anthropic` and its transitive deps land in the env.

- [ ] **Step 3: Add `llm_max_tokens` to Settings**

Edit `server/server/config.py`. Add the field:

```python
"""Environment-driven configuration (Phase 1: minimal)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    ws_port: int = 8765
    log_level: str = "INFO"
    model_name: str = "mock"
    model_context_max: int = 200000
    llm_max_tokens: int = 1024


settings = Settings()
```

- [ ] **Step 4: Verify nothing broke**

Run from `server/`:

```bash
pytest tests/ -q
```

Expected: all tests pass (same green state as before).

- [ ] **Step 5: Commit**

```bash
git add server/pyproject.toml server/server/config.py
git commit -m "feat(α): add anthropic dep and llm_max_tokens config"
```

---

## Task 2: `parse_prefix` + `PREFIX_MAP`

**Files:**
- Create: `server/server/pipelines/claude_llm.py`
- Create: `server/tests/test_claude_llm.py`

- [ ] **Step 1: Write failing tests for prefix parsing**

Create `server/tests/test_claude_llm.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `server/`:

```bash
pytest tests/test_claude_llm.py -v
```

Expected: ImportError or ModuleNotFoundError for `server.pipelines.claude_llm`.

- [ ] **Step 3: Implement `parse_prefix` and `PREFIX_MAP`**

Create `server/server/pipelines/claude_llm.py`:

```python
"""Claude-backed LLM pipeline (v0.2 α)."""

from __future__ import annotations


PREFIX_MAP: dict[str, str] = {
    "/haiku": "claude-haiku-4-5",
    "/sonnet": "claude-sonnet-4-6",
    "/opus": "claude-opus-4-7",
}


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content). If no recognized prefix, return (default, text)."""
    head, _, rest = text.partition(" ")
    if head in PREFIX_MAP:
        return PREFIX_MAP[head], rest.lstrip()
    return default, text
```

- [ ] **Step 4: Run tests to verify they pass**

Run from `server/`:

```bash
pytest tests/test_claude_llm.py -v
```

Expected: all 8 tests in `TestParsePrefix` pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/claude_llm.py server/tests/test_claude_llm.py
git commit -m "feat(α): parse_prefix and PREFIX_MAP for /haiku /sonnet /opus routing"
```

---

## Task 3: `max_tokens_for` scaling + `JARVIS_SYSTEM_PROMPT`

**Files:**
- Modify: `server/server/pipelines/claude_llm.py`
- Modify: `server/tests/test_claude_llm.py`

- [ ] **Step 1: Write failing tests**

Append to `server/tests/test_claude_llm.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_claude_llm.py -v
```

Expected: 7 new tests fail (ImportError for `JARVIS_SYSTEM_PROMPT` and `max_tokens_for`).

- [ ] **Step 3: Implement scaling and persona prompt**

Edit `server/server/pipelines/claude_llm.py`. Add after `PREFIX_MAP`:

```python
JARVIS_SYSTEM_PROMPT = """\
You are JARVIS, Max Haegeman's personal AI assistant. You speak the way a
trusted senior colleague would: concise, occasionally wry, never sycophantic.
You address Max by name only when natural. You skip preambles like "Sure!"
and "I'd be happy to help" — you just answer.

Your replies are spoken aloud, so:
- Plain prose, no markdown headings or bullet points
- No code blocks unless Max explicitly asks for code
- Numbers and dates in conversational form ("ten thirty" not "10:30")
- One topic at a time. If multiple things are in play, ask which to tackle first

When you don't know, say so plainly. When asked a yes/no, lead with yes or no.
"""


_MAX_TOKENS_SCALE: dict[str, int] = {
    "claude-haiku-4-5": 1,
    "claude-sonnet-4-6": 2,
    "claude-opus-4-7": 4,
}


def max_tokens_for(model: str, base: int) -> int:
    """Return per-request max_tokens for `model`, scaled from `base`.

    Heavier models get more headroom because they're invoked for harder questions.
    Unknown model ids fall back to `base`.
    """
    return base * _MAX_TOKENS_SCALE.get(model, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_claude_llm.py -v
```

Expected: all tests pass (8 prefix + 5 max_tokens + 2 system prompt = 15).

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/claude_llm.py server/tests/test_claude_llm.py
git commit -m "feat(α): max_tokens_for scaling and JARVIS_SYSTEM_PROMPT"
```

---

## Task 4: `ClaudeLLM` skeleton + happy-path streaming

**Files:**
- Modify: `server/server/pipelines/claude_llm.py`
- Modify: `server/tests/test_claude_llm.py`

- [ ] **Step 1: Add the fake Anthropic client to the test file**

Append to `server/tests/test_claude_llm.py`:

```python
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
```

- [ ] **Step 2: Write failing test for happy-path streaming**

Append to `server/tests/test_claude_llm.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_claude_llm.py::TestStream -v
```

Expected: ImportError or AttributeError for `ClaudeLLM`.

- [ ] **Step 4: Implement `ClaudeLLM` skeleton with happy-path streaming**

Edit `server/server/pipelines/claude_llm.py`. Add the imports at the top and the class at the bottom:

```python
"""Claude-backed LLM pipeline (v0.2 α)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from .interfaces import LLM


logger = logging.getLogger(__name__)


# ... existing PREFIX_MAP, JARVIS_SYSTEM_PROMPT, _MAX_TOKENS_SCALE, parse_prefix, max_tokens_for ...


class ClaudeLLM(LLM):
    """Streams responses from the Anthropic Messages API."""

    def __init__(
        self,
        *,
        default_model: str = "claude-haiku-4-5",
        max_tokens: int = 1024,
        system_prompt: str = JARVIS_SYSTEM_PROMPT,
        client: Any | None = None,
    ) -> None:
        self._default_model = default_model
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt
        self._client = client if client is not None else anthropic.AsyncAnthropic()

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        model, content = parse_prefix(user_text, self._default_model)
        messages = [*history, {"role": "user", "content": content}]
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens_for(model, self._max_tokens),
            system=self._system_prompt,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and event.delta is not None:
                    if event.delta.type == "text_delta":
                        yield event.delta.text
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_claude_llm.py -v
```

Expected: all tests pass (15 from before + 4 new in `TestStream` = 19).

- [ ] **Step 6: Commit**

```bash
git add server/server/pipelines/claude_llm.py server/tests/test_claude_llm.py
git commit -m "feat(α): ClaudeLLM happy-path streaming with FakeAnthropic test harness"
```

---

## Task 5: Cancellation cleanup

**Files:**
- Modify: `server/tests/test_claude_llm.py`

The implementation already handles cancellation correctly via the `async with` exit protocol — this task only adds the test that proves it.

- [ ] **Step 1: Write failing test for cancellation**

Append to `server/tests/test_claude_llm.py` inside `class TestStream`:

```python
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
```

- [ ] **Step 2: Run test to verify it passes**

```bash
pytest tests/test_claude_llm.py::TestStream::test_cancellation_calls_aexit -v
```

Expected: PASS — the existing `async with` already handles cleanup.

If this test fails, the implementation is leaking the context manager — fix by ensuring `stream()` is not bypassing the `async with` in any branch.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_claude_llm.py
git commit -m "test(α): assert ClaudeLLM cancellation invokes stream __aexit__"
```

---

## Task 6: `_spoken_error_for` and stream-time error handling

**Files:**
- Modify: `server/server/pipelines/claude_llm.py`
- Modify: `server/tests/test_claude_llm.py`

- [ ] **Step 1: Write failing tests for the spoken-error helper**

Append to `server/tests/test_claude_llm.py`:

```python
import httpx

from server.pipelines.claude_llm import _spoken_error_for


def _http_response(status: int) -> httpx.Response:
    return httpx.Response(
        status,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )


def _make_status_error(cls, status: int) -> anthropic.APIStatusError:
    return cls(message="test", response=_http_response(status), body=None)


class TestSpokenErrorFor:
    def test_rate_limit(self):
        exc = _make_status_error(anthropic.RateLimitError, 429)
        assert _spoken_error_for(exc) == "Rate limit. Try again shortly."

    def test_authentication(self):
        exc = _make_status_error(anthropic.AuthenticationError, 401)
        assert _spoken_error_for(exc) == "API key is invalid."

    def test_permission_denied(self):
        exc = _make_status_error(anthropic.PermissionDeniedError, 403)
        assert _spoken_error_for(exc) == "API key lacks permission for that model."

    def test_not_found(self):
        exc = _make_status_error(anthropic.NotFoundError, 404)
        assert _spoken_error_for(exc) == "Model not found. Check the model ID."

    def test_bad_request(self):
        exc = _make_status_error(anthropic.BadRequestError, 400)
        assert _spoken_error_for(exc) == "The request was rejected. Check the model and prompt."

    def test_timeout(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        exc = anthropic.APITimeoutError(request=request)
        assert _spoken_error_for(exc) == "Anthropic timed out. Try again."

    def test_connection(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        exc = anthropic.APIConnectionError(message="boom", request=request)
        assert _spoken_error_for(exc) == "Network error reaching Anthropic."

    def test_other_status_error(self):
        exc = _make_status_error(anthropic.InternalServerError, 500)
        assert _spoken_error_for(exc) == "Anthropic server error. Try again."

    def test_generic_api_error(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        exc = anthropic.APIError(message="weird", request=request, body=None)
        assert _spoken_error_for(exc) == "API error. Check the logs."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_claude_llm.py::TestSpokenErrorFor -v
```

Expected: ImportError for `_spoken_error_for`.

- [ ] **Step 3: Implement `_spoken_error_for`**

Edit `server/server/pipelines/claude_llm.py`. Add the function after `max_tokens_for` and before `class ClaudeLLM`:

```python
def _spoken_error_for(exc: anthropic.APIError) -> str:
    """Map an Anthropic exception to a short, factual sentence for TTS.

    Order matters — most-specific subclasses first, generic APIError last.
    """
    if isinstance(exc, anthropic.RateLimitError):
        return "Rate limit. Try again shortly."
    if isinstance(exc, anthropic.AuthenticationError):
        return "API key is invalid."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "API key lacks permission for that model."
    if isinstance(exc, anthropic.NotFoundError):
        return "Model not found. Check the model ID."
    if isinstance(exc, anthropic.BadRequestError):
        return "The request was rejected. Check the model and prompt."
    if isinstance(exc, anthropic.APITimeoutError):
        return "Anthropic timed out. Try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Network error reaching Anthropic."
    if isinstance(exc, anthropic.APIStatusError):
        return "Anthropic server error. Try again."
    return "API error. Check the logs."
```

- [ ] **Step 4: Run helper tests to verify they pass**

```bash
pytest tests/test_claude_llm.py::TestSpokenErrorFor -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Write failing test for stream-time error catching**

Append to `server/tests/test_claude_llm.py` inside `class TestStream`:

```python
    async def test_api_error_yields_spoken_message_and_ends_cleanly(self):
        """An exception inside the stream produces one spoken delta then clean end."""
        rate_limit = _make_status_error(anthropic.RateLimitError, 429)
        client = FakeAnthropic(raise_on_stream=rate_limit)
        llm = ClaudeLLM(default_model=HAIKU, client=client)

        chunks = [chunk async for chunk in llm.stream(history=[], user_text="hi")]

        assert chunks == ["Rate limit. Try again shortly."]

    async def test_connection_error_yields_spoken_message(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        conn_err = anthropic.APIConnectionError(message="boom", request=request)
        client = FakeAnthropic(raise_on_stream=conn_err)
        llm = ClaudeLLM(default_model=HAIKU, client=client)

        chunks = [chunk async for chunk in llm.stream(history=[], user_text="hi")]

        assert chunks == ["Network error reaching Anthropic."]
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
pytest tests/test_claude_llm.py::TestStream::test_api_error_yields_spoken_message_and_ends_cleanly tests/test_claude_llm.py::TestStream::test_connection_error_yields_spoken_message -v
```

Expected: FAIL — exception propagates instead of being caught.

- [ ] **Step 7: Wrap `stream()` with `try/except anthropic.APIError`**

Edit `ClaudeLLM.stream` in `server/server/pipelines/claude_llm.py` to wrap the `async with` in a try/except:

```python
    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        model, content = parse_prefix(user_text, self._default_model)
        messages = [*history, {"role": "user", "content": content}]
        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens_for(model, self._max_tokens),
                system=self._system_prompt,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta is not None:
                        if event.delta.type == "text_delta":
                            yield event.delta.text
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            yield _spoken_error_for(exc)
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
pytest tests/test_claude_llm.py -v
```

Expected: all `claude_llm` tests pass (15 + 4 + 1 + 9 + 2 = 31).

- [ ] **Step 9: Commit**

```bash
git add server/server/pipelines/claude_llm.py server/tests/test_claude_llm.py
git commit -m "feat(α): map Anthropic exceptions to short spoken messages"
```

---

## Task 7: `_build_llm()` factory in `main.py`

**Files:**
- Modify: `server/server/main.py`
- Create: `server/tests/test_main_factory.py`

- [ ] **Step 1: Write failing tests for the factory**

Create `server/tests/test_main_factory.py`:

```python
"""Tests for the LLM factory in main.py."""

from __future__ import annotations

import pytest

from server.main import _build_llm
from server.pipelines.claude_llm import ClaudeLLM
from server.pipelines.mock_llm import MockLLM


class TestBuildLLM:
    def test_mock_returns_mock_llm(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.model_name", "mock")
        llm = _build_llm()
        assert isinstance(llm, MockLLM)

    def test_claude_haiku_returns_claude_llm_when_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr("server.main.settings.model_name", "claude-haiku-4-5")
        llm = _build_llm()
        assert isinstance(llm, ClaudeLLM)

    def test_claude_without_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr("server.main.settings.model_name", "claude-haiku-4-5")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            _build_llm()

    def test_unknown_model_name_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.model_name", "gpt-99")
        with pytest.raises(ValueError, match="JARVIS_MODEL_NAME"):
            _build_llm()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main_factory.py -v
```

Expected: ImportError or AttributeError for `_build_llm`.

- [ ] **Step 3: Add `os` import and the new pipeline imports**

The current top of `server/server/main.py` is:

```python
"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator, MutableMapping
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session
```

Edit it to:

```python
"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator, MutableMapping
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .pipelines.claude_llm import ClaudeLLM
from .pipelines.interfaces import LLM
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session
```

(Three additions: `import os`; `from .pipelines.claude_llm import ClaudeLLM`; `from .pipelines.interfaces import LLM`.)

- [ ] **Step 4: Add the `_build_llm()` factory**

Insert this function after `log = logging.getLogger(__name__)` (currently line 19) and before the `lifespan` async context manager:

```python
def _build_llm() -> LLM:
    """Construct the LLM pipeline based on `JARVIS_MODEL_NAME`.

    Raises:
        RuntimeError: when a Claude model is selected but `ANTHROPIC_API_KEY` is unset.
        ValueError: when `model_name` is not 'mock' and does not start with 'claude-'.
    """
    name = settings.model_name
    if name == "mock":
        return MockLLM()
    if name.startswith("claude-"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "JARVIS_MODEL_NAME selects a Claude model but ANTHROPIC_API_KEY is unset."
            )
        return ClaudeLLM(default_model=name, max_tokens=settings.llm_max_tokens)
    raise ValueError(f"unknown JARVIS_MODEL_NAME: {name!r}")
```

- [ ] **Step 5: Wire the factory into `ws_endpoint`**

Replace the existing `llm=MockLLM()` line in `ws_endpoint` (around line 59) with `llm=_build_llm()`. The full block becomes:

```python
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    # Per-connection pipelines (stateless; cheap to allocate).
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=MockSTT(),
        llm=_build_llm(),
        tts=MockTTS(),
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()
```

- [ ] **Step 6: Run factory tests to verify they pass**

```bash
pytest tests/test_main_factory.py -v
```

Expected: 4 tests pass.

- [ ] **Step 7: Run the full test suite**

```bash
pytest tests/ -q
```

Expected: full suite green. Specifically, `tests/test_session.py` and `tests/test_ws_integration.py` still pass — they don't set `JARVIS_MODEL_NAME`, so the factory routes to `MockLLM`.

- [ ] **Step 8: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(α): _build_llm factory wires ClaudeLLM via JARVIS_MODEL_NAME"
```

---

## Task 8: Document env vars and smoke recipe in `server/README.md`

**Files:**
- Modify: `server/README.md`

- [ ] **Step 1: Read the current README**

```bash
cat server/README.md
```

Locate (or create) a "Configuration" or "Environment variables" section. If neither exists, add one near the top.

- [ ] **Step 2: Add the Claude pipeline section**

Insert this section into `server/README.md` (replacing or extending any existing env-var documentation):

```markdown
## LLM pipeline

Two backends are wired through the `LLM` ABC: a deterministic mock (default, used for offline dev / CI / demos) and a real Claude-backed pipeline.

### Selecting a backend

Set `JARVIS_MODEL_NAME`:

| Value | Backend | Notes |
|---|---|---|
| `mock` (default) | `MockLLM` | Scripted replies; no network calls. |
| `claude-haiku-4-5` | `ClaudeLLM` | Default Claude model. Requires `ANTHROPIC_API_KEY`. |
| `claude-sonnet-4-6` | `ClaudeLLM` | Same, with Sonnet as the default for un-prefixed messages. |
| `claude-opus-4-7` | `ClaudeLLM` | Same, with Opus as the default for un-prefixed messages. |

### Per-turn model prefixes

When `JARVIS_MODEL_NAME` selects a Claude model, you can promote a single turn to a different model with a slash prefix:

| Prefix | Routes to |
|---|---|
| `/haiku ...` | `claude-haiku-4-5` |
| `/sonnet ...` | `claude-sonnet-4-6` |
| `/opus ...` | `claude-opus-4-7` |

Unrecognized prefixes are passed through to the default model verbatim — JARVIS will see and react to the literal text, including the slash.

### Other env vars

- `ANTHROPIC_API_KEY` — required when `JARVIS_MODEL_NAME` selects Claude. The server will refuse to accept WebSocket connections at startup if it's missing, rather than 401-looping every turn.
- `JARVIS_LLM_MAX_TOKENS` — base per-request `max_tokens` (default `1024`). Auto-scaled to `2 ×` for `/sonnet` and `4 ×` for `/opus` because heavier models are invoked for harder questions, not for verbosity.

### Smoke test

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_MODEL_NAME=claude-haiku-4-5
cd server
python -m server.main  # in one terminal
python -m server.cli_test  # in another; type messages, observe deltas
```

Verify in [Anthropic's usage dashboard](https://console.anthropic.com/) that `/sonnet` and `/opus` prefixes route to the right model IDs.
```

- [ ] **Step 3: Visually inspect the rendered file**

```bash
cat server/README.md | head -120
```

Confirm the section reads well and the table is rendered correctly.

- [ ] **Step 4: Commit**

```bash
git add server/README.md
git commit -m "docs(α): document Claude pipeline, prefixes, and smoke recipe"
```

---

## Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

From `server/`:

```bash
pytest tests/ -v
```

Expected: all tests pass. Specifically:
- All 31 `test_claude_llm.py` tests pass
- All 4 `test_main_factory.py` tests pass
- Existing `test_mock_llm.py`, `test_session.py`, `test_ws_integration.py` etc. unchanged and still green

- [ ] **Step 2: Type-check**

```bash
mypy server/
```

Expected: clean (or at most pre-existing warnings unrelated to this change).

- [ ] **Step 3: Lint**

```bash
ruff check server/
```

Expected: clean.

- [ ] **Step 4: Manual smoke test (requires `ANTHROPIC_API_KEY`)**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_MODEL_NAME=claude-haiku-4-5
cd server
python -m server.main &
sleep 2
python -m server.cli_test
```

In the CLI client:
1. Type "Good morning" — expect a brief, JARVIS-flavored reply that calls you "Max" if at all.
2. Type "/sonnet Explain quantum entanglement in one sentence" — expect a longer, Sonnet-quality reply.
3. Type "/opus Design a simple URL shortener architecture" — expect a thorough Opus reply.
4. Disconnect your Wi-Fi, type "anything" — expect "Network error reaching Anthropic." spoken/printed.
5. Re-enable Wi-Fi, confirm subsequent messages work.

Verify in [Anthropic's usage dashboard](https://console.anthropic.com/) that the right model IDs were billed.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin alpha/claude-llm
```

Expected: branch pushes; no PR created (the user will open one manually if desired).
