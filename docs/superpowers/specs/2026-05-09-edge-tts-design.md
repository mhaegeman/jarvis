# EdgeTTS Integration Design

**Date:** 2026-05-09  
**Status:** Approved  

## Problem

The server falls back to `MockTTS` (silence) because OpenVoice requires heavy model files (~2 GB) and slow CPU inference. Jarvis responds with text but no audible voice. The user needs a working TTS engine with minimal setup friction.

## Chosen Approach

Add `edge-tts` (Microsoft's neural TTS) as a new `JARVIS_TTS_ENGINE=edge` option. It requires no model downloads, produces high-quality speech in ~200 ms, and needs only two pip packages. The `auto` fallback order becomes: openvoice → edge → mock.

## Architecture

No client changes. The existing `PlaybackQueue` expects PCM int16 chunks streamed via the binary WebSocket protocol; `EdgeTTS` produces exactly that.

```
edge_tts.Communicate.stream()
    → MP3 bytes (Microsoft TTS cloud)
    → asyncio.to_thread(miniaudio.decode, ..., sample_rate=24000)
    → PCM int16 @ 24 kHz mono
    → 100 ms chunks (9 600 bytes each)
    → encode_tts_chunk → WebSocket binary frame
    → PlaybackQueue (inputRate=24000) → AudioContext (16 kHz) → speakers
```

## Components

### `server/pipelines/edge_tts.py` (new)

`EdgeTTS(TTS)` with one public method:

```python
async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]
```

Implementation:
1. Collect all MP3 audio from `edge_tts.Communicate(text, self._voice).stream()` (async, cloud call).
2. Decode + resample in a thread: `asyncio.to_thread(miniaudio.decode, mp3_bytes, nchannels=1, output_format=miniaudio.SampleFormat.SIGNED16, sample_rate=24000)`.
3. Yield 100 ms chunks: `chunk_bytes = 24000 * 2 // 10 = 4800 bytes`.
4. Return empty on empty text (guard against blank sentences from the splitter).

Constructor args: `voice: str`, `loader` (injected in tests to avoid network calls).

### `server/config.py`

- Extend `tts_engine` field comment: `auto | mock | openvoice | edge`
- Add `tts_voice: str = "en-US-ChristopherNeural"` (env var: `JARVIS_TTS_VOICE`)

### `server/main.py` — `_build_tts()`

New `edge` branch (added between `openvoice` and the final `raise`):

```python
if engine in ("auto", "edge"):
    if importlib.util.find_spec("edge_tts") is None or importlib.util.find_spec("miniaudio") is None:
        if engine == "edge":
            raise ImportError("edge-tts/miniaudio not installed; run `pip install -e .[tts-edge]`.")
        log.warning("TTS auto: edge-tts/miniaudio not installed; using MockTTS.")
        return MockTTS()
    from .pipelines.edge_tts import EdgeTTS
    return EdgeTTS(voice=settings.tts_voice)
```

`auto` resolution order in `_build_tts()`:
1. `openvoice` if torch + assets present
2. `edge` if edge-tts + miniaudio present  
3. `MockTTS` (warning logged)

### `pyproject.toml`

New optional group:

```toml
tts-edge = [
  "edge-tts>=7.0",
  "miniaudio>=1.2",
]
```

### `server/deploy/README.md`

Add an `edge-tts` subsection under "Real pipelines":

```bash
pip install -e .[tts-edge]
export JARVIS_TTS_ENGINE=edge          # or leave =auto (tries openvoice first)
export JARVIS_TTS_VOICE=en-US-ChristopherNeural  # optional, this is the default
```

## Data Flow

| Step | Detail |
|------|--------|
| Server receives `audio.end` | Session calls `_end_listening()` → `_start_turn()` |
| STT | Whisper transcribes audio → `stt.final` sent to client |
| LLM | Claude streams tokens → `llm.token` events; sentence splitter groups into sentences |
| TTS per sentence | `EdgeTTS.synthesize(sentence, audio_id)` called; MP3 fetched from Microsoft; decoded to PCM; yielded as 100 ms chunks |
| Wire | Each chunk → `encode_tts_chunk` → binary WS frame |
| Client | `PlaybackQueue.enqueue(audioId, int16)` → `AudioBufferSourceNode` at 24 kHz → resampled to 16 kHz by AudioContext → speakers |

## Error Handling

- Empty `text` → return immediately (no API call).
- `edge_tts.exceptions.NoAudioReceived` (blank response from MS) → log warning, yield nothing; the sentence is silently skipped (LLM text still visible).
- Network error → propagate exception; session's `_run_turn` catches and emits `session.turn_failed` to client.

## Testing

- Unit test: inject a `loader` stub that returns pre-encoded PCM bytes as fake MP3; assert `synthesize` yields the correct chunk count and size.
- No network calls in tests (loader is injected).
- Existing `test_mock_tts.py` pattern is the template.

## Out of Scope

- Streaming TTS (sending chunks before full MP3 arrives): edge-tts streams, but decoding requires the full MP3. Deferred.
- Voice selection UI: user sets via env var for now.
- OpenVoice setup: separate concern, unchanged.
