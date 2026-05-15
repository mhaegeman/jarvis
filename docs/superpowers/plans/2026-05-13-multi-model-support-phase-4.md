# Multi-model support — Phase 4 (UI surface) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The web HUD reflects two personas + live agent runs. Centerpiece tints by speaker (cyan = Jarvis, amber = Pepper). Topbar shows two persona chips with click-to-pin. Dispatch ribbon shows the current plan above the transcript. System panel grows persona rows. New Agent panel renders `agent.*` events with approval cards + cancel button. Voice-dock commands carry a speaker tag.

**Architecture:** Additive on the existing Vite + TypeScript HUD. New types in `types.ts` mirror the Phase 2/3 server messages. `events/wsEventSource.ts` parses the new fields/messages; mock event source extends with synthetic emissions for demo mode. The store gains `currentSpeaker`, `lastPlan`, `personas`, `activeAgentRun`. Five new UI components, plus targeted edits to Centerpiece + Topbar + the existing System panel. No backend changes.

**Tech Stack:** TypeScript 5.x, Vite, Vitest (unit), Playwright (e2e). Existing `Store<AppState>` pattern.

**Spec:** `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` — §9.2 (UI changes).

**Branch:** `claude/multi-model-support-phase-4` (already checked out off `main` @ `8b09c0a`).

**Working directory:** `web/` for all `npm` commands. Test runner: `npm run test` (vitest). E2E: `npm run test:e2e` (Playwright; system Chromium libs may already be installed in dev).

---

## Phase 3 → Phase 4 decision log

| # | Decision | Implication for Phase 4 |
|---|---|---|
| 1 | `llm.token` and `tts.sentence` gained optional `speaker` + `segmentIdx`. Old shape preserved when omitted. | Frontend treats them as optional; UI distinguishes when present, falls back to "jarvis only" rendering when absent (demo mode parity). |
| 2 | New server messages: `dispatch.plan` (emitted before tokens), `llm.segment_end`, `agent.start` / `agent.step` / `agent.approval` / `agent.progress` / `agent.end`. | New `events.on(...)` handlers in `main.ts` populate store fields. `types.ts` gets new payload interfaces. |
| 3 | New client messages: `agent.approve {runId, choice}` + `agent.cancel {runId}`. | The `events` interface needs a `send(msg)` path that the Agent panel can call. Today's frontend only consumes server messages; check `wsEventSource.ts` for a `send` method (likely exists). |
| 4 | `state.snapshot.system.personas` is a `{jarvis, pepper, lastDispatch}` dict added by the server. The factory passes it through `dict[str, Any]`, so it shows up as `system.personas` in the snapshot payload. | Extend `PanelDataSystem` with an optional `personas?` field. System panel renders the new rows when present. |
| 5 | Backend dormancy regression test asserts the new modules stay unimported when the flag is off. | Frontend should similarly degrade gracefully: when `dispatch.plan` / `agent.*` / `speaker` fields are absent, the new UI affordances are hidden (no dual chip pulse, no dispatch ribbon, no agent panel) — preserving the single-Jarvis UX. |
| 6 | `tts.sentence.audioId` is independent per sentence; PCM bytes arrive sequenced over the WS binary path; voice swaps are seamless from the playback queue's perspective. | The centerpiece tint logic reads `currentSpeaker` from the *currently-playing* chunk; record speaker per scheduled chunk in `playbackQueue.ts`. |
| 7 | `dispatch.plan.segments` is 1–3 segments capped (pydantic enforces). Each has `speaker / tier / mode / intent / handoff_style?`. | UI ribbon renders `Jarvis → Pepper (code)` for a 2-segment plan; "Jarvis solo" for a 1-segment plan. |
| 8 | `agent.step.detail` is `dict[str, Any] | None`. For `file_edit` it includes `path / additions / deletions`. For `shell` it includes `command`. | Agent panel renders typed cards per `kind`: file_edit shows the diff stat; shell shows the command; thinking shows the summary. |
| 9 | `agent.approval.choices` is a list of strings (currently `["approve", "deny", "approve_session"]`). | Render one button per choice. Pressing one sends `agent.approve {runId, choice}`. |
| 10 | Codex agent narration sentences flow through the SAME `tts.sentence` path with `speaker=pepper`. | The Agent panel doesn't double-render the narration — the existing transcript / centerpiece already pick it up. The Agent panel is for the structured agent.* events (steps, approvals, progress). |
| 11 | Tests use vitest with the existing patterns in `web/test/`. Playwright e2e lives in `web/e2e/`. | Phase 4 tests use vitest for unit-level component logic; one Playwright snapshot test for the cyan→amber tint transition is the recommended ceiling. |

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `web/src/types.ts` | modify | Add `Speaker`, `Tier`, `SegmentMode`, optional `speaker` / `segmentIdx` on `LlmToken` / `TtsSentence`, new `LlmSegmentEnd` / `DispatchPlan` / `AgentStart` / `AgentStep` / `AgentApproval` / `AgentProgress` / `AgentEnd` / `PersonaStatus` / `PanelDataSystemPersonas` interfaces. Extend `EventMap`. |
| `web/src/events/wsEventSource.ts` | modify | Parse new server messages into the existing event bus. Add `send()` for `agent.approve` / `agent.cancel`. |
| `web/src/events/mockEventSource.ts` | modify | Emit synthetic `dispatch.plan` + speaker-tagged tokens + `agent.*` events in demo mode so the UI can be tested without a backend. |
| `web/src/state/store.ts` | unchanged |  |
| `web/src/main.ts` | modify | Extend `AppState` with `currentSpeaker`, `lastPlan`, `personas`, `activeAgentRun`. Wire new event handlers into the store. |
| `web/src/ui/Centerpiece.ts` | modify | Tint follows `currentSpeaker` (cyan = jarvis, amber = pepper). 120ms crossfade at boundaries. |
| `web/src/audio/playbackQueue.ts` | modify | Record the speaker per scheduled chunk; expose a `currentSpeaker()` getter the centerpiece reads on each render frame. |
| `web/src/ui/compass/Topbar.ts` | modify | Replace single "JARVIS" mark with two persona chips. Active pulses; click pins the next turn. |
| `web/src/ui/compass/DispatchRibbon.ts` | create | Renders `dispatch.plan` segments above the transcript (e.g. `Jarvis → Pepper (code)`). Auto-hides on `llm.end`. |
| `web/src/ui/compass/AgentPanel.ts` | create | Renders the active agent run: task line, event log (one row per `agent.step`), approval card stack, progress bar, cancel button. |
| `web/src/ui/panels/SystemPanel.ts` *(if exists; else find equivalent)* | modify | Two `model` rows under the existing system data when `personas` field present. |
| `web/src/ui/compass/commandHistory.ts` | modify | Each pushed command optionally carries a `speaker` tag, displayed in the dock. |
| `web/test/types.test.ts` | create | Round-trip type guards / message shape tests. |
| `web/test/wsEventSource.phase4.test.ts` | create | Parser tests for new server messages + `send()` for client messages. |
| `web/test/dispatchRibbon.test.ts` | create | Component tests for ribbon rendering. |
| `web/test/agentPanel.test.ts` | create | Component tests for agent panel (events log, approval flow, cancel). |
| `web/test/playbackQueue.speaker.test.ts` | create | `currentSpeaker()` returns the speaker of the currently-playing chunk. |
| `web/e2e/personasTint.spec.ts` | create | Playwright snapshot diff: cyan → amber tint across a synthetic 2-segment turn. |

