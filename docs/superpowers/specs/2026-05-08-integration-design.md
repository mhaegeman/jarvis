# spec-03 · Browser ↔ Backend Integration — Design

**Date:** 2026-05-08
**Status:** Approved (orchestrator, per Architect delegation; user approved 2026-05-08)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)
**Sister specs:** `docs/superpowers/specs/2026-05-07-frontend-shell-design.md` (spec-01 — `EventSource` contract) · `docs/superpowers/specs/2026-05-08-backend-streaming-design.md` (spec-02 — WS protocol, binary framing)

---

## 1. Goal

Connect the spec-01 frontend (`web/`) to the spec-02 backend (`server/`) over WebSocket so a real voice conversation works end-to-end in a Chromium browser pointed at a locally-running FastAPI server.

The frontend's existing `EventSource` interface (`web/src/events/eventSource.ts`) is the only seam that changes implementation: `MockEventSource` is replaced at boot by a `WSEventSource` that speaks the spec-02 wire protocol verbatim. Mic audio is captured via AudioWorklet at 16 kHz PCM Int16 LE; assistant audio is played back via a Web Audio scheduling queue that feeds an `AnalyserNode` so the centerpiece waveform reacts to the assistant's voice.

When the backend is unreachable at boot the deployed site transparently falls back to `MockEventSource` so the visual demo still works on GitHub Pages without a laptop running.

## 2. Non-goals (out of scope for this spec)

- Authentication, password gate, deployment (spec-04)
- Replacing mocks in `server/` with real Whisper/LLM/OpenVoice (spec-02 Phase 2)
- Persistent reconnect of an in-flight turn — any drop cancels the turn and returns to idle
- HTTPS / `wss://` — Phase 1 stays on `ws://localhost`
- Multi-tab session coordination
- Mobile / non-Chromium browsers (architecture §2)
- New protocol messages — spec-03 consumes spec-02's protocol as-is

## 3. Inputs from prior specs (binding contracts)

| From | Contract | Used by |
|---|---|---|
| spec-01 | `EventSource` interface (`start/stop/beginListening/endListening/sendText/interrupt/on`) and `EventMap` types | `WSEventSource` implements verbatim — drop-in for `MockEventSource` |
| spec-01 | State machine `idle → listening → thinking → speaking → idle`; push-to-talk via `onMicDown/onMicUp` | Unchanged. WS source plugs into the same `actions` in `main.ts` |
| spec-01 | TelemetryPanel consumes `TelemetryEvent` | Now sourced from backend `telemetry` messages instead of synthetic data |
| spec-02 | JSON message shapes (`ready`, `stt.partial/final`, `llm.token/end`, `tts.sentence/end`, `error`, `telemetry`) | Decoded by `WSEventSource` 1:1 |
| spec-02 | Binary frame `kind\|idLen\|id\|payload`; `kind=0x01` mic, `kind=0x02` TTS | Encoded/decoded in `web/src/audio/wsCodec.ts` |
| spec-02 | Mic 16 kHz mono PCM Int16 LE; TTS 24 kHz mono PCM Int16 LE; ~100 ms TTS chunks | AudioWorklet emits 1600-sample (≈100 ms) mic frames; playback resamples via AudioContext |

## 4. Architecture

```
                 web/src/main.ts (boot)
                          │
                          ▼
     web/src/events/connect.ts ── tries ws:// with 1s timeout
        │                  │
        ├── success ──────►│
        │                  ▼
        │      web/src/events/wsEventSource.ts
        │           ├─ JSON in/out
        │           ├─ binary frame in/out  ── wsCodec.ts
        │           ├─ reconnect (1/2/4/8/…/30 s, capped)
        │           └─ telemetry pass-through
        │                  │
        │       beginListening ▼            ▲ tts.audioChunk
        │           audio/micWorklet.ts     │
        │           public/mic-processor.js │
        │                  │                │
        │                  ▼                ▼
        │       backend WS               audio/playbackQueue.ts
        │                                ├─ AudioBufferSource chain
        │                                └─ AnalyserNode → waveform
        │
        └── failure ───► MockEventSource (demo mode)
```

## 5. Module-level design

### 5.1 `web/src/events/connect.ts`

```ts
export interface ConnectOptions {
  url: string;            // default ws://localhost:8000/ws
  openTimeoutMs?: number; // default 1000
}

export interface ConnectResult {
  events: EventSource;     // WSEventSource | MockEventSource
  mode: "live" | "demo";
}

export async function connect(opts: ConnectOptions): Promise<ConnectResult>;
```

