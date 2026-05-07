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

## Architecture

See `docs/superpowers/specs/2026-05-07-frontend-shell-design.md` (this
spec) and `docs/superpowers/specs/2026-05-07-jarvis-architecture.md`
(the umbrella architecture).

The mock event source (`src/events/mockEventSource.ts`) implements the
same `EventSource` interface (`src/events/eventSource.ts`) the real
WebSocket client will provide in spec-03 — no UI rewiring required when
the swap happens.

## State

`idle | listening | thinking | speaking`. Transitions are guarded by
`src/state/stateMachine.ts`. The render loop reads from a tiny
observable store (`src/state/store.ts`) and updates components.

## Keyboard

- **Space (hold)** — push-to-talk
- **Esc** — interrupt current reply
