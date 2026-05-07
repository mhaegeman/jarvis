"""Phase 1 mock LLM — keyword-routed, paced token streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from random import Random

from .interfaces import LLM
from .scenarios import DEFAULT_REPLY, pick_scenario


class MockLLM(LLM):
    def __init__(self, token_delay_ms: int = 33, seed: int | None = None) -> None:
        self._delay = token_delay_ms / 1000.0
        self._rand = Random(seed)

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        scenario = pick_scenario(user_text)
        reply = scenario.reply if scenario else DEFAULT_REPLY
        i = 0
        while i < len(reply):
            step = 3 + self._rand.randint(0, 3)
            j = min(i + step, len(reply))
            yield reply[i:j]
            i = j
            if self._delay:
                await asyncio.sleep(self._delay)
