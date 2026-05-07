# Jarvis · Backend (`server/`)

FastAPI WebSocket server implementing the Jarvis protocol (architecture
§4.1). **Spec-02 Phase 1**: real protocol + framing + Session
orchestrator + tests, **mock pipelines** for STT / LLM / TTS. Phase 2
will swap mocks for `faster-whisper`, an OpenAI-compatible LLM client
(default LM Studio), and OpenVoice.

## Develop

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn server.main:app --port 8765
```

Health check: `GET http://localhost:8765/health` → `{"status":"ok"}`.
WebSocket: `ws://localhost:8765/ws`.

## Quality gates

```bash
ruff check .
mypy
pytest -q
```

Phase 1 ships with **54 tests** covering: protocol message round-trip,
binary frame codec, streaming sentence splitter, mock STT/LLM/TTS,
Session orchestrator (text + audio + interrupt + history),
WS integration (Starlette TestClient), and toolchain sanity.

## Try it

```bash
# Terminal 1
uvicorn server.main:app --port 8765

# Terminal 2 — one-shot
python -m server.cli_test --text "Brief me on today"

# Terminal 2 — REPL (Ctrl-D to exit)
python -m server.cli_test

# Terminal 2 — replay a WAV as mic input
python -m server.cli_test --audio-fixture tests/fixtures/silence.wav
```

## Architecture

See `docs/superpowers/specs/2026-05-08-backend-streaming-design.md`.

The pipeline interfaces (`server/pipelines/interfaces.py`) match the
shape that real `faster-whisper`, `openai.AsyncOpenAI`, and OpenVoice
will need in Phase 2. Swap is mechanical at the interface boundary.

## Phase 1 limitations (lifted in Phase 2)

- Replies come from a static scenario library (`scenarios.py`); no real LLM.
- STT returns canned text regardless of audio content.
- TTS emits sentence markers (`tts.sentence` / `tts.end`) but **no audio
  chunks**; spec-03 frontend uses its synthetic amplitude envelope
  during the `speaking` state.

## Configuration

Phase 1 reads two env vars (prefix `JARVIS_`):

| Var | Default | Notes |
|---|---|---|
| `JARVIS_WS_PORT` | `8765` | uvicorn port |
| `JARVIS_LOG_LEVEL` | `INFO` | uvicorn + app logger |

Phase 2 will add `JARVIS_LLM_BASE_URL`, `JARVIS_WHISPER_MODEL`,
`JARVIS_OPENVOICE_PATH`, etc.
