# Real TTS Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `MockTTS` with `OpenVoiceTTS` (per-sentence synth, ~100 ms PCM chunks at 24 kHz, optional voice cloning via `JARVIS_SPEAKER_WAV`) so Claude's reply is spoken by Jarvis end-to-end.

**Architecture:** New `pipelines/openvoice_tts.py` exposes `OpenVoiceTTS(TTS)` with an injectable `loader` callable returning a `LoadedOpenVoice` dataclass (the BaseSpeakerTTS model, ToneColorConverter, en_source_se tensor, optional target_se for cloning, sample rate). Production `_default_loader` prepends `JARVIS_OPENVOICE_PATH` to `sys.path` and imports `api`, `se_extractor` lazily on first synth — so `from .pipelines.openvoice_tts import OpenVoiceTTS` is cheap and CI's `[dev]` install never touches OpenVoice. A module-level cache keyed by `(openvoice_path, device, speaker_wav)` keeps the heavy state singleton across WS connections. `_build_tts()` factory mirrors `_build_stt()`: `JARVIS_TTS_ENGINE` (`auto`/`mock`/`openvoice`) + `importlib.util.find_spec("torch")` for the auto-fallback decision.

**Tech Stack:** Python 3.12, OpenVoice (cloned, not pip-installed), `torch>=2.1`, `librosa>=0.10`, `soundfile>=0.12`, `numpy>=1.26`, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-05-08-real-stt-tts-design.md` — TTS half (§5, §6 TTS-specific vars, §7, §8, §9, §10, §11).

**Sister plan (already shipped):** `docs/superpowers/plans/2026-05-08-real-stt-pipeline.md`. Patterns from STT (loader injection, find_spec factory, MPS handling, deploy README) are reused below — references inline.

---

### Task 1: Add TTS settings fields to `config.py`

**Files:**
- Modify: `server/server/config.py`
- Modify: `server/tests/test_config.py`

- [ ] **Step 1: Append failing tests**

Append to `server/tests/test_config.py`:

```python
class TestTTSSettings:
    def test_tts_engine_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_TTS_ENGINE", raising=False)
        s = Settings()
        assert s.tts_engine == "auto"

    def test_openvoice_path_default(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPENVOICE_PATH", raising=False)
        s = Settings()
        assert s.openvoice_path == "~/OpenVoice"

    def test_speaker_wav_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("JARVIS_SPEAKER_WAV", raising=False)
        s = Settings()
        assert s.speaker_wav is None

    def test_tts_env_overrides(self, monkeypatch):
        monkeypatch.setenv("JARVIS_TTS_ENGINE", "openvoice")
        monkeypatch.setenv("JARVIS_OPENVOICE_PATH", "/opt/OpenVoice")
        monkeypatch.setenv("JARVIS_SPEAKER_WAV", "/tmp/voice.wav")
        s = Settings()
        assert s.tts_engine == "openvoice"
        assert s.openvoice_path == "/opt/OpenVoice"
        assert s.speaker_wav == "/tmp/voice.wav"
```

- [ ] **Step 2: Run; verify fail**

```
cd /home/user/jarvis/server && python -m pytest tests/test_config.py::TestTTSSettings -v
```

Expected: 4 failures with `AttributeError: 'Settings' object has no attribute 'tts_engine'` (or similar).

- [ ] **Step 3: Add the fields**

Modify `server/server/config.py` — append to the `Settings` body (after the existing STT fields):

```python
    # TTS pipeline selection.
    tts_engine: str = "auto"  # auto | mock | openvoice
    openvoice_path: str = "~/OpenVoice"
    speaker_wav: str | None = None
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_config.py -v
```

Expected: all pass (existing 4 STT tests + 4 new TTS tests).

- [ ] **Step 5: Commit**

```bash
git add server/server/config.py server/tests/test_config.py
git commit -m "feat(tts): add Settings fields for TTS engine, OpenVoice path, speaker WAV"
```

---

### Task 2: `OpenVoiceTTS` skeleton — class shape + lazy `sample_rate()`

**Files:**
- Create: `server/server/pipelines/openvoice_tts.py`
- Create: `server/tests/test_openvoice_tts.py`

The plan locks in the wrapper shape: a `LoadedOpenVoice` dataclass holding the four heavyweight objects, an injectable `loader` callable (mirrors `WhisperSTT`'s pattern), and module-level cache keyed by `(openvoice_path_resolved, device, speaker_wav)`. Tasks 3–7 add tests that assert against this shape; Task 8 grows `_default_loader`.

- [ ] **Step 1: Write failing test**

Create `server/tests/test_openvoice_tts.py`:

```python
"""Unit tests for OpenVoiceTTS."""

from __future__ import annotations

from collections.abc import AsyncIterator
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

    # speech_text_speech.py uses `tts_model.get_text(...)`, `tts_model.hps`,
    # `tts_model.language_marks`, `tts_model.model.infer(...)`. Stub each.
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
        # Return a tensor-shaped stub — real wrapper calls .unsqueeze(0) and .size(0).
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
    def model(self) -> "FakeInner":
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
        # Mimic speech_text_speech.py: result[0][0, 0].data.cpu().float().numpy()
        from types import SimpleNamespace
        arr = self.parent.return_audio
        leaf = SimpleNamespace(data=SimpleNamespace(
            cpu=lambda: SimpleNamespace(float=lambda: SimpleNamespace(numpy=lambda: arr))
        ))
        # arr-shaped: outer[0] indexable, inner[0, 0] returns leaf.
        class _Outer:
            def __getitem__(self, _i: int) -> "_Inner":
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
```

- [ ] **Step 2: Run; verify fail**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py::TestSampleRate -v
```

Expected: `ImportError: cannot import name 'LoadedOpenVoice' from 'server.pipelines.openvoice_tts'`.

- [ ] **Step 3: Implement skeleton**

Create `server/server/pipelines/openvoice_tts.py`:

```python
"""OpenVoiceTTS — real TTS via OpenVoice (per-sentence synth, ~100ms PCM chunks)."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .interfaces import TTS

log = logging.getLogger(__name__)


@dataclass
class LoadedOpenVoice:
    """Bundle of OpenVoice singletons cached per (path, device, speaker_wav).

    `target_se` is `None` when no `JARVIS_SPEAKER_WAV` is configured;
    `synthesize()` then skips the tone-color conversion step and uses the
    default English speaker directly.
    """

    tts_model: Any  # api.BaseSpeakerTTS
    tone_color_converter: Any  # api.ToneColorConverter
    en_source_se: Any  # torch.Tensor
    target_se: Any | None  # torch.Tensor | None
    sample_rate: int


# Module-level cache keyed by the resolved (path, device, speaker_wav) tuple.
_loaded_cache: dict[tuple[str, str, str | None], LoadedOpenVoice] = {}


def _default_loader(
    openvoice_path: str, device: str, speaker_wav: str | None
) -> LoadedOpenVoice:
    """Lazy import + cached construction of OpenVoice models. See Task 8."""
    raise NotImplementedError("populated in Task 8")


class OpenVoiceTTS(TTS):
    def __init__(
        self,
        *,
        openvoice_path: str = "~/OpenVoice",
        device: str = "cpu",
        speaker_wav: str | None = None,
        loader: Callable[[str, str, str | None], LoadedOpenVoice] | None = None,
    ) -> None:
        self._path = openvoice_path
        self._device = device
        self._speaker_wav = speaker_wav
        self._loader = loader or _default_loader
        self._loaded: LoadedOpenVoice | None = None

    def _ensure_loaded(self) -> LoadedOpenVoice:
        if self._loaded is None:
            self._loaded = self._loader(self._path, self._device, self._speaker_wav)
        return self._loaded

    def sample_rate(self) -> int:
        return self._ensure_loaded().sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        # Implemented in Task 3; yields nothing for now so the file imports.
        if False:  # pragma: no cover
            yield b""
        return
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py -v
```

Expected: 1 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/openvoice_tts.py server/tests/test_openvoice_tts.py
git commit -m "feat(tts): OpenVoiceTTS skeleton — LoadedOpenVoice dataclass + lazy sample_rate"
```

---

### Task 3: `synthesize()` wraps text with language marks and calls `infer`

**Files:**
- Modify: `server/server/pipelines/openvoice_tts.py:60-65`
- Modify: `server/tests/test_openvoice_tts.py`

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_openvoice_tts.py`:

```python
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
```

- [ ] **Step 2: Run; verify fail**

Expected: `assert fake_tts.get_text_calls == ["[EN]hello world[EN]"]` fails because the skeleton's `synthesize` returns immediately.

- [ ] **Step 3: Implement `synthesize()` core**

Replace `synthesize()` in `server/server/pipelines/openvoice_tts.py` with:

```python
    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        loaded = self._ensure_loaded()
        pcm = await asyncio.to_thread(self._synth_one, loaded, text)
        if not pcm:
            return
        # Chunking is added in Task 4.
        yield pcm

    def _synth_one(self, loaded: LoadedOpenVoice, text: str) -> bytes:
        import torch  # type: ignore[import-not-found]

        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        mark = loaded.tts_model.language_marks.get("english", None)
        wrapped = f"[{mark}]{text}[{mark}]"
        stn = loaded.tts_model.get_text(wrapped, loaded.tts_model.hps, False)
        with torch.no_grad():
            x = stn.unsqueeze(0).to(loaded.tts_model.device)
            x_len = torch.LongTensor([stn.size(0)]).to(loaded.tts_model.device)
            sid = torch.LongTensor(
                [loaded.tts_model.hps.speakers["default"]]
            ).to(loaded.tts_model.device)
            audio = loaded.tts_model.model.infer(
                x, x_len, sid=sid, noise_scale=0.667, noise_scale_w=0.6
            )[0][0, 0].data.cpu().float().numpy()
            if loaded.target_se is not None:
                audio = loaded.tone_color_converter.convert_from_tensor(
                    audio=audio, src_se=loaded.en_source_se, tgt_se=loaded.target_se
                )
        clipped = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        return clipped.tobytes()
```

The fake `torch` is needed for `torch.LongTensor`, `torch.no_grad`. The test file injects a fake `torch` module via `sys.modules` so this code runs without real torch. Add this to the top of `tests/test_openvoice_tts.py` (above the imports of `LoadedOpenVoice`):

```python
import sys
import types

if "torch" not in sys.modules:
    fake_torch = types.ModuleType("torch")
    fake_torch.no_grad = lambda: _NoOpCM()  # type: ignore[attr-defined]
    fake_torch.LongTensor = lambda data: _FakeTensor(data)  # type: ignore[attr-defined]
    sys.modules["torch"] = fake_torch


class _NoOpCM:
    def __enter__(self): return self
    def __exit__(self, *args): return False


class _FakeTensor:
    def __init__(self, data): self.data = data
    def to(self, _device): return self
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py -v
```

Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/openvoice_tts.py server/tests/test_openvoice_tts.py
git commit -m "feat(tts): OpenVoiceTTS synthesize wraps text with [mark] and calls infer"
```

---

### Task 4: Chunk PCM output into ~100 ms windows

**Files:**
- Modify: `server/server/pipelines/openvoice_tts.py` (`synthesize` body)
- Modify: `server/tests/test_openvoice_tts.py`

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_openvoice_tts.py`:

```python
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
```

- [ ] **Step 2: Run; verify fail**

Expected: first test fails because Task 3's `synthesize` yields the full PCM as one chunk.

- [ ] **Step 3: Replace `synthesize()` with chunking version**

In `server/server/pipelines/openvoice_tts.py`, change `synthesize` to:

```python
    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        loaded = self._ensure_loaded()
        pcm = await asyncio.to_thread(self._synth_one, loaded, text)
        if not pcm:
            return
        chunk_bytes = int(loaded.sample_rate * 0.1) * 2  # 100 ms of Int16 LE mono
        for i in range(0, len(pcm), chunk_bytes):
            yield pcm[i : i + chunk_bytes]
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py -v
```

Expected: 5 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/openvoice_tts.py server/tests/test_openvoice_tts.py
git commit -m "feat(tts): yield synthesized PCM in ~100ms chunks for transport pacing"
```

---

### Task 5: Case-boundary regex preprocessing

**Files:**
- Modify: `server/tests/test_openvoice_tts.py` (test only — Task 3 already implements the regex)

- [ ] **Step 1: Append test pinning the regex behavior**

Append to `server/tests/test_openvoice_tts.py`:

```python
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
```

- [ ] **Step 2: Run; verify pass (already implemented in Task 3)**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py::TestTextPreprocessing -v
```

Expected: 2 pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_openvoice_tts.py
git commit -m "test(tts): pin lower→upper case-boundary space insertion"
```

---

### Task 6: Voice cloning path — `target_se` triggers `convert_from_tensor`

**Files:**
- Modify: `server/tests/test_openvoice_tts.py`

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_openvoice_tts.py`:

```python
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
```

- [ ] **Step 2: Run; verify pass (already implemented in Task 3)**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py::TestVoiceCloning -v
```

Expected: 1 pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_openvoice_tts.py
git commit -m "test(tts): pin voice-cloning path through ToneColorConverter"
```

---

### Task 7: PCM Int16 LE clipping correctness

**Files:**
- Modify: `server/tests/test_openvoice_tts.py`

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_openvoice_tts.py`:

```python
class TestPCMConversion:
    async def test_float32_clipped_to_int16_range(self):
        # Out-of-range floats must clip to ±32767 / -32768, not wrap.
        # Construct: -2.0, -0.5, 0.0, 0.5, 2.0 → -32768, -16384, 0, 16384, 32767.
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
        assert samples[1] == -16384  # -0.5 → -16384
        assert samples[2] == 0
        assert samples[3] == 16384   # 0.5 → 16384 (within float rounding)
        assert samples[4] == 32767   # 2.0 clamped
```

- [ ] **Step 2: Run; verify pass (already implemented in Task 3 via np.clip)**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py::TestPCMConversion -v
```

Expected: 1 pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_openvoice_tts.py
git commit -m "test(tts): pin float32 → Int16 LE clipping at full-scale boundaries"
```

---

### Task 8: Implement `_default_loader` — sys.path injection + checkpoint loading + cache

**Files:**
- Modify: `server/server/pipelines/openvoice_tts.py`
- Modify: `server/tests/test_openvoice_tts.py`

This is the production loader: prepends `JARVIS_OPENVOICE_PATH` to `sys.path`, imports `api`/`se_extractor`/`utils` lazily, builds the four singletons, and caches by `(path, device, speaker_wav)`.

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_openvoice_tts.py`:

```python
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
        se_calls: list[str] = []

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
            se_calls.append(wav)
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
        # Re-uses the same stubs as the previous test; only difference is
        # speaker_wav is set, which must invoke se_extractor.get_se exactly
        # once across repeated _default_loader calls (cache hit on 2nd call).
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
```

- [ ] **Step 2: Run; verify fail**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py::TestDefaultLoaderCache -v
```

Expected: 2 failures with `NotImplementedError: populated in Task 8`.

- [ ] **Step 3: Implement `_default_loader`**

Replace the stub `_default_loader` in `server/server/pipelines/openvoice_tts.py` with:

```python
def _default_loader(
    openvoice_path: str, device: str, speaker_wav: str | None
) -> LoadedOpenVoice:
    """Lazy import + cached construction of the OpenVoice singletons.

    Prepends `openvoice_path` to `sys.path` so the user-cloned `api`,
    `se_extractor`, and `utils` modules become importable. Constructs
    `BaseSpeakerTTS`, `ToneColorConverter`, the `en_default_se` tensor,
    and (when `speaker_wav` is set) the cloned `target_se` exactly once
    per `(path, device, speaker_wav)` tuple.
    """
    resolved_path = str(Path(openvoice_path).expanduser())
    key = (resolved_path, device, speaker_wav)
    if key in _loaded_cache:
        return _loaded_cache[key]

    if resolved_path not in sys.path:
        sys.path.insert(0, resolved_path)

    import torch  # type: ignore[import-not-found]
    from api import BaseSpeakerTTS, ToneColorConverter  # type: ignore[import-not-found]

    base_dir = Path(resolved_path) / "checkpoints" / "base_speakers" / "EN"
    conv_dir = Path(resolved_path) / "checkpoints" / "converter"

    tts_model = BaseSpeakerTTS(str(base_dir / "config.json"), device=device)
    tts_model.load_ckpt(str(base_dir / "checkpoint.pth"))
    tone_color_converter = ToneColorConverter(
        str(conv_dir / "config.json"), device=device
    )
    tone_color_converter.load_ckpt(str(conv_dir / "checkpoint.pth"))
    en_source_se = torch.load(str(base_dir / "en_default_se.pth")).to(device)

    target_se: Any | None = None
    if speaker_wav:
        import se_extractor  # type: ignore[import-not-found]
        target_se, _ = se_extractor.get_se(
            speaker_wav, tone_color_converter, target_dir="processed", vad=True
        )

    sample_rate = int(tts_model.hps.data.sampling_rate)
    loaded = LoadedOpenVoice(
        tts_model=tts_model,
        tone_color_converter=tone_color_converter,
        en_source_se=en_source_se,
        target_se=target_se,
        sample_rate=sample_rate,
    )
    _loaded_cache[key] = loaded
    return loaded
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_openvoice_tts.py -v
```

Expected: all pass (sample_rate + synthesize + chunking + preprocessing + cloning + clipping + 2 loader-cache tests).

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/openvoice_tts.py server/tests/test_openvoice_tts.py
git commit -m "feat(tts): _default_loader builds OpenVoice singletons with sys.path injection"
```

---

### Task 9: `_build_tts()` — `mock` engine returns `MockTTS`

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Append failing test**

Append to `server/tests/test_main_factory.py`:

```python
from server.pipelines.mock_tts import MockTTS

# Update the existing single-line server.main import:
# from server.main import _build_llm, _build_stt, _resolve_device
# →
# from server.main import _build_llm, _build_stt, _build_tts, _resolve_device
```

(Update that import line in-place.)

Then append:

```python
class TestBuildTTS:
    def test_mock_engine_returns_mock_tts(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.tts_engine", "mock")
        tts = _build_tts()
        assert isinstance(tts, MockTTS)
```

- [ ] **Step 2: Run; verify fail**

Expected: `ImportError: cannot import name '_build_tts'`.

- [ ] **Step 3: Implement minimal factory**

In `server/server/main.py`:
- Extend `from .pipelines.interfaces import LLM, STT` to `from .pipelines.interfaces import LLM, STT, TTS`.
- Add `_build_tts()` after `_build_stt()`:

```python
def _build_tts() -> TTS:
    """Construct the TTS pipeline based on `JARVIS_TTS_ENGINE`.

    `auto` (default) returns `OpenVoiceTTS` when torch is importable
    (faster-whisper + OpenVoice both ride on torch), otherwise logs a
    warning and returns `MockTTS`. Setting the engine explicitly to
    `openvoice` makes a missing dep a hard `ImportError`.

    Raises:
        ImportError: when `engine="openvoice"` and torch is not installed.
        ValueError: when `engine` is not one of {auto, mock, openvoice}.
    """
    engine = settings.tts_engine
    if engine == "mock":
        return MockTTS()
    raise ValueError(f"unknown JARVIS_TTS_ENGINE: {engine!r}")
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_main_factory.py::TestBuildTTS -v
```

Expected: 1 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(tts): _build_tts mock branch"
```

---

### Task 10: `_build_tts()` — `auto` and `openvoice` branches via `find_spec("torch")`

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Append failing tests**

Append to `TestBuildTTS`:

```python
    def test_auto_with_torch_returns_openvoice_tts(self, monkeypatch):
        from server.pipelines.openvoice_tts import OpenVoiceTTS
        monkeypatch.setattr("server.main.settings.tts_engine", "auto")
        monkeypatch.setattr("server.main.settings.openvoice_path", "~/OpenVoice")
        monkeypatch.setattr("server.main.settings.speaker_wav", None)
        monkeypatch.setattr("server.main.settings.device", "cpu")
        monkeypatch.setattr(
            "server.main.importlib.util.find_spec",
            lambda name: object() if name == "torch" else None,
        )
        tts = _build_tts()
        assert isinstance(tts, OpenVoiceTTS)

    def test_explicit_openvoice_returns_openvoice_tts(self, monkeypatch):
        from server.pipelines.openvoice_tts import OpenVoiceTTS
        monkeypatch.setattr("server.main.settings.tts_engine", "openvoice")
        monkeypatch.setattr("server.main.settings.openvoice_path", "~/OpenVoice")
        monkeypatch.setattr("server.main.settings.speaker_wav", "/tmp/voice.wav")
        monkeypatch.setattr("server.main.settings.device", "cpu")
        monkeypatch.setattr(
            "server.main.importlib.util.find_spec",
            lambda name: object() if name == "torch" else None,
        )
        tts = _build_tts()
        assert isinstance(tts, OpenVoiceTTS)
        # Speaker WAV plumbed through.
        assert tts._speaker_wav == "/tmp/voice.wav"
```

- [ ] **Step 2: Run; verify fail**

Expected: `ValueError: unknown JARVIS_TTS_ENGINE: 'auto'` for both new tests.

- [ ] **Step 3: Extend `_build_tts()`**

Replace the `_build_tts()` body with:

```python
def _build_tts() -> TTS:
    """[same docstring]"""
    engine = settings.tts_engine
    if engine == "mock":
        return MockTTS()
    if engine in ("auto", "openvoice"):
        if importlib.util.find_spec("torch") is None:
            if engine == "openvoice":
                raise ImportError(
                    "torch is not installed; run `pip install -e .[tts]` "
                    "and clone OpenVoice into JARVIS_OPENVOICE_PATH."
                )
            log.warning(
                "TTS auto: torch not installed; using MockTTS. "
                "Install with `pip install -e .[tts]`."
            )
            return MockTTS()
        from .pipelines.openvoice_tts import OpenVoiceTTS
        return OpenVoiceTTS(
            openvoice_path=settings.openvoice_path,
            device=_resolve_device(),
            speaker_wav=settings.speaker_wav,
        )
    raise ValueError(f"unknown JARVIS_TTS_ENGINE: {engine!r}")
```

- [ ] **Step 4: Run; verify pass**

```
cd /home/user/jarvis/server && python -m pytest tests/test_main_factory.py::TestBuildTTS -v
```

Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(tts): _build_tts auto/explicit openvoice branches"
```

---

### Task 11: `_build_tts()` — auto-fallback warning and explicit-engine `ImportError` (test only)

**Files:**
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Append tests**

Append to `TestBuildTTS`:

```python
    def test_auto_without_torch_logs_and_returns_mock(self, monkeypatch, caplog):
        import logging
        monkeypatch.setattr("server.main.settings.tts_engine", "auto")
        monkeypatch.setattr(
            "server.main.importlib.util.find_spec", lambda name: None
        )
        with caplog.at_level(logging.WARNING, logger="server.main"):
            tts = _build_tts()
        assert isinstance(tts, MockTTS)
        assert any("torch not installed" in rec.message for rec in caplog.records)

    def test_explicit_openvoice_without_torch_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.tts_engine", "openvoice")
        monkeypatch.setattr(
            "server.main.importlib.util.find_spec", lambda name: None
        )
        with pytest.raises(ImportError, match="torch is not installed"):
            _build_tts()
```

- [ ] **Step 2: Run; verify pass (Task 10 already implemented these branches)**

Expected: 5 `TestBuildTTS` tests pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_main_factory.py
git commit -m "test(tts): pin auto-fallback warning and explicit-engine ImportError"
```

---

### Task 12: `_build_tts()` — invalid engine raises `ValueError`

**Files:**
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Append test**

Append to `TestBuildTTS`:

```python
    def test_unknown_engine_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.tts_engine", "espeak")
        with pytest.raises(ValueError, match="JARVIS_TTS_ENGINE"):
            _build_tts()
```

- [ ] **Step 2: Run; verify pass**

Expected: 6 `TestBuildTTS` tests pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_main_factory.py
git commit -m "test(tts): pin invalid-engine ValueError"
```

---

### Task 13: Wire `_build_tts()` into `ws_endpoint`

**Files:**
- Modify: `server/server/main.py:ws_endpoint`

- [ ] **Step 1: Confirm baseline**

```
cd /home/user/jarvis/server && python -m pytest tests/test_ws_integration.py -v
```

Expected: all pass.

- [ ] **Step 2: Replace `MockTTS()` with `_build_tts()` in `ws_endpoint`**

In `server/server/main.py`, change the `Session(...)` call to:

```python
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=_build_stt(),
        llm=_build_llm(),
        tts=_build_tts(),
    )
```

- [ ] **Step 3: Re-run full suite; verify nothing regresses**

```
cd /home/user/jarvis/server && python -m pytest -q
```

Expected: all green. With `JARVIS_TTS_ENGINE=auto` (default) and torch unavailable in CI, the factory falls back to `MockTTS` — same observable behavior as before.

- [ ] **Step 4: Commit**

```bash
git add server/server/main.py
git commit -m "feat(tts): wire _build_tts into ws_endpoint (auto-fallback to MockTTS)"
```

---

### Task 14: Add `[tts]` extra to `pyproject.toml`

**Files:**
- Modify: `server/pyproject.toml:[project.optional-dependencies]`

- [ ] **Step 1: Add the group**

Modify `server/pyproject.toml` — add `[tts]` after `[stt]` (preserve existing `dev` and `stt`):

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.7",
  "mypy>=1.13",
  "types-psutil>=5.9",
  # Required to import server.pipelines.whisper_stt for unit tests, even
  # though the real STT engine itself lives behind the [stt] extra.
  "numpy>=1.26",
]
stt = [
  "faster-whisper>=1.0",
  "numpy>=1.26",
]
tts = [
  "torch>=2.1",
  "numpy>=1.26",
  "librosa>=0.10",
  "soundfile>=0.12",
]
```

(`torch` install is left to the user's pip index — README documents the CUDA vs CPU wheel choice.)

- [ ] **Step 2: Validate the toml**

```
cd /home/user/jarvis/server && python -c "import tomllib; tomllib.loads(open('pyproject.toml').read()); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add server/pyproject.toml
git commit -m "build(tts): add [tts] optional-dependency group"
```

---

### Task 15: Replace TTS placeholder in `server/deploy/README.md`

**Files:**
- Modify: `server/deploy/README.md` (the existing `### TTS — OpenVoice` placeholder section)

