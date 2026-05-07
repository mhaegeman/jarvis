# spec-01 · Frontend Shell — Design

**Date:** 2026-05-07
**Status:** Approved (orchestrator, per Architect delegation)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)

---

## 1. Goal

Deliver a `web/` Vite + TypeScript project that renders the production Jarvis UI — HUD frame with audio-reactive waveform centerpiece — in all four conversational states (`idle | listening | thinking | speaking`), driven by a **fake event source** with the exact same interface the real WebSocket client will expose later. Looks and feels production-ready visually; not yet connected to a backend.

This spec exists to **de-risk the visual layer in isolation** before the backend (spec-02) and integration (spec-03) phases.

## 2. Non-goals (out of scope for this spec)

- Real WebSocket client (spec-03)
- Real Whisper / LLM / OpenVoice integration (spec-02 + spec-03)
- staticrypt encryption (spec-04)
- GitHub Actions / GH Pages deployment (spec-04)
- Authentication / login (spec-04)
- Service worker / offline support
- i18n
- Persistent settings beyond a sensible default theme

## 3. Architecture

### 3.1 Module layout

```
web/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  .eslintrc.cjs
  src/
    main.ts                 # entry: bootstraps store, event source, UI
    types.ts                # shared types (State, Message, Telemetry)
    state/
      store.ts              # tiny observable store (subscribe/select)
      stateMachine.ts       # transitions + guards
    events/
      eventSource.ts        # interface: EventSource (real one comes in spec-03)
      mockEventSource.ts    # spec-01 implementation: scripted scenarios
      scenarios.ts          # canned conversation data
    audio/
      micCapture.ts         # getUserMedia + AudioWorklet → amplitude stream
      analyzer.ts           # FFT-lite amplitude/spectrum extraction
    ui/
      Hud.ts                # root component: assembles the grid
      Panel.ts              # generic bordered panel with corner brackets
      Header.ts             # top: clock + JARVIS ID
      panels/
        SystemPanel.ts      # uptime, load, tokens/min
        MemoryPanel.ts      # context window, recall %
        AudioPanel.ts       # input/output meters, mic permission UX
        TasksPanel.ts       # queued/active/done
        CalendarPanel.ts    # static today's events (mock)
        NetworkPanel.ts     # endpoint, latency, packets
        TelemetryPanel.ts   # scrolling event feed
      Centerpiece.ts        # waveform + transcript overlay
      Waveform.ts           # canvas-based layered waves
      Controls.ts           # bottom: state buttons + status
      Transcript.ts         # streaming text renderer with caret
    styles/
      global.css            # CSS variables, base, grid layout
      panel.css             # panel chrome (borders, brackets, scan)
  test/
    state.test.ts
    mockEventSource.test.ts
    transcript.test.ts
  e2e/
    smoke.spec.ts           # Playwright headless smoke
```

### 3.2 Layering

```
                      main.ts
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   eventSource        store           audio/micCapture
       │                 │                 │
       └─── pushes events into store ──────┘
                         │
                         ▼
                    UI components
                  (subscribe to store)
```

- **One-way data flow.** Events come in → store updates → UI re-renders the affected panels. UI never mutates state directly except via user-action callbacks that go back through the store.
- **No framework.** Components are plain TS classes/functions that own a DOM root and a `subscribe` to the store. ~30-line `Component` base class for lifecycle.

## 4. Data flow

### 4.1 State machine

```
   ┌────────┐  start listening   ┌──────────┐  stop listening   ┌──────────┐
   │ idle   │──────────────────▶ │ listening│─────────────────▶ │ thinking │
   └────────┘                    └──────────┘                   └──────────┘
        ▲                              │                             │
        │                              │ mic denied / cancelled      │
        │                              ▼                             │
        │                          ┌────────┐                        │
        │                          │  idle  │                        │
        │                          └────────┘                        │
        │                                                            │
        │                                  reply complete            │
        │                          ┌──────────┐  ◀──────────────┐    │
        └──────────────────────────│ speaking │                 │    │
                                    └──────────┘                ▼    ▼
                                                          (interrupt → idle)
```

States: `idle | listening | thinking | speaking`. Transitions are guarded — e.g., you cannot enter `listening` without mic permission.

### 4.2 EventSource interface

The contract is what the real WebSocket client will implement in spec-03. The mock implementation in spec-01 emulates it.