- Resolves WS URL: `?ws=` query param > `opts.url` > `ws://localhost:8000/ws`.
- Opens a probe `WebSocket(url)`. Awaits whichever fires first: `open`, `error`, or `setTimeout(openTimeoutMs)`.
- On `open` within timeout → wraps the socket in `WSEventSource` and returns `{events, mode: "live"}`.
- On `error` or timeout → closes the probe, instantiates `MockEventSource`, returns `{events, mode: "demo"}`. The first telemetry event the caller will see is `{level: "warn", message: "backend offline — demo mode"}`.

### 5.2 `web/src/events/wsEventSource.ts`

`WSEventSource` implements `EventSource` and owns:

- **Connection state machine:** `connecting → open → reconnecting → open → … → closed`.
- **`start()`** — sends `{type: "hello", clientVersion}`. Resolves on `ready`.
- **`beginListening()`** — boots an `AudioContext`/worklet, sends `{type: "audio.start", sampleRate: 16000, format: "pcm_s16le"}`, starts forwarding worklet PCM frames as binary.
- **`endListening()`** — flushes pending mic frames, sends `{type: "audio.end"}`, stops the worklet node.
- **`sendText(text)`** — sends `{type: "text", content: text}`.
- **`interrupt()`** — sends `{type: "interrupt"}` and synchronously cancels the local playback queue (do not wait for server's `llm.end`).
- **`on(event, handler)`** — same dispatcher pattern as `MockEventSource`; returns unsubscribe fn.

**Inbound dispatch:**
- Text frame → JSON-parse → switch on `type` → emit corresponding typed event. Unknown types log a warning, are not dispatched.
- Binary frame → `wsCodec.decode()` → `tts.audioChunk` event with `{audioId, samples: Float32Array}` (Int16 → Float32 conversion happens here).
- `error` JSON message → emit `error` event verbatim.
- `telemetry` JSON message → emit `telemetry` event verbatim. Backend heartbeats reach the HUD's TelemetryPanel.

**Reconnect:**
- WebSocket `close` (not initiated by us) or send-side error triggers reconnect.
- Backoff sequence `[1, 2, 4, 8, 16, 30]` seconds, then sticks at 30 s.
- Each attempt: emit `telemetry: {level: "warn", message: "reconnecting (attempt N)…"}`.
- On success: emit `telemetry: {level: "ok", message: "reconnected"}` and synthesize an `interrupt`-equivalent local cleanup (cancel any in-flight turn — server has already lost the turn). The state machine's `interrupt` action handles centerpiece reset.
- `stop()` sets a "user closed" flag → no further reconnect attempts.

### 5.3 `web/src/audio/wsCodec.ts`

Mirror of `server/server/audio.py`.

```ts
export const KIND_CLIENT_MIC = 0x01;
export const KIND_SERVER_TTS = 0x02;

export function encodeMicFrame(int16: Int16Array): ArrayBuffer; // kind=0x01, idLen=0
export function decodeAudioFrame(buf: ArrayBuffer): { kind: number; audioId: string; samples: Int16Array };
```

Layout: `[kind:u8][idLen:u8][id:utf8 idLen bytes][payload]`. Mic frames have `idLen=0`. TTS frames carry the `audioId`.

### 5.4 `web/src/audio/playbackQueue.ts`

```ts
export class PlaybackQueue {
  constructor(ctx: AudioContext, opts?: { sampleRate?: number /* default 24000 */ });
  readonly analyser: AnalyserNode; // for centerpiece consumption
  enqueue(audioId: string, int16: Int16Array): void;
  endSentence(audioId: string): void;
  interrupt(): void;
  destroy(): void;
}
```

- Single `AudioContext` (browser default rate, typically 48 kHz). PCM Int16 at 24 kHz is decoded to Float32 / 32768 and placed in an `AudioBuffer` at sample rate 24000 — the AudioContext resamples on playback.
- Per-audioId queue. A scheduling cursor `nextStart` tracks `ctx.currentTime` of the next chunk start. Every `enqueue()` creates an `AudioBufferSourceNode`, connects to `analyser → ctx.destination`, schedules `start(nextStart)`, and advances `nextStart += buffer.duration`.
- `endSentence(audioId)` is bookkeeping (lets us detect orphan chunks for later audioIds).
- `interrupt()` calls `stop()` on every currently-scheduled source, clears the queue, resets `nextStart` to `ctx.currentTime`.
- `analyser.frequencyBinCount` is sampled by `main.ts` while in `speaking` state to drive the centerpiece waveform amplitude (replaces synthetic `Math.random()` for `inputDb`/`amp`).

### 5.5 Mic capture: `web/src/audio/micWorklet.ts` + `web/public/mic-processor.js`

- `mic-processor.js` is the AudioWorkletProcessor running on the audio thread. It receives 128-sample Float32 buffers, accumulates into a 1600-sample ring (≈100 ms at 16 kHz), and `port.postMessage(ringSlice)` when full.
- `micWorklet.ts` (main thread) loads the worklet module via `audioWorkletNode = new AudioWorkletNode(ctx, "mic-processor")`, listens to messages, converts Float32 → Int16 (clamp to `[-1, 1]`, multiply by 32767, round), and hands the `Int16Array` to `WSEventSource` to encode + send.
- Critical: the AudioContext must be created at 16 000 Hz. Chromium ignores non-default rates on some hardware; if the chosen rate doesn't match, we resample in the worklet (linear) before posting.
- Mic permission flow already lives in `audio/micCapture.ts`; we reuse `ensureMic()` for permission and `MediaStream` plumbing.

## 6. Wiring change in `web/src/main.ts`

```ts
// before:
const events = new MockEventSource();

// after:
const { events, mode } = await connect({ url: import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws" });
if (mode === "demo") banner.show("Demo mode — backend offline");
```

Boot order: `events.start()` is awaited before user-facing controls become interactive. The synthetic telemetry generator in `main.ts` is removed; the panel now consumes only `telemetry` events from `events.on("telemetry", …)`. In demo mode, `MockEventSource` continues to emit synthetic telemetry as today.

The centerpiece waveform driver gains a branch: while in `speaking` state and `mode==="live"`, sample `playbackQueue.analyser` for amplitude; otherwise (idle / listening / thinking / demo) keep the existing logic.

## 7. Reconnect / state recovery

| Trigger | Action |
|---|---|
| WS `close` while no turn active | Begin reconnect loop. State stays `idle`. |
| WS `close` mid-turn (any state ≠ idle) | Cancel local playback (`playbackQueue.interrupt()`), stop mic worklet if listening, force state machine `interrupt`, then begin reconnect loop. |
| Reconnect attempt N | Emit `telemetry: warn "reconnecting (attempt N)…"`. |
| Reconnect succeeds | Re-send `hello`. On `ready`, emit `telemetry: ok "reconnected"`. |
| `stop()` called | Set user-closed flag, send no further packets, no further reconnects. |

We never attempt to resume a turn server-side after reconnect; spec-02 has no resume primitive and this is explicitly out of scope.

## 8. Telemetry surfacing

The existing TelemetryPanel takes `TelemetryEvent[]`. `main.ts` already subscribes to `events.on("telemetry", …)`. Spec-03 keeps that subscription and removes the synthetic generator. Backend heartbeats (every 5 s) become the live signal. Reconnect attempts and demo-mode banner also flow through this channel — no new UI.

## 9. Error mapping

- Backend `error` JSON → emitted as `error` event. Existing handler in `main.ts` already logs to telemetry; no change.
- WS open failure during reconnect → swallowed (logged at debug); only the user-visible `telemetry: warn "reconnecting…"` surfaces.
- Codec decode failure on a binary frame → emit `error` event with code `client.bad_frame`, drop the frame. Does not tear down the connection.
- AudioContext / AudioWorklet boot failure → emit `error` event with code `client.audio_unavailable`; mic actions become no-ops; UI still works for text input.

## 10. Testing strategy

### 10.1 Vitest unit tests (new)

| File | Tests |
|---|---|
| `test/wsCodec.test.ts` | round-trip mic frame, decode TTS frame with audioId, reject malformed (idLen overflow, short payload), Int16↔Float32 fidelity |
| `test/wsEventSource.test.ts` | hello/ready handshake; dispatch each JSON message type; binary TTS frame → `tts.audioChunk`; `interrupt()` cancels local playback before server confirms; reconnect with fake timers walks the backoff sequence; user-stop suppresses reconnect |
| `test/playbackQueue.test.ts` | interrupt cancels pending sources; `enqueue` order preserved per audioId; orphan chunks (audioId without `tts.sentence`) are dropped with a warning; `endSentence` is idempotent |
| `test/connect.test.ts` | open within timeout → live; open never resolves within timeout → demo + telemetry warn; open errors immediately → demo |

Mocks: a small `FakeWebSocket` test util (replaces `globalThis.WebSocket`) plus an `AudioContext` stub for `playbackQueue` (records scheduled sources; we don't actually play audio in tests).

### 10.2 Integration test (new, optional but recommended)

`test/integration.test.ts` (Vitest) — boots a `ws` server in-process that scripts the spec-02 message sequence, drives `WSEventSource` through one full turn, asserts emitted events match the canned scenario from spec-01. Not a substitute for manual e2e but catches drift between codec and protocol.

### 10.3 Manual e2e checklist (added to `web/README.md`)

1. **Live mode boot.** Start backend (`uvicorn server.main:app`). Reload page → no demo banner; TelemetryPanel shows server `heartbeat` entries within ~5 s.
2. **Push-to-talk text path.** Press the text-input shortcut, type "Brief me on today", submit → expect `stt.final`, `llm.token` stream, `tts.sentence` lines, and assistant audio audibly plays.
3. **Push-to-talk audio path.** Hold mic → speak → release. Expect `stt.partial` updates during hold, `stt.final` on release, then thinking → speaking with audio.
4. **Barge-in.** Mid-speak, press Esc. Audio cuts immediately; centerpiece returns to idle pose; `llm.end` arrives once.
5. **Reconnect.** Mid-conversation, kill `uvicorn`. Banner shows "reconnecting (attempt N)…". Restart `uvicorn`. Within 30 s see "reconnected"; UI is in `idle` and a new turn works.
6. **Demo fallback.** Stop backend, hard-reload page. See "demo mode" banner; mock scenario plays end-to-end with synthetic audio amplitude on centerpiece.
7. **Mic denied.** Block mic permission, attempt to listen. Error toast / telemetry "client.audio_unavailable"; text input still works.

### 10.4 Existing tests

Spec-01's 30 Vitest tests remain green. No state-machine or store changes.

## 11. Acceptance criteria

- All Vitest tests pass: existing 30 + new ~24 (estimate, not a target).
- `tsc --noEmit` clean. ESLint clean.
- `vite build` succeeds and the bundle stays under 30 KB gzip JS (current: ~7 KB; we add codec + ws source + worklet shim, expected delta < 15 KB).
- All seven items in §10.3 manual checklist pass against a real `uvicorn server.main:app` instance.
- `connect()` falls back to `MockEventSource` when no backend listens on the configured URL.
- Reconnect walks the documented backoff sequence (verified by Vitest with fake timers).
- TelemetryPanel surfaces backend heartbeats verbatim within one heartbeat cycle of connect.
- Centerpiece waveform reacts to assistant audio amplitude during `speaking` (live mode).
- No protocol drift: `wsCodec` round-trips against fixtures generated by `server/server/audio.py`.

## 12. Risks & open questions

| Risk | Mitigation |
|---|---|
| Chromium AudioContext not honoring 16 kHz rate | Worklet does linear resample if `ctx.sampleRate ≠ 16000`. Simple, sufficient for v1 STT. |
| AudioWorklet module loading path differences (Vite dev vs build) | Place processor in `web/public/mic-processor.js`; import URL is stable in both modes. |
| User reloads page during reconnect | `stop()` is called by `beforeunload` if we wire it; otherwise the closing socket is silent. |
| Backend latency variability causes audio underruns | Each TTS chunk is a fully-self-contained AudioBuffer; mid-sentence underrun shows as a brief silence, not a distortion. Acceptable for v1. |
| Browser denies AudioContext autoplay before user gesture | All AudioContext creation is gated on the first user gesture (already true for mic; same for playback queue — first `tts.audioChunk` after a gesture). |

## 13. Self-review notes (orchestrator before commit)

- [x] No "TBD" or placeholders remain
- [x] Internal consistency: protocol §3 matches spec-02 §4.4 binary framing
- [x] Scope: no overlap with spec-04 (no auth, no deploy, no static encryption)
- [x] Ambiguity: `connect()` precedence (`?ws=` > opts > default) is explicit; AudioContext sample rate fallback is explicit
- [x] No new protocol messages introduced — strictly consumes spec-02
