"""Unit tests for WhisperSTT."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from server.pipelines.whisper_stt import WhisperSTT


@dataclass
class FakeSegment:
    text: str


@dataclass
class FakeWhisperModel:
    """Captures call args; returns canned segments."""
    return_segments: list[FakeSegment] = field(default_factory=list)
    transcribe_calls: list[tuple[Any, dict[str, Any]]] = field(default_factory=list)

    def transcribe(self, arr: Any, **kwargs: Any) -> tuple[Any, None]:
        self.transcribe_calls.append((arr, kwargs))
        return iter(list(self.return_segments)), None


def make_loader(fake: FakeWhisperModel) -> Any:
    """Loader that always returns the same fake."""
    counter = {"calls": 0}
    def _load(name: str, device: str) -> FakeWhisperModel:
        counter["calls"] += 1
        return fake
    _load.counter = counter  # type: ignore[attr-defined]
    return _load


async def _audio_iter(*chunks: bytes) -> AsyncIterator[bytes]:
    for c in chunks:
        yield c


class TestEmptyAudio:
    async def test_empty_iterator_returns_empty_string(self):
        fake = FakeWhisperModel()
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter())
        assert result == ""

    async def test_empty_does_not_call_model(self):
        fake = FakeWhisperModel()
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        await stt.final(_audio_iter())
        assert fake.transcribe_calls == []


class TestThreshold:
    async def test_one_chunk_under_200ms_returns_empty(self):
        # 100 ms @ 16 kHz mono Int16 = 3200 bytes — below the 6400-byte floor.
        short = b"\x00" * 3200
        fake = FakeWhisperModel()
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(short))
        assert result == ""
        assert fake.transcribe_calls == []

    async def test_exactly_threshold_calls_model(self):
        # 6400 bytes hits the threshold exactly.
        at_threshold = b"\x00" * 6400
        fake = FakeWhisperModel(return_segments=[FakeSegment(text="ok")])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(at_threshold))
        assert result == "ok"
        assert len(fake.transcribe_calls) == 1
