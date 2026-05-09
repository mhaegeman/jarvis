"""Microsoft edge-tts TTS pipeline — produces PCM int16 @ 24 kHz."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from .interfaces import TTS

log = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_CHUNK_BYTES = _SAMPLE_RATE * 2 // 10  # 4800 bytes = 100 ms of int16 mono

Loader = Callable[[str, str], Awaitable[bytes]]


async def _default_loader(text: str, voice: str) -> bytes:
    import edge_tts  # type: ignore[import-not-found]

    chunks: list[bytes] = []
    try:
        async for item in edge_tts.Communicate(text, voice).stream():
            if item["type"] == "audio":
                chunks.append(item["data"])
    except edge_tts.exceptions.NoAudioReceived:
        log.warning("EdgeTTS: no audio received from Microsoft TTS for %r", text[:40])
    return b"".join(chunks)


def _decode_pcm(data: bytes) -> bytes:
    """Decode audio bytes (MP3/WAV/…) to PCM int16 LE @ 24 kHz mono.

    Runs in a thread via asyncio.to_thread — never call from the event loop.
    """
    import miniaudio  # type: ignore[import-untyped]

    result = miniaudio.decode(
        data,
        nchannels=1,
        output_format=miniaudio.SampleFormat.SIGNED16,
        sample_rate=_SAMPLE_RATE,
    )
    return bytes(result.samples)


class EdgeTTS(TTS):
    def __init__(self, voice: str, loader: Loader | None = None) -> None:
        self._voice = voice
        self._loader: Loader = loader if loader is not None else _default_loader

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        if not text.strip():
            return

        audio_bytes = await self._loader(text, self._voice)
        if not audio_bytes:
            return

        pcm = await asyncio.to_thread(_decode_pcm, audio_bytes)

        for offset in range(0, len(pcm), _CHUNK_BYTES):
            yield pcm[offset : offset + _CHUNK_BYTES]

    def sample_rate(self) -> int:
        return _SAMPLE_RATE