```ts
// src/events/eventSource.ts
export interface EventSource {
  start(): Promise<void>;          // open connection / arm mock
  stop(): void;                     // close
  beginListening(): void;           // user pressed mic
  endListening(): void;             // user released mic
  sendText(text: string): void;     // text fallback
  interrupt(): void;                // barge-in
  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void;
}

export type EventName =
  | "ready"
  | "stt.partial"
  | "stt.final"
  | "llm.token"
  | "llm.end"
  | "tts.sentence"
  | "tts.audioChunk"
  | "tts.end"
  | "error"
  | "telemetry";
```

The exact event payloads mirror §4.1 of the umbrella architecture doc.

### 4.3 Mock event source behavior

`mockEventSource.ts` simulates a realistic conversation timeline:

1. **`beginListening()`** — emits `stt.partial` events incrementally (word-by-word from a scripted user line), 60–120 ms per word.
2. **`endListening()`** — emits `stt.final` with the full user line, 150 ms later.
3. After 600–1200 ms (fake "thinking"), emits `llm.token` events streaming a scripted assistant reply at ~30 tokens/sec.
4. As sentences in the reply complete, emits `tts.sentence` + a stream of `tts.audioChunk` events at realistic timing (chunks every ~100ms over the duration the sentence would take to speak).
5. Emits `tts.end` per sentence and `llm.end` at the end of the reply.
6. Returns to `idle`.

`scenarios.ts` holds 5 scripted Q&A pairs; mock picks one randomly (or the user can cycle via the `Run scenario` button, which is a dev-only control hidden behind a query string).

### 4.4 Audio reactivity

Even without a backend, the waveform is **driven by real signals** in v1:

| State | Waveform amplitude source |
|---|---|
| `idle` | Synthetic gentle ambient envelope |
| `listening` | **Real mic input amplitude** (via `getUserMedia` + AudioWorklet) |
| `thinking` | Synthetic medium pulse (suggests internal activity) |
| `speaking` | Synthetic envelope shaped to mock TTS chunk timing |

Mic permission is requested the first time the user activates `listening`. If denied, listening is disabled and the AudioPanel shows an inline reason + a retry link.

## 5. Components

### 5.1 Component base

A 30-line base class:

```ts
abstract class Component<S = unknown> {
  protected root: HTMLElement;
  protected unsubs: Array<() => void> = [];
  constructor(rootSelector: string) { /* … */ }
  abstract render(state: S): void;
  destroy() { this.unsubs.forEach(u => u()); this.root.replaceChildren(); }
}
```

Subclasses subscribe to the relevant store slice in their constructor and re-render on update. Re-render is targeted (no virtual DOM) — usually `textContent`, `style.width`, `classList.toggle`.

### 5.2 Panel composition

Every info panel is `Panel.ts` + content. `Panel` provides:

- Border + corner-bracket chrome
- Title row
- Scoped CSS via class names
- Accessibility (`role="region"`, `aria-label`)

### 5.3 Centerpiece (waveform + transcript)

The center grid cell contains:

- A full-bleed `<canvas>` rendering 3 layered waveforms + drifting particles (port the proven prototype-B Canvas code).
- An overlaid transcript area: large headline (last assistant line) + smaller running stream when `speaking`.
- A scan-line decoration ported from prototype C.

### 5.4 Controls

Bottom bar:

- `[Speak]` `[Listen]` `[Idle]` buttons
- `[Mic 🎙]` push-to-talk button — primary affordance
- Status text (right-aligned): `— idle —` / `— listening —` / `— thinking —` / `— speaking —`
- Keyboard:
  - `Space` (hold) = push-to-talk; releasing ends listening
  - `Esc` = interrupt
  - `1` / `2` / `3` = jump to idle / listening / thinking (dev-only behind query string)

### 5.5 Telemetry feed

Scrolling list of pseudo-events fed by `mockEventSource` and the local clock:
- Real events: state transitions, mic permission grants/denials, errors injected by the mock.
- Periodic: simulated `gpu.temp`, `latency`, `tokens/min`.

Newest at top; capped at 14 lines.

## 6. Error handling