**Backend files NOT modified in Phase 4.** All UI work is additive.

---

## Task 1: Type system (`types.ts`)

**Files:**
- Modify: `web/src/types.ts`
- Create: `web/test/types.test.ts`

Add the new shapes mirroring Phase 2/3 server messages. Keep existing interfaces back-compat (optional fields only).

- [ ] **Step 1: Write failing tests**

Create `web/test/types.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import type {
  LlmToken,
  TtsSentence,
  LlmSegmentEnd,
  DispatchPlan,
  AgentStart,
  AgentStep,
  AgentApproval,
  AgentProgress,
  AgentEnd,
  Speaker,
  EventMap,
} from "@/types";

describe("Phase 4 types", () => {
  it("LlmToken accepts old shape (delta only)", () => {
    const t: LlmToken = { delta: "hello" };
    expect(t.delta).toBe("hello");
    expect(t.speaker).toBeUndefined();
  });

  it("LlmToken accepts new shape with speaker + segmentIdx", () => {
    const t: LlmToken = { delta: "hi", speaker: "pepper", segmentIdx: 1 };
    expect(t.speaker).toBe("pepper");
  });

  it("TtsSentence accepts optional speaker", () => {
    const s1: TtsSentence = { text: "hi.", audioId: "a1" };
    const s2: TtsSentence = { text: "hi.", audioId: "a1", speaker: "jarvis" };
    expect(s1.speaker).toBeUndefined();
    expect(s2.speaker).toBe("jarvis");
  });

  it("LlmSegmentEnd carries speaker + segmentIdx", () => {
    const e: LlmSegmentEnd = { speaker: "pepper", segmentIdx: 0 };
    expect(e.segmentIdx).toBe(0);
  });

  it("DispatchPlan shape", () => {
    const p: DispatchPlan = {
      turnId: "t-abc",
      segments: [
        { speaker: "jarvis", tier: "balanced", mode: "chat", intent: "design" },
        { speaker: "pepper", tier: "deep", mode: "chat", intent: "implement" },
      ],
      rationale: "design then implement",
    };
    expect(p.segments).toHaveLength(2);
  });

  it("AgentStep with file_edit detail", () => {
    const s: AgentStep = {
      runId: "r1",
      kind: "file_edit",
      summary: "x.py +3 -1",
      detail: { path: "x.py", additions: 3, deletions: 1 },
    };
    expect(s.detail?.path).toBe("x.py");
  });

  it("AgentEnd has constrained status", () => {
    const ok: AgentEnd = { runId: "r1", status: "ok", summary: "done." };
    const failed: AgentEnd = { runId: "r1", status: "failed", summary: "x." };
    const cancelled: AgentEnd = { runId: "r1", status: "cancelled", summary: "x." };
    expect([ok.status, failed.status, cancelled.status]).toEqual(
      ["ok", "failed", "cancelled"],
    );
  });

  it("EventMap includes new event names", () => {
    // Compile-time check (smoke at runtime via type assertion).
    type _Plan = EventMap["dispatch.plan"];
    type _Seg = EventMap["llm.segment_end"];
    type _AS = EventMap["agent.start"];
    type _AE = EventMap["agent.end"];
    expect(true).toBe(true);
  });

  it("Speaker is a string literal union", () => {
    const j: Speaker = "jarvis";
    const p: Speaker = "pepper";
    expect([j, p]).toEqual(["jarvis", "pepper"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd web && npm run test -- types.test
```

