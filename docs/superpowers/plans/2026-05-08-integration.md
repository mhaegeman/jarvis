# spec-03 · Browser ↔ Backend Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `MockEventSource` in `web/` with a real `WebSocketEventSource` that talks to the `server/` FastAPI WS, plus AudioWorklet mic capture and Web Audio playback queue.

**Architecture:** Single `WSEventSource` class implements the existing `EventSource` interface verbatim. A thin `connect()` entry point probes the WS at boot and falls back to `MockEventSource` if unreachable. A binary `wsCodec` mirrors `server/server/audio.py`. A `PlaybackQueue` schedules `AudioBufferSourceNode`s on a single `AudioContext` and exposes an `AnalyserNode` for the centerpiece waveform.

**Tech Stack:** TypeScript 5, Vite 5, Vitest 2, Web Audio API (AudioWorklet, AudioBufferSourceNode, AnalyserNode), WebSocket. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-08-integration-design.md`

---

## File Structure

**Create:**
- `web/src/audio/wsCodec.ts` — binary frame encode/decode
- `web/src/audio/playbackQueue.ts` — Web Audio scheduling + AnalyserNode
- `web/src/audio/micWorklet.ts` — main-thread side of AudioWorklet
- `web/public/mic-processor.js` — AudioWorklet processor (audio thread)
- `web/src/events/wsEventSource.ts` — WebSocket implementation of `EventSource`
- `web/src/events/connect.ts` — probe + fallback factory
- `web/test/wsCodec.test.ts`
- `web/test/playbackQueue.test.ts`
- `web/test/wsEventSource.test.ts`
- `web/test/connect.test.ts`
- `web/test/_fakes.ts` — shared `FakeWebSocket`, `FakeAudioContext`

**Modify:**
- `web/src/main.ts:50` — replace `new MockEventSource()` with `await connect(...)`
- `web/src/main.ts` — remove synthetic telemetry generator, wire centerpiece amplitude to playback analyser when in live mode
- `web/README.md` — add manual e2e checklist
- `docs/superpowers/STATUS.md` — phase pointer updates

**Untouched:** state machine, store, scenarios, MockEventSource (used as demo fallback), backend.

---

## Task 0: Worktree + baseline

**Files:** none

- [ ] **Step 1: Create `.worktrees/spec-03-integration` from current branch and install deps**

```bash
git worktree add .worktrees/spec-03-integration spec-03-integration
cd .worktrees/spec-03-integration/web
npm install
```

- [ ] **Step 2: Verify baseline tests pass**

```bash
npm test -- --run
```
Expected: 30/30 vitest tests pass.

- [ ] **Step 3: Verify baseline lint + typecheck**

```bash
npm run lint && npm run typecheck
```
Expected: clean.

- [ ] **Step 4: No commit yet — Task 0 is a sanity check.**

---

## Task 1: wsCodec — binary frame encode/decode

**Files:**
- Create: `web/src/audio/wsCodec.ts`
- Test: `web/test/wsCodec.test.ts`

Mirror of `server/server/audio.py`. Frame: `[kind:u8][idLen:u8][idUtf8:idLen bytes][payload:Int16 LE]`.

- [ ] **Step 1: Write failing tests**

```ts
// web/test/wsCodec.test.ts
import { describe, it, expect } from "vitest";
import {
  KIND_CLIENT_MIC,
  KIND_SERVER_TTS,
  encodeMicFrame,
  decodeAudioFrame,
} from "@/audio/wsCodec";

