"""Haiku-backed summarization for cross-session memory.

All three calls go to Haiku regardless of which model handles the
conversation. Predictable cost, good-enough quality. Failures are
logged and degraded to safe defaults (empty string / empty list).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from .types import Fact, Turn

log = logging.getLogger(__name__)


_RECENT_SYSTEM = (
    "You are a terse note-taker. Given the latest turns of a conversation, "
    "produce ONE OR TWO sentences capturing what was discussed and any pending "
    "action. No preamble. No bullet points. Plain prose."
)

_SESSION_SYSTEM = (
    "You are a terse note-taker. Given a finished conversation, produce ONE OR "
    "TWO sentences capturing the topic and any decisions or open questions. "
    "No preamble. Plain prose."
)

_FACTS_SYSTEM = (
    "You extract durable user-stated facts from a conversation. A fact is a "
    "stable piece of information about the user (preferences, identity claims, "
    "long-term circumstances). Skip ephemeral state ('I'm tired'), tasks, "
    "and questions. Respond with a JSON array of objects {\"key\": str, "
    "\"value\": str}, or [] if none. Output ONLY the JSON array — no prose."
)


def _format_turns(turns: list[Turn]) -> str:
    return "\n".join(f"{t.role}: {t.content}" for t in turns)


class Summarizer(Protocol):
    async def refresh_recent_summary(self, turns: list[Turn]) -> str: ...
    async def summarize_session(self, turns: list[Turn]) -> str: ...
    async def extract_facts(self, turns: list[Turn]) -> list[Fact]: ...


class ClaudeSummarizer:
    def __init__(
        self,
        *,
        client: Any,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 256,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    async def _one_shot(self, system: str, transcript: str) -> str:
        try:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": transcript}],
            )
            blocks = getattr(msg, "content", []) or []
            for b in blocks:
                text = getattr(b, "text", None)
                if text:
                    return str(text).strip()
            return ""
        except Exception:
            log.exception("summarizer call failed")
            return ""

    async def refresh_recent_summary(self, turns: list[Turn]) -> str:
        if not turns:
            return ""
        return await self._one_shot(_RECENT_SYSTEM, _format_turns(turns))

    async def summarize_session(self, turns: list[Turn]) -> str:
        if not turns:
            return ""
        return await self._one_shot(_SESSION_SYSTEM, _format_turns(turns))

    async def extract_facts(self, turns: list[Turn]) -> list[Fact]:
        if not turns:
            return []
        raw = await self._one_shot(_FACTS_SYSTEM, _format_turns(turns))
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("extract_facts: malformed JSON: %r", raw[:200])
            return []
        if not isinstance(data, list):
            return []
        out: list[Fact] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            value = item.get("value")
            if isinstance(key, str) and isinstance(value, str) and key:
                out.append(Fact(key=key, value=value))
        return out
