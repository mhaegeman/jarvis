# spec-02 · Backend Streaming Server — Design

**Date:** 2026-05-08
**Status:** Approved (orchestrator, per Architect delegation)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)
**Sister spec:** `docs/superpowers/specs/2026-05-07-frontend-shell-design.md` (spec-01 — frontend `EventSource` interface contract)

---

## 0. Implementation phasing (decision: 2026-05-08)

Spec-02 is implemented in two phases:

- **Phase 1 — mock pipelines (this plan).** Real FastAPI server, real WS protocol, real binary framing, real CLI test client, real session orchestrator and sentence splitter. The STT / LLM / TTS pipelines are **mocked**: the server emits canned events on realistic timings, drawn from a small library of scripted scenarios (analogous to the frontend's `MockEventSource`). No external service dependencies. Sufficient for spec-03 (browser ↔ backend integration) to proceed.
- **Phase 2 — real pipelines (future spec-02b).** Replace the three mock pipelines with `faster-whisper` (STT), `openai.AsyncOpenAI` streaming (LLM, default LM Studio), and OpenVoice (TTS). Triggered after spec-04 deploys the mock end-to-end stack.

Sections §5.1, §5.2, §5.4 below describe the full Phase 2 design. The Phase 1 plan implements them with mocks that share the **same async interface** as the real pipelines, so swap is mechanical.

§11 lists Phase 1 and Phase 2 acceptance criteria separately.

---

## 1. Goal

Deliver a `server/` Python package: a FastAPI WebSocket server that wraps streaming Whisper (STT), an OpenAI-compatible LLM client, and OpenVoice (TTS) into a single per-session pipeline. End-to-end: mic audio in → transcribed text → LLM tokens → spoken sentences out, all streaming.

The server implements the protocol from umbrella architecture §4.1 verbatim — same event names, same payload shapes — so the spec-01 frontend's `EventSource` interface (`web/src/events/eventSource.ts`) becomes the WebSocket client in spec-03 with no protocol drift.

A CLI test client (`python -m server.cli_test`) proves the round-trip in a terminal without a browser.

## 2. Non-goals (out of scope for this spec)

- Browser integration (spec-03)
- Authentication / multi-user / multi-session (architecture §8 — out of v1)
- Tunnels / cloud deployment (always `ws://localhost`)
- Persistent conversation memory beyond the WS session
- Tool use / function calling
- A second LLM provider abstraction layer — we commit to OpenAI-compatible
- Hot-swap of models at runtime (config sets it; restart applies it)

## 3. Architecture

### 3.1 Module layout

```
server/
  pyproject.toml
  README.md
  server/
    __init__.py
    main.py                  # FastAPI app, WS route, lifespan
    session.py               # per-connection orchestrator, holds conv history
    protocol.py              # pydantic message types + (de)serialization
    config.py                # pydantic-settings, env-driven
    audio.py                 # PCM resampling, base64 codec helpers
    pipelines/
      __init__.py
      stt.py                 # faster-whisper wrapper, chunked decode
      llm.py                 # OpenAI-compatible streaming client
      tts.py                 # OpenVoice wrapper, sentence-paced
      sentence_split.py      # streaming sentence boundary detector
    cli_test.py              # terminal client (text-only) for protocol smoke
  tests/
    __init__.py
    test_protocol.py         # message round-trip
    test_sentence_split.py   # streaming boundary detection
    test_session.py          # mock pipelines, full WS protocol exercise
    integration/
      __init__.py
      test_full_pipeline.py  # marker: requires_models · slow · opt-in
```

### 3.2 Layering

```
                 WebSocket (FastAPI)
                         │
                       Session
            ┌────────────┼────────────┐
            ▼            ▼            ▼
           STT          LLM          TTS
       (faster-      (openai      (OpenVoice +
        whisper)    streaming)   sentence-split)
```

- **Session** owns: conversation history (in-memory list), STT decoder instance, LLM client, TTS engine, the in-flight task graph (asyncio Tasks), and WS send/receive coroutines.
- **Pipelines** expose async generators. Session orchestrates them with `asyncio.create_task` and `asyncio.Queue` between stages.
- All blocking model calls run in `asyncio.to_thread` (or are inherently async via `openai.AsyncClient`). The event loop never blocks on inference.

### 3.3 Concurrency model

A WS connection lifecycle:

1. **Open** → server creates a `Session`. Emits `ready` once models are loaded (or immediately if pre-loaded at app startup).
2. **Receive loop**: parses inbound JSON / binary frames, dispatches to session methods.
3. **Pipeline orchestration**: when `audio.end` fires, the queued mic audio (or a pre-buffered tail) goes to STT → final text → LLM → token stream → sentence splitter → TTS → audio chunks.
4. **Send loop**: drains an outbound queue and writes JSON / binary frames back to the WS.
5. **Close** → session cancels all tasks, flushes nothing, releases STT decoder reference (singleton model stays loaded).

**Backpressure:** outbound `tts.audioChunk` frames are dropped (with a warning telemetry event) if the send queue is full. Generation never blocks waiting for the client. Send queue size: 256.

**Barge-in (`interrupt` from client):** session cancels all in-flight pipeline tasks and clears the outbound TTS queue. Drains the `interrupt` ack. Conversation history is preserved up to the last completed `assistant` turn (the in-flight reply is dropped).

## 4. Protocol — Wire Format

The architecture §4.1 message names are binding. This spec finalizes framing.

### 4.1 Message classes

All WS frames are either:
- **JSON text frames** — every message documented in arch §4.1 except audio chunks
- **Binary frames** — `tts.audioChunk` payload, see §4.4

### 4.2 Client → Server

| Message | Frame | Body |
|---|---|---|
| `hello` | text | `{type, clientVersion, capabilities?}` |
| `audio.start` | text | `{type, sampleRate, format: "pcm_s16le"}` |
| audio chunk | **binary** | raw PCM Int16 little-endian, `sampleRate` from preceding `audio.start` |
| `audio.end` | text | `{type}` |
| `text` | text | `{type, content}` |
| `interrupt` | text | `{type}` |

### 4.3 Server → Client

| Message | Frame | Body |
|---|---|---|
| `ready` | text | `{type}` |
| `stt.partial` | text | `{type, text}` |
| `stt.final` | text | `{type, text}` |
| `llm.token` | text | `{type, delta}` |
| `llm.end` | text | `{type}` |
| `tts.sentence` | text | `{type, text, audioId, sampleRate}` |
| `tts.audioChunk` | **binary** | see §4.4 |
| `tts.end` | text | `{type, audioId}` |
| `error` | text | `{type, code, message}` |
| `telemetry` | text | `{type, ts, level, message}` |

### 4.4 Binary frame format (audio chunks, both directions)

To avoid the cost of a JSON sidecar message per chunk while remaining self-describing, audio chunks are length-prefixed:

```
┌─────────────┬─────────────┬─────────────┬─────────────────────────────┐
│ kind (1B)   │ idLen (1B)  │ id (idLen)  │ samples (PCM, remainder)    │
└─────────────┴─────────────┴─────────────┴─────────────────────────────┘
   uint8         uint8          ASCII        Int16 LE  (s2c: see below)
```

- `kind`:
  - `0x01` — client → server, mic audio chunk. `id` is empty (`idLen=0`).
  - `0x02` — server → client, TTS audio chunk. `id` is the `audioId` from a preceding `tts.sentence`.
- `idLen`: number of ASCII bytes in `id` (0–255). For `kind=0x01`, always 0.
- `id`: ASCII identifier matching a prior `tts.sentence.audioId`.
- `samples`:
  - `kind=0x01`: PCM Int16 LE at the rate declared in the `audio.start` JSON message.
  - `kind=0x02`: PCM Int16 LE at the `sampleRate` declared in the matching `tts.sentence`.

**Why Int16 (not Float32)?**
- Wire size halved versus Float32; mic and TTS quality are not audibly affected at typical SNR.
- Browser AudioContext can decode either; conversion to Float32 happens on receipt.

**Why fixed length-prefix instead of separate JSON sidecar?**
- One frame per chunk. No cross-frame ordering hazard.
- 2 bytes overhead vs ≥40-byte JSON sidecar.

### 4.5 Audio format

| Stream | Sample rate | Channels | Format |
|---|---|---|---|
| Client mic → server | 16000 Hz | mono | PCM Int16 LE (declared in `audio.start`) |
| Server TTS → client | 24000 Hz | mono | PCM Int16 LE (declared per `tts.sentence`) |

**Why 16 kHz mic?** Whisper internally resamples to 16 kHz. Sending at 16 kHz removes a resampling stage on the server.

**Why 24 kHz TTS?** OpenVoice native sample rate is 24 kHz. Browser AudioContext resamples to its hardware rate (typically 48 kHz) on playback.

### 4.6 audioId

Format: `s<index>-<rand>` where `<index>` is the sentence index in the current reply (0-based) and `<rand>` is a 6-character `[a-z0-9]` token. Total length ≤ 12 ASCII bytes. Stable for the duration of one reply.

### 4.7 Heartbeat

The server sends a `telemetry` event every 5 s while the connection is otherwise idle. The client should treat absence of any frame for 30 s as a dead connection and reconnect.

## 5. Pipelines

### 5.1 STT (`pipelines/stt.py`)

- **Engine:** `faster-whisper` (CTranslate2 backend; ~4× faster than `openai-whisper`).
- **Model:** configurable; default `base.en` matches the legacy script.
- **Mode:** non-streaming Whisper but called on bounded chunks.
- **Strategy:**
  - The session buffers mic Int16 samples into a rolling list.
  - On `audio.end` (push-to-talk release): join the buffer, run Whisper once, emit `stt.final`.
  - Optionally during the listening window, run Whisper on cumulative buffer every 750 ms and emit `stt.partial` (truncated to the latest decode). Cancellable on `audio.end`.
- **VAD:** **not used in v1.** Push-to-talk is the user's commitment that "I'm done." Server VAD is a future enhancement when continuous listening is added.
- **Loaded once at app startup** to amortize the load cost (~3 s for `base.en`).

### 5.2 LLM (`pipelines/llm.py`)

- **Client:** `openai.AsyncOpenAI` with `base_url`, `api_key` from config (defaults: LM Studio, `not-needed`).
- **Model:** configurable; default `local-model` (LM Studio's auto-selected loaded model).
- **Streaming:** `chat.completions.create(stream=True)` → async iterate deltas → emit `llm.token` per delta.
- **History:** session keeps a list `[{role, content}]`. After each turn, append user message and assistant message. Cap at 20 messages (matches legacy script). System prompt prepended; configurable.
- **Cancellation:** holds a reference to the streaming response so `interrupt()` can `await response.close()` to abort generation server-side (frees the LM Studio worker).

### 5.3 Sentence splitter (`pipelines/sentence_split.py`)

- Pure function generator: input async iterator of token deltas, output async iterator of complete sentences.
- Boundary detection: buffer tokens. Whenever `[.!?]` is followed by whitespace or end-of-buffer, emit the buffered chunk as a sentence. Trailing prose without terminal punctuation at `llm.end` flushes as the last sentence.
- Tested with edge cases: ellipses (`...`), abbreviations (`Mr. Smith`), quoted speech (`"Yes." he said.`), code/numbers (`v1.0`).
- A small skip-list of abbreviations (`Mr|Mrs|Dr|Mt|St|Jr|Sr|vs|etc|i.e|e.g`) prevents false splits.

### 5.4 TTS (`pipelines/tts.py`)

- **Engine:** OpenVoice (re-uses the existing local install referenced by `speech_text_speech.py`).
- **Inputs:** sentence text + speaker (default).
- **Output:** Float32 numpy array at 24 kHz → converted to Int16 LE bytes.
- **Chunking:** the synthesized PCM is sliced into ~100 ms windows (2400 samples at 24 kHz) and yielded one window per chunk via the binary protocol.
- **Loaded once at app startup.**
- **Failure mode:** if OpenVoice raises, emit `error` with `code: tts.failed` + the exception message; skip the sentence; continue with subsequent sentences.

### 5.5 Pipeline graph (per turn)

```
       ┌─ stt.partial ─→ client (every 750 ms during listening)
       │
mic ──→ STT ──── stt.final ──→ LLM ──→ token deltas ──→ llm.token (each)
                                  │              │
                                  │              └→ sentence_split ──┐
                                  │                                  │
                                  └─ on completion ──→ llm.end ──┐   │
                                                                 │   │
                                                                 ▼   ▼
                                                              TTS engine
                                                                 │
                                                  ┌──────────────┼──────────────┐
                                                  ▼              ▼              ▼
                                            tts.sentence ─→ chunk frames ─→ tts.end
```

## 6. Session & main.py

### 6.1 Session lifecycle

```python
class Session:
    def __init__(self, ws: WebSocket, stt, llm, tts): ...
    async def run(self): ...                # main receive loop
    async def _handle_audio_start(msg): ...
    async def _handle_audio_chunk(buf): ...
    async def _handle_audio_end(): ...
    async def _handle_text(msg): ...
    async def _handle_interrupt(): ...
    async def _emit(msg): ...               # JSON
    async def _emit_audio(audio_id, pcm_int16): ...   # binary, framed
    async def cleanup(): ...
```

- Session holds `self._send_q: asyncio.Queue` (size 256) and a `self._sender_task` consuming it. All emits go through the queue. `cleanup()` cancels and drains.
- The current pipeline turn (STT → LLM → TTS) runs as a single `asyncio.Task` stored on the session. `interrupt()` cancels it.

### 6.2 main.py

```python
app = FastAPI()

@asynccontextmanager
async def lifespan(app):
    stt = await asyncio.to_thread(load_whisper, settings.whisper_model)
    llm = LLMClient(settings)
    tts = await asyncio.to_thread(load_openvoice, settings.openvoice_path)
    yield {"stt": stt, "llm": llm, "tts": tts}

app.router.lifespan_context = lifespan

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    session = Session(ws, **app.state.pipelines)
    try:
        await session.run()
    finally:
        await session.cleanup()
```

CORS / origin: in v1, accept any origin. (Local-only; see arch §2.)

### 6.3 Entry

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8765
```

Settings via `JARVIS_*` env vars (see §8 below).

## 7. CLI test client

`python -m server.cli_test [--text "Brief me"] [--ws ws://localhost:8765/ws]`

Behavior:
- Connects, prints `ready`, prints incoming `stt.*`, `llm.token` (concatenated), `tts.sentence`/`tts.end` markers, `error`, `telemetry`.
- If `--text` given: sends `text` once, prints reply, exits when `llm.end` arrives.
- If `--text` omitted: REPL — read line, send as `text`, print reply, repeat until `Ctrl-D`.
- Discards binary audio chunks (the CLI does not play audio in v1).

This is enough to prove the protocol end-to-end without browser, microphone, or speakers.

## 8. Configuration

`server/config.py` uses `pydantic-settings`:

| Env var | Default | Notes |
|---|---|---|
| `JARVIS_WS_PORT` | `8765` | uvicorn port |
| `JARVIS_LLM_BASE_URL` | `http://localhost:1234/v1` | LM Studio default |
| `JARVIS_LLM_MODEL` | `local-model` | LM Studio loaded model alias |
| `JARVIS_LLM_API_KEY` | `not-needed` | OpenAI client requires a non-empty value |
| `JARVIS_LLM_SYSTEM_PROMPT` | `"You are Jarvis, Maxime's personal AI assistant. Keep responses short and conversational."` | Override per session in spec-03+ |
| `JARVIS_LLM_HISTORY_CAP` | `20` | Messages retained in memory |
| `JARVIS_WHISPER_MODEL` | `base.en` | faster-whisper model id |
| `JARVIS_WHISPER_DEVICE` | `auto` | `cuda`, `cpu`, `auto` |
| `JARVIS_OPENVOICE_PATH` | `~/OpenVoice` | path to existing local install |
| `JARVIS_LOG_LEVEL` | `INFO` | uvicorn + app logger |

`.env` file in `server/` is loaded (gitignored).

## 9. Error handling

| Condition | Server behavior |
|---|---|
| Malformed JSON / unknown `type` | `error {code: "protocol.bad_message", message: "<details>"}` and continue |
| Binary frame before `audio.start` | `error {code: "protocol.audio_unframed"}` and discard |
| LLM endpoint unreachable | `error {code: "llm.unreachable", message: "<exception>"}`, drop the turn, return to ready |
| Whisper exception | `error {code: "stt.failed"}`, skip the turn |
| OpenVoice exception | `error {code: "tts.failed"}` per affected sentence; continue with next |
| WS disconnect mid-turn | session cancels in-flight task graph, no further emits |
| Send queue full | drop the chunk; emit `telemetry {level: "warn", message: "send queue overflow, dropped audio chunk"}` |

No bare `except:` clauses. Specific exception types per pipeline. Tracebacks logged via `uvicorn`/Python `logging`, not sent to client.

## 10. Testing

### 10.1 Unit (pytest + pytest-asyncio)

- `test_protocol.py` — every message type round-trips via `protocol.encode` / `protocol.decode`. Binary framing parser handles edge cases (empty audioId, max-length audioId, truncated frames).
- `test_sentence_split.py` — fixtures cover ellipses, abbreviations, quotes, no-final-punctuation, single-sentence, empty input.
- `test_session.py` — Session is constructed with mock pipelines that return scripted async iterators. A test WS using `httpx.AsyncClient` connects, drives the protocol, asserts the emitted event sequence matches expectations for: text input flow, audio input flow, interrupt mid-reply, malformed input, send queue overflow.

### 10.2 Integration (opt-in)

- `tests/integration/test_full_pipeline.py` — marked `@pytest.mark.requires_models`. Skipped by default. When run with `pytest -m requires_models`, exercises real STT + LLM + TTS against a recorded WAV. Assumes LM Studio is up.

### 10.3 Coverage

- Unit tests target ≥80% for protocol/session/sentence_split. Pipelines are thin wrappers and tested via integration.

### 10.4 What we don't test

- Real audio output quality (manual ear-test in spec-03).
- Cross-platform (Linux + WSL only; macOS/Windows are best-effort).
- Latency under load (this is a single-user system).

## 11. Acceptance criteria

### 11.A Phase 1 (mock pipelines — this plan)

1. `cd server && pip install -e .[dev]` succeeds with no external model dependencies.
2. `uvicorn server.main:app --port 8765` boots and emits `ready` immediately (no model loading).
3. `pytest` passes (unit suite, ≥80% coverage on `protocol.py` / `session.py` / `sentence_split.py`).
4. `python -m server.cli_test --text "say hi"` connects, prints streamed `llm.token`s and `tts.sentence`/`tts.end` markers, exits on `llm.end`. The reply comes from the canned scenario library; no external service needed.
5. `python -m server.cli_test` REPL accepts multi-turn input, preserves history (verifiable: a follow-up scenario references the prior turn's content slot).
6. Sending `interrupt` mid-reply cancels server generation: subsequent `llm.token`s and `tts.sentence`s stop arriving, exactly one `llm.end` is emitted (idempotent), and the CLI returns to the prompt.
7. Binary frame round-trip: a self-test in `test_protocol.py` proves the §4.4 framing.
8. Audio-input flow (CLI sends `audio.start` + N binary chunks + `audio.end`): server emits `stt.partial`(s) and `stt.final` with a canned transcription, then proceeds to LLM+TTS path.
9. `ruff check` clean (lint).
10. `mypy server` clean (strict).
11. Mock TTS in Phase 1 emits `tts.sentence` and `tts.end` for every sentence but **does not** emit binary `tts.audioChunk` frames. (The frontend's synthetic amplitude envelope handles "speaking" state visualization in spec-03 until Phase 2 delivers real audio.)

### 11.B Phase 2 (real pipelines — future spec-02b, not run in this plan)

12. `python -m server.cli_test --text "say hi"` against a running LM Studio produces a real reply.
13. Real Whisper + OpenVoice integration test passes when run with `pytest -m requires_models tests/integration/` on a machine with the local model infra set up.
14. Audio-output flow: `tts.audioChunk` binary frames carry actual PCM Int16 from OpenVoice synthesis; chunks pace at ~100 ms windows per §5.4.

## 12. Risks

| Risk | Mitigation |
|---|---|
| LM Studio not running → confusing errors | `error {code: "llm.unreachable"}` with explicit message; CLI client shows it prominently |
| OpenVoice install path varies per machine | Configurable via `JARVIS_OPENVOICE_PATH`; readme has setup steps |
| Whisper first-load is slow (~3s) and blocks ws accept if done lazily | Pre-load in FastAPI lifespan; emit `ready` only after load |
| Conversation history capped at 20 → context loss | Acceptable for v1; spec-03+ may persist or summarise older turns |
| Async cancellation during cancellation (interrupt mid-shutdown) | Session.cleanup() awaits with timeout; logs warnings rather than re-raising |
| Send queue overflow during long replies | Documented backpressure: drop chunks, emit telemetry; client renders best-effort |
| OpenVoice runs sync in thread → blocks one CPU core | Acceptable for single-user; future: dedicated worker process |

## 13. Out of scope (deferred to later specs / post-v1)

- Continuous listening / VAD-driven turn detection
- Multi-speaker / voice cloning at runtime
- Tool use, structured outputs
- Conversation persistence across sessions
- Streaming Whisper proper (not chunked)
- Multiple concurrent WS connections
- Health endpoint / readiness probe (none needed for single-user local)

## 14. Self-review notes (orchestrator)

- [x] No "TBD"
- [x] No internal contradictions (protocol §4 ↔ pipeline §5 ↔ acceptance §11 aligned)
- [x] Scope: spec-02 only; the EventSource interface from spec-01 is treated as a fixed contract that this server must satisfy
- [x] Ambiguity check: §4.4 audio framing is fully specified (kind byte + length-prefixed id + sample rate from sidecar); §4.6 audioId format pinned
- [x] All acceptance criteria are mechanically verifiable
- [x] Spec-01 frontend's expectations satisfied: every event the frontend `events.on(...)` calls is emitted with matching payload shape
