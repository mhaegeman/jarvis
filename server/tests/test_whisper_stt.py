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
