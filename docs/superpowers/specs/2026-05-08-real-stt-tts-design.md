# spec-02b — Real STT + TTS Pipelines (Design)

**Date:** 2026-05-08
**Status:** approved
**Supersedes:** spec-02 §11.B Phase 2 acceptance criteria
**Predecessors:** spec-02 (mock pipelines, merged), claude-llm α (real LLM via Anthropic, merged PR #9)

---

## 1. Goal

Replace the two remaining mock pipelines in `server/server/pipelines/` with real
implementations:

- `MockSTT` → `WhisperSTT` (faster-whisper)
- `MockTTS` → `OpenVoiceTTS` (OpenVoice)

The LLM half of "spec-02 Phase 2" already shipped as the Claude α pipeline.
Once this spec lands, the user can press the talk key, speak into the mic,
hear Jarvis reply, end-to-end, with no mocks in the path.

## 2. Non-goals

- Replacing the LLM pipeline (already done via `ClaudeLLM`).
- Streaming partial transcripts (`stt.partial`). One-shot final on
  `audio.end` is sufficient; the frontend already tolerates the absence of
  partials.
- Server-side voice activity detection / silence trimming. The frontend
  controls turn boundaries via `audio.start` / `audio.end`.
- True low-latency / streaming TTS synthesis. OpenVoice synthesizes
  per-sentence in one shot; we slice the resulting PCM into ~100 ms chunks
  for transport pacing only.
- Multi-language support. Whisper model defaults to `base.en`; OpenVoice
  uses the English default speaker.
- Persisting model checkpoints in the repo. Users clone OpenVoice
  themselves into `JARVIS_OPENVOICE_PATH`.

## 3. Architecture

Two new modules implementing the existing ABCs in
`server/server/pipelines/interfaces.py`. No protocol changes. No session
changes. Two factory functions in `main.py` mirror `_build_llm()`:

```
ws_endpoint
  └── Session(
        stt = _build_stt(),   # MockSTT | WhisperSTT
        llm = _build_llm(),   # MockLLM | ClaudeLLM (already shipped)
        tts = _build_tts(),   # MockTTS | OpenVoiceTTS
      )
```

Engine selection is env-driven (`JARVIS_STT_ENGINE`, `JARVIS_TTS_ENGINE`),
defaulting to `auto`. `auto` tries the real implementation; if its
optional pip dependency isn't installed, the factory logs a warning and
falls back to the mock. Setting the engine explicitly to `whisper` /
`openvoice` makes a missing dep a hard failure (so the user knows their
setup is wrong).

Models are loaded lazily — the first session that needs them pays the
warmup cost; subsequent sessions reuse the cached singleton.

## 4. STT — `pipelines/whisper_stt.py`

### 4.1 Engine

`faster-whisper` (CTranslate2 backend; ~4× faster than `openai-whisper`).
Default model: `base.en` (English-only, ~140 MB, runs CPU-acceptably).
Override via `JARVIS_WHISPER_MODEL`.

`compute_type`:
- `cuda` → `float16`
- `cpu` / `mps` → `int8`

Device per `_resolve_device()` (see §6).

### 4.2 Module shape

```python
# server/server/pipelines/whisper_stt.py
from collections.abc import AsyncIterator
import numpy as np
from .interfaces import STT

_model = None  # type: faster_whisper.WhisperModel | None

def _load_model(name: str, device: str) -> "WhisperModel":
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        compute = "float16" if device == "cuda" else "int8"
        _model = WhisperModel(name, device=device, compute_type=compute)
    return _model

class WhisperSTT(STT):
    def __init__(self, *, model: str, device: str) -> None:
        self._model_name = model
        self._device = device

    async def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        # No partials in v1. Drain the iterator so the producer is not
        # blocked, but yield nothing.
        async for _ in audio:
            pass
        return
        yield  # unreachable; makes this an async generator

    async def final(self, audio: AsyncIterator[bytes]) -> str:
        chunks = [c async for c in audio]
        if not chunks:
            return ""
        raw = b"".join(chunks)
        if len(raw) < 16000 * 2 // 5:  # <200 ms at 16 kHz mono Int16
            return ""
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        model = _load_model(self._model_name, self._device)
        # Run blocking transcribe in a thread.
        import asyncio
        segments, _info = await asyncio.to_thread(
            model.transcribe, arr, beam_size=1, language="en"
        )
        return " ".join(seg.text for seg in segments).strip()
```

### 4.3 Failure modes

| Condition | Behavior |
|---|---|
| Empty / sub-200ms audio | Return `""`. Session emits `stt.final("")` and skips the LLM turn (existing path in `_do_stt`). |
| Whisper raises | Re-raise. Session catches and emits `error {code: "stt.failed", message: ...}` (existing path). |
| Model file missing | Whisper raises on first load; same as above. README documents how to pre-fetch. |

### 4.4 Tests

`tests/test_whisper_stt.py`:

- `FakeWhisperModel` with a `.transcribe(arr, **kw)` that returns
  `([SimpleNamespace(text="hello world")], None)`. Monkeypatched into
  `whisper_stt._load_model` via `monkeypatch.setattr`.
- Asserts:
  - PCM Int16 LE bytes are decoded to float32 in `[-1, 1]`.
  - `language="en"` and `beam_size=1` are passed through.
  - `_load_model` is called once across multiple `final()` calls (singleton).
  - Empty / sub-threshold audio returns `""` without calling the model.
  - `partials()` drains the iterator and yields nothing.

## 5. TTS — `pipelines/openvoice_tts.py`

### 5.1 Engine

OpenVoice. Imported from a user-cloned directory at `JARVIS_OPENVOICE_PATH`
(default `~/OpenVoice`). The path is prepended to `sys.path` lazily on
first synthesize; `api`, `se_extractor`, `utils` are then importable.
Same approach as `speech_text_speech.py`.

Sample rate: `tts_model.hps.data.sampling_rate` (24000 for English).

### 5.2 Module shape

```python
# server/server/pipelines/openvoice_tts.py
from collections.abc import AsyncIterator
from pathlib import Path
import os, sys, re, asyncio
import numpy as np
from .interfaces import TTS

_loaded = False
_tts_model = None
_tone_color_converter = None
_en_source_se = None
_target_se = None  # populated only when JARVIS_SPEAKER_WAV is set
_sample_rate = 0

def _load(openvoice_path: str, device: str, speaker_wav: str | None) -> None:
    global _loaded, _tts_model, _tone_color_converter, _en_source_se, _target_se, _sample_rate
    if _loaded:
        return
    sys.path.insert(0, str(Path(openvoice_path).expanduser()))
    import torch
    from api import BaseSpeakerTTS, ToneColorConverter  # type: ignore
    import se_extractor  # type: ignore

    base = Path(openvoice_path).expanduser() / "checkpoints" / "base_speakers" / "EN"
    conv = Path(openvoice_path).expanduser() / "checkpoints" / "converter"

    _tts_model = BaseSpeakerTTS(str(base / "config.json"), device=device)
    _tts_model.load_ckpt(str(base / "checkpoint.pth"))
    _tone_color_converter = ToneColorConverter(str(conv / "config.json"), device=device)
    _tone_color_converter.load_ckpt(str(conv / "checkpoint.pth"))
    _en_source_se = torch.load(str(base / "en_default_se.pth")).to(device)
    _sample_rate = _tts_model.hps.data.sampling_rate

    if speaker_wav:
        _target_se, _ = se_extractor.get_se(
            speaker_wav, _tone_color_converter, target_dir="processed", vad=True
        )
    _loaded = True


class OpenVoiceTTS(TTS):
    def __init__(self, *, openvoice_path: str, device: str, speaker_wav: str | None) -> None:
        self._path = openvoice_path
        self._device = device
        self._speaker_wav = speaker_wav

    def sample_rate(self) -> int:
        # Loaded on first synthesize. If queried before, load now.
        _load(self._path, self._device, self._speaker_wav)
        return _sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        await asyncio.to_thread(_load, self._path, self._device, self._speaker_wav)
        pcm = await asyncio.to_thread(self._synth, text)
        chunk_bytes = int(_sample_rate * 0.1) * 2  # 100 ms of Int16 LE mono
        for i in range(0, len(pcm), chunk_bytes):
            yield pcm[i : i + chunk_bytes]

    def _synth(self, text: str) -> bytes:
        import torch
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        mark = _tts_model.language_marks.get("english", None)
        wrapped = f"[{mark}]{text}[{mark}]"
        stn = _tts_model.get_text(wrapped, _tts_model.hps, False)
        with torch.no_grad():
            x = stn.unsqueeze(0).to(_tts_model.device)
            x_len = torch.LongTensor([stn.size(0)]).to(_tts_model.device)
            sid = torch.LongTensor([_tts_model.hps.speakers["default"]]).to(_tts_model.device)
            audio = _tts_model.model.infer(
                x, x_len, sid=sid, noise_scale=0.667, noise_scale_w=0.6
            )[0][0, 0].data.cpu().float().numpy()
            if _target_se is not None:
                audio = _tone_color_converter.convert_from_tensor(
                    audio=audio, src_se=_en_source_se, tgt_se=_target_se
                )
        clipped = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        return clipped.tobytes()
```

### 5.3 Failure modes

| Condition | Behavior |
|---|---|
| `import api` / missing checkpoints (factory time) | Factory logs warning, returns `MockTTS` (auto path). With `JARVIS_TTS_ENGINE=openvoice`, raises. |
| `infer()` raises mid-conversation | Session emits `error {code: "tts.failed"}` for that sentence and continues to the next (existing protocol). |
| Speaker WAV missing | `se_extractor` raises at first synthesize; bubbled up as `tts.failed`; user fixes path and reconnects. |
| OOM on GPU | Bubbles up as `tts.failed`. v1 does not auto-fallback to CPU. |

### 5.4 Tests

`tests/test_openvoice_tts.py`:

- `FakeBaseSpeakerTTS`, `FakeToneColorConverter`, `FakeSeExtractor` modules
  inserted into `sys.modules` under names `api`, `se_extractor`, `utils`
  before `_load` runs. Plus a stub `torch` module that exposes only what
  the wrapper uses (`torch.no_grad`, `torch.LongTensor`, `torch.load`).
  Pattern mirrors how `tests/test_claude_llm.py` stubs the Anthropic SDK.
- Asserts:
  - First `synthesize()` call appends `JARVIS_OPENVOICE_PATH` to `sys.path`
    once.
  - PCM is yielded in chunks of `int(sr * 0.1) * 2` bytes (last chunk may
    be shorter).
  - `JARVIS_SPEAKER_WAV` set → `se_extractor.get_se` called once across
    repeated synthesize calls (singleton).
  - `JARVIS_SPEAKER_WAV` unset → `se_extractor.get_se` not called;
    `convert_from_tensor` not invoked.
  - Lower→upper case-boundary regex applied to the input text.

## 6. Configuration

New env vars added to `Settings` in `server/server/config.py`:

| Var | Default | Range / Notes |
|---|---|---|
| `JARVIS_STT_ENGINE` | `auto` | `auto` \| `mock` \| `whisper` |
| `JARVIS_TTS_ENGINE` | `auto` | `auto` \| `mock` \| `openvoice` |
| `JARVIS_WHISPER_MODEL` | `base.en` | any faster-whisper model id (e.g. `small.en`, `medium.en`, `tiny.en`) |
| `JARVIS_OPENVOICE_PATH` | `~/OpenVoice` | dir holding `api.py`, `se_extractor.py`, `utils.py`, `checkpoints/` |
| `JARVIS_SPEAKER_WAV` | unset | optional reference WAV path for tone-color cloning |
| `JARVIS_DEVICE` | `auto` | `auto` \| `cuda` \| `mps` \| `cpu` |

`_resolve_device()` in `main.py`:
- `JARVIS_DEVICE` set → return as-is.
- `auto` → try `import torch`; if `cuda.is_available()` → `cuda`; elif
  `backends.mps.is_available()` → `mps`; else `cpu`. If `torch` not
  importable → `cpu` (the wrappers will fall back to mocks anyway).

## 7. Factory wiring (`main.py`)

```python
def _build_stt() -> STT:
    engine = settings.stt_engine
    if engine == "mock":
        return MockSTT()
    if engine in ("auto", "whisper"):
        try:
            from .pipelines.whisper_stt import WhisperSTT
            return WhisperSTT(
                model=settings.whisper_model,
                device=_resolve_device(),
            )
        except ImportError as e:
            if engine == "whisper":
                raise
            log.warning(
                "STT auto: faster-whisper not installed (%s); using MockSTT", e
            )
            return MockSTT()
    raise ValueError(f"unknown JARVIS_STT_ENGINE: {engine!r}")


def _build_tts() -> TTS:
    engine = settings.tts_engine
    if engine == "mock":
        return MockTTS()
    if engine in ("auto", "openvoice"):
        try:
            from .pipelines.openvoice_tts import OpenVoiceTTS
            return OpenVoiceTTS(
                openvoice_path=settings.openvoice_path,
                device=_resolve_device(),
                speaker_wav=settings.speaker_wav,
            )
        except ImportError as e:
            if engine == "openvoice":
                raise
            log.warning(
                "TTS auto: torch/OpenVoice deps not installed (%s); using MockTTS", e
            )
            return MockTTS()
    raise ValueError(f"unknown JARVIS_TTS_ENGINE: {engine!r}")
```

`ws_endpoint` change is one line:

```python
session = Session(
    ws=_StarletteWSAdapter(ws),
    stt=_build_stt(),
    llm=_build_llm(),
    tts=_build_tts(),
)
```

## 8. Packaging

`server/pyproject.toml`:

```toml
[project.optional-dependencies]
stt = ["faster-whisper>=1.0", "numpy>=1.26"]
tts = ["torch>=2.1", "numpy>=1.26", "librosa>=0.10", "soundfile>=0.12"]
```

`numpy` is duplicated by design — pip dedupes. `torch` install is
documented in the README rather than enforced, because GPU vs CPU wheel
selection is platform-specific.

OpenVoice itself is **not** a pip dependency. Users clone the upstream
repo and Hugging Face checkpoints into `JARVIS_OPENVOICE_PATH`. README
addendum (§9) documents the exact commands.

## 9. Tests and CI

### Unit tests (run in CI, no model deps required)

- `tests/test_whisper_stt.py` — `FakeWhisperModel` harness
- `tests/test_openvoice_tts.py` — `FakeBaseSpeakerTTS` / `FakeToneColorConverter`
  / `FakeSeExtractor` injected via `sys.modules`
- `tests/test_main_factories.py` — extends existing factory tests:
  - `_build_stt()` with `engine=mock|auto|whisper` × import-success / import-fail
  - `_build_tts()` with `engine=mock|auto|openvoice` × import-success / import-fail
  - `_resolve_device()` with `JARVIS_DEVICE=cpu|cuda|mps|auto`

### Integration test (gated, not in CI)

`tests/integration/test_real_pipelines.py` — marked
`@pytest.mark.requires_models` (marker already declared in
`pyproject.toml`), additionally gated on `JARVIS_RUN_INTEGRATION=1` to
prevent accidental runs. Loads `tests/fixtures/hello.wav` (~1 s "hello
jarvis"), checks:

- `WhisperSTT().final(audio_iter)` returns text containing "hello"
- `OpenVoiceTTS().synthesize("Standing by.", "id1")` yields >0 chunks
  totaling at least `0.5 * sample_rate * 2` bytes
- Sample rate matches `tts.sample_rate()`

### CI behavior

`.github/workflows/ci.yml` server job stays unchanged: `pip install -e .[dev]`
only. No `[stt]` / `[tts]` install. All unit tests use fakes, so existing
97/97 + new tests stay green and fast.

## 10. Deploy notes

`server/deploy/README.md` gets a new section: "Real pipelines (optional)".

```markdown
## Real STT/TTS pipelines (optional)

The default install runs with mock pipelines. To enable real Whisper STT
and/or OpenVoice TTS:

### STT only (faster-whisper)

```
pip install -e .[stt]
```

Set `JARVIS_STT_ENGINE=whisper` (or leave `auto`) and restart the server.
First connection downloads the `base.en` model (~140 MB) into
`~/.cache/huggingface/hub`.

### TTS only (OpenVoice)

OpenVoice is not a pip package. Clone it and the HF checkpoints:

```
git clone https://github.com/myshell-ai/OpenVoice ~/OpenVoice
cd ~/OpenVoice
git clone https://huggingface.co/myshell-ai/OpenVoice
cp -r OpenVoice/* .
```

Then install torch and the [tts] extras (CPU example; replace the
torch index URL for CUDA):

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .[tts]
```

Set `JARVIS_TTS_ENGINE=openvoice` (or leave `auto`) and restart.

### Optional voice cloning

Set `JARVIS_SPEAKER_WAV=/path/to/voice-sample.wav` (10–30 s of clean
speech). The reference is loaded once at first synthesis.

### Device

`JARVIS_DEVICE` defaults to `auto` (cuda > mps > cpu). Override with
`cpu` to avoid GPU contention.
```

`web/README.md` gets a one-line pointer at the top of the manual e2e
checklist: "For real voice round-trip, see `server/deploy/README.md` →
Real pipelines."

## 11. Acceptance criteria

1. **No-extras install unchanged.** `pip install -e .` (no extras) →
   server runs; `JARVIS_STT_ENGINE=auto` and `JARVIS_TTS_ENGINE=auto` log
   fallback warnings on first connect; mocks behave exactly as today;
   existing 97/97 pytest stays green.
2. **STT real path.** With `[stt]` installed and `JARVIS_STT_ENGINE=auto`:
   speaking into the mic produces a real `stt.final` event whose text
   matches the spoken phrase. Manual smoke via the deployed web UI.
3. **TTS real path.** With `[tts]` + OpenVoice cloned and
   `JARVIS_TTS_ENGINE=auto`: Claude's reply is spoken; PCM frames arrive
   at 24 kHz Int16 LE in ~100 ms windows; the centerpiece waveform
   responds to live amplitude.
4. **Voice cloning.** `JARVIS_SPEAKER_WAV=path/to/voice.wav` swaps the
   voice without code changes. `se_extractor` runs once per process, not
   per turn.
5. **Barge-in.** Pressing the talk key during a reply cancels the
   in-flight turn cleanly. The tail of one in-flight `infer()` call is
   discarded; no stuck async tasks; the next utterance starts a fresh
   turn.
6. **Quality gates.** `mypy --strict server` clean; `ruff check` clean;
   new unit tests pass under existing CI.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OpenVoice HF checkpoint layout shifts between releases. | README pins to the `myshell-ai/OpenVoice` HF snapshot path. Wrapper raises a clear error if `checkpoints/base_speakers/EN/checkpoint.pth` is missing. |
| `librosa` pulls `numba` which has Python-version constraints. | Extras are isolated. If `numba` blocks 3.12 we drop `librosa` (only used by `se_extractor`); the no-cloning path keeps working. |
| First-call cold model latency 2–5 s on CPU. | Documented as "first conversation feels slow." Future spec: warm models in `lifespan`. |
| `sys.path` insertion is process-global — running pytest in the same process can leak the OpenVoice path. | Tests insert their fakes into `sys.modules` before importing the wrapper, never call the real `_load`. |
| `JARVIS_OPENVOICE_PATH` not absolute / not expanded. | `Path(openvoice_path).expanduser()` everywhere it's used. |
| Auto-detect silently falls back to mock when user expected real. | Factory logs a `WARNING` with the import error. Setting engine explicitly to `whisper`/`openvoice` makes it a hard failure. |

## 13. Out of scope (future work)

- Streaming / incremental TTS synthesis (true low-latency speech).
- Server-side VAD / silence trimming.
- Multi-language Whisper + OpenVoice.
- Eager model warmup at app startup.
- Reusable model server (separate process, multiple sessions share GPU).
- GPU OOM auto-fallback to CPU.
- Persisting conversation memory beyond the WS session (separate spec).
