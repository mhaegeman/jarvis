"""Phase 1 mock STT — emits progressive prefixes; final = canned text."""

from __future__ import annotations

from collections.abc import AsyncIterator

from .interfaces import STT


class MockSTT(STT):
    def __init__(self, canned_final: str = "Brief me on today.") -> None:
        self._canned = canned_final

    async def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        words = self._canned.split()
        emitted = 0
        async for _chunk in audio:
            emitted = min(emitted + 1, len(words))
            yield " ".join(words[:emitted])

    async def final(self, audio: AsyncIterator[bytes]) -> str:
        async for _ in audio:
            pass
        return self._canned

    def set_canned(self, text: str) -> None:
        self._canned = text
