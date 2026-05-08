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

## LLM pipeline

Two backends are wired through the `LLM` ABC: a deterministic mock (default, used for offline dev / CI / demos) and a real Claude-backed pipeline.

### Selecting a backend

Set `JARVIS_MODEL_NAME`:

| Value | Backend | Notes |
|---|---|---|
| `mock` (default) | `MockLLM` | Scripted replies; no network calls. |
| `claude-haiku-4-5` | `ClaudeLLM` | Default Claude model. Requires `ANTHROPIC_API_KEY`. |
| `claude-sonnet-4-6` | `ClaudeLLM` | Same, with Sonnet as the default for un-prefixed messages. |
| `claude-opus-4-7` | `ClaudeLLM` | Same, with Opus as the default for un-prefixed messages. |

### Per-turn model prefixes

When `JARVIS_MODEL_NAME` selects a Claude model, you can promote a single turn to a different model with a slash prefix:

| Prefix | Routes to |
|---|---|
| `/haiku ...` | `claude-haiku-4-5` |
| `/sonnet ...` | `claude-sonnet-4-6` |
| `/opus ...` | `claude-opus-4-7` |

Unrecognized prefixes are passed through to the default model verbatim — JARVIS will see and react to the literal text, including the slash.

### Other env vars

- `ANTHROPIC_API_KEY` — required when `JARVIS_MODEL_NAME` selects Claude. The server will refuse to accept WebSocket connections at startup if it's missing, rather than 401-looping every turn.
- `JARVIS_LLM_MAX_TOKENS` — base per-request `max_tokens` (default `1024`). Auto-scaled to `2 ×` for `/sonnet` and `4 ×` for `/opus` because heavier models are invoked for harder questions, not for verbosity.

### Smoke test

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_MODEL_NAME=claude-haiku-4-5
cd server
python -m server.main  # in one terminal
python -m server.cli_test  # in another; type messages, observe deltas
```

Verify in [Anthropic's usage dashboard](https://console.anthropic.com/) that `/sonnet` and `/opus` prefixes route to the right model IDs.

## Configuration

Phase 1 reads env vars (prefix `JARVIS_`):

| Var | Default | Notes |
|---|---|---|
| `JARVIS_WS_PORT` | `8765` | uvicorn port |
| `JARVIS_LOG_LEVEL` | `INFO` | uvicorn + app logger |
| `JARVIS_MODEL_NAME` | `mock` | LLM backend selector (see "LLM pipeline" section above) |
| `ANTHROPIC_API_KEY` | — | Claude API key; see "LLM pipeline" section |
| `JARVIS_LLM_MAX_TOKENS` | `1024` | Base token limit; see "LLM pipeline" section |
