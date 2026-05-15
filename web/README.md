# Jarvis · Frontend (`web/`)

Vite + TypeScript SPA implementing the Jarvis HUD with audio-reactive
waveform centerpiece. Spec-01 of the Jarvis build.

## Develop

```bash
cd web
npm install
npm run dev          # dev server on http://localhost:5173
```

Append `?dev=1` to the URL to expose the **Run scenario** button — useful
for demoing the full state cycle without using the microphone.

## Quality gates

```bash
npm run lint          # ESLint (flat config)
npm run test          # Vitest unit tests (state machine, store, mock event source, transcript, analyzer)
npm run test:e2e      # Playwright smoke (Chromium) — see note below
npm run build         # tsc --noEmit && vite build → dist/
npm run preview       # serve the production build
```

### Playwright system dependencies (one-time)

The smoke test needs Chromium's shared libraries. On Debian/Ubuntu:

```bash
sudo npx playwright install-deps chromium
```

Without those libraries the test will fail with `libnspr4.so: cannot open shared object file`.

## Live deployment

Deployed at: **https://mhaegeman.github.io/jarvis/** (password-gated via [staticrypt](https://github.com/robinmoisson/staticrypt)).

Deploy is automatic: every push to `main` rebuilds the site, encrypts
`index.html` with the `STATICRYPT_PASSWORD` repo secret, and publishes to
GitHub Pages via `actions/deploy-pages`.

The unlock page is a custom staticrypt template at `web/unlock-template.html`.
Editing it changes the look of the password gate; the encryption pipeline
(CI workflow, `STATICRYPT_PASSWORD` secret) is unchanged.

### Rotate the password

1. Settings → Secrets and variables → Actions → `STATICRYPT_PASSWORD` → Update.
2. Re-run the **Deploy** workflow from the Actions tab (or push any commit to `main`).

### Backend autostart

The deployed site connects to `ws://localhost:8000/ws`, so a backend must
be running on the laptop. See `../server/deploy/README.md` for a
`systemd --user` unit that keeps `uvicorn` alive across reboots and login.

## Architecture

See `docs/superpowers/specs/2026-05-07-frontend-shell-design.md` (this
spec) and `docs/superpowers/specs/2026-05-07-jarvis-architecture.md`
(the umbrella architecture).

The frontend connects to the backend via `src/events/connect.ts`, which
probes `ws://localhost:8000/ws` (override with `VITE_WS_URL`) for ~1 s
and either returns a real `WSEventSource` (live mode) or falls back to
`MockEventSource` (demo mode). Both implement the same `EventSource`
interface (`src/events/eventSource.ts`).

Audio capture uses an AudioWorklet (`public/mic-processor.js`) emitting
1600-sample (≈100 ms) Int16 LE PCM frames at 16 kHz. Assistant audio is
played through `src/audio/playbackQueue.ts`, which schedules
`AudioBufferSourceNode`s through an `AnalyserNode` — the centerpiece
waveform reacts to that analyser while in `speaking` state.

## State

`idle | listening | thinking | speaking`. Transitions are guarded by
`src/state/stateMachine.ts`. The render loop reads from a tiny
observable store (`src/state/store.ts`) and updates components.

## Keyboard

- **Space (hold)** — push-to-talk
- **Esc** — interrupt current reply

## Phase 4 — Multi-model UI surface

Phase 4 adds dual-persona rendering to the HUD. All new affordances are flag-driven: when the backend's `JARVIS_PERSONAS_ENABLED` flag is off (or the server is offline), the single-Jarvis UX is preserved.

**Demo mode** (`?dev=1` + no backend): MockEventSource emits a synthetic 2-segment plan (Jarvis design → Pepper implement) so all Phase 4 UI can be exercised without a backend.

### New WebSocket messages consumed

| Message | Payload | Effect |
|---|---|---|
| `dispatch.plan` | `{turnId, segments[], rationale}` | DispatchRibbon above transcript; speaker dots on voice-dock entries |
| `llm.segment_end` | `{speaker, segmentIdx}` | Signals segment boundary (tint crossfade is triggered by next `llm.token`) |
| `agent.start` | `{speaker, task, runId}` | Activates Agent Panel in the East Code zone |
| `agent.step` | `{runId, kind, summary, detail?}` | Appends a step row in the Agent Panel |
| `agent.approval` | `{runId, prompt, choices[]}` | Renders approval card with one button per choice |
| `agent.progress` | `{runId, phase, percent?}` | Updates the Agent Panel progress bar |
| `agent.end` | `{runId, status, summary}` | Collapses the Agent Panel; East Code zone is restored |