Expected: type errors (interfaces don't exist yet).

- [ ] **Step 3: Extend `types.ts`**

Edit `web/src/types.ts`. Add (after the existing primitive interfaces, before the `EventMap`):

```ts
// ─── Phase 2/3 additions ────────────────────────────────────────────────

export type Speaker = "jarvis" | "pepper";
export type Tier = "fast" | "balanced" | "deep";
export type SegmentMode = "chat" | "codex_agent";
export type HandoffStyle = "flat" | "soft";

// Extend existing LlmToken with optional fields.
export interface LlmToken {
  delta: string;
  speaker?: Speaker;
  segmentIdx?: number;
}

// Extend existing TtsSentence with optional speaker.
export interface TtsSentence {
  text: string;
  audioId: string;
  speaker?: Speaker;
}

export interface LlmSegmentEnd {
  speaker: Speaker;
  segmentIdx: number;
}

export interface PlanSegment {
  speaker: Speaker;
  tier: Tier;
  mode: SegmentMode;
  intent: string;
  handoff_style?: HandoffStyle | null;
}

export interface DispatchPlan {
  turnId: string;
  segments: PlanSegment[];
  rationale: string;
}

export interface AgentStart {
  speaker: Speaker;
  task: string;
  runId: string;
}

export interface AgentStep {
  runId: string;
  kind: "thinking" | "file_edit" | "shell" | "tool" | string;
  summary: string;
  detail?: Record<string, unknown>;
}

export interface AgentApproval {
  runId: string;
  prompt: string;
  choices: string[];
}

export interface AgentProgress {
  runId: string;
  phase: string;
  percent?: number;
}

export interface AgentEnd {
  runId: string;
  status: "ok" | "failed" | "cancelled";
  summary: string;
}

export interface PersonaStatus {
  model: string;
  tier: Tier;
  status: "idle" | "thinking" | "speaking" | "agent";
}

export interface PanelDataSystemPersonas {
  jarvis?: PersonaStatus;
  pepper?: PersonaStatus;
  lastDispatch?: { turnId: string; segments: PlanSegment[] } | null;
}
```

**Modify** the existing `PanelDataSystem` to include optional `personas`:

```ts
export interface PanelDataSystem {
  load: number;
  tokensPerMin: number;
  sessionId: string;
  modelName: string;
  personas?: PanelDataSystemPersonas;
}
```

**Modify** `EventMap` to include the new server events:

```ts
export type EventMap = {
  ready: void;
  "stt.partial": SttPartial;
  "stt.final": SttFinal;
  "llm.token": LlmToken;
  "llm.segment_end": LlmSegmentEnd;
  "llm.end": void;
  "tts.sentence": TtsSentence;
  "tts.audioChunk": TtsAudioChunk;
  "tts.end": TtsEnd;
  "dispatch.plan": DispatchPlan;
  "agent.start": AgentStart;
  "agent.step": AgentStep;
  "agent.approval": AgentApproval;
  "agent.progress": AgentProgress;
  "agent.end": AgentEnd;
  error: ProtocolError;
  telemetry: TelemetryEvent;
  "state.snapshot": StateSnapshot;
  "calendar.update": CalendarUpdate;
};
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd web && npm run test -- types.test
```

Expected: all 9 tests pass.

- [ ] **Step 5: Run typecheck + full unit test suite**

```bash
cd web && npx tsc --noEmit && npm run test
```

Expected: zero TypeScript errors. All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add web/src/types.ts web/test/types.test.ts
git commit -m "feat(web/types): Phase 4 — speakers, plans, agent events

Optional speaker/segmentIdx on LlmToken + TtsSentence (back-compat
preserved). New LlmSegmentEnd, DispatchPlan, AgentStart/Step/Approval/
Progress/End, PersonaStatus interfaces. PanelDataSystem grows an
optional 'personas' field. EventMap extends with the new server event
names. No runtime code changes — types only."
```

---

## Task 2: WS event source parses Phase 4 messages

**Files:**
- Modify: `web/src/events/wsEventSource.ts`
- Modify: `web/src/events/mockEventSource.ts`
- Create: `web/test/wsEventSource.phase4.test.ts`

The event source receives JSON-encoded server messages over the WS. The existing `wsEventSource.ts` likely has a `switch (msg.type)` block. Phase 4 adds cases for the new types and surfaces them on the existing event bus. Client → server messages (`agent.approve` / `agent.cancel`) flow back via a `send()` method that already exists (or needs adding).

- [ ] **Step 1: Read the existing `wsEventSource.ts`**

```bash
cat /home/user/jarvis/web/src/events/wsEventSource.ts | head -120
```

Identify the dispatch switch and the existing `send()` method (if any).

- [ ] **Step 2: Write failing tests**

Create `web/test/wsEventSource.phase4.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { WSEventSource } from "@/events/wsEventSource";

// The test pattern follows the existing wsCodec / wsEventSource tests:
// inject a fake WebSocket-like object, push messages, observe handlers.

class FakeWS extends EventTarget {
  readyState = WebSocket.OPEN;
  sent: string[] = [];
  send(data: string): void { this.sent.push(data); }
  close(): void { /* noop */ }
}

function newEventSource(): { es: WSEventSource; ws: FakeWS } {
  const ws = new FakeWS();
  // ⚠️ Adapt this to the actual WSEventSource constructor signature.
  // Existing tests in web/test/wsEventSource.test.ts show the pattern.
  const es = new WSEventSource(ws as unknown as WebSocket);
  return { es, ws };
}

function pushMessage(ws: FakeWS, payload: object): void {
  ws.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(payload) }));
}

