"""Tests for the EdgeTTS pipeline."""
from __future__ import annotations

import io
import wave

import pytest

from server.pipelines.edge_tts import EdgeTTS

_SAMPLE_RATE = 24000
_CHUNK_BYTES = _SAMPLE_RATE * 2 // 10  # 4800 bytes = 100 ms of int16 mono


def _make_wav(n_samples: int) -> bytes:
    """Minimal WAV file with n_samples of int16 silence at 24 kHz mono."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


async def _fake_loader(text: str, voice: str) -> bytes:
    return _make_wav(n_samples=_SAMPLE_RATE)  # 1 s → 24 000 samples → 48 000 bytes PCM


@pytest.mark.asyncio
async def test_synthesize_yields_correct_chunk_count() -> None:
    """1 s WAV → 48 000 bytes PCM → exactly 10 chunks of 4 800 bytes."""
    tts = EdgeTTS(voice="en-US-Test", loader=_fake_loader)
    chunks = [c async for c in tts.synthesize("Hello.", "a1")]
    assert len(chunks) == 10
    assert all(len(c) == _CHUNK_BYTES for c in chunks)


@pytest.mark.asyncio
async def test_synthesize_empty_text_yields_nothing() -> None:
    tts = EdgeTTS(voice="en-US-Test", loader=_fake_loader)
    chunks = [c async for c in tts.synthesize("", "a2")]
    assert chunks == []


@pytest.mark.asyncio
async def test_synthesize_whitespace_text_yields_nothing() -> None:
    tts = EdgeTTS(voice="en-US-Test", loader=_fake_loader)
    chunks = [c async for c in tts.synthesize("   ", "a3")]
    assert chunks == []


@pytest.mark.asyncio
async def test_synthesize_empty_loader_response_yields_nothing() -> None:
    """Loader returning empty bytes (e.g. NoAudioReceived path) → synthesize yields nothing."""

    async def empty_loader(text: str, voice: str) -> bytes:
        return b""

    tts = EdgeTTS(voice="en-US-Test", loader=empty_loader)
    chunks = [c async for c in tts.synthesize("hello", "a4")]
    assert chunks == []


def test_sample_rate_is_24000() -> None:
    tts = EdgeTTS(voice="en-US-Test", loader=_fake_loader)
    assert tts.sample_rate() == 24000
