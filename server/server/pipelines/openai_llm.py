"""OpenAI chat LLM pipeline — Pepper's chat backend.

Mirrors the shape of `claude_llm.py`: an async generator over token deltas,
prefix parsing, tier-scaled max_tokens, spoken error mapping. The Codex CLI
agent backend lives separately in `codex_agent.py` (Phase 3).

Spec anchor: §4.2 (Pepper persona), §5.3 (prefix rules), §13 (error matrix).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import openai

from .interfaces import LLM

logger = logging.getLogger(__name__)


# Per-turn prefix routes (spec §5.3.2). `/codex` pins Pepper at the deep
# tier in chat mode — the Dispatcher additionally promotes it to mode=
# codex_agent when the request is concretely actionable; that promotion
# happens upstream of this class.
PEPPER_PREFIX_MAP: dict[str, str] = {
    "/gpt": "gpt-5",
    "/codex": "gpt-5-codex",
}


PEPPER_SYSTEM_PROMPT_FALLBACK = """\
You are PEPPER, Max Haegeman's chief-of-staff AI for code and dev tasks.
Speak clipped, technically blunt, never sycophantic, no preambles. Your
replies are spoken aloud: plain prose, no markdown, no code blocks unless
Max asks for code.
"""


_MAX_TOKENS_SCALE: dict[str, int] = {
    "gpt-5-mini": 1,
    "gpt-5": 2,
    "gpt-5-codex": 4,
}


def max_tokens_for(model: str, base: int) -> int:
    """Return per-request max_tokens for `model`, scaled from `base`.

    Mirrors the Claude scaling pattern: deeper models get more headroom.
    Unknown ids fall back to `base`.
    """
    return base * _MAX_TOKENS_SCALE.get(model, 1)


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content).

    Slash heads are matched case-insensitively to keep behaviour aligned
    with `dialog.dispatcher._detect_slash`, which lowercases too. Without
    this, "/CODEX fix tests" would route to Pepper at the dispatcher layer
    but fall back to the default model here — silent inconsistency.

    Unrecognised prefixes pass through verbatim — matches the existing
    Claude `parse_prefix` behaviour so users can experiment without
    triggering surprise upgrades.
    """
    head, _, rest = text.partition(" ")
    head_lower = head.lower()
    if head_lower in PEPPER_PREFIX_MAP:
        return PEPPER_PREFIX_MAP[head_lower], rest.lstrip()
    return default, text


def _spoken_error_for(exc: openai.APIError) -> str:
    """Map an OpenAI exception to a short, factual sentence for TTS.

    Order matters — most-specific subclasses first, generic APIError last.
    """
    if isinstance(exc, openai.RateLimitError):
        return "Rate limit. Try again shortly."
    if isinstance(exc, openai.AuthenticationError):
        return "API key is invalid."
    if isinstance(exc, openai.PermissionDeniedError):
        return "API key lacks permission for that model."
    if isinstance(exc, openai.NotFoundError):
        return "Model not found. Check the model ID."
    if isinstance(exc, openai.BadRequestError):
        return "The request was rejected. Check the model and prompt."
    if isinstance(exc, openai.APITimeoutError):
        return "OpenAI timed out. Try again."
    if isinstance(exc, openai.APIConnectionError):
        return "Network error reaching OpenAI."
    if isinstance(exc, openai.APIStatusError):
        return "OpenAI server error. Try again."
    return "API error. Check the logs."


class OpenAILLM(LLM):
    """Streams responses from the OpenAI Chat Completions API.

    Phase 1 only — the DialogManager (Phase 2) constructs one of these per
    Pepper segment and reads its async generator. The Codex CLI agent path
    is a separate backend (CodexAgent, Phase 3).
    """

    def __init__(
        self,
        *,
        default_model: str = "gpt-5-mini",
        max_tokens: int = 1024,
        system_prompt: str = PEPPER_SYSTEM_PROMPT_FALLBACK,
        client: Any | None = None,
    ) -> None:
        self._default_model = default_model
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt
        self._client: Any = client if client is not None else openai.AsyncOpenAI()

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        """Yield token deltas. Mirrors ClaudeLLM.stream's contract.

        Per the LLM ABC, the caller has already appended the current user
        turn (with the raw slash prefix, if any) as the last entry in
        history. We send history[:-1] plus a freshly-built last turn with
        the prefix stripped.
        """
        model, content = parse_prefix(user_text, self._default_model)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        if extra_context:
            messages.append({"role": "system", "content": extra_context})
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": content})

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens_for(model, self._max_tokens),
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    yield text
        except openai.APIError as exc:
            logger.exception("OpenAI API error")
            yield _spoken_error_for(exc)
