"""Unit tests for OpenVoiceTTS."""

from __future__ import annotations

import sys
import types

if "torch" not in sys.modules:
    fake_torch = types.ModuleType("torch")

    class _NoOpCM:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class _FakeTensor:
        def __init__(self, data): self.data = data
        def to(self, _device): return self

    fake_torch.no_grad = lambda: _NoOpCM()  # type: ignore[attr-defined]
    fake_torch.LongTensor = lambda data: _FakeTensor(data)  # type: ignore[attr-defined]
    sys.modules["torch"] = fake_torch

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from server.pipelines.openvoice_tts import LoadedOpenVoice, OpenVoiceTTS


@dataclass
class FakeBaseSpeakerTTS:
    """Captures the calls our wrapper makes; returns canned audio."""
    return_audio: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    infer_calls: list[dict[str, Any]] = field(default_factory=list)
    get_text_calls: list[str] = field(default_factory=list)

    @property
    def hps(self) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(
            data=SimpleNamespace(sampling_rate=24000),
            speakers={"default": 0},
        )

    @property
    def language_marks(self) -> dict[str, str]:
        return {"english": "EN"}

    def get_text(self, text: str, hps: Any, _flag: bool) -> Any:
        self.get_text_calls.append(text)
        from types import SimpleNamespace
        stn = SimpleNamespace(
            size=lambda _i: 1,
            unsqueeze=lambda _dim: SimpleNamespace(to=lambda _device: object()),
        )
        return stn

    @property
    def device(self) -> str:
        return "cpu"

    @property
    def model(self) -> FakeInner:
        return FakeInner(parent=self)


@dataclass
class FakeInner:
    parent: FakeBaseSpeakerTTS

    def infer(self, x: Any, x_lengths: Any, sid: Any,
              noise_scale: float, noise_scale_w: float) -> Any:
        self.parent.infer_calls.append({
            "noise_scale": noise_scale,
            "noise_scale_w": noise_scale_w,
        })
        from types import SimpleNamespace
        arr = self.parent.return_audio
        leaf = SimpleNamespace(data=SimpleNamespace(
            cpu=lambda: SimpleNamespace(float=lambda: SimpleNamespace(numpy=lambda: arr))
        ))
        class _Outer:
            def __getitem__(self, _i: int) -> _Inner:
                return _Inner()
        class _Inner:
            def __getitem__(self, _key: tuple[int, int]) -> Any:
                return leaf
        return _Outer()


@dataclass
class FakeToneColorConverter:
    convert_calls: list[dict[str, Any]] = field(default_factory=list)
    return_audio: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))

    def convert_from_tensor(self, audio: np.ndarray, src_se: Any, tgt_se: Any) -> np.ndarray:
        self.convert_calls.append({"src_se": src_se, "tgt_se": tgt_se})
        return self.return_audio


def make_loader(loaded: LoadedOpenVoice) -> Any:
    """Loader that always returns the same pre-built LoadedOpenVoice."""
    def _load(path: str, device: str, speaker_wav: str | None) -> LoadedOpenVoice:
        return loaded
    return _load


class TestSampleRate:
    async def test_sample_rate_lazy_loads_via_loader(self):
        # The loader is invoked the first time sample_rate() is called.
        fake_tts = FakeBaseSpeakerTTS()
        fake_conv = FakeToneColorConverter()
        loaded = LoadedOpenVoice(
            tts_model=fake_tts,
            tone_color_converter=fake_conv,
            en_source_se=object(),
            target_se=None,
            sample_rate=24000,
        )
        loader_calls: list[tuple[str, str, str | None]] = []

        def counting_loader(path: str, device: str, speaker_wav: str | None) -> LoadedOpenVoice:
            loader_calls.append((path, device, speaker_wav))
            return loaded

        tts = OpenVoiceTTS(
            openvoice_path="~/OpenVoice", device="cpu", speaker_wav=None,
            loader=counting_loader,
        )
        assert tts.sample_rate() == 24000
        # Second call reuses the cached LoadedOpenVoice (loader called once).
        assert tts.sample_rate() == 24000
        assert len(loader_calls) == 1


class TestSynthesizeInfer:
    async def test_text_wrapped_with_language_marks(self):
        fake_tts = FakeBaseSpeakerTTS(
            return_audio=np.zeros(2400, dtype=np.float32),
        )
        loaded = LoadedOpenVoice(
            tts_model=fake_tts,
            tone_color_converter=FakeToneColorConverter(),
            en_source_se=object(),
            target_se=None,
            sample_rate=24000,
        )
        tts = OpenVoiceTTS(
            openvoice_path="~/OpenVoice", device="cpu", speaker_wav=None,
            loader=make_loader(loaded),
        )
        async for _ in tts.synthesize("hello world", "id1"):
            pass

        # The wrapper must wrap text in [mark]...[mark] using the english mark
        # before calling get_text. Mark for english per FakeBaseSpeakerTTS is "EN".
        assert fake_tts.get_text_calls == ["[EN]hello world[EN]"]
        # infer is called with OpenVoice's documented noise_scale defaults.
        assert fake_tts.infer_calls == [{"noise_scale": 0.667, "noise_scale_w": 0.6}]

    async def test_no_target_se_skips_tone_color_convert(self):
        fake_tts = FakeBaseSpeakerTTS(return_audio=np.zeros(2400, dtype=np.float32))
        fake_conv = FakeToneColorConverter()
        loaded = LoadedOpenVoice(
            tts_model=fake_tts,
            tone_color_converter=fake_conv,
            en_source_se=object(),
            target_se=None,
            sample_rate=24000,
        )
        tts = OpenVoiceTTS(
            openvoice_path="~/OpenVoice", device="cpu", speaker_wav=None,
            loader=make_loader(loaded),
        )
        async for _ in tts.synthesize("hi", "id1"):
            pass

        assert fake_conv.convert_calls == []  # no tone-color conversion when target_se is None