### New client messages sent

| Message | When |
|---|---|
| `agent.approve {runId, choice}` | User clicks an approval card button |
| `agent.cancel {runId}` | User clicks the cancel button in the Agent Panel |

### New UI components

- **Dual persona chip (Topbar)** — Jarvis (cyan) and Pepper (amber) chips side by side; active chip pulses.
- **Dispatch ribbon** — One-line banner above the transcript showing the current plan (e.g. `Jarvis → Pepper (code)`). Auto-hides when no plan is active.
- **Agent Panel** — Renders in the East Code zone when an agent run is active. Shows task line, step log, approval cards, progress bar, and cancel button.
- **System panel persona rows** — When `state.snapshot.system.personas` is present, two extra rows appear (`jarvis <model> <tier>` / `pepper <model> <tier>`).
- **Voice-dock speaker dots** — Each recent command entry optionally carries a speaker dot (cyan for Jarvis, amber for Pepper) derived from the `dispatch.plan` that responded to it.

### Playwright e2e

`web/e2e/personasTint.spec.ts` exercises the cyan→amber tint transition during the synthetic 2-segment mock turn. Requires Chromium system libraries (`npx playwright install --with-deps chromium`). Skips gracefully if the dev bypass or browser is unavailable in the current environment.

## Manual end-to-end checklist (spec-03)

Run with the backend up:

```bash
# terminal A
cd server && uvicorn server.main:app --port 8000

# terminal B
cd web && npm run dev
```

Then in Chromium at http://localhost:5173:

1. **Live boot.** No "demo mode" telemetry entry. TelemetryPanel shows backend `heartbeat` entries within ~5 s.
2. **Text path.** Type "Brief me on today" through the dev controls or scenario hook → `stt.final`, streamed `llm.token`s, audible TTS.
3. **Audio path.** Hold mic (Space) → speak → release. Partial transcripts appear during hold; final on release; assistant replies aloud.
4. **Barge-in.** Mid-speak press Esc. Audio cuts immediately, UI returns to idle, no orphan `tts.end`.
5. **Reconnect.** Kill `uvicorn` mid-conversation. TelemetryPanel: `reconnecting (attempt N)…`. Restart. Telemetry: `reconnected`. Next turn works.
6. **Demo fallback.** Stop backend, hard-reload page. TelemetryPanel: `backend offline — demo mode`. Mock scenario plays end-to-end.
7. **Mic denied.** Block mic permission, attempt to listen. Telemetry: `mic: denied`. Text/scenario paths still work.
8. **Centerpiece audio reactivity.** During step 2/3, the waveform should pulse to the assistant's audio (driven by the playback `AnalyserNode`), not synthetic noise.

## Manual end-to-end checklist (panels-v2)

With backend running, every panel should display real, live data within 1–2 s of connect:

- **Header** — `LIVE` badge appears next to the title. Toggling backend off/on flips through `RECONNECT…` to `LIVE`. In demo mode shows `DEMO`.
- **System** — `load` updates with backend CPU; `tokens / min` climbs while a turn is being generated; `session` shows the server's 8-hex session id (not `A271`); `model` row shows `mock` (or whatever `JARVIS_MODEL_NAME` is set to).
- **Memory** — `context` bar fills in proportion to the last turn's history-token count; no `recall` row.
- **Calendar** — empty by default with `Click Sync to load today's calendar`. Clicking `Sync` triggers a Google Calendar fetch (browser may pop OAuth on first run); fetched entries replace the empty state. Button shows `Syncing…` while in flight.
- **Network** — `endpoint` shows `ws://localhost:8000/ws`; `latency` shows real RTT in ms (`-- ms` until first heartbeat); `packets` increments with every WS message; busy bar = `sendQueueDepth / sendQueueMax`.
- **Tasks** — counts reflect anything enqueued via `tasks_queue.enqueue()` from the server (zero by default until ingestor/scheduler wires arrive in a future spec).
- **Telemetry** — backend events (errors, turn transitions, reconnect notices) appear with timestamps and level icons; capped at 14 lines.
- **Audio** — `output dB` reacts to assistant speech RMS during `speaking` (matches the centerpiece amplitude); idle/listening still uses synthetic values.

Demo mode (no backend): all panels keep working with `--`/zero values + Calendar Sync uses a canned demo response.