| Failure | Behavior |
|---|---|
| Mic permission denied | AudioPanel inline message + "Retry" link; Listen button disabled with tooltip |
| Mic device disconnected mid-session | Telemetry warn + return to `idle`; show banner |
| Mock backend injects error event (test path) | Telemetry shows error; controls re-enable; state returns to `idle` |
| Rendering exception (uncaught in component) | Caught at top-level `window.onerror`; errors become a top-of-screen toast; UI continues |
| `getUserMedia` not supported (Safari old, etc.) | Detect on load; show "Voice mode unavailable" in AudioPanel |

No `try/catch` defensive padding inside components — only at boundaries (`micCapture`, top-level error handler).

## 7. Testing

### 7.1 Unit (Vitest)

- `state.test.ts` — every documented transition, every guard, no orphan transitions.
- `mockEventSource.test.ts` — given a scenario, the emitted event sequence matches the documented behavior, with timing windows asserted via `vi.useFakeTimers()`.
- `transcript.test.ts` — streaming append is idempotent; `interrupt` cancels in-flight typing.

### 7.2 Smoke (Playwright, headless Chromium)

A single `smoke.spec.ts`:
1. `pnpm dev` starts; navigate to `http://localhost:5173`.
2. Wait for `[data-ready]` attribute on body (set when initial state reaches `idle`).
3. Assert all 9 grid cells are present (selectors).
4. Assert no console errors (via `page.on('console')`).
5. Click `[data-action="run-scenario"]`.
6. Wait for state to cycle through `listening → thinking → speaking → idle`.
7. Assert transcript contains the expected reply substring.

### 7.3 What we don't test in spec-01

- Visual regression (looks too tactile-dependent at this stage)
- Real mic input (Playwright headless can't easily fake mic; spec-03 covers this manually)
- Cross-browser (Chromium-only is the support baseline)

## 8. Acceptance criteria

A reviewer can verify spec-01 is done by checking, in order:

1. `cd web && pnpm install` succeeds without warnings (or `npm install` — both supported).
2. `pnpm dev` opens a working HUD on `localhost:5173` in Chromium.
3. The HUD shows all 9 panels populated with sensible content.
4. Clicking `[Listen]` (or holding `Space`) requests mic permission; on grant, the waveform reacts to mic input; on deny, AudioPanel shows the denial state.
5. Clicking `[Speak]` (or `[Run scenario]` via `?dev=1`) cycles through `listening → thinking → speaking → idle` with appropriate transcript and waveform behavior.
6. `pnpm build` produces a `dist/` that opens correctly via `pnpm preview`.
7. `pnpm test` passes (Vitest).
8. `pnpm test:e2e` passes (Playwright smoke against the dev server or preview).
9. `pnpm lint` is clean.
10. No console errors in any of the above.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Component base class encourages an ad-hoc "framework" that grows uncontrolled | Keep base ≤ 50 lines. If pressure mounts to add features, log it and re-evaluate at spec-03. |
| Mock event source diverges from the real backend protocol | Single shared `EventSource` interface in `events/eventSource.ts` is the contract. Spec-02 must respect it. |
| Real mic capture has cross-browser quirks | Chromium-only support is explicit. AudioWorklet is widely supported; fallback is `ScriptProcessor` (deprecated) — not implemented. |
| Vite/TS configuration creep | Minimal `tsconfig.json` (strict mode, no `paths` aliases except `@/`). Single eslint config (`@typescript-eslint/recommended` + minor rules). |
| Performance on lower-end laptops | Waveform canvas runs at 30fps if `prefers-reduced-motion`, capped at 60fps otherwise. |

## 10. Implementation sequencing hint (informs the plan, spec-only is design)

Plan will likely sequence:
1. Vite scaffold + tooling (lint, test, ts strict)
2. Store + state machine + tests
3. Layout shell (HTML grid, panel chrome, header)
4. Static panels (System, Memory, Calendar, Network, Tasks, Telemetry)
5. AudioPanel + mic capture + permission UX
6. Waveform canvas
7. Centerpiece (transcript + waveform integration)
8. Controls + keyboard handlers
9. Mock event source + scenarios + wiring
10. Smoke test
11. Accessibility pass + polish

## 11. Self-review notes

- [x] No "TBD"
- [x] No internal contradictions (state machine ↔ mock behavior ↔ tests are aligned)
- [x] Scope: focused on spec-01 only; no premature commitments to spec-02/03/04
- [x] Ambiguity: dev-only behaviors (`?dev=1`) explicitly called out; no implicit hidden controls
- [x] All acceptance criteria are mechanically verifiable
