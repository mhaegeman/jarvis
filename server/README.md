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

## Multi-model support (Phase 3 — Codex CLI agent escalation, behind a flag)

Phase 1 of the multi-model build adds Pepper-flavoured plumbing without
changing any user-visible behaviour. The new code is dormant unless
`JARVIS_PERSONAS_ENABLED=true` is set, and even then it's not yet wired
into the Session — that happens in Phase 2.

See the design at `docs/superpowers/specs/2026-05-13-multi-model-support-design.md`.

### New env vars

| Var | Default | Notes |
|---|---|---|
| `JARVIS_PERSONAS_ENABLED` | `false` | Master feature flag. Leave off until Phase 5. |
| `OPENAI_API_KEY` | — | Required for Pepper. Bypasses `JARVIS_` prefix (mirrors `ANTHROPIC_API_KEY`). |
| `OPENAI_BASE_URL` | — | Optional pass-through to the OpenAI client. |
| `JARVIS_TIER_DEFAULT_JARVIS` | `fast` | One of `fast`/`balanced`/`deep`. |
| `JARVIS_TIER_DEFAULT_PEPPER` | `fast` | Same set. |
| `JARVIS_DISPATCHER_MODEL` | `claude-haiku-4-5` | Router LLM (used in Phase 2). |
| `JARVIS_PERSONA_WARMTH` | `subtle` | `subtle` or `off` — toggles the quiet-warmth clause in both prompts. |
| `JARVIS_PERSONA_REFRESH_TURNS` | `20` | Learning-loop cadence (used in Phase 5). |
| `JARVIS_LEARNING` | `on` | Master switch for the learning loop (used in Phase 5). |
| `JARVIS_CODEX_CLI_PATH` | — | Optional path to the `codex` binary (used in Phase 3). |
| `JARVIS_CODEX_APPROVAL` | `auto-low` | `auto-low`/`manual`/`never` (Phase 3). |
| `JARVIS_CODEX_SANDBOX` | `workspace-write` | `read-only`/`workspace-write`/`full-access` (Phase 3). |
| `JARVIS_CODEX_WORKDIR` | — | Overrides `JARVIS_GIT_ROOT` for the Codex agent specifically (Phase 3). |

### Phase 1 quick check

```bash
cd server
python -m pytest -q          # all green, including the new tests
ruff check . && mypy         # clean

# With the flag on, the registry can be constructed (still no Session wiring):
ANTHROPIC_API_KEY=fake OPENAI_API_KEY=fake JARVIS_PERSONAS_ENABLED=true \
  python -c "from server.personas import build_registry_from_settings; \
             from server.config import settings; \
             r = build_registry_from_settings(settings, codex_workdir=None); \
             print(r.available_ids())"
# Expected: ['jarvis', 'pepper']
```

### Phase 2 — multi-persona chat

With `JARVIS_PERSONAS_ENABLED=true` and both API keys set, the Session
delegates each turn to a `DialogManager`. Jarvis (Claude) and Pepper
(OpenAI) take turns within a single utterance via Dispatcher-planned
segments; each segment streams in its persona's voice.

Quick manual check:

```bash
ANTHROPIC_API_KEY=sk-ant-... \
OPENAI_API_KEY=sk-... \
JARVIS_PERSONAS_ENABLED=true \
JARVIS_TTS_ENGINE=edge \
uvicorn server.main:app --port 8000

# In another terminal:
python -m server.cli_test --text "Pepper, add a test for parse_prefix"
# Expect: dispatch.plan in the WS log; llm.token events with speaker=pepper;
# tts.sentence events with speaker=pepper; voice = en-US-AriaNeural.

python -m server.cli_test --text "Design and then implement a CSV exporter"
# Expect: 2-segment plan (Jarvis design, Pepper implement); voice swaps
# between Christopher and Aria mid-turn.
```

Phase 2 ships chat-only — `mode=codex_agent` segments degrade to chat
with a warning. The Codex CLI agent lands in Phase 3.

### Phase 3 — Codex CLI agent escalation

When Pepper is available AND the `codex` CLI is resolvable on `$PATH`
(or `JARVIS_CODEX_CLI_PATH`), `mode=codex_agent` segments dispatch to
the local CLI instead of running a chat stream. Pepper narrates
summary sentences in parallel (debounced ≥4s) so the user isn't
listening to silence while the agent grinds.

Quick manual check (real codex installed):

```bash
ANTHROPIC_API_KEY=sk-ant-... \
OPENAI_API_KEY=sk-... \
JARVIS_PERSONAS_ENABLED=true \
JARVIS_TTS_ENGINE=edge \
JARVIS_CODEX_CLI_PATH=/usr/local/bin/codex \
JARVIS_CODEX_WORKDIR=$(pwd) \
uvicorn server.main:app --port 8000

python -m server.cli_test --text "/codex add a test for parse_prefix"
# Expect: dispatch.plan with mode=codex_agent;
#         agent.start, agent.step events stream;
#         tts.sentence events with speaker=pepper carry the narration;
#         agent.end status=ok on completion.
```

Without the `codex` binary, the segment degrades to chat with a logged
warning — the rest of Phase 2 behaviour is unchanged.

Sandbox: defaults to `workspace-write` (Codex can read anywhere, write
only inside `JARVIS_CODEX_WORKDIR`). Approval mode: `auto-low` (low-
risk shell ops auto-approve; higher-risk ones surface as `agent.approval`
WS events the HUD will render in Phase 4).

## Configuration

Phase 1 reads env vars (prefix `JARVIS_`):

| Var | Default | Notes |
|---|---|---|
| `JARVIS_WS_PORT` | `8765` | uvicorn port |
| `JARVIS_LOG_LEVEL` | `INFO` | uvicorn + app logger |
| `JARVIS_MODEL_NAME` | `mock` | LLM backend selector (see "LLM pipeline" section above) |
| `ANTHROPIC_API_KEY` | — | Claude API key; see "LLM pipeline" section |
| `JARVIS_LLM_MAX_TOKENS` | `1024` | Base token limit; see "LLM pipeline" section |
