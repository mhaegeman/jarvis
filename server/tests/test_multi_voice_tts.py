"""Tests for server.pipelines.multi_voice_tts — speaker-keyed TTS facade."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from server.pipelines.multi_voice_tts import MultiVoiceTTS


class _FakeTTS:
    """Records the texts it was asked to synthesize."""

    def __init__(self, voice_label: str, sample_rate: int = 24000) -> None:
        self.voice_label = voice_label
        self._sample_rate = sample_rate
        self.calls: list[tuple[str, str]] = []  # (text, audio_id)

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        self.calls.append((text, audio_id))
        # Yield one fake chunk so the async iterator is non-empty.
        yield self.voice_label.encode("utf-8")

    def sample_rate(self) -> int:
        return self._sample_rate


async def _collect(stream: AsyncIterator[bytes]) -> list[bytes]:
    return [b async for b in stream]


# ── Construction ──────────────────────────────────────────────────────


def test_construct_with_voice_map() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    assert tts.sample_rate() == 24000


def test_construct_rejects_mismatched_sample_rates() -> None:
    jarvis = _FakeTTS("J", sample_rate=24000)
    pepper = _FakeTTS("P", sample_rate=16000)
    with pytest.raises(ValueError):
        MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")


def test_construct_rejects_empty_map() -> None:
    with pytest.raises(ValueError):
        MultiVoiceTTS({}, default_speaker="jarvis")


def test_construct_rejects_unknown_default() -> None:
    jarvis = _FakeTTS("J")
    with pytest.raises(ValueError):
        MultiVoiceTTS({"jarvis": jarvis}, default_speaker="pepper")


# ── synthesize_for_speaker (Phase 2 entry point) ──────────────────────


@pytest.mark.asyncio
async def test_synthesize_for_speaker_routes_to_jarvis() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize_for_speaker("hello.", "a1", speaker="jarvis"))
    assert out == [b"J"]
    assert jarvis.calls == [("hello.", "a1")]
    assert pepper.calls == []


@pytest.mark.asyncio
async def test_synthesize_for_speaker_routes_to_pepper() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize_for_speaker("hi.", "a1", speaker="pepper"))
    assert out == [b"P"]
    assert pepper.calls == [("hi.", "a1")]
    assert jarvis.calls == []


@pytest.mark.asyncio
async def test_synthesize_for_speaker_falls_back_when_speaker_missing() -> None:
    jarvis = _FakeTTS("J")
    tts = MultiVoiceTTS({"jarvis": jarvis}, default_speaker="jarvis")
    # Pepper isn't registered; route to default.
    out = await _collect(tts.synthesize_for_speaker("hi.", "a1", speaker="pepper"))
    assert out == [b"J"]
    assert jarvis.calls == [("hi.", "a1")]


# ── TTS ABC compatibility ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_uses_default_speaker() -> None:
    """`synthesize` (the ABC method) routes to the default speaker."""
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize("hi.", "a1"))
    assert out == [b"J"]
