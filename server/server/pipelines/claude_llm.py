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
        # Per the LLM ABC contract, Session has already appended the current user
        # turn (with the raw slash prefix, if any) as the last entry in history.
        # We send history[:-1] plus a freshly-built last turn whose content has
        # the prefix stripped — never re-append user_text, which would duplicate
        # the turn and, for prefixed messages, send both the raw and stripped
        # versions back-to-back.
        model, content = parse_prefix(user_text, self._default_model)
        messages = [*history[:-1], {"role": "user", "content": content}]
        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens_for(model, self._max_tokens),
                system=self._system_prompt,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta is not None
                        and event.delta.type == "text_delta"
                    ):
                        yield event.delta.text
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            yield _spoken_error_for(exc)
