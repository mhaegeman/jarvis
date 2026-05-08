"""Claude-backed LLM pipeline (v0.2 α)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from .interfaces import LLM


logger = logging.getLogger(__name__)


PREFIX_MAP: dict[str, str] = {
    "/haiku": "claude-haiku-4-5",
    "/sonnet": "claude-sonnet-4-6",
    "/opus": "claude-opus-4-7",
}


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


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content). If no recognized prefix, return (default, text)."""
    head, _, rest = text.partition(" ")
    if head in PREFIX_MAP:
        return PREFIX_MAP[head], rest.lstrip()
    return default, text


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
        self._client: Any = client if client is not None else anthropic.AsyncAnthropic()

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
