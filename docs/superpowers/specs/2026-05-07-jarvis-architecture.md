# Jarvis — Umbrella Architecture

**Date:** 2026-05-07
**Status:** Draft, pending Architect (user) approval
**Owner:** Maxime Haegeman
**Type:** Cross-cutting architecture (anchors four sub-specs)

---

## 1. Vision

Jarvis is Maxime's personal AI assistant for daily work: a futuristic, voice-first, locally-private conversational interface deployed as a password-protected static website that connects to a local backend running Whisper (STT), a local LLM (via LM Studio / Ollama), and OpenVoice (TTS) — all streaming end-to-end so the system feels alive while it speaks.

The aesthetic is **a holographic HUD framing an audio-reactive waveform centerpiece** — sci-fi command-surface meets ambient sound visualization.

## 2. Decisions Locked In

| Concern | Decision | Why |
|---|---|---|
| **Visual language** | HUD frame (prototype C) with audio-reactive waveform (prototype B) in the central panel | Density + life; both are achievable in vanilla web |
| **Frontend stack** | Vite + vanilla TypeScript | Smallest abstraction over Canvas/SVG/CSS; HMR + types; clean static build |
| **Frontend deployment** | GitHub Pages | Free, static, sufficient for personal use |
| **Auth at site entry** | `staticrypt` — AES-256-GCM client-side bundle encryption with a password the user knows | "Secure enough for now" by user's standard; zero server, no auth surface |
| **Backend stack** | FastAPI + Python `websockets`, async throughout | WebSocket-native, streaming-friendly, fits Python ML stack |
| **Backend access** | `ws://localhost:PORT/ws` from the deployed HTTPS frontend | Chromium browsers treat `localhost` as a secure origin → mixed-content carve-out |
| **Browser support** | Chromium (Chrome, Edge, Brave) only for connected mode; visual demo works everywhere | User controls their browser |
| **STT** | Whisper, streaming with chunked audio + VAD | Already in use in `speech_text_speech.py` |
| **LLM** | OpenAI-compatible client pointed at local LM Studio (or Ollama) | Already in use; trivially swappable |
| **TTS** | OpenVoice, sentence-segmented streaming | Already in use; chunking enables lower latency |
| **v1 scope** | Full streaming pipeline end-to-end (mic → STT chunks → LLM token stream → TTS sentence stream → audio playback queue) | User chose ambition over staging |
| **Repo layout** | `web/`, `server/`, existing `prototypes/`, existing `second-brain/`, existing `speech_text_speech.py` left as legacy reference | Clean separation of concerns |

## 3. System Architecture

```
┌────────────────────────────────────────────────────┐
│  Browser  ·  https://<user>.github.io/jarvis        │
│  ┌──────────────────────────────────────────────┐  │
│  │ staticrypt unlock gate (password → AES-GCM)  │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │ Jarvis SPA (Vite + TS)                       │  │
│  │  • HUD layout (panels, telemetry, calendar)  │  │
│  │  • Center: audio-reactive waveform canvas    │  │
│  │  • Mic capture (getUserMedia + AudioWorklet) │  │
│  │  • Audio playback queue (Web Audio API)      │  │
│  │  • WebSocket client                          │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────┬─────────────────────────────────┘
                   │ ws://localhost:PORT/ws
                   ▼
┌────────────────────────────────────────────────────┐
│  Local backend (Maxime's laptop)                   │
│  FastAPI + websockets, single-user, no auth        │
│  ┌──────────────────────────────────────────────┐  │
│  │ Session orchestrator (per WS connection)     │  │
│  │  ── pipelines/ ──                            │  │
│  │  • whisper_stream.py   (chunked STT + VAD)   │  │
│  │  • llm_client.py       (OpenAI-compat stream)│  │
│  │  • openvoice_stream.py (sentence-chunked TTS)│  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

## 4. Cross-Cutting Concerns

### 4.1 WebSocket message protocol (binding contract for spec-02 & spec-03)

All messages are JSON except for raw audio binary frames. Each session maps 1:1 to one WebSocket connection.

**Client → Server:**
- `{type: "hello", clientVersion}` — handshake
- `{type: "audio.start", sampleRate, format}` — begin mic stream
- *(binary frame)* — PCM audio chunk
- `{type: "audio.end"}` — end mic stream, trigger inference
- `{type: "text", content}` — text-only input (fallback)
- `{type: "interrupt"}` — barge-in: stop current TTS playback and LLM generation

**Server → Client:**
- `{type: "ready"}` — session ready
- `{type: "stt.partial", text}` — interim transcription
- `{type: "stt.final", text}` — finalized user utterance
- `{type: "llm.token", delta}` — LLM token stream
- `{type: "llm.end"}` — LLM generation complete
- `{type: "tts.sentence", text, audioId}` — start of a TTS sentence
- *(binary frame, prefixed with audioId header)* — PCM audio chunk
- `{type: "tts.end", audioId}` — end of a TTS sentence's audio
- `{type: "error", code, message}` — error
- `{type: "telemetry", ...}` — non-essential signals (latency, queue depth, etc.) for HUD

The exact framing details (how `audioId` prefixes binary, sample rates, encoding) are finalized in **spec-02**.

### 4.2 Repository layout

```
jarvis/
  web/                   # Vite + TS frontend (spec-01 / spec-03)
    src/
      ui/                # HUD panels, waveform canvas
      audio/             # mic capture, playback queue
      ws/                # WebSocket client + protocol types
      main.ts
    public/
    index.html
    vite.config.ts
    package.json

  server/                # FastAPI backend (spec-02 / spec-03)
    main.py              # FastAPI app + WS route
    session.py           # per-connection orchestrator
    pipelines/
      whisper_stream.py
      llm_client.py
      openvoice_stream.py
    pyproject.toml

  docs/
    superpowers/
      specs/             # this file + four sub-specs
      plans/             # one plan per sub-spec

  prototypes/            # kept for reference (4 visual prototypes)

  second-brain/          # unchanged

  speech_text_speech.py  # legacy CLI, retained until spec-02 supersedes it

  .github/workflows/
    deploy.yml           # builds web/, encrypts with staticrypt, publishes to gh-pages
