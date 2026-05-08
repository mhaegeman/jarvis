# Real STT Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `MockSTT` with `WhisperSTT` (faster-whisper, `base.en`, one-shot final on `audio.end`) so a real spoken utterance produces a real transcript through the existing WS pipeline.

**Architecture:** New `pipelines/whisper_stt.py` module exposes a `WhisperSTT(STT)` class with an injectable `loader` callable. A module-level `_model_cache` dict keyed by `(name, device)` keeps the model singleton across WebSocket connections. `_build_stt()` factory in `main.py` decides between `MockSTT` and `WhisperSTT` based on `JARVIS_STT_ENGINE` and `importlib.util.find_spec("faster_whisper")` — auto falls back to `MockSTT` with a logged warning when the dep isn't installed.

**Tech Stack:** Python 3.12, `faster-whisper` (CTranslate2-backed), `numpy`, FastAPI, `pydantic-settings`, pytest with monkeypatch.

**Spec:** `docs/superpowers/specs/2026-05-08-real-stt-tts-design.md` — STT half (§4, §6, §7, §8, §9, §10, §11).

---

### Task 1: Add STT settings fields to `config.py`

**Files:**
- Modify: `server/server/config.py`
- Test: `server/tests/test_config.py` (create if missing)

- [ ] **Step 1: Write failing test for new Settings fields**

Create `server/tests/test_config.py`:

```python
"""Settings defaults — guard against accidental drift."""

from __future__ import annotations

from server.config import Settings


class TestSTTSettings:
    def test_stt_engine_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_STT_ENGINE", raising=False)
        s = Settings()
        assert s.stt_engine == "auto"

    def test_whisper_model_default(self, monkeypatch):
        monkeypatch.delenv("JARVIS_WHISPER_MODEL", raising=False)
        s = Settings()
        assert s.whisper_model == "base.en"

    def test_device_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_DEVICE", raising=False)
        s = Settings()
        assert s.device == "auto"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("JARVIS_STT_ENGINE", "whisper")
        monkeypatch.setenv("JARVIS_WHISPER_MODEL", "small.en")
        monkeypatch.setenv("JARVIS_DEVICE", "cuda")
        s = Settings()
        assert s.stt_engine == "whisper"
        assert s.whisper_model == "small.en"
        assert s.device == "cuda"
```

- [ ] **Step 2: Run tests; verify they fail**

```
cd server && pytest tests/test_config.py -v
```

Expected: 4 failures with `AttributeError: 'Settings' object has no attribute 'stt_engine'` (or similar).

- [ ] **Step 3: Add the fields**

Modify `server/server/config.py` — replace the body of `Settings` with:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    ws_port: int = 8765
    log_level: str = "INFO"
    model_name: str = "mock"
    model_context_max: int = 200000
    llm_max_tokens: int = 1024

    # validation_alias bypasses env_prefix so this loads from ANTHROPIC_API_KEY
    # (the SDK's standard convention) in either .env or the process environment.
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )

    # STT pipeline selection.
    stt_engine: str = "auto"  # auto | mock | whisper
    whisper_model: str = "base.en"
    device: str = "auto"  # auto | cuda | mps | cpu
```

- [ ] **Step 4: Run tests; verify they pass**

```
cd server && pytest tests/test_config.py -v
```

Expected: 4 passes.

- [ ] **Step 5: Commit**

```bash
git add server/server/config.py server/tests/test_config.py
git commit -m "feat(stt): add Settings fields for STT engine, model, device"
```

---

### Task 2: Implement `_resolve_device()` helper in `main.py`

**Files:**
- Modify: `server/server/main.py`
- Test: `server/tests/test_main_factory.py:end-of-file`

- [ ] **Step 1: Write failing tests**

Append to `server/tests/test_main_factory.py`:

```python
class TestResolveDevice:
    def test_explicit_cpu(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "cpu")
        from server.main import _resolve_device
        assert _resolve_device() == "cpu"

    def test_explicit_cuda(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "cuda")
        from server.main import _resolve_device
        assert _resolve_device() == "cuda"

    def test_explicit_mps(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "mps")
        from server.main import _resolve_device
        assert _resolve_device() == "mps"

    def test_auto_without_torch_returns_cpu(self, monkeypatch):
        """When torch is not importable, auto resolves to cpu."""
        import sys
        monkeypatch.setattr("server.main.settings.device", "auto")
        # Block the import of torch within _resolve_device.
        monkeypatch.setitem(sys.modules, "torch", None)
        from server.main import _resolve_device
        assert _resolve_device() == "cpu"