- [ ] **Step 1: Locate the existing TTS placeholder**

```
grep -n "TTS — OpenVoice\|Coming in the next release" /home/user/jarvis/server/deploy/README.md
```

Expected: a single `### TTS — OpenVoice` heading followed by the "(Coming in the next release ...)" line.

- [ ] **Step 2: Replace the placeholder section with real content**

Replace the lines from `### TTS — OpenVoice` through the closing parenthesis of the "Coming in the next release" paragraph with:

```markdown
### TTS — OpenVoice

OpenVoice is not a pip package. Clone the upstream repo and the Hugging Face
checkpoints into one directory:

```bash
git clone https://github.com/myshell-ai/OpenVoice ~/OpenVoice
cd ~/OpenVoice
git clone https://huggingface.co/myshell-ai/OpenVoice
cp -r OpenVoice/* .
```

Then install torch and the [tts] extras (CPU example; replace the torch
index URL for CUDA):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .[tts]
```

Set the engine and (optionally) the cloning reference WAV:

```bash
export JARVIS_TTS_ENGINE=openvoice                  # or leave =auto (default)
export JARVIS_OPENVOICE_PATH=~/OpenVoice            # default; override if cloned elsewhere
# Optional: 10–30 s of clean speech to clone the user's voice. Without it,
# OpenVoice uses its default English speaker.
export JARVIS_SPEAKER_WAV=/path/to/voice-sample.wav
```

The first synthesize call loads the OpenVoice models and (if cloning) runs
`se_extractor` once. Subsequent turns reuse the cached singletons.

If `JARVIS_TTS_ENGINE=auto` and torch isn't installed, the server logs a
`WARNING` and falls back to `MockTTS`. Set the engine to `openvoice` to make
a missing dep a hard failure.
```

- [ ] **Step 3: Commit**

```bash
git add server/deploy/README.md
git commit -m "docs(tts): document JARVIS_TTS_ENGINE, JARVIS_OPENVOICE_PATH, voice cloning"
```

---

### Task 16: Smoke test full suite + linters

**Files:** none (verification only).

- [ ] **Step 1: Run pytest**

```
cd /home/user/jarvis/server && python -m pytest -q
```

Expected: all green.

- [ ] **Step 2: Run ruff**

```
cd /home/user/jarvis/server && ruff check .
```

Expected: clean.

- [ ] **Step 3: Run mypy**

```
cd /home/user/jarvis/server && mypy
```

Expected: no errors. (`openvoice_tts.py` uses `# type: ignore[import-not-found]` on the lazy `torch`, `api`, `se_extractor` imports — same pattern as `whisper_stt.py`.)

- [ ] **Step 4: Manual e2e smoke (optional, requires `[tts]` + OpenVoice cloned)**

```bash
cd server
JARVIS_MODEL_NAME=mock JARVIS_TTS_ENGINE=openvoice \
  python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

In another terminal, run the web client. Type or speak a short phrase.
Expected: PCM frames arrive at 24 kHz Int16 LE in ~100 ms windows; the
centerpiece waveform responds to live amplitude; first reply pays a 5–15 s
warmup, subsequent replies are fast.

If `JARVIS_SPEAKER_WAV=path/to/voice.wav` is set, the spoken output uses the
cloned voice. `se_extractor.get_se` runs once on first synthesize, never
again.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin <branch-name>
```

---

## Notes for the implementer

- **TDD discipline:** every task starts with a failing test, even when later tests pass on the first run because earlier production code already covers them. The tests pin the behavior so a future refactor can't silently regress.
- **No new top-level imports of OpenVoice.** Both `from faster_whisper import ...` (in `whisper_stt.py`) and `from api import ...` / `import torch` (in `openvoice_tts.py`) MUST live inside `_default_loader`. CI's `[dev]` install never has these, so any module-level reference would break test collection.
- **`# type: ignore[import-not-found]`** belongs on every line that imports `torch`, `api`, `se_extractor`, or `utils` — these are not in `[dev]`. `numpy` is in `[dev]` (Task 14), so its module-level import does NOT need a type-ignore.
- **`mypy --strict`** is on. With `strict`, an unused `# type: ignore` becomes an `unused-ignore` error — only add the suppression when the dep is genuinely missing in `[dev]`.
- **The `loader` injection pattern is the test seam.** Production code uses `_default_loader`. Tests pass a closure that returns a `LoadedOpenVoice` containing `FakeBaseSpeakerTTS` etc. Don't try to monkeypatch the production singletons — inject.
- **Sample rate is 24 000.** Read it from `tts_model.hps.data.sampling_rate` for forward compatibility, but expect 24 kHz everywhere (matches OpenVoice English).
- **Chunk size is `int(sample_rate * 0.1) * 2`.** At 24 kHz that's 4 800 bytes. Keep the calculation derived from `sample_rate` so the wrapper still works if OpenVoice ships a 16 kHz model.
- **Sentence splitting happens in `Session._do_llm_and_tts`, not in `OpenVoiceTTS.synthesize`.** Each call to `synthesize` receives one sentence — so we synthesize the whole thing in one `infer` call and chunk the resulting PCM purely for transport pacing. Don't try to split sentences inside the wrapper.
- **Barge-in:** `synthesize` runs `infer` inside `asyncio.to_thread(...)`. When Session cancels the turn task between sentences (per spec §11 #5), the in-flight `infer` finishes its tail and is discarded; the next utterance starts a fresh turn. Don't implement mid-`infer` cancellation — too invasive for v1.
- **MPS handling:** unlike Whisper, OpenVoice runs on PyTorch directly and CAN use MPS. Don't normalize MPS → CPU here. `_resolve_device()` already gives the right value.
- **Integration test deferred again:** spec §9 also describes a real-WAV-roundtrip test for both pipelines. The `silence.wav` fixture is already in the repo (`server/tests/fixtures/silence.wav`). Adding the actual integration test that exercises real OpenVoice + faster-whisper is a follow-up after this plan lands — it requires a non-silent reference WAV and `JARVIS_RUN_INTEGRATION=1` gating, which is a separate concern from the unit-test path.