describe("WSEventSource — Phase 4", () => {
  it("forwards llm.token with speaker + segmentIdx", () => {
    const { es, ws } = newEventSource();
    const handler = vi.fn();
    es.on("llm.token", handler);
    pushMessage(ws, { type: "llm.token", delta: "hi", speaker: "pepper", segmentIdx: 1 });
    expect(handler).toHaveBeenCalledWith({ delta: "hi", speaker: "pepper", segmentIdx: 1 });
  });

  it("forwards llm.segment_end", () => {
    const { es, ws } = newEventSource();
    const handler = vi.fn();
    es.on("llm.segment_end", handler);
    pushMessage(ws, { type: "llm.segment_end", speaker: "jarvis", segmentIdx: 0 });
    expect(handler).toHaveBeenCalledWith({ speaker: "jarvis", segmentIdx: 0 });
  });

  it("forwards dispatch.plan", () => {
    const { es, ws } = newEventSource();
    const handler = vi.fn();
    es.on("dispatch.plan", handler);
    pushMessage(ws, {
      type: "dispatch.plan",
      turnId: "t-1",
      segments: [
        { speaker: "jarvis", tier: "fast", mode: "chat", intent: "hi" },
      ],
      rationale: "trivial",
    });
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({
      turnId: "t-1", rationale: "trivial",
    }));
  });

  it("forwards each agent.* event", () => {
    const { es, ws } = newEventSource();
    const starts = vi.fn(); es.on("agent.start", starts);
    const steps = vi.fn(); es.on("agent.step", steps);
    const approvals = vi.fn(); es.on("agent.approval", approvals);
    const progress = vi.fn(); es.on("agent.progress", progress);
    const ends = vi.fn(); es.on("agent.end", ends);

    pushMessage(ws, { type: "agent.start", speaker: "pepper", task: "x", runId: "r1" });
    pushMessage(ws, { type: "agent.step", runId: "r1", kind: "file_edit", summary: "x.py +3 -1" });
    pushMessage(ws, { type: "agent.approval", runId: "r1", prompt: "ok?", choices: ["approve","deny"] });
    pushMessage(ws, { type: "agent.progress", runId: "r1", phase: "editing", percent: 0.5 });
    pushMessage(ws, { type: "agent.end", runId: "r1", status: "ok", summary: "done." });

    expect(starts).toHaveBeenCalled();
    expect(steps).toHaveBeenCalled();
    expect(approvals).toHaveBeenCalled();
    expect(progress).toHaveBeenCalled();
    expect(ends).toHaveBeenCalled();
  });

  it("sendAgentApprove writes the right WS payload", () => {
    const { es, ws } = newEventSource();
    es.sendAgentApprove("r1", "approve");
    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "agent.approve", runId: "r1", choice: "approve",
    });
  });

  it("sendAgentCancel writes the right WS payload", () => {
    const { es, ws } = newEventSource();
    es.sendAgentCancel("r1");
    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "agent.cancel", runId: "r1",
    });
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd web && npm run test -- wsEventSource.phase4
```

- [ ] **Step 4: Extend `wsEventSource.ts`**

Open `web/src/events/wsEventSource.ts`. Find the `switch (msg.type)` (or equivalent dispatch). Add cases for each new server event type that forwards the payload (minus the `type` field) to the matching listener. Example pattern (adapt to actual code):

```ts
case "llm.segment_end":
  this.emit("llm.segment_end", { speaker: msg.speaker, segmentIdx: msg.segmentIdx });
  break;
case "dispatch.plan":
  this.emit("dispatch.plan", {
    turnId: msg.turnId, segments: msg.segments, rationale: msg.rationale,
  });
  break;