```

- [ ] **Step 2: Run tests; verify they fail**

```
cd server && pytest tests/test_main_factory.py::TestResolveDevice -v
```

Expected: 4 failures (`ImportError: cannot import name '_resolve_device'`).

- [ ] **Step 3: Implement `_resolve_device()`**

Add to `server/server/main.py` after the `_build_llm` function:

```python
def _resolve_device() -> str:
    """Return the torch device string for STT/TTS pipelines.

    Honors `JARVIS_DEVICE` when set to a concrete value; with `auto`,
    probes torch (cuda → mps → cpu) and falls back to `cpu` when torch
    is not importable.
    """
    explicit = settings.device
    if explicit in ("cuda", "mps", "cpu"):
        return explicit
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
```

- [ ] **Step 4: Run tests; verify they pass**

```
cd server && pytest tests/test_main_factory.py::TestResolveDevice -v
```

Expected: 4 passes.

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(stt): _resolve_device honors JARVIS_DEVICE with cpu fallback"
```

---

### Task 3: WhisperSTT skeleton — empty audio returns `""`

**Files:**
- Create: `server/server/pipelines/whisper_stt.py`
- Create: `server/tests/test_whisper_stt.py`

- [ ] **Step 1: Write failing test**

Create `server/tests/test_whisper_stt.py`:

```python
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
```

- [ ] **Step 2: Run tests; verify they fail**

```
cd server && pytest tests/test_whisper_stt.py -v
```

Expected: `ImportError: cannot import name 'WhisperSTT' from 'server.pipelines.whisper_stt'`.

- [ ] **Step 3: Implement minimal skeleton**

Create `server/server/pipelines/whisper_stt.py`:

```python
"""WhisperSTT — real STT via faster-whisper (one-shot final, no partials)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np

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
        async for _chunk in audio:
            pass
        return
        yield ""  # pragma: no cover — yield turns this into an async generator

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
```

- [ ] **Step 4: Run tests; verify they pass**

```
cd server && pytest tests/test_whisper_stt.py::TestEmptyAudio -v
```

Expected: 2 passes.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/whisper_stt.py server/tests/test_whisper_stt.py
git commit -m "feat(stt): WhisperSTT skeleton — empty audio short-circuits"
```

---

### Task 4: WhisperSTT — sub-200ms audio returns `""`

**Files:**
- Modify: `server/tests/test_whisper_stt.py`

- [ ] **Step 1: Write failing test**

Append to `server/tests/test_whisper_stt.py` (after the existing `TestEmptyAudio` class):

```python
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
```

- [ ] **Step 2: Run tests; verify they pass without code changes**

```
cd server && pytest tests/test_whisper_stt.py::TestThreshold -v
```

Expected: 2 passes (already implemented in Task 3).

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_whisper_stt.py
git commit -m "test(stt): assert sub-200ms audio short-circuits without calling model"
```

---

### Task 5: WhisperSTT — PCM bytes normalized to float32 in `[-1, 1]`

**Files:**
- Modify: `server/tests/test_whisper_stt.py`

- [ ] **Step 1: Write failing test**

Append to `server/tests/test_whisper_stt.py`:

```python
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
```

- [ ] **Step 2: Run tests; verify they pass**

```
cd server && pytest tests/test_whisper_stt.py::TestNormalization -v
```

Expected: 2 passes (already implemented in Task 3).

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_whisper_stt.py
git commit -m "test(stt): verify PCM Int16 LE normalization to float32 in [-1, 1]"
```

---

### Task 6: WhisperSTT — pass `language="en"`, `beam_size=1`; return joined text

**Files:**
- Modify: `server/tests/test_whisper_stt.py`

- [ ] **Step 1: Write failing test**

Append to `server/tests/test_whisper_stt.py`:

```python
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
        # Segments joined by single space, then stripped.
        assert result == "hello   there,  Max."

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
```

- [ ] **Step 2: Run tests; verify they pass**

```
cd server && pytest tests/test_whisper_stt.py::TestTranscribeArgsAndOutput -v
```

Expected: 4 passes (already implemented in Task 3).

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_whisper_stt.py
git commit -m "test(stt): pin transcribe kwargs and segment-join behavior"
```

---

### Task 7: WhisperSTT — `partials()` drains the audio iterator and yields nothing

**Files:**
- Modify: `server/tests/test_whisper_stt.py`

- [ ] **Step 1: Write failing test**

Append to `server/tests/test_whisper_stt.py`:

```python
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
```

- [ ] **Step 2: Run tests; verify it passes**

```
cd server && pytest tests/test_whisper_stt.py::TestPartials -v
```

