"""Unit tests for WhisperSTT."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import numpy as np

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
    def _load(name: str, device: str) -> FakeWhisperModel:
        return fake
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


class TestNormalization:
    async def test_int16_pcm_normalized_to_float32(self):
        # Construct a known Int16 LE payload covering the full range.
        samples = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
        # Pad to threshold so we don't short-circuit.
        pad = np.zeros(3200, dtype=np.int16)
        payload = np.concatenate([samples, pad]).tobytes()

        fake = FakeWhisperModel(return_segments=[FakeSegment(text="x")])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        await stt.final(_audio_iter(payload))

        arr, _kwargs = fake.transcribe_calls[0]
        assert arr.dtype == np.float32
        assert -1.0 <= arr.min() <= arr.max() <= 1.0
        # Spot-check the boundary samples (within float rounding tolerance).
        np.testing.assert_allclose(arr[0], 0.0, atol=1e-6)
        np.testing.assert_allclose(arr[1], 16384 / 32768.0, atol=1e-6)
        np.testing.assert_allclose(arr[3], 32767 / 32768.0, atol=1e-6)
        np.testing.assert_allclose(arr[4], -1.0, atol=1e-6)

    async def test_multi_chunk_audio_concatenated(self):
        # Two 3300-byte chunks — together cross the 6400-byte threshold.
        chunk_a = b"\x01\x00" * 1650  # 3300 bytes
        chunk_b = b"\x02\x00" * 1650  # 3300 bytes
        fake = FakeWhisperModel(return_segments=[FakeSegment(text="hello")])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(chunk_a, chunk_b))

        assert result == "hello"
        assert len(fake.transcribe_calls) == 1
        arr, _ = fake.transcribe_calls[0]
        # 3300 + 3300 = 6600 bytes → 3300 Int16 samples.
        assert arr.shape == (3300,)


class TestTranscribeArgsAndOutput:
    async def test_passes_language_en_and_beam_one(self):
        payload = b"\x00" * 6400
        fake = FakeWhisperModel(return_segments=[FakeSegment(text="x")])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        await stt.final(_audio_iter(payload))

        _arr, kwargs = fake.transcribe_calls[0]
        assert kwargs["language"] == "en"
        assert kwargs["beam_size"] == 1

    async def test_joins_segment_texts_with_space(self):
        payload = b"\x00" * 6400
        fake = FakeWhisperModel(return_segments=[
            FakeSegment(text="hello "),
            FakeSegment(text="there, "),
            FakeSegment(text="Max."),
        ])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(payload))
        # Join inserts one space between segments; the segments already carry
        # trailing whitespace, so the result has double-spaces internally.
        assert result == "hello  there,  Max."

    async def test_strips_outer_whitespace(self):
        payload = b"\x00" * 6400
        fake = FakeWhisperModel(return_segments=[FakeSegment(text="  spaced  ")])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(payload))
        assert result == "spaced"

    async def test_no_segments_returns_empty(self):
        payload = b"\x00" * 6400
        fake = FakeWhisperModel(return_segments=[])
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        result = await stt.final(_audio_iter(payload))
        assert result == ""


class TestDefaultLoaderCache:
    """Spec §4.4: the module-level singleton must construct each
    (model_name, device) WhisperModel exactly once across the process.
    Tested by patching `faster_whisper.WhisperModel` and counting
    constructions across repeated `_default_loader` calls."""

    def test_default_loader_caches_per_model_and_device(self, monkeypatch):
        import sys
        import types

        from server.pipelines import whisper_stt

        constructions: list[tuple[str, str, str]] = []

        class FakeWhisperModel:
            def __init__(self, name: str, device: str, compute_type: str) -> None:
                constructions.append((name, device, compute_type))

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
        monkeypatch.setattr(whisper_stt, "_model_cache", {})

        m1 = whisper_stt._default_loader("base.en", "cpu")
        m2 = whisper_stt._default_loader("base.en", "cpu")
        assert m1 is m2
        assert len(constructions) == 1
        assert constructions[0] == ("base.en", "cpu", "int8")

        # Different (name, device) → fresh construction.
        m3 = whisper_stt._default_loader("small.en", "cpu")
        assert m3 is not m1
        assert len(constructions) == 2

        # cuda → float16 compute type.
        whisper_stt._default_loader("base.en", "cuda")
        assert constructions[-1] == ("base.en", "cuda", "float16")

    def test_default_loader_normalizes_mps_to_cpu_with_warning(
        self, monkeypatch, caplog
    ):
        # faster-whisper's CTranslate2 backend doesn't accept "mps".
        # _resolve_device may return "mps" on Apple Silicon when
        # JARVIS_DEVICE=auto, so the loader silently downgrades it to
        # "cpu" and logs a warning. Without this normalization, every
        # turn on a Mac would crash with ValueError: unsupported device.
        import logging
        import sys
        import types

        from server.pipelines import whisper_stt

        constructions: list[tuple[str, str, str]] = []

        class FakeWhisperModel:
            def __init__(self, name: str, device: str, compute_type: str) -> None:
                constructions.append((name, device, compute_type))

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
        monkeypatch.setattr(whisper_stt, "_model_cache", {})

        with caplog.at_level(
            logging.WARNING, logger="server.pipelines.whisper_stt"
        ):
            whisper_stt._default_loader("base.en", "mps")

        assert constructions == [("base.en", "cpu", "int8")]
        assert any("does not support MPS" in r.message for r in caplog.records)


class TestPartials:
    async def test_partials_drains_iterator_and_yields_nothing(self):
        consumed: list[bytes] = []

        async def producer() -> AsyncIterator[bytes]:
            for c in (b"a", b"b", b"c"):
                consumed.append(c)
                yield c

        fake = FakeWhisperModel()
        stt = WhisperSTT(model="base.en", device="cpu", loader=make_loader(fake))
        emitted = [p async for p in stt.partials(producer())]

        assert emitted == []
        assert consumed == [b"a", b"b", b"c"]
        # partials must not call the model.
        assert fake.transcribe_calls == []