case "agent.start":
  this.emit("agent.start", { speaker: msg.speaker, task: msg.task, runId: msg.runId });
  break;
// … and so on for agent.step / agent.approval / agent.progress / agent.end
```

For `llm.token` / `tts.sentence`: the existing handlers already pass-through the payload as-is. Verify that `speaker` and `segmentIdx` aren't being stripped. If they are, include them.

Add two `send*` methods:

```ts
sendAgentApprove(runId: string, choice: "approve" | "deny" | "approve_session"): void {
  this.ws.send(JSON.stringify({ type: "agent.approve", runId, choice }));
}

sendAgentCancel(runId: string): void {
  this.ws.send(JSON.stringify({ type: "agent.cancel", runId }));
}
```

- [ ] **Step 5: Extend `mockEventSource.ts` (for demo mode)**

In `mockEventSource.ts`, augment the existing scripted turn with one synthetic 2-segment plan (Jarvis design → Pepper implement) so the UI can be smoke-tested with the backend off. The mock should:

1. Emit `dispatch.plan` before the first `llm.token`.
2. Emit speaker-tagged `llm.token` events with `segmentIdx`.
3. Emit `llm.segment_end` between segments.
4. Emit a final `llm.end`.

Also stub `sendAgentApprove` / `sendAgentCancel` as no-ops (or log to console for debugging).

- [ ] **Step 6: Run tests + typecheck**

```bash
cd web && npx tsc --noEmit && npm run test -- wsEventSource
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add web/src/events/wsEventSource.ts web/src/events/mockEventSource.ts web/test/wsEventSource.phase4.test.ts
git commit -m "feat(web/events): parse Phase 4 server messages + send agent.*

WSEventSource dispatches dispatch.plan, llm.segment_end, and the five
agent.* server events. Adds sendAgentApprove / sendAgentCancel for
client → server messages. MockEventSource emits a synthetic 2-segment
plan in demo mode so the new UI is visible without a backend."
```

---

## Task 3: Store + main.ts wiring

**Files:**
- Modify: `web/src/main.ts`
- Create: `web/test/store.phase4.test.ts`

Extend `AppState` with persona-aware fields and wire the new event handlers into the store.

- [ ] **Step 1: Write failing tests**

Create `web/test/store.phase4.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { createStore } from "@/state/store";
import type { Speaker, DispatchPlan, AgentStart, AgentEnd } from "@/types";

interface PersonaState {
  currentSpeaker: Speaker | null;
  lastPlan: DispatchPlan | null;
  activeAgentRun: { runId: string; task: string; speaker: Speaker } | null;
}

describe("Phase 4 store extensions", () => {
  it("currentSpeaker starts null, updates on llm.token with speaker", () => {
    const s = createStore<PersonaState>({
      currentSpeaker: null, lastPlan: null, activeAgentRun: null,
    });
    s.update(() => ({ currentSpeaker: "pepper" }));
    expect(s.get().currentSpeaker).toBe("pepper");
  });

  it("activeAgentRun set on agent.start, cleared on agent.end", () => {
    const s = createStore<PersonaState>({
      currentSpeaker: null, lastPlan: null, activeAgentRun: null,
    });
    const start: AgentStart = { speaker: "pepper", task: "rename X", runId: "r1" };
    s.update(() => ({ activeAgentRun: { runId: start.runId, task: start.task, speaker: start.speaker } }));
    expect(s.get().activeAgentRun?.runId).toBe("r1");
    const end: AgentEnd = { runId: "r1", status: "ok", summary: "done." };
    s.update(() => ({ activeAgentRun: null }));
    expect(s.get().activeAgentRun).toBeNull();
    expect(end.status).toBe("ok"); // silence unused
  });
});
```

- [ ] **Step 2: Run tests to verify they fail (or are at the wrong assertion)**

```bash
cd web && npm run test -- store.phase4
```

- [ ] **Step 3: Extend `AppState` in `main.ts`**

Open `web/src/main.ts`. Find the `AppState` interface definition. Add:

```ts
import type { Speaker, DispatchPlan, AgentStart } from "@/types";

export interface AppState {
  state: ConvState;
  micAmplitude: number;
  micStatus: MicStatus;
  telemetry: TelemetryEvent[];
  centerTitle: string;
  panelData: PanelData;
  wsState: WsState;
  // ─── Phase 4 additions ───
  currentSpeaker: Speaker | null;
  lastPlan: DispatchPlan | null;
  activeAgentRun: { runId: string; task: string; speaker: Speaker } | null;
}
```

Initialize the new fields in the `createStore<AppState>({ … })` call:

```ts
currentSpeaker: null,
lastPlan: null,
activeAgentRun: null,
```

Wire the new event handlers (near the existing `events.on("llm.token", …)` block):

```ts
events.on("llm.token", ({ delta, speaker }) => {
  if (store.get().state === "thinking") {
    tryTransition("replyStart");
    store.update(() => ({ centerTitle: "" }));
  }
  store.update((d) => ({
    centerTitle: d.centerTitle + delta,
    currentSpeaker: speaker ?? d.currentSpeaker,
  }));
});

