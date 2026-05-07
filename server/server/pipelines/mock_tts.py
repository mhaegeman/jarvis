"""Phase 1 mock TTS — emits no audio chunks."""

from __future__ import annotations

from collections.abc import AsyncIterator

from .interfaces import TTS


class MockTTS(TTS):
    def __init__(self, sample_rate: int = 24000) -> None:
        self._sample_rate = sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        # Phase 1: no audio synthesized. Phase 2 will yield PCM Int16 LE chunks.
        if False:  # pragma: no cover
            yield b""
        return

    def sample_rate(self) -> int:
        return self._sample_rate
