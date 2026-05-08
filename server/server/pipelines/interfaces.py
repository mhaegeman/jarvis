"""Async pipeline interfaces — implemented by both mock and (future) real pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class STT(ABC):
    """Speech-to-text pipeline."""

    @abstractmethod
    def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Yield interim transcriptions as audio is consumed."""

    @abstractmethod
    async def final(self, audio: AsyncIterator[bytes]) -> str:
        """Return the final transcription once audio is exhausted."""


class LLM(ABC):
    """Large language model client."""

    @abstractmethod
    def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        """Yield token deltas. Caller appends user/assistant to history.

        `extra_context` is concatenated onto the system prompt for this turn
        only. Used by Session to inject memory blobs without touching `history`.
        """


class TTS(ABC):
    """Text-to-speech pipeline.

    Phase 1 mock skips audio synthesis: synthesize() returns an empty bytes
    AsyncIterator. Phase 2 (real OpenVoice) yields PCM Int16 LE chunks.
    """

    @abstractmethod
    def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        """Yield PCM Int16 LE chunks at the rate declared by sample_rate()."""

    @abstractmethod
    def sample_rate(self) -> int: ...