events.on("llm.segment_end", () => {
  // Optional: append a soft separator in the transcript. For now just no-op;
  // the next llm.token's speaker update is what flips the centerpiece tint.
});

events.on("dispatch.plan", (plan) => {
  store.update(() => ({ lastPlan: plan }));
});

events.on("agent.start", ({ runId, task, speaker }) => {
  store.update(() => ({ activeAgentRun: { runId, task, speaker } }));
});

events.on("agent.end", () => {
  store.update(() => ({ activeAgentRun: null }));
});
```

On `llm.end`, leave `lastPlan` populated (the ribbon hides itself when `state` returns to idle/listening, not when the plan goes away — feels less flickery).

- [ ] **Step 4: Run tests + typecheck**

```bash
cd web && npx tsc --noEmit && npm run test
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add web/src/main.ts web/test/store.phase4.test.ts
git commit -m "feat(web/store): extend AppState for personas + active agent run

currentSpeaker tracks the speaker of the most recent llm.token.
lastPlan holds the most recent dispatch.plan. activeAgentRun is set
on agent.start, cleared on agent.end. New event handlers wire the
Phase 2/3 server messages into the store. Old single-Jarvis path
unchanged when the new fields stay null."
```

---

## Task 4: Centerpiece tint + playback queue speaker tracking

**Files:**
- Modify: `web/src/audio/playbackQueue.ts`
- Modify: `web/src/ui/Centerpiece.ts` (or wherever the centerpiece tint is rendered)
- Create: `web/test/playbackQueue.speaker.test.ts`

The centerpiece tint must follow the **currently-playing** audio chunk's speaker, not the most-recent `llm.token`. Two reasons:

1. Token events arrive faster than audio plays, so following tokens would shift the tint ahead of the audio.
2. During an agent run there are no `llm.token` events, only `tts.sentence` events for narration — the tint must still flip to Pepper.

So: `playbackQueue.ts` records the speaker per scheduled chunk; the centerpiece reads `currentSpeaker()` on each render frame.

- [ ] **Step 1: Read `playbackQueue.ts`** to find the chunk-scheduling code.

- [ ] **Step 2: Write failing tests**

Create `web/test/playbackQueue.speaker.test.ts`:

```ts
import { describe, it, expect } from "vitest";

// ⚠️ Adapt the import to the actual exported API.
import { PlaybackQueue } from "@/audio/playbackQueue";

describe("PlaybackQueue.currentSpeaker", () => {
  it("returns null when nothing has played", () => {
    const q = new PlaybackQueue({ /* … existing constructor args */ });
    expect(q.currentSpeaker()).toBeNull();
  });

  it("returns the speaker of the currently-playing chunk", () => {
    const q = new PlaybackQueue({ /* … */ });
    q.enqueueSentence("a1", "jarvis");
    q.enqueueSentence("a2", "pepper");
    // Simulate playback advancing to a2.
    q.markChunkPlaying("a2");
    expect(q.currentSpeaker()).toBe("pepper");
  });
});
```

- [ ] **Step 3: Extend `PlaybackQueue`** to track the speaker per scheduled audio item. Expose `currentSpeaker(): Speaker | null`.

The simplest design: when `tts.sentence` arrives, register `(audioId → speaker)` in a Map. As chunks for that `audioId` start playing, update an internal `currentSpeaker` field. On `tts.end`, leave it alone (the next sentence will overwrite); the centerpiece reads the latest value.

- [ ] **Step 4: Update Centerpiece tint logic**

Find where the centerpiece renders its color. Read `playbackQueue.currentSpeaker()` on each frame (or subscribe to a change event). Render cyan for `"jarvis"` (current behaviour), amber (e.g. `#ffb86b`) for `"pepper"`. Crossfade over 120ms when the value changes.

If the centerpiece is purely declarative (CSS variable swap), set `--centerpiece-tint` based on the speaker; the CSS transition handles the crossfade.

- [ ] **Step 5: Run tests + typecheck**

```bash
cd web && npx tsc --noEmit && npm run test
```

- [ ] **Step 6: Commit**

```bash
git add web/src/audio/playbackQueue.ts web/src/ui/Centerpiece.ts web/test/playbackQueue.speaker.test.ts
git commit -m "feat(web/audio,centerpiece): tint by currently-playing speaker

PlaybackQueue records speaker per scheduled chunk and exposes
currentSpeaker(). Centerpiece reads it each frame: cyan for Jarvis
(unchanged), amber for Pepper. 120ms crossfade at boundaries."
```

---

## Task 5: Topbar dual chip

**Files:**
- Modify: `web/src/ui/compass/Topbar.ts`