Expected: 1 pass (already implemented in Task 3).

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_whisper_stt.py
git commit -m "test(stt): partials() drains audio without yielding partials in v1"
```

---

### Task 8: `_build_stt()` — `mock` engine returns `MockSTT`

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Write failing test**

Append to `server/tests/test_main_factory.py`:

```python
from server.pipelines.mock_stt import MockSTT


class TestBuildSTT:
    def test_mock_engine_returns_mock_stt(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.stt_engine", "mock")
        from server.main import _build_stt
        stt = _build_stt()
        assert isinstance(stt, MockSTT)
```

- [ ] **Step 2: Run tests; verify they fail**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT -v
```

Expected: `ImportError: cannot import name '_build_stt' from 'server.main'`.

- [ ] **Step 3: Implement minimal factory**

Add to `server/server/main.py` (after `_resolve_device`, before `lifespan`):

```python
import importlib.util  # add to imports at top of file

from .pipelines.interfaces import STT  # add to imports near LLM import


def _build_stt() -> STT:
    """Construct the STT pipeline based on `JARVIS_STT_ENGINE`.

    `auto` (default) returns `WhisperSTT` when faster-whisper is importable,
    otherwise logs a warning and returns `MockSTT`. Setting the engine
    explicitly to `whisper` makes a missing dep a hard `ImportError`.

    Raises:
        ImportError: when `engine="whisper"` and faster-whisper is not installed.
        ValueError: when `engine` is not one of {auto, mock, whisper}.
    """
    engine = settings.stt_engine
    if engine == "mock":
        return MockSTT()
    raise ValueError(f"unknown JARVIS_STT_ENGINE: {engine!r}")
```

Add `importlib.util` to the standard-library imports at the top:

```python
import contextlib
import importlib.util
import logging
```

And extend the existing `from .pipelines.interfaces import LLM` line to:

```python
from .pipelines.interfaces import LLM, STT
```

And import `MockSTT` if it isn't already imported (it is — `from .pipelines.mock_stt import MockSTT` is already at the top of `main.py`).

- [ ] **Step 4: Run tests; verify they pass**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT -v
```

Expected: 1 pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(stt): _build_stt mock branch"
```

---

### Task 9: `_build_stt()` — `auto` returns `WhisperSTT` when faster-whisper is importable

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Write failing test**

Append to `TestBuildSTT` in `server/tests/test_main_factory.py`:

```python
    def test_auto_with_faster_whisper_returns_whisper_stt(self, monkeypatch):
        from server.pipelines.whisper_stt import WhisperSTT
        monkeypatch.setattr("server.main.settings.stt_engine", "auto")
        monkeypatch.setattr("server.main.settings.whisper_model", "base.en")
        monkeypatch.setattr("server.main.settings.device", "cpu")
        # Stub find_spec → faster-whisper appears installed.
        monkeypatch.setattr(
            "importlib.util.find_spec",
            lambda name: object() if name == "faster_whisper" else None,
        )
        from server.main import _build_stt
        stt = _build_stt()
        assert isinstance(stt, WhisperSTT)

    def test_explicit_whisper_returns_whisper_stt(self, monkeypatch):
        from server.pipelines.whisper_stt import WhisperSTT
        monkeypatch.setattr("server.main.settings.stt_engine", "whisper")
        monkeypatch.setattr("server.main.settings.whisper_model", "base.en")
        monkeypatch.setattr("server.main.settings.device", "cpu")
        monkeypatch.setattr(
            "importlib.util.find_spec",
            lambda name: object() if name == "faster_whisper" else None,
        )
        from server.main import _build_stt
        stt = _build_stt()
        assert isinstance(stt, WhisperSTT)
```

- [ ] **Step 2: Run tests; verify they fail**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT -v
```

Expected: 2 new failures (`ValueError: unknown JARVIS_STT_ENGINE: 'auto'`).

- [ ] **Step 3: Extend `_build_stt()`**

Modify `_build_stt()` in `server/server/main.py`:

```python
def _build_stt() -> STT:
    """Construct the STT pipeline based on `JARVIS_STT_ENGINE`.

    `auto` (default) returns `WhisperSTT` when faster-whisper is importable,
    otherwise logs a warning and returns `MockSTT`. Setting the engine
    explicitly to `whisper` makes a missing dep a hard `ImportError`.

    Raises:
        ImportError: when `engine="whisper"` and faster-whisper is not installed.
        ValueError: when `engine` is not one of {auto, mock, whisper}.
    """
    engine = settings.stt_engine
    if engine == "mock":
        return MockSTT()
    if engine in ("auto", "whisper"):
        if importlib.util.find_spec("faster_whisper") is None:
            if engine == "whisper":
                raise ImportError(
                    "faster-whisper is not installed; run `pip install -e .[stt]`."
                )
            log.warning(
                "STT auto: faster-whisper not installed; using MockSTT. "
                "Install with `pip install -e .[stt]`."
            )
            return MockSTT()
        from .pipelines.whisper_stt import WhisperSTT
        return WhisperSTT(
            model=settings.whisper_model,
            device=_resolve_device(),
        )
    raise ValueError(f"unknown JARVIS_STT_ENGINE: {engine!r}")
```

- [ ] **Step 4: Run tests; verify they pass**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT -v
```

Expected: 3 passes.

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py server/tests/test_main_factory.py
git commit -m "feat(stt): _build_stt auto/explicit whisper branches"
```

---

### Task 10: `_build_stt()` — auto-fallback when faster-whisper missing logs warning and returns `MockSTT`

**Files:**
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Write failing test**

Append to `TestBuildSTT`:

```python
    def test_auto_without_faster_whisper_logs_and_returns_mock(self, monkeypatch, caplog):
        import logging
        monkeypatch.setattr("server.main.settings.stt_engine", "auto")
        monkeypatch.setattr(
            "importlib.util.find_spec", lambda name: None
        )
        from server.main import _build_stt
        with caplog.at_level(logging.WARNING, logger="server.main"):
            stt = _build_stt()
        assert isinstance(stt, MockSTT)
        assert any(
            "faster-whisper not installed" in rec.message for rec in caplog.records
        )

    def test_explicit_whisper_without_faster_whisper_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.stt_engine", "whisper")
        monkeypatch.setattr(
            "importlib.util.find_spec", lambda name: None
        )
        from server.main import _build_stt
        with pytest.raises(ImportError, match="faster-whisper is not installed"):
            _build_stt()
```

- [ ] **Step 2: Run tests; verify they pass**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT -v
```

Expected: 5 passes (Task 9 already implemented these branches).

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_main_factory.py
git commit -m "test(stt): pin auto-fallback warning and explicit-engine ImportError"
```

---

### Task 11: `_build_stt()` — invalid engine raises `ValueError`

**Files:**
- Modify: `server/tests/test_main_factory.py`

- [ ] **Step 1: Write failing test**

Append to `TestBuildSTT`:

```python
    def test_unknown_engine_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.stt_engine", "vosk")
        from server.main import _build_stt
        with pytest.raises(ValueError, match="JARVIS_STT_ENGINE"):
            _build_stt()
```

- [ ] **Step 2: Run tests; verify it passes**

```
cd server && pytest tests/test_main_factory.py::TestBuildSTT::test_unknown_engine_raises -v
```

Expected: 1 pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_main_factory.py
git commit -m "test(stt): pin invalid-engine ValueError"
```

---

### Task 12: Wire `_build_stt()` into `ws_endpoint`

**Files:**
- Modify: `server/server/main.py:86-91`

- [ ] **Step 1: Confirm existing WS integration test still passes before change**

```
cd server && pytest tests/test_ws_integration.py -v
```

Expected: all pass (current state, using `MockSTT`).

- [ ] **Step 2: Replace `MockSTT()` with `_build_stt()` in `ws_endpoint`**

Modify `server/server/main.py` — change the `Session(...)` call inside `ws_endpoint`:

```python
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    # Per-connection pipelines (stateless; cheap to allocate).
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=_build_stt(),
        llm=_build_llm(),
        tts=MockTTS(),
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()
```

- [ ] **Step 3: Run the existing WS integration test; verify still passes**

```
cd server && pytest tests/test_ws_integration.py -v
```

Expected: all pass. (`JARVIS_STT_ENGINE` defaults to `auto`; faster-whisper isn't installed in the dev env, so factory returns `MockSTT` — same behavior as before.)

- [ ] **Step 4: Run the full suite; verify nothing regresses**

```
cd server && pytest -v
```

Expected: all green (existing 97/97 + new STT tests).

- [ ] **Step 5: Commit**

```bash
git add server/server/main.py
git commit -m "feat(stt): wire _build_stt into ws_endpoint (auto-fallback to MockSTT)"
```

---

### Task 13: Add `[stt]` extra to `pyproject.toml`

**Files:**
- Modify: `server/pyproject.toml:19-27`

- [ ] **Step 1: Add the optional-dependency group**

Modify `server/pyproject.toml` — replace the `[project.optional-dependencies]` table with:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.7",
  "mypy>=1.13",
  "types-psutil>=5.9",
]
stt = [
  "faster-whisper>=1.0",
  "numpy>=1.26",
]
```

- [ ] **Step 2: Verify the toml parses**

```
cd server && python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"
```

Expected: silent success (returns 0).

- [ ] **Step 3: Verify `pip install -e .[stt]` resolves (dry run)**

```
cd server && pip install --dry-run -e .[stt] 2>&1 | tail -20
```

Expected: pip prints the resolved set including `faster-whisper` and `numpy`. (Actual install is optional — CI uses `[dev]` only.)

- [ ] **Step 4: Commit**

```bash
git add server/pyproject.toml
git commit -m "build(stt): add [stt] optional-dependency group"
```

---

### Task 14: Update deploy README — Real STT pipeline section

**Files:**
- Modify: `server/deploy/README.md`

- [ ] **Step 1: Read the current README to find the right insertion point**

```
sed -n '1,60p' server/deploy/README.md
```

Expected: prints the top of the file. Identify a logical place to add a new top-level section "## Real pipelines (optional)" — typically near the bottom, after deploy/run instructions.

- [ ] **Step 2: Append the section**

Append this Markdown block to `server/deploy/README.md`:

```markdown

## Real pipelines (optional)

The default install runs with mock pipelines. To enable real Whisper STT:

### STT — faster-whisper

```bash
cd server
pip install -e .[stt]
```

Then either leave `JARVIS_STT_ENGINE=auto` (default) or set it explicitly:

```bash
export JARVIS_STT_ENGINE=whisper
export JARVIS_WHISPER_MODEL=base.en   # or small.en, tiny.en, medium.en
export JARVIS_DEVICE=auto              # auto | cuda | mps | cpu
```

Restart the server. The first WS connection downloads the model (~140 MB
for `base.en`) into `~/.cache/huggingface/hub` and warms the singleton;
later connections reuse the cached model.

If `JARVIS_STT_ENGINE=auto` and faster-whisper isn't installed, the
server logs a `WARNING` and falls back to `MockSTT`. Set the engine to
`whisper` to make a missing dep a hard failure.

### TTS — OpenVoice

(Coming in the next release — see `docs/superpowers/specs/2026-05-08-real-stt-tts-design.md`.)
```

- [ ] **Step 3: Commit**

```bash
git add server/deploy/README.md
git commit -m "docs(stt): document JARVIS_STT_ENGINE, [stt] extra, model cache path"
```

---

### Task 15: Smoke test the full suite + linters one last time

**Files:** none (verification only).

- [ ] **Step 1: Run pytest**

```
cd server && pytest -v
```

Expected: all green.

- [ ] **Step 2: Run ruff**

```
cd server && ruff check .
```

Expected: no errors.

- [ ] **Step 3: Run mypy**

```
cd server && mypy --strict server
```

Expected: no errors. (Note: `whisper_stt.py` uses `# type: ignore[import-not-found]` on the lazy faster-whisper import — that's intentional and documented in the spec.)

- [ ] **Step 4: Manual e2e smoke (optional, requires `[stt]` installed)**

If you have faster-whisper installed in your dev env:

```bash
cd server
JARVIS_MODEL_NAME=mock JARVIS_STT_ENGINE=whisper python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

Open the web client, press the talk key, say "hello jarvis", release. The
first turn pays a 2–5 s warmup; the `stt.final` event in the dev console
should contain the transcript of what you said.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin claude/continue-project-saIuj
```

---

## Notes for the implementer

- **TDD discipline:** Every task starts with a failing test. If a test passes immediately because earlier code already covers it (Tasks 4–7 mostly do), commit anyway — the test pins the behavior so a later refactor can't silently break it.
- **No new dependencies in `[dev]`:** all unit tests run against fakes. `numpy` enters via `[stt]` only.
- **CI behavior:** `.github/workflows/ci.yml` should not change. Existing `pip install -e .[dev]` step stays as-is; new tests use fakes; `_build_stt()` falls back to `MockSTT` because faster-whisper isn't in `[dev]`.
- **Singleton caveat:** `_model_cache` lives in module scope. If a test ever runs the real `_default_loader` and then another test changes the cache, the cache leaks across tests. Mitigation: tests in this plan never touch `_default_loader` — they always inject `loader=`. Don't break that pattern.
- **mypy on the lazy import:** `from faster_whisper import WhisperModel` inside `_default_loader` needs `# type: ignore[import-not-found]` because faster-whisper isn't a hard dep. Documented in the file.
- **Integration test deferred:** Spec §9 describes a gated `tests/integration/test_real_pipelines.py` that exercises real Whisper end-to-end on a recorded WAV. It needs a `tests/fixtures/hello.wav` and benefits from being written alongside the TTS half so one fixture covers both. Add it as the first task of the TTS plan, or as a follow-up after both pipelines land.