```

### 4.3 Worktrees

Per `.claude/skills/using-git-worktrees.md`, each sub-spec runs in `.worktrees/spec-NN-<slug>`. Worktrees never overlap on the same files (frontend vs backend).

### 4.4 Testing strategy

- **Frontend:** Vitest unit tests for protocol/state-machine code; Playwright headless smoke test for the HUD (loads, panels render, no console errors).
- **Backend:** pytest with `pytest-asyncio` for pipeline modules; integration test using a local WS client that exercises the full message protocol.
- **End-to-end:** spec-03 includes a manual checklist (mic, full conversation, barge-in, error recovery).

## 5. Sub-Spec Decomposition

Each sub-spec gets its own brainstorm → spec → plan → implementation cycle, dispatched to fresh subagents per the multi-agent setup (section 6).

| ID | Title | Scope | Deliverable | Dependencies |
|---|---|---|---|---|
| **spec-01** | Frontend shell | HUD + waveform UI driven by a fake event source; idle/listen/think/speak states; mic permission UX; not yet connected | Static `web/` site that runs on `localhost:5173` and visually demonstrates all states | none |
| **spec-02** | Backend streaming | FastAPI WebSocket server; streaming Whisper + LLM + OpenVoice; CLI test client; protocol from §4.1 fully implemented | `server/` runnable with `uvicorn`; `python -m server.cli_test` proves end-to-end voice roundtrip in terminal | none (parallel-safe with spec-01) |
| **spec-03** | Integration | Replace fake event source in `web/` with real WebSocket client; mic capture + Web Audio playback queue + barge-in; end-to-end voice in browser | `web/` connected to `server/`, working voice conversation locally | spec-01, spec-02 |
| **spec-04** | Deploy + gate | staticrypt config; GH Actions workflow; password-protected GH Pages publish; first deployed version | Live URL; merging to `main` redeploys | spec-01 (visual must work), spec-03 (so deployed version actually does something) |

## 6. Multi-Agent Development Team

The full team design (Tier 0 Architect → Tier 1 Orchestrator → Tier 2 Phase Leads → Tier 3 Domain Specialists → Tier 4 Quality Gates) was approved in the brainstorming session preceding this doc. Summary:

| Tier | Role | Permanence |
|---|---|---|
| 0 | Architect (Maxime) | Permanent |
| 1 | Orchestrator (main Claude session) | Persistent across the build |
| 2 | Brainstorming / Planning / Implementation / Review / Verification Leads | Fresh per phase |
| 3 | Frontend / Backend / ML-Audio / DevOps Engineers | Fresh per task |
| 4 | Code Reviewer, Spec Self-Reviewer, Plan Self-Reviewer, Bug Diagnostician, Test Runner | Fresh per invocation |

**Coordination rules:**
- Sealed context per dispatch: skill + relevant spec section + scope boundary + deliverable format.
- No specialist sees another specialist's output unless the plan says so.
- Two-stage review on every implementation task (implementer + fresh reviewer).
- One worktree per spec.
- Only the Orchestrator talks to the Architect.

## 7. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| `ws://localhost` blocked by browser policy in the future | Architecture supports moving to a tunnel (`cloudflared`) without frontend code changes — only the WS URL flips |
| OpenVoice / Whisper streaming has GPU latency variability | spec-02 includes telemetry; HUD surfaces it so the user sees pipeline state |
| staticrypt password leaked = whole site exposed | Acceptable risk per Architect; rotate by rebuilding with new password |
| LM Studio model swap changes prompt format | LLM client is OpenAI-compatible — model swap is a config change |
| Repo grows to require a real framework | We stay vanilla until pain justifies React/Svelte; not on critical path |

## 8. Out of Scope for v1

- Multi-user / multi-session support
- Cloud-hosted backend
- Mobile / phone access (would require backend tunnel — easy upgrade later)
- Persistent conversation memory beyond in-session context
- Tool use / function calling (LLM is conversational only in v1)
- Calendar / email integration (the HUD shows mock data in v1)

These are all viable post-v1 expansions and the architecture does not preclude any of them.

---

## Self-review notes (for orchestrator before commit)

- [x] No "TBD" or placeholders remain
- [x] No internal contradictions (verified protocol §4.1 matches mention in §3 and §5)
- [x] Scope: this doc is purely architectural — it does not pre-decide details that belong in sub-specs
- [x] Ambiguity: the `audioId` framing detail is explicitly deferred to spec-02