Replace the single "JARVIS" mark with two persona chips side by side. The active chip pulses; inactive is dim. Click pins the next turn to that speaker — implemented as a small "pending pin" piece of store state the next outbound text message reads (out of scope for Phase 4's *UI shipping* — just hook the click to a console log + a TODO comment for Phase 5/follow-up).

- [ ] **Step 1: Read existing `Topbar.ts`** to understand the rendering pattern.

- [ ] **Step 2: Replace the single mark with two chips**

Render two stacked chips: "Jarvis" (cyan border) and "Pepper" (amber border). Use `currentSpeaker` from the store to pulse the active one. Click handler: for now, `log("info", ...)` (the actual "pin next turn" hook ships in a follow-up phase or as a small Phase 4 extra if budget allows).

- [ ] **Step 3: Smoke test in dev mode**

```bash
cd web && npm run dev
# open http://localhost:5173 — confirm dual chip renders
```

- [ ] **Step 4: Commit**

```bash
git add web/src/ui/compass/Topbar.ts
git commit -m "feat(web/ui/Topbar): dual persona chip

Replaces the single JARVIS mark with two stacked chips. Active chip
(by currentSpeaker) pulses. Click handler stubbed — logs the pin
intent; the pin-next-turn outbound path is a follow-up."
```

---

## Task 6: Dispatch ribbon

**Files:**
- Create: `web/src/ui/compass/DispatchRibbon.ts`
- Create: `web/test/dispatchRibbon.test.ts`
- Wire into the layout (likely in `CompassApp.ts`)

A one-line ribbon above the transcript. Renders the current plan: `Jarvis → Pepper (code)` for a 2-segment plan, `Jarvis (planning)` for a 1-segment plan. Auto-hides when there's no `lastPlan` or when the conversation state returns to `idle`.

- [ ] **Step 1: Write failing tests**

Create `web/test/dispatchRibbon.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { renderDispatchRibbon } from "@/ui/compass/DispatchRibbon";

describe("DispatchRibbon", () => {
  it("renders empty when no plan", () => {
    const html = renderDispatchRibbon(null);
    expect(html).toBe("");
  });

  it("renders 1-segment plan as solo", () => {
    const html = renderDispatchRibbon({
      turnId: "t1",
      segments: [{ speaker: "jarvis", tier: "fast", mode: "chat", intent: "hi" }],
      rationale: "",
    });
    expect(html.toLowerCase()).toContain("jarvis");
    expect(html).not.toContain("→");
  });

  it("renders 2-segment plan with arrow + mode label", () => {
    const html = renderDispatchRibbon({
      turnId: "t1",
      segments: [
        { speaker: "jarvis", tier: "balanced", mode: "chat", intent: "design" },
        { speaker: "pepper", tier: "deep", mode: "codex_agent", intent: "implement" },
      ],
      rationale: "design then implement",
    });
    expect(html).toContain("Jarvis");
    expect(html).toContain("Pepper");
    expect(html).toContain("→");
    expect(html.toLowerCase()).toContain("code"); // mode hint
  });
});
```

- [ ] **Step 2: Implement `DispatchRibbon.ts`**

Export `renderDispatchRibbon(plan: DispatchPlan | null): string` returning the HTML markup, plus a `mountDispatchRibbon(container, store)` that subscribes to `lastPlan` and re-renders. Pattern matches existing compass components.

- [ ] **Step 3: Wire into the layout**

In `CompassApp.ts` (or wherever the central transcript area is mounted), add a `<div id="dispatch-ribbon">` and mount the ribbon into it.

- [ ] **Step 4: Run tests + manual check**

```bash
cd web && npm run test -- dispatchRibbon
# Then: npm run dev — verify ribbon shows in demo mode
```

- [ ] **Step 5: Commit**

```bash
git add web/src/ui/compass/DispatchRibbon.ts web/src/ui/compass/CompassApp.ts web/test/dispatchRibbon.test.ts
git commit -m "feat(web/ui): add DispatchRibbon above the transcript

Renders the Dispatcher's per-turn plan as 'Jarvis → Pepper (code)' or
'Jarvis (planning)' for solo turns. Hidden when lastPlan is null.
Subscribed to the store; re-renders on plan change."
```

---

## Task 7: Agent panel

**Files:**
- Create: `web/src/ui/compass/AgentPanel.ts`
- Create: `web/test/agentPanel.test.ts`
- Wire into the layout (likely replacing the East Code zone when an agent is running)

The agent panel renders the live agent run: task line at top, scrollable event log (one row per `agent.step`), approval card stack inline, optional progress bar, cancel button. Hidden when `activeAgentRun` is null.

The approval card displays the prompt + a button per choice. Pressing a button calls `events.sendAgentApprove(runId, choice)`.

- [ ] **Step 1: Write failing tests**

Create `web/test/agentPanel.test.ts`. Cover:
- Renders empty (or hidden) when no `activeAgentRun`.
- Renders task line when `activeAgentRun` is set.
- Renders each appended `agent.step` row.
- Approval card renders one button per choice; click calls the right `send*` callback.
- Cancel button calls `sendAgentCancel(runId)`.

Use the same DOM-rendering pattern as the existing `transcript.test.ts` (jsdom).

- [ ] **Step 2: Implement `AgentPanel.ts`**

Export `mountAgentPanel(container, store, events)`. Subscribes to `activeAgentRun`, `agent.step`, `agent.approval`, `agent.progress` events; updates the DOM on each.

- [ ] **Step 3: Wire into the layout**

Place the agent panel in the East Code zone. When `activeAgentRun` is non-null, show it (and hide the existing East Code content). When null, restore the existing content.

- [ ] **Step 4: Run tests + manual check**

```bash
cd web && npm run test -- agentPanel
# Then: npm run dev — trigger the synthetic agent run from the mock event source
```

- [ ] **Step 5: Commit**

```bash
git add web/src/ui/compass/AgentPanel.ts web/src/ui/compass/CompassApp.ts web/test/agentPanel.test.ts
git commit -m "feat(web/ui): add AgentPanel for live Codex agent runs

Renders task line, event-log rows for each agent.step, inline approval
cards (one button per choice, click sends agent.approve via WS), cancel
button (sends agent.cancel via WS), optional progress bar. Replaces
the East Code zone when activeAgentRun is set; restores it otherwise."
```

---

## Task 8: System panel persona rows + voice-dock speaker tag

**Files:**
- Modify: `web/src/ui/panels/SystemPanel.ts` (or equivalent)
- Modify: `web/src/ui/compass/commandHistory.ts`
- Modify: `web/src/ui/compass/VoiceDock.ts`

System panel: when `state.snapshot.system.personas` is present, render two extra rows under the existing system data:

```
jarvis    claude-haiku-4-5   fast
pepper    gpt-5-mini         fast
```

Voice-dock: each command in `CommandHistory` carries an optional `speaker` tag (set by reading the *next* incoming `dispatch.plan`'s first segment speaker, or `null` if no plan arrives within ~2s). The dock renders a small cyan/amber dot beside each entry.

- [ ] **Step 1: Extend `CommandHistory.push`**

Add an optional `speaker?: Speaker` parameter. Store it alongside the text. Re-render entries with a colour-matched dot.

- [ ] **Step 2: Update `main.ts`** to call `CommandHistory.push(text, speaker)` — read the speaker from the first segment of the most recent `dispatch.plan`, falling back to `null`.

- [ ] **Step 3: System panel** renders two persona rows when `panelData.system.personas` is present. Use the same row-rendering primitive as the existing rows.

- [ ] **Step 4: Run tests + manual check**

```bash
cd web && npx tsc --noEmit && npm run test
```

- [ ] **Step 5: Commit**

```bash
git add web/src/ui/panels/SystemPanel.ts web/src/ui/compass/commandHistory.ts web/src/ui/compass/VoiceDock.ts web/src/main.ts
git commit -m "feat(web/ui): system-panel persona rows + voice-dock speaker tag

System panel renders 'jarvis claude-haiku-4-5 fast' and 'pepper
gpt-5-mini fast' rows when the snapshot carries a personas field.
Voice dock entries carry a speaker dot (cyan/amber) matched to the
dispatch.plan that handled each command."
```

---

## Task 9: E2E + README + push

**Files:**
- Create: `web/e2e/personasTint.spec.ts`
- Modify: `web/README.md`

- [ ] **Step 1: Playwright snapshot**

Add a single e2e test that:
1. Loads the HUD in demo mode.
2. Triggers the synthetic 2-segment plan via the existing dev controls.
3. Asserts the centerpiece tint colour shifts from cyan → amber midway.

A simple way: read `getComputedStyle(centerpieceEl).color` (or a CSS variable) at two timestamps and assert they differ.

- [ ] **Step 2: README update**

Open `web/README.md`. Add a Phase 4 section noting:
- Demo mode now includes a 2-segment plan smoke (visible on `?dev=1`).
- The dual chip / dispatch ribbon / agent panel are flag-driven by the backend's `JARVIS_PERSONAS_ENABLED`.
- New WS messages consumed: list them briefly.

- [ ] **Step 3: Full quality gates**

```bash
cd web && npx tsc --noEmit && npm run lint && npm run test && npm run build
```

- [ ] **Step 4: Commit + push**

```bash
git add web/e2e/personasTint.spec.ts web/README.md
git commit -m "docs(web): Phase 4 README + e2e tint snapshot

Playwright snapshot exercises the cyan→amber transition during a
synthetic 2-segment turn in demo mode. README adds a Phase 4
section listing the new WS messages consumed and the demo-mode
behaviours."
git push -u origin claude/multi-model-support-phase-4
```

---

## Phase 4 acceptance checklist

- [ ] `npx tsc --noEmit` clean.
- [ ] `npm run lint` clean.
- [ ] `npm run test` green.
- [ ] `npm run build` succeeds.
- [ ] `npm run test:e2e` green (or documented why it was skipped — e.g. missing Chromium libs in CI).
- [ ] With backend off (demo mode), HUD shows the synthetic 2-segment plan, voice tint shifts, agent panel renders mock events.
- [ ] With `JARVIS_PERSONAS_ENABLED=false` on the backend, all new UI affordances stay hidden — single-Jarvis UX preserved.

---

## Phase 4 → Phase 5 decision log

To be filled in as Phase 4 lands. Format:

```
- Task N (<file>): <decision worth carrying forward to Phase 5>
```

Initial entries (populated by implementer):

- _(empty — fill in during execution)_

---

*End of Phase 4 implementation plan.*
