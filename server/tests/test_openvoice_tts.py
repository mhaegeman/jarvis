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


class TestChunking:
    async def test_chunks_into_100ms_windows_at_24khz(self):
        # 250 ms at 24 kHz mono = 6000 samples → 12000 bytes.
        # 100 ms chunk at 24 kHz = 2400 samples = 4800 bytes.
        # Expect 3 chunks: 4800 + 4800 + 2400 bytes (last partial).
        fake_tts = FakeBaseSpeakerTTS(
            return_audio=np.full(6000, 0.5, dtype=np.float32),
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
        chunks = [c async for c in tts.synthesize("hi", "id1")]

        chunk_sizes = [len(c) for c in chunks]
        assert chunk_sizes == [4800, 4800, 2400]
        # Total bytes match 6000 Int16 LE samples.
        assert sum(chunk_sizes) == 6000 * 2

    async def test_empty_audio_yields_nothing(self):
        fake_tts = FakeBaseSpeakerTTS(return_audio=np.zeros(0, dtype=np.float32))
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
        chunks = [c async for c in tts.synthesize("", "id1")]
        assert chunks == []


class TestTextPreprocessing:
    async def test_lower_to_upper_boundary_inserts_space(self):
        # Mirrors speech_text_speech.py: re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        # so "iAmJarvis" → "i Am Jarvis" before the [mark] wrap.
        fake_tts = FakeBaseSpeakerTTS(return_audio=np.zeros(0, dtype=np.float32))
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
        async for _ in tts.synthesize("iAmJarvis", "id1"):
            pass
        assert fake_tts.get_text_calls == ["[EN]i Am Jarvis[EN]"]

    async def test_text_without_case_boundaries_unchanged(self):
        fake_tts = FakeBaseSpeakerTTS(return_audio=np.zeros(0, dtype=np.float32))
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
        async for _ in tts.synthesize("hello there", "id1"):
            pass
        assert fake_tts.get_text_calls == ["[EN]hello there[EN]"]


class TestVoiceCloning:
    async def test_target_se_triggers_tone_color_convert(self):
        original = np.full(2400, 0.5, dtype=np.float32)
        cloned = np.full(2400, 0.25, dtype=np.float32)
        fake_tts = FakeBaseSpeakerTTS(return_audio=original)
        fake_conv = FakeToneColorConverter(return_audio=cloned)
        sentinel_src_se = object()
        sentinel_tgt_se = object()
        loaded = LoadedOpenVoice(
            tts_model=fake_tts,
            tone_color_converter=fake_conv,
            en_source_se=sentinel_src_se,
            target_se=sentinel_tgt_se,
            sample_rate=24000,
        )
        tts = OpenVoiceTTS(
            openvoice_path="~/OpenVoice", device="cpu",
            speaker_wav="/some/voice.wav",
            loader=make_loader(loaded),
        )
        chunks = [c async for c in tts.synthesize("hi", "id1")]

        # Conversion called once with the configured src/tgt embeddings.
        assert len(fake_conv.convert_calls) == 1
        assert fake_conv.convert_calls[0]["src_se"] is sentinel_src_se
        assert fake_conv.convert_calls[0]["tgt_se"] is sentinel_tgt_se
        # Output PCM is the cloned waveform, not the original.
        joined = b"".join(chunks)
        expected = np.clip(cloned * 32767.0, -32768, 32767).astype(np.int16).tobytes()
        assert joined == expected


class TestPCMConversion:
    async def test_float32_clipped_to_int16_range(self):
        # Out-of-range floats must clip to ±32767 / -32768, not wrap.
        # Inputs -2.0 and 2.0 hit the clamp; ±0.5 lands at ±0.5 * 32767 =
        # ±16383.5, which float32 → int16 truncation rounds to either
        # ±16383 or ±16384 depending on platform/numpy version. We allow
        # both so the test pins clipping behavior, not rounding direction.
        # Pad with zeros so chunking yields a single chunk.
        edges = np.array([-2.0, -0.5, 0.0, 0.5, 2.0], dtype=np.float32)
        pad = np.zeros(2395, dtype=np.float32)  # total 2400 samples = 100 ms
        fake_tts = FakeBaseSpeakerTTS(
            return_audio=np.concatenate([edges, pad]),
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
        chunks = [c async for c in tts.synthesize("hi", "id1")]

        joined = b"".join(chunks)
        samples = np.frombuffer(joined, dtype=np.int16)
        assert samples[0] == -32768  # -2.0 clamped
        assert samples[1] in (-16384, -16383)  # -0.5 → ≈-16383.5, float32 rounding
        assert samples[2] == 0
        assert samples[3] in (16383, 16384)   # 0.5 → ≈16383.5, float32 rounding
        assert samples[4] == 32767   # 2.0 clamped


class TestDefaultLoaderCache:
    """Verify the production loader: sys.path mutation, lazy imports of
    api/se_extractor, checkpoint construction, speaker_wav singleton, and
    the (path, device, speaker_wav) cache."""

    def test_default_loader_caches_per_key(self, monkeypatch, tmp_path):
        # Stub api + se_extractor + torch into sys.modules so the lazy
        # imports inside _default_loader resolve.
        import sys
        import types

        from server.pipelines import openvoice_tts

        # Track constructions to assert singleton behavior.
        constructions: list[str] = []

        class StubBaseSpeakerTTS:
            def __init__(self, config_path: str, device: str) -> None:
                constructions.append(f"BaseSpeakerTTS({config_path}, {device})")
                self.hps = types.SimpleNamespace(
                    data=types.SimpleNamespace(sampling_rate=24000),
                    speakers={"default": 0},
                )

            def load_ckpt(self, ckpt_path: str) -> None:
                constructions.append(f"BaseSpeakerTTS.load({ckpt_path})")

        class StubToneColorConverter:
            def __init__(self, config_path: str, device: str) -> None:
                constructions.append(f"ToneColorConverter({config_path}, {device})")

            def load_ckpt(self, ckpt_path: str) -> None:
                constructions.append(f"ToneColorConverter.load({ckpt_path})")

        api_module = types.ModuleType("api")
        api_module.BaseSpeakerTTS = StubBaseSpeakerTTS  # type: ignore[attr-defined]
        api_module.ToneColorConverter = StubToneColorConverter  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "api", api_module)

        se_module = types.ModuleType("se_extractor")
        def _get_se(wav: str, conv: Any, **_kw: Any) -> tuple[Any, str]:
            return (object(), "processed")
        se_module.get_se = _get_se  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "se_extractor", se_module)

        # Stub torch.load to return a sentinel embedding.
        torch_module = sys.modules.get("torch") or types.ModuleType("torch")
        torch_module.load = lambda _path: types.SimpleNamespace(  # type: ignore[attr-defined]
            to=lambda _device: object()
        )
        monkeypatch.setitem(sys.modules, "torch", torch_module)

        # Build a fake OpenVoice tree with the expected layout.
        ov = tmp_path / "OpenVoice"
        (ov / "checkpoints" / "base_speakers" / "EN").mkdir(parents=True)
        (ov / "checkpoints" / "base_speakers" / "EN" / "config.json").touch()
        (ov / "checkpoints" / "base_speakers" / "EN" / "checkpoint.pth").touch()
        (ov / "checkpoints" / "base_speakers" / "EN" / "en_default_se.pth").touch()
        (ov / "checkpoints" / "converter").mkdir(parents=True)
        (ov / "checkpoints" / "converter" / "config.json").touch()
        (ov / "checkpoints" / "converter" / "checkpoint.pth").touch()

        monkeypatch.setattr(openvoice_tts, "_loaded_cache", {})

        loaded1 = openvoice_tts._default_loader(str(ov), "cpu", None)
        loaded2 = openvoice_tts._default_loader(str(ov), "cpu", None)

        assert loaded1 is loaded2  # cache hit
        assert loaded1.sample_rate == 24000
        assert loaded1.target_se is None
        # Construction happened exactly once.
        assert sum(1 for c in constructions if "BaseSpeakerTTS(" in c) == 1
        assert sum(1 for c in constructions if "ToneColorConverter(" in c) == 1

    def test_default_loader_runs_se_extractor_when_speaker_wav_set(
        self, monkeypatch, tmp_path
    ):
        import sys
        import types

        from server.pipelines import openvoice_tts

        se_calls: list[str] = []

        class StubBaseSpeakerTTS:
            def __init__(self, *_a: Any, **_k: Any) -> None:
                self.hps = types.SimpleNamespace(
                    data=types.SimpleNamespace(sampling_rate=24000),
                    speakers={"default": 0},
                )
            def load_ckpt(self, *_a: Any, **_k: Any) -> None: pass

        class StubToneColorConverter:
            def __init__(self, *_a: Any, **_k: Any) -> None: pass
            def load_ckpt(self, *_a: Any, **_k: Any) -> None: pass

        api_module = types.ModuleType("api")
        api_module.BaseSpeakerTTS = StubBaseSpeakerTTS  # type: ignore[attr-defined]
        api_module.ToneColorConverter = StubToneColorConverter  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "api", api_module)

        se_module = types.ModuleType("se_extractor")
        def _get_se(wav: str, *_a: Any, **_k: Any) -> tuple[Any, str]:
            se_calls.append(wav)
            return (object(), "processed")
        se_module.get_se = _get_se  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "se_extractor", se_module)

        torch_module = sys.modules.get("torch") or types.ModuleType("torch")
        torch_module.load = lambda _p: types.SimpleNamespace(  # type: ignore[attr-defined]
            to=lambda _d: object()
        )
        monkeypatch.setitem(sys.modules, "torch", torch_module)

        ov = tmp_path / "OpenVoice"
        for sub in (
            "checkpoints/base_speakers/EN",
            "checkpoints/converter",
        ):
            (ov / sub).mkdir(parents=True)
        for f in (
            "checkpoints/base_speakers/EN/config.json",
            "checkpoints/base_speakers/EN/checkpoint.pth",
            "checkpoints/base_speakers/EN/en_default_se.pth",
            "checkpoints/converter/config.json",
            "checkpoints/converter/checkpoint.pth",
        ):
            (ov / f).touch()

        monkeypatch.setattr(openvoice_tts, "_loaded_cache", {})

        wav = "/abs/path/to/voice.wav"
        loaded1 = openvoice_tts._default_loader(str(ov), "cpu", wav)
        loaded2 = openvoice_tts._default_loader(str(ov), "cpu", wav)

        assert loaded1 is loaded2
        assert loaded1.target_se is not None
        # se_extractor.get_se ran exactly once across both loader calls.
        assert se_calls == [wav]
