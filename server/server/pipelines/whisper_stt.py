"""WhisperSTT — real STT via faster-whisper (one-shot final, no partials)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np  # type: ignore[import-not-found]

from .interfaces import STT

# Module-level cache so multiple WhisperSTT instances (one per WS connection)
# share the loaded model.
_model_cache: dict[tuple[str, str], Any] = {}

# 200 ms at 16 kHz mono Int16 = 16000 * 0.2 * 2 bytes = 6400.
_MIN_BYTES = 6400


def _default_loader(model_name: str, device: str) -> Any:
    """Lazy import + cached construction of `faster_whisper.WhisperModel`."""
    key = (model_name, device)
    if key not in _model_cache:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        compute = "float16" if device == "cuda" else "int8"
        _model_cache[key] = WhisperModel(model_name, device=device, compute_type=compute)
    return _model_cache[key]


class WhisperSTT(STT):
    def __init__(
        self,
        *,
        model: str = "base.en",
        device: str = "cpu",
        loader: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._model_name = model
        self._device = device
        self._loader = loader or _default_loader

    async def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        # Drain so the caller's send loop terminates; v1 has no interim
        # transcripts — final() handles transcription on audio.end.
        async for _chunk in audio:
            pass
        return
        yield ""  # pragma: no cover — unreachable; yield makes this an async generator

    async def final(self, audio: AsyncIterator[bytes]) -> str:
        chunks: list[bytes] = []
        async for c in audio:
            chunks.append(c)
        if not chunks:
            return ""
        raw = b"".join(chunks)
        if len(raw) < _MIN_BYTES:
            return ""
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        model = await asyncio.to_thread(self._loader, self._model_name, self._device)
        segments, _info = await asyncio.to_thread(
            model.transcribe, arr, beam_size=1, language="en"
        )
        return " ".join(seg.text for seg in segments).strip()