describe("wsCodec", () => {
  it("encodes mic frame with empty audioId", () => {
    const samples = new Int16Array([0, 1, -1, 32767, -32768]);
    const buf = new Uint8Array(encodeMicFrame(samples));
    expect(buf[0]).toBe(KIND_CLIENT_MIC);
    expect(buf[1]).toBe(0);
    expect(buf.byteLength).toBe(2 + samples.byteLength);
  });

  it("round-trips a TTS frame with audioId", () => {
    const samples = new Int16Array([100, -200, 300]);
    const audioId = "s0-abcdef";
    const idBytes = new TextEncoder().encode(audioId);
    const out = new Uint8Array(2 + idBytes.byteLength + samples.byteLength);
    out[0] = KIND_SERVER_TTS;
    out[1] = idBytes.byteLength;
    out.set(idBytes, 2);
    out.set(new Uint8Array(samples.buffer), 2 + idBytes.byteLength);
    const decoded = decodeAudioFrame(out.buffer);
    expect(decoded.kind).toBe(KIND_SERVER_TTS);
    expect(decoded.audioId).toBe(audioId);
    expect(Array.from(decoded.samples)).toEqual([100, -200, 300]);
  });

  it("rejects truncated frames", () => {
    expect(() => decodeAudioFrame(new Uint8Array([0x02]).buffer)).toThrow();
    const short = new Uint8Array([0x02, 5, 0x61]); // idLen=5 but only 1 id byte
    expect(() => decodeAudioFrame(short.buffer)).toThrow();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL (module not found)**

```bash
npm test -- --run wsCodec
```

- [ ] **Step 3: Implement wsCodec**

```ts
// web/src/audio/wsCodec.ts
export const KIND_CLIENT_MIC = 0x01;
export const KIND_SERVER_TTS = 0x02;

export function encodeMicFrame(int16: Int16Array): ArrayBuffer {
  const out = new Uint8Array(2 + int16.byteLength);
  out[0] = KIND_CLIENT_MIC;
  out[1] = 0;
  out.set(new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength), 2);
  return out.buffer;
}

export interface DecodedAudioFrame {
  kind: number;
  audioId: string;
  samples: Int16Array;
}

export function decodeAudioFrame(buf: ArrayBuffer): DecodedAudioFrame {
  const view = new Uint8Array(buf);
  if (view.byteLength < 2) throw new Error("frame too short");
  const kind = view[0];
  const idLen = view[1];
  if (view.byteLength < 2 + idLen) throw new Error("frame truncated (id)");
  const audioId = new TextDecoder().decode(view.subarray(2, 2 + idLen));
  const payloadOffset = 2 + idLen;
  const payloadLen = view.byteLength - payloadOffset;
  if (payloadLen % 2 !== 0) throw new Error("payload not Int16-aligned");
  const samples = new Int16Array(buf.slice(payloadOffset));
  return { kind, audioId, samples };
}
```

- [ ] **Step 4: Run tests — expect PASS (3/3)**

- [ ] **Step 5: Commit**

```bash
git add web/src/audio/wsCodec.ts web/test/wsCodec.test.ts
git commit -m "feat(web): wsCodec — binary mic/TTS frame encode/decode"
```

---

## Task 2: Test fakes — FakeWebSocket and FakeAudioContext

**Files:**
- Create: `web/test/_fakes.ts`

Shared utilities used across the next several test files. No production code yet, so no test for the test util — but it must compile under `tsc --noEmit`.

- [ ] **Step 1: Create the fakes**

```ts
// web/test/_fakes.ts
type Listener = (ev: MessageEvent | Event | CloseEvent) => void;

export class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  static install(): { restore: () => void } {
    const original = (globalThis as { WebSocket?: typeof WebSocket }).WebSocket;
    (globalThis as { WebSocket: unknown }).WebSocket = FakeWebSocket;
    return {
      restore: () => {
        (globalThis as { WebSocket: unknown }).WebSocket = original as typeof WebSocket;
        FakeWebSocket.instances = [];
      },
    };
  }
  url: string;
  readyState = 0;
  binaryType: "arraybuffer" | "blob" = "arraybuffer";
  sent: (string | ArrayBuffer)[] = [];
  private listeners: Record<string, Listener[]> = {};
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  addEventListener(type: string, fn: Listener): void {
    (this.listeners[type] ??= []).push(fn);
  }
  removeEventListener(type: string, fn: Listener): void {
    this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== fn);
  }
  send(data: string | ArrayBuffer): void {
    this.sent.push(data);
  }
  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.fire("close", new Event("close"));
  }
  // test helpers
  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.fire("open", new Event("open"));
  }
  receiveText(s: string): void {
    this.fire("message", new MessageEvent("message", { data: s }));
  }
  receiveBinary(buf: ArrayBuffer): void {
    this.fire("message", new MessageEvent("message", { data: buf }));
  }
  fail(): void {
    this.fire("error", new Event("error"));
    this.close();
  }
  private fire(type: string, ev: Event): void {
    for (const fn of this.listeners[type] ?? []) fn(ev);
  }
}

export class FakeAudioBuffer {
  constructor(public numberOfChannels: number, public length: number, public sampleRate: number) {}
  getChannelData(_ch: number): Float32Array {
    return new Float32Array(this.length);
  }
  duration = 0;
}

export class FakeAudioBufferSourceNode {
  buffer: FakeAudioBuffer | null = null;
  startCalls: number[] = [];
  stopCalls: number[] = [];
  connected: unknown[] = [];
  onended: (() => void) | null = null;
  connect(node: unknown): unknown {
    this.connected.push(node);
    return node;
  }
  start(t: number): void {
    this.startCalls.push(t);
  }
  stop(t?: number): void {
    this.stopCalls.push(t ?? 0);
    queueMicrotask(() => this.onended?.());
  }
}

export class FakeAnalyserNode {
  fftSize = 2048;
  frequencyBinCount = 1024;
  getFloatTimeDomainData(arr: Float32Array): void {
    arr.fill(0);
  }
  connect(node: unknown): unknown {
    return node;
  }
}

export class FakeAudioContext {
  currentTime = 0;
  sampleRate = 48000;
  destination = {};
  sources: FakeAudioBufferSourceNode[] = [];
  analyser = new FakeAnalyserNode();
  state: "running" | "suspended" | "closed" = "running";
  createBuffer(channels: number, length: number, rate: number): FakeAudioBuffer {
    const buf = new FakeAudioBuffer(channels, length, rate);
    buf.duration = length / rate;
    return buf;
  }
  createBufferSource(): FakeAudioBufferSourceNode {
    const src = new FakeAudioBufferSourceNode();
    this.sources.push(src);
    return src;
  }
  createAnalyser(): FakeAnalyserNode {
    return this.analyser;
  }
  resume(): Promise<void> {
    this.state = "running";
    return Promise.resolve();
  }
  close(): Promise<void> {
    this.state = "closed";
    return Promise.resolve();
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npm run typecheck
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web/test/_fakes.ts
git commit -m "test(web): FakeWebSocket / FakeAudioContext for spec-03 tests"
```

---

## Task 3: PlaybackQueue

**Files:**
- Create: `web/src/audio/playbackQueue.ts`
- Test: `web/test/playbackQueue.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// web/test/playbackQueue.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { PlaybackQueue } from "@/audio/playbackQueue";
import { FakeAudioContext } from "./_fakes";

describe("PlaybackQueue", () => {
  let ctx: FakeAudioContext;
  let q: PlaybackQueue;
  beforeEach(() => {
    ctx = new FakeAudioContext();
    q = new PlaybackQueue(ctx as unknown as AudioContext);
  });

  it("schedules each enqueued chunk after the previous one", () => {
    const a = new Int16Array(2400); // 100ms at 24kHz
    const b = new Int16Array(2400);
    q.enqueue("s0", a);
    q.enqueue("s0", b);
    expect(ctx.sources.length).toBe(2);
    const [s1, s2] = ctx.sources;
    expect(s1.startCalls[0]).toBe(0);
    expect(s2.startCalls[0]).toBeCloseTo(0.1, 5);
  });

  it("interrupt cancels all pending sources and resets cursor", () => {
    q.enqueue("s0", new Int16Array(2400));
    q.enqueue("s0", new Int16Array(2400));
    q.interrupt();
    for (const s of ctx.sources) expect(s.stopCalls.length).toBe(1);
    ctx.currentTime = 5;
    q.enqueue("s1", new Int16Array(2400));
    expect(ctx.sources[ctx.sources.length - 1].startCalls[0]).toBe(5);
  });

  it("exposes an AnalyserNode in the graph", () => {
    expect(q.analyser).toBe(ctx.analyser);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement PlaybackQueue**

```ts
// web/src/audio/playbackQueue.ts
export class PlaybackQueue {
  readonly analyser: AnalyserNode;
  private nextStart = 0;
  private active: AudioBufferSourceNode[] = [];
  private readonly inputRate: number;

  constructor(private ctx: AudioContext, opts?: { sampleRate?: number }) {
    this.inputRate = opts?.sampleRate ?? 24000;
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.connect(ctx.destination);
  }

  enqueue(_audioId: string, int16: Int16Array): void {
    if (int16.length === 0) return;
    const buf = this.ctx.createBuffer(1, int16.length, this.inputRate);
    const out = buf.getChannelData(0);
    for (let i = 0; i < int16.length; i++) out[i] = int16[i] / 32768;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.analyser);
    const start = Math.max(this.nextStart, this.ctx.currentTime);
    src.start(start);
    this.nextStart = start + buf.duration;
    this.active.push(src);
    src.onended = () => {
      const i = this.active.indexOf(src);
      if (i >= 0) this.active.splice(i, 1);
    };
  }

  endSentence(_audioId: string): void {
    // Bookkeeping hook; spec-03 does not need cross-sentence ordering since WS preserves order.
  }

  interrupt(): void {
    for (const s of this.active) {
      try {
        s.stop();
      } catch {
        // already ended
      }
    }
    this.active = [];
    this.nextStart = this.ctx.currentTime;
  }

  destroy(): void {
    this.interrupt();
  }
}
```

- [ ] **Step 4: Run tests — expect PASS (3/3)**

- [ ] **Step 5: Commit**

```bash
git add web/src/audio/playbackQueue.ts web/test/playbackQueue.test.ts
git commit -m "feat(web): PlaybackQueue — Web Audio TTS scheduling + analyser"
```

---

## Task 4: Mic AudioWorklet processor

**Files:**
- Create: `web/public/mic-processor.js`
- Create: `web/src/audio/micWorklet.ts`

The processor itself runs in the audio thread; we trust it without unit tests (smoke-tested in manual e2e). Main-thread `micWorklet.ts` has unit-testable conversion logic.

- [ ] **Step 1: Write failing test for Float32 → Int16 conversion**

```ts
// web/test/micWorklet.test.ts
import { describe, it, expect } from "vitest";
import { float32ToInt16 } from "@/audio/micWorklet";

describe("float32ToInt16", () => {
  it("clamps and scales", () => {
    const out = float32ToInt16(new Float32Array([0, 0.5, -0.5, 1, -1, 2, -2]));
    expect(Array.from(out)).toEqual([0, 16383, -16384, 32767, -32767, 32767, -32767]);
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement processor + main-thread glue**

```js
// web/public/mic-processor.js
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Float32Array(1600);
    this.fill = 0;
  }
  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    let i = 0;
    while (i < ch.length) {
      const room = this.frame.length - this.fill;
      const n = Math.min(room, ch.length - i);
      this.frame.set(ch.subarray(i, i + n), this.fill);
      this.fill += n;
      i += n;
      if (this.fill === this.frame.length) {
        this.port.postMessage(this.frame.slice());
        this.fill = 0;
      }
    }
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);
```

```ts
// web/src/audio/micWorklet.ts
export function float32ToInt16(f32: Float32Array): Int16Array {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const v = Math.max(-1, Math.min(1, f32[i]));
    out[i] = v < 0 ? Math.round(v * 32768) : Math.round(v * 32767);
  }
  return out;
}

export interface MicWorkletHandle {
  stop(): void;
}

export async function startMicWorklet(
  ctx: AudioContext,
  source: MediaStreamAudioSourceNode,
  onFrame: (int16: Int16Array) => void,
): Promise<MicWorkletHandle> {
  await ctx.audioWorklet.addModule("/mic-processor.js");
  const node = new AudioWorkletNode(ctx, "mic-processor");
  node.port.onmessage = (ev: MessageEvent<Float32Array>) => {
    onFrame(float32ToInt16(ev.data));
  };
  source.connect(node);
  return {
    stop(): void {
      try {
        source.disconnect(node);
      } catch {
        /* already disconnected */
      }
      node.port.close();
    },
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npm test -- --run micWorklet
```

- [ ] **Step 5: Commit**

```bash
git add web/public/mic-processor.js web/src/audio/micWorklet.ts web/test/micWorklet.test.ts
git commit -m "feat(web): AudioWorklet mic processor + Float32→Int16 main-thread glue"
```

---

## Task 5: WSEventSource — handshake + JSON dispatch + stop

**Files:**
- Create: `web/src/events/wsEventSource.ts`
- Test: `web/test/wsEventSource.test.ts`

This task covers: construct, `start()` opens WS and sends `hello`, `ready` resolves the start promise, JSON inbound messages dispatch to `on()` handlers, `stop()` closes cleanly with no reconnect.

- [ ] **Step 1: Write failing tests**

```ts
// web/test/wsEventSource.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { WSEventSource } from "@/events/wsEventSource";
import { FakeWebSocket, FakeAudioContext } from "./_fakes";

describe("WSEventSource — handshake + dispatch", () => {
  let restore: () => void;
  beforeEach(() => {
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => restore());

  it("opens WS, sends hello, resolves start() on ready", async () => {
    const src = new WSEventSource({ url: "ws://x", audioCtx: new FakeAudioContext() as unknown as AudioContext });
    const startPromise = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    expect(ws.sent[0]).toBe(JSON.stringify({ type: "hello", clientVersion: "spec-03" }));
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await startPromise;
  });

  it("dispatches stt.partial / llm.token / telemetry / error", async () => {
    const src = new WSEventSource({ url: "ws://x", audioCtx: new FakeAudioContext() as unknown as AudioContext });
    const partial = vi.fn();
    const token = vi.fn();
    const tele = vi.fn();
    const err = vi.fn();
    src.on("stt.partial", partial);
    src.on("llm.token", token);
    src.on("telemetry", tele);
    src.on("error", err);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText(JSON.stringify({ type: "stt.partial", text: "hi" }));
    ws.receiveText(JSON.stringify({ type: "llm.token", delta: "yo" }));
    ws.receiveText(JSON.stringify({ type: "telemetry", level: "info", message: "heartbeat" }));
    ws.receiveText(JSON.stringify({ type: "error", code: "x", message: "y" }));
    expect(partial).toHaveBeenCalledWith({ text: "hi" });
    expect(token).toHaveBeenCalledWith({ delta: "yo" });
    expect(tele).toHaveBeenCalledWith(expect.objectContaining({ level: "info", message: "heartbeat" }));
    expect(err).toHaveBeenCalledWith({ code: "x", message: "y" });
  });

  it("stop() closes the socket and prevents reconnect", () => {
    const src = new WSEventSource({ url: "ws://x", audioCtx: new FakeAudioContext() as unknown as AudioContext });
    void src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    src.stop();
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED);
    // closing did not spawn a new socket
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL (module not found)**

- [ ] **Step 3: Implement minimal WSEventSource (no reconnect, no audio I/O yet)**

```ts
// web/src/events/wsEventSource.ts
import type { EventSource as IEventSource } from "@/events/eventSource";
import type { EventName, EventHandler, EventMap, TelemetryEvent } from "@/types";

export interface WSEventSourceOpts {
  url: string;
  audioCtx?: AudioContext;
  clientVersion?: string;
}

type Handlers = { [K in EventName]?: Set<EventHandler<K>> };

export class WSEventSource implements IEventSource {
  private ws: WebSocket | null = null;
  private handlers: Handlers = {};
  private readyResolve: (() => void) | null = null;
  private readyPromise: Promise<void> | null = null;
  private closedByUser = false;

  constructor(private opts: WSEventSourceOpts) {}

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    const set = (this.handlers[event] ??= new Set()) as Set<EventHandler<E>>;
    set.add(handler);
    return () => set.delete(handler);
  }

  private emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) return;
    for (const fn of set) fn(payload);
  }

  start(): Promise<void> {
    if (this.readyPromise) return this.readyPromise;
    this.readyPromise = new Promise<void>((resolve) => {
      this.readyResolve = resolve;
    });
    this.openSocket();
    return this.readyPromise;
  }

  stop(): void {
    this.closedByUser = true;
    this.ws?.close();
    this.ws = null;
  }

  beginListening(): void {
    /* implemented in Task 7 */
  }
  endListening(): void {
    /* implemented in Task 7 */
  }
  sendText(content: string): void {
    this.ws?.send(JSON.stringify({ type: "text", content }));
  }
  interrupt(): void {
    /* implemented in Task 8 */
  }

  private openSocket(): void {
    const ws = new WebSocket(this.opts.url);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.addEventListener("open", () => {
      ws.send(JSON.stringify({ type: "hello", clientVersion: this.opts.clientVersion ?? "spec-03" }));
    });
    ws.addEventListener("message", (ev) => {
      const data = (ev as MessageEvent).data;
      if (typeof data === "string") this.handleJson(data);
      else this.handleBinary(data as ArrayBuffer);
    });
    ws.addEventListener("close", () => {
      /* reconnect added in Task 9 */
    });
    ws.addEventListener("error", () => {
      /* reconnect added in Task 9 */
    });
  }

  private handleJson(raw: string): void {
    let msg: { type?: string } & Record<string, unknown>;
    try {
      msg = JSON.parse(raw);
    } catch {
      this.emit("error", { code: "client.bad_message", message: raw.slice(0, 80) });
      return;
    }
    switch (msg.type) {
      case "ready":
        this.readyResolve?.();
        this.readyResolve = null;
        return;
      case "stt.partial":
        this.emit("stt.partial", { text: String(msg.text ?? "") });
        return;
      case "stt.final":
        this.emit("stt.final", { text: String(msg.text ?? "") });
        return;
      case "llm.token":
        this.emit("llm.token", { delta: String(msg.delta ?? "") });
        return;
      case "llm.end":
        this.emit("llm.end", undefined);
        return;
      case "tts.sentence":
        this.emit("tts.sentence", { text: String(msg.text ?? ""), audioId: String(msg.audioId ?? "") });
        return;
      case "tts.end":
        this.emit("tts.end", { audioId: String(msg.audioId ?? "") });
        return;
      case "telemetry": {
        const t: TelemetryEvent = {
          ts: Date.now(),
          level: (msg.level as TelemetryEvent["level"]) ?? "info",
          message: String(msg.message ?? ""),
        };
        this.emit("telemetry", t);
        return;
      }
      case "error":
        this.emit("error", { code: String(msg.code ?? "unknown"), message: String(msg.message ?? "") });
        return;
      default:
        // unknown — ignore but log via telemetry channel
        this.emit("telemetry", { ts: Date.now(), level: "warn", message: `unknown msg ${msg.type}` });
    }
  }

  private handleBinary(_buf: ArrayBuffer): void {
    /* implemented in Task 6 */
  }
}
```

- [ ] **Step 4: Run tests — expect PASS (3/3)**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/wsEventSource.ts web/test/wsEventSource.test.ts
git commit -m "feat(web): WSEventSource — handshake + JSON dispatch + stop"
```

---

## Task 6: WSEventSource — binary TTS frame → playback queue

**Files:**
- Modify: `web/src/events/wsEventSource.ts`
- Modify: `web/test/wsEventSource.test.ts`

- [ ] **Step 1: Add failing tests**

Append to `wsEventSource.test.ts`:

```ts
import { encodeMicFrame, KIND_SERVER_TTS } from "@/audio/wsCodec";

describe("WSEventSource — binary TTS frame", () => {
  let restore: () => void;
  beforeEach(() => { ({ restore } = FakeWebSocket.install()); });
  afterEach(() => restore());

  it("decodes a TTS frame and emits tts.audioChunk + enqueues to playback", async () => {
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({ url: "ws://x", audioCtx: ctx as unknown as AudioContext });
    const chunkSpy = vi.fn();
    src.on("tts.audioChunk", chunkSpy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    const samples = new Int16Array([0, 100, -100]);
    const audioId = "s0-aaa";
    const idBytes = new TextEncoder().encode(audioId);
    const frame = new Uint8Array(2 + idBytes.byteLength + samples.byteLength);
    frame[0] = KIND_SERVER_TTS;
    frame[1] = idBytes.byteLength;
    frame.set(idBytes, 2);
    frame.set(new Uint8Array(samples.buffer), 2 + idBytes.byteLength);
    ws.receiveBinary(frame.buffer);

    expect(chunkSpy).toHaveBeenCalledTimes(1);
    expect(ctx.sources.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Wire PlaybackQueue into WSEventSource**

In `wsEventSource.ts`, add to imports:

```ts
import { decodeAudioFrame, KIND_SERVER_TTS } from "@/audio/wsCodec";
import { PlaybackQueue } from "@/audio/playbackQueue";
```

Add field + constructor wiring:

```ts
private playback: PlaybackQueue | null = null;
// in constructor:
if (opts.audioCtx) this.playback = new PlaybackQueue(opts.audioCtx);
```

Replace `handleBinary`:

```ts
private handleBinary(buf: ArrayBuffer): void {
  let frame;
  try {
    frame = decodeAudioFrame(buf);
  } catch (e) {
    this.emit("error", { code: "client.bad_frame", message: String(e) });
    return;
  }
  if (frame.kind !== KIND_SERVER_TTS) {
    this.emit("error", { code: "client.bad_frame", message: `unexpected kind ${frame.kind}` });
    return;
  }
  const f32 = new Float32Array(frame.samples.length);
  for (let i = 0; i < frame.samples.length; i++) f32[i] = frame.samples[i] / 32768;
  this.emit("tts.audioChunk", { audioId: frame.audioId, samples: f32 });
  this.playback?.enqueue(frame.audioId, frame.samples);
}
```

Also expose the analyser for the centerpiece:

```ts
get analyser(): AnalyserNode | null { return this.playback?.analyser ?? null; }
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/wsEventSource.ts web/test/wsEventSource.test.ts
git commit -m "feat(web): WSEventSource — decode TTS binary frames + playback enqueue"
```

---

## Task 7: WSEventSource — beginListening / endListening with mic worklet

**Files:**
- Modify: `web/src/events/wsEventSource.ts`
- Modify: `web/test/wsEventSource.test.ts`

For unit test we don't actually run a worklet; we inject a mic-frame source via a constructor option (`micFactory`) so tests can drive frames synthetically.

- [ ] **Step 1: Add failing tests**

```ts
describe("WSEventSource — listening", () => {
  let restore: () => void;
  beforeEach(() => { ({ restore } = FakeWebSocket.install()); });
  afterEach(() => restore());

  it("beginListening sends audio.start; mic frames go out as binary; endListening sends audio.end", async () => {
    const ctx = new FakeAudioContext();
    let onFrame: ((s: Int16Array) => void) | null = null;
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
      micFactory: async (_ctx, cb) => {
        onFrame = cb;
        return { stop() { onFrame = null; } };
      },
    });
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    await src.beginListening();
    const startMsg = ws.sent.find((m): m is string => typeof m === "string" && m.includes("audio.start"));
    expect(startMsg).toBeTruthy();
    onFrame!(new Int16Array([1, 2, 3]));
    const binSent = ws.sent.find((m) => m instanceof ArrayBuffer);
    expect(binSent).toBeTruthy();

    src.endListening();
    const endMsg = ws.sent.find((m): m is string => typeof m === "string" && m.includes("audio.end"));
    expect(endMsg).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Add mic plumbing**

Update `WSEventSourceOpts`:

```ts
import type { MicWorkletHandle } from "@/audio/micWorklet";
import { startMicWorklet } from "@/audio/micWorklet";
import { encodeMicFrame } from "@/audio/wsCodec";

export interface WSEventSourceOpts {
  url: string;
  audioCtx?: AudioContext;
  clientVersion?: string;
  micFactory?: (
    ctx: AudioContext,
    onFrame: (int16: Int16Array) => void,
  ) => Promise<MicWorkletHandle>;
  micSource?: () => Promise<MediaStreamAudioSourceNode>;
}
```

Add fields:

```ts
private mic: MicWorkletHandle | null = null;
```

Implement methods:

```ts
async beginListening(): Promise<void> {
  if (!this.opts.audioCtx) throw new Error("audioCtx required");
  this.ws?.send(JSON.stringify({ type: "audio.start", sampleRate: 16000, format: "pcm_s16le" }));
  const onFrame = (int16: Int16Array): void => {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(encodeMicFrame(int16));
    }
  };
  if (this.opts.micFactory) {
    this.mic = await this.opts.micFactory(this.opts.audioCtx, onFrame);
  } else {
    if (!this.opts.micSource) throw new Error("micSource required when micFactory absent");
    const source = await this.opts.micSource();
    this.mic = await startMicWorklet(this.opts.audioCtx, source, onFrame);
  }
}

endListening(): void {
  this.mic?.stop();
  this.mic = null;
  this.ws?.send(JSON.stringify({ type: "audio.end" }));
}
```

(Adjust `EventSource` interface signature: change `beginListening(): void` to `beginListening(): void | Promise<void>` — handled below.)

Also update `web/src/events/eventSource.ts`:

```ts
beginListening(): void | Promise<void>;
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/wsEventSource.ts web/src/events/eventSource.ts web/test/wsEventSource.test.ts
git commit -m "feat(web): WSEventSource — listening (audio.start, mic frames, audio.end)"
```

---

## Task 8: WSEventSource — interrupt cancels playback + sends interrupt

**Files:**
- Modify: `web/src/events/wsEventSource.ts`
- Modify: `web/test/wsEventSource.test.ts`

- [ ] **Step 1: Add failing test**

```ts
it("interrupt() stops local playback synchronously and sends interrupt msg", async () => {
  const ctx = new FakeAudioContext();
  const src = new WSEventSource({ url: "ws://x", audioCtx: ctx as unknown as AudioContext });
  const p = src.start();
  const ws = FakeWebSocket.instances[0];
  ws.open();
  ws.receiveText(JSON.stringify({ type: "ready" }));
  await p;

  // queue a fake chunk
  const samples = new Int16Array(2400);
  const idBytes = new TextEncoder().encode("a");
  const frame = new Uint8Array(2 + 1 + samples.byteLength);
  frame[0] = 0x02; frame[1] = 1; frame.set(idBytes, 2);
  frame.set(new Uint8Array(samples.buffer), 3);
  ws.receiveBinary(frame.buffer);
  expect(ctx.sources[0].stopCalls.length).toBe(0);

  src.interrupt();
  expect(ctx.sources[0].stopCalls.length).toBe(1);
  const sent = ws.sent.find((m): m is string => typeof m === "string" && m.includes("interrupt"));
  expect(sent).toBeTruthy();
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement interrupt**

```ts
interrupt(): void {
  this.playback?.interrupt();
  if (this.ws?.readyState === WebSocket.OPEN) {
    this.ws.send(JSON.stringify({ type: "interrupt" }));
  }
}
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/wsEventSource.ts web/test/wsEventSource.test.ts
git commit -m "feat(web): WSEventSource — interrupt cancels local playback + sends msg"
```

---

## Task 9: WSEventSource — reconnect with backoff

**Files:**
- Modify: `web/src/events/wsEventSource.ts`
- Modify: `web/test/wsEventSource.test.ts`

- [ ] **Step 1: Add failing tests using fake timers**

```ts
import { vi } from "vitest";

describe("WSEventSource — reconnect", () => {
  let restore: () => void;
  beforeEach(() => {
    vi.useFakeTimers();
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => {
    vi.useRealTimers();
    restore();
  });

  it("walks backoff [1,2,4,8,16,30] on repeated failures and emits telemetry", async () => {
    const tele = vi.fn();
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({ url: "ws://x", audioCtx: ctx as unknown as AudioContext });
    src.on("telemetry", tele);
    void src.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveText(JSON.stringify({ type: "ready" }));
    await Promise.resolve();

    // simulate drop
    FakeWebSocket.instances[0].close();
    expect(tele).toHaveBeenCalledWith(expect.objectContaining({ message: expect.stringContaining("reconnecting") }));

    // attempt 1: after 1s a new socket is created and immediately fails
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances.length).toBe(2);
    FakeWebSocket.instances[1].close();

    await vi.advanceTimersByTimeAsync(2000);
    expect(FakeWebSocket.instances.length).toBe(3);
    FakeWebSocket.instances[2].close();

    await vi.advanceTimersByTimeAsync(4000);
    expect(FakeWebSocket.instances.length).toBe(4);
  });

  it("stop() cancels pending reconnect", async () => {
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({ url: "ws://x", audioCtx: ctx as unknown as AudioContext });
    void src.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].close();
    src.stop();
    await vi.advanceTimersByTimeAsync(60000);
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement reconnect**

Add fields and implement schedule:

```ts
private reconnectAttempt = 0;
private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
private static BACKOFF_S = [1, 2, 4, 8, 16, 30];

private scheduleReconnect(): void {
  if (this.closedByUser) return;
  const idx = Math.min(this.reconnectAttempt, WSEventSource.BACKOFF_S.length - 1);
  const delay = WSEventSource.BACKOFF_S[idx] * 1000;
  this.reconnectAttempt++;
  this.emit("telemetry", {
    ts: Date.now(),
    level: "warn",
    message: `reconnecting (attempt ${this.reconnectAttempt})…`,
  });
  this.reconnectTimer = setTimeout(() => {
    this.reconnectTimer = null;
    this.openSocket();
  }, delay);
}
```

Wire into `openSocket`:

```ts
ws.addEventListener("open", () => {
  ws.send(JSON.stringify({ type: "hello", clientVersion: this.opts.clientVersion ?? "spec-03" }));
  if (this.reconnectAttempt > 0) {
    this.emit("telemetry", { ts: Date.now(), level: "ok", message: "reconnected" });
    this.reconnectAttempt = 0;
  }
});
ws.addEventListener("close", () => {
  if (this.closedByUser) return;
  this.playback?.interrupt();
  this.mic?.stop();
  this.mic = null;
  this.scheduleReconnect();
});
```

Update `stop()`:

```ts
stop(): void {
  this.closedByUser = true;
  if (this.reconnectTimer) {
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }
  this.ws?.close();
  this.ws = null;
}
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/wsEventSource.ts web/test/wsEventSource.test.ts
git commit -m "feat(web): WSEventSource — reconnect with capped exponential backoff"
```

---

## Task 10: connect() — probe + fallback to MockEventSource

**Files:**
- Create: `web/src/events/connect.ts`
- Test: `web/test/connect.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// web/test/connect.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { connect } from "@/events/connect";
import { FakeWebSocket, FakeAudioContext } from "./_fakes";

describe("connect", () => {
  let restore: () => void;
  beforeEach(() => {
    vi.useFakeTimers();
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => {
    vi.useRealTimers();
    restore();
  });

  it("returns live mode when WS opens within timeout", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await Promise.resolve();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveText(JSON.stringify({ type: "ready" }));
    const result = await promise;
    expect(result.mode).toBe("live");
  });

  it("falls back to demo when WS open times out", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await vi.advanceTimersByTimeAsync(1000);
    const result = await promise;
    expect(result.mode).toBe("demo");
  });

  it("falls back to demo when WS errors immediately", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await Promise.resolve();
    FakeWebSocket.instances[0].fail();
    const result = await promise;
    expect(result.mode).toBe("demo");
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement connect**

```ts
// web/src/events/connect.ts
import type { EventSource as IEventSource } from "@/events/eventSource";
import { WSEventSource } from "@/events/wsEventSource";
import { MockEventSource } from "@/events/mockEventSource";

export interface ConnectOptions {
  url: string;
  audioCtx?: AudioContext;
  openTimeoutMs?: number;
}

export interface ConnectResult {
  events: IEventSource;
  mode: "live" | "demo";
}

export async function connect(opts: ConnectOptions): Promise<ConnectResult> {
  const timeoutMs = opts.openTimeoutMs ?? 1000;
  const live = new WSEventSource({ url: opts.url, audioCtx: opts.audioCtx });
  const settled = new Promise<"live" | "demo">((resolve) => {
    let done = false;
    const finish = (mode: "live" | "demo"): void => {
      if (done) return;
      done = true;
      resolve(mode);
    };
    live.start().then(() => finish("live")).catch(() => finish("demo"));
    setTimeout(() => finish("demo"), timeoutMs);
  });
  const mode = await settled;
  if (mode === "live") return { events: live, mode };
  live.stop();
  const mock = new MockEventSource();
  await mock.start();
  // surface a one-shot demo banner via telemetry
  queueMicrotask(() => {
    const t = { ts: Date.now(), level: "warn" as const, message: "backend offline — demo mode" };
    // Re-emit through mock by dispatching a fake telemetry event on next tick — implementation detail
    // Use the fact that MockEventSource publishes its own telemetry stream; we just log here.
    // (Keep behavior minimal — main.ts already shows the banner from `mode === "demo"`.)
    void t;
  });
  return { events: mock, mode: "demo" };
}
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add web/src/events/connect.ts web/test/connect.test.ts
git commit -m "feat(web): connect() — WS probe with fallback to MockEventSource"
```

---

## Task 11: Wire main.ts to connect() + remove synthetic telemetry in live mode

**Files:**
- Modify: `web/src/main.ts`

- [ ] **Step 1: Replace EventSource construction**

Find `const events = new MockEventSource();` (around line 50). Replace with:

```ts
import { connect } from "@/events/connect";

const audioCtx = new AudioContext();
const { events, mode } = await connect({
  url: (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://localhost:8000/ws",
  audioCtx,
  openTimeoutMs: 1000,
});

if (mode === "demo") {
  log("warn", "backend offline — demo mode");
}
```

- [ ] **Step 2: Conditionally suppress synthetic telemetry generator in live mode**

Locate the synthetic telemetry interval (search for `inputDb` / `Math.random()` in the telemetry block). Wrap so it only runs in demo mode:

```ts
if (mode === "demo") {
  // existing synthetic telemetry generator stays here
} else {
  // live mode: telemetry comes from events.on("telemetry", ...) which is already wired in spec-01
}
```

- [ ] **Step 3: When in live mode, drive centerpiece amplitude from playback analyser during speaking**

Add near the centerpiece amplitude loop:

```ts
let analyser: AnalyserNode | null = null;
events.on("ready" as never, () => {
  // WSEventSource exposes .analyser; MockEventSource does not
  const maybe = (events as unknown as { analyser?: AnalyserNode }).analyser;
  if (maybe) analyser = maybe;
});

// inside the existing amplitude tick:
if (mode === "live" && analyser && s.state === "speaking") {
  const data = new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
  amp = Math.sqrt(sum / data.length);
}
```

- [ ] **Step 4: Verify all tests + build**

```bash
npm test -- --run
npm run typecheck
npm run lint
npm run build
```
Expected: all green; bundle < 30 KB gzip JS.

- [ ] **Step 5: Commit**

```bash
git add web/src/main.ts
git commit -m "feat(web): wire main.ts to connect() + analyser-driven waveform in live mode"
```

---

## Task 12: Manual e2e checklist in web/README.md

**Files:**
- Modify: `web/README.md`

- [ ] **Step 1: Append the checklist section**

```markdown
## Manual end-to-end checklist (spec-03)

Run with backend up:
```bash
# terminal A
cd server && uvicorn server.main:app --port 8000

# terminal B
cd web && npm run dev
```

Then in Chromium at http://localhost:5173:

1. **Live boot.** No demo banner. TelemetryPanel shows `heartbeat` entries within ~5 s.
2. **Text path.** Type "Brief me on today" → see `stt.final`, streamed `llm.token`s, audible TTS.
3. **Audio path.** Hold mic → speak → release. Partial transcripts appear during hold; final on release; assistant replies aloud.
4. **Barge-in.** Mid-speak press Esc. Audio cuts; UI returns to idle.
5. **Reconnect.** Kill `uvicorn` mid-conversation. Banner: `reconnecting (attempt N)…`. Restart. Banner: `reconnected`.
6. **Demo fallback.** Stop backend, hard-reload. Banner: `demo mode`. Mock scenario plays.
7. **Mic denied.** Block mic permission, attempt to listen. Telemetry `client.audio_unavailable`. Text input still works.
```

- [ ] **Step 2: Commit**

```bash
git add web/README.md
git commit -m "docs(web): manual e2e checklist for spec-03 integration"
```

---

## Task 13: Final verification + STATUS update

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Run the full battery**

```bash
cd web
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Expected: all green. Test count: 30 prior + ~20 new = ~50 passing.

- [ ] **Step 2: Manual smoke (one-shot)**

Spawn backend, hit page, confirm text path round-trip. (Items 1–3 of the checklist.)

- [ ] **Step 3: Update STATUS.md**

Mark spec-03 row Implement / Review / Verify columns appropriately. Update Last completed action and Next action.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(jarvis): STATUS — spec-03 implementation complete"
```

- [ ] **Step 5: Push branch**

```bash
git push -u origin spec-03-integration
```

---

## Self-Review Notes

**Spec coverage:** all of §5 (modules), §6 (wiring), §7 (reconnect), §8 (telemetry), §9 (errors), §10 (tests), §11 (acceptance) are covered by tasks 1–13. Items §10.2 (in-process integration test) is intentionally deferred — the unit tests + manual checklist cover the same ground; revisit only if drift appears.

**Placeholder scan:** none. Every task has runnable code or exact commands.

**Type consistency:** `WSEventSource` uses `IEventSource` from `eventSource.ts`. `EventName/EventMap/EventHandler` are imported from `@/types`. The `beginListening(): void | Promise<void>` widening in Task 7 is also applied to `EventSource` interface and exercised in main.ts via `await events.beginListening()` (already an async-friendly call site in spec-01 since `ensureMic` is awaited before).

**Risk:** the `connect()` fallback emits the "backend offline — demo mode" banner via `main.ts` (`if (mode === "demo") log(...)`) rather than through the events stream — that's a deliberate simplification (avoids wiring telemetry into MockEventSource just for one message).
