# Frontend Shell (spec-01) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `web/` Vite + TypeScript project that renders the production Jarvis HUD with audio-reactive waveform centerpiece in all four states (idle / listening / thinking / speaking), driven by a mock event source whose interface matches what the real WebSocket client (spec-03) will implement.

**Architecture:** Plain TS components subscribe to a single observable store; state transitions are guarded by an explicit state machine; events come from a swappable `EventSource` interface (mock in spec-01, WebSocket in spec-03). One-way data flow, no framework, ~30-line component base class. Real mic capture in v1 drives the waveform during `listening`.

**Tech Stack:** Vite, TypeScript (strict), Vitest, Playwright, ESLint, Prettier, Web Audio API (AudioWorklet), Canvas 2D.

**Spec:** `docs/superpowers/specs/2026-05-07-frontend-shell-design.md`

**Worktree:** `.worktrees/spec-01-frontend-shell` (created at start of Task 1)

---

## Task index

1. Create worktree + scaffold Vite TS project
2. Configure tsconfig strict, ESLint, Prettier, Vitest
3. Define shared types
4. State machine with TDD
5. Observable store with TDD
6. EventSource interface + Mock (skeleton with TDD)
7. HTML grid shell + base CSS
8. Component base class
9. Header + Panel chrome
10. Static info panels (System, Memory, Calendar, Network, Tasks)
11. TelemetryPanel with scrolling feed
12. Mic capture + analyzer
13. AudioPanel with mic permission UX
14. Waveform canvas
15. Transcript renderer with streaming
16. Centerpiece (waveform + transcript composition)
17. Controls + keyboard handlers
18. Mock event source: full scenario behavior + scenarios.ts
19. main.ts wiring + boot sequence
20. Playwright smoke test
21. Accessibility + polish pass
22. Final verification + merge prep

---

## Task 1: Create worktree + scaffold Vite TS project

**Files:**
- Create: `.worktrees/spec-01-frontend-shell/` (worktree on new branch `spec-01-frontend-shell`)
- Create: `web/package.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/.gitignore`

- [ ] **Step 1: Create the worktree**

```bash
cd /home/max/perso/jarvis
git worktree add -b spec-01-frontend-shell .worktrees/spec-01-frontend-shell main
cd .worktrees/spec-01-frontend-shell
```

Expected: new branch + working tree. Verify with `git worktree list`.

- [ ] **Step 2: Scaffold Vite manually (Node 18-compatible)**

`create-vite@latest` requires Node ≥20. Since we're on Node 18 and don't want to introduce a Node upgrade, scaffold the project files by hand. Output is identical in shape to what `create-vite --template vanilla-ts` produces.

```bash
mkdir -p web/src web/public
cd web
```

Create `web/package.json`:

```json
{
  "name": "jarvis-web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "~5.4.5",
    "vite": "^5.4.10"
  }
}
```

Create `web/tsconfig.json` (interim — replaced in Task 2):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

Create `web/vite.config.ts`:

```ts
import { defineConfig } from "vite";

export default defineConfig({
  server: { port: 5173 },
});
```

Create `web/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

Run install:

```bash
npm install
```

- [ ] **Step 3: (no-op — manual scaffold has no demo files to remove)**

- [ ] **Step 4: Replace `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Jarvis</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: Replace `web/src/main.ts` with a smoke entry**

```ts
const app = document.getElementById("app");
if (app) {
  app.textContent = "Jarvis booting…";
  document.body.dataset.ready = "true";
}
```

- [ ] **Step 6: Replace `web/src/style.css` with a minimal reset**

```css
:root {
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: #03060d; color: #e6f1ff; font-family: -apple-system, "Inter", system-ui, sans-serif; }
```

Wire it in `web/src/main.ts` by adding at the top:

```ts
import "./style.css";
```

- [ ] **Step 7: Verify dev server boots**

```bash
npm run dev -- --port 5173 &
sleep 3
curl -s http://localhost:5173 | grep -q '<div id="app">' && echo OK || echo FAIL
kill %1
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add web/
git commit -m "chore(web): scaffold Vite + TS project"
```

---

## Task 2: Configure tsconfig strict, ESLint, Prettier, Vitest

**Files:**
- Modify: `web/package.json`
- Modify: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/.eslintrc.cjs`
- Create: `web/.prettierrc.json`
- Create: `web/vitest.config.ts`
- Create: `web/test/sanity.test.ts`

- [ ] **Step 1: Replace `web/tsconfig.json` with strict config**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src", "test"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 2: Create `web/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 3: Install dev deps**

```bash
npm install -D vitest @vitest/ui jsdom \
  eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin \
  prettier eslint-config-prettier \
  @playwright/test
```

- [ ] **Step 4: Create `web/.eslintrc.cjs`**

```js
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module", project: "./tsconfig.json" },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "prettier"
  ],
  env: { browser: true, es2022: true, node: true },
  ignorePatterns: ["dist", "node_modules", "playwright-report", "test-results"],
  rules: {
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/consistent-type-imports": "error"
  }
};
```

- [ ] **Step 5: Create `web/.prettierrc.json`**

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2
}
```

- [ ] **Step 6: Create `web/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.ts"],
    globals: false,
  },
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
});
```

- [ ] **Step 7: Create `web/test/sanity.test.ts`**

```ts
import { describe, it, expect } from "vitest";

describe("toolchain sanity", () => {
  it("runs vitest with jsdom and TS", () => {
    const el = document.createElement("div");
    el.textContent = "ok";
    expect(el.textContent).toBe("ok");
  });
});
```

- [ ] **Step 8: Add scripts to `web/package.json`**

Replace the `scripts` block with:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "lint": "eslint . --ext .ts",
    "format": "prettier --write ."
  }
}
```

- [ ] **Step 9: Run all checks**

```bash
npm run lint
npm run test
npm run build
```

Expected: all three exit with code 0.

- [ ] **Step 10: Commit**

```bash
git add web/
git commit -m "chore(web): configure tsconfig strict, eslint, prettier, vitest"
```

---

## Task 3: Define shared types

**Files:**
- Create: `web/src/types.ts`

- [ ] **Step 1: Create `web/src/types.ts`**

```ts
export type ConvState = "idle" | "listening" | "thinking" | "speaking";

export interface TelemetryEvent {
  ts: number;            // epoch ms
  level: "info" | "ok" | "warn" | "error";
  message: string;
}

export interface SttPartial { text: string; }
export interface SttFinal   { text: string; }
export interface LlmToken   { delta: string; }
export interface TtsSentence { text: string; audioId: string; }
export interface TtsAudioChunk { audioId: string; samples: Float32Array; }
export interface TtsEnd     { audioId: string; }
export interface ProtocolError { code: string; message: string; }

export type EventMap = {
  ready: void;
  "stt.partial": SttPartial;
  "stt.final": SttFinal;
  "llm.token": LlmToken;
  "llm.end": void;
  "tts.sentence": TtsSentence;
  "tts.audioChunk": TtsAudioChunk;
  "tts.end": TtsEnd;
  error: ProtocolError;
  telemetry: TelemetryEvent;
};

export type EventName = keyof EventMap;
export type EventHandler<E extends EventName> = (payload: EventMap[E]) => void;
```

- [ ] **Step 2: Run typecheck**

```bash
cd web && npm run lint
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/types.ts
git commit -m "feat(web): define shared protocol and state types"
```

---

## Task 4: State machine with TDD

**Files:**
- Create: `web/test/stateMachine.test.ts`
- Create: `web/src/state/stateMachine.ts`

- [ ] **Step 1: Write failing tests**

Create `web/test/stateMachine.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { transition, canTransition } from "@/state/stateMachine";
import type { ConvState } from "@/types";

describe("state machine", () => {
  it("starts in idle and accepts startListening", () => {
    expect(transition("idle", "startListening")).toBe<ConvState>("listening");
  });

  it("listening accepts stopListening → thinking", () => {
    expect(transition("listening", "stopListening")).toBe("thinking");
  });

  it("listening accepts cancelListening → idle", () => {
    expect(transition("listening", "cancelListening")).toBe("idle");
  });

  it("thinking accepts replyStart → speaking", () => {
    expect(transition("thinking", "replyStart")).toBe("speaking");
  });

  it("speaking accepts replyEnd → idle", () => {
    expect(transition("speaking", "replyEnd")).toBe("idle");
  });

  it("any state accepts interrupt → idle", () => {
    const states: ConvState[] = ["idle", "listening", "thinking", "speaking"];
    for (const s of states) expect(transition(s, "interrupt")).toBe("idle");
  });

  it("rejects invalid transition (idle + replyStart)", () => {
    expect(() => transition("idle", "replyStart")).toThrow(/invalid/i);
  });

  it("canTransition returns false for invalid combos", () => {
    expect(canTransition("idle", "replyStart")).toBe(false);
    expect(canTransition("listening", "startListening")).toBe(false);
    expect(canTransition("idle", "startListening")).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd web && npm run test
```

Expected: FAIL — module `@/state/stateMachine` does not exist.

- [ ] **Step 3: Implement state machine**

Create `web/src/state/stateMachine.ts`:

```ts
import type { ConvState } from "@/types";

export type ConvEvent =
  | "startListening"
  | "stopListening"
  | "cancelListening"
  | "replyStart"
  | "replyEnd"
  | "interrupt";

const TABLE: Record<ConvState, Partial<Record<ConvEvent, ConvState>>> = {
  idle:      { startListening: "listening", interrupt: "idle" },
  listening: { stopListening: "thinking", cancelListening: "idle", interrupt: "idle" },
  thinking:  { replyStart: "speaking", interrupt: "idle" },
  speaking:  { replyEnd: "idle", interrupt: "idle" },
};

export function canTransition(from: ConvState, event: ConvEvent): boolean {
  return TABLE[from][event] !== undefined;
}

export function transition(from: ConvState, event: ConvEvent): ConvState {
  const next = TABLE[from][event];
  if (next === undefined) {
    throw new Error(`invalid transition: ${from} + ${event}`);
  }
  return next;
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 8/8 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/state/stateMachine.ts web/test/stateMachine.test.ts
git commit -m "feat(web): state machine with guarded transitions"
```

---

## Task 5: Observable store with TDD

**Files:**
- Create: `web/test/store.test.ts`
- Create: `web/src/state/store.ts`

- [ ] **Step 1: Write failing tests**

Create `web/test/store.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import { createStore } from "@/state/store";

interface Shape { count: number; name: string; }

describe("store", () => {
  it("returns initial state", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    expect(s.get()).toEqual({ count: 0, name: "a" });
  });

  it("set updates state and notifies subscribers", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    s.subscribe(sub);
    s.set({ count: 1, name: "b" });
    expect(s.get()).toEqual({ count: 1, name: "b" });
    expect(sub).toHaveBeenCalledOnce();
    expect(sub).toHaveBeenCalledWith({ count: 1, name: "b" });
  });

  it("update applies a partial patch", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    s.update((d) => ({ count: d.count + 1 }));
    expect(s.get()).toEqual({ count: 1, name: "a" });
  });

  it("subscribe returns an unsubscribe", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    const off = s.subscribe(sub);
    off();
    s.update(() => ({ count: 99 }));
    expect(sub).not.toHaveBeenCalled();
  });

  it("select notifies only when the selected slice changes (===)", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    s.select((d) => d.count, sub);
    s.update(() => ({ name: "b" })); // count unchanged
    expect(sub).not.toHaveBeenCalled();
    s.update(() => ({ count: 1 }));
    expect(sub).toHaveBeenCalledOnce();
    expect(sub).toHaveBeenCalledWith(1);
  });
});
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd web && npm run test
```

Expected: FAIL — `@/state/store` does not exist.

- [ ] **Step 3: Implement store**

Create `web/src/state/store.ts`:

```ts
export interface Store<T> {
  get(): T;
  set(next: T): void;
  update(patch: (current: T) => Partial<T>): void;
  subscribe(fn: (next: T) => void): () => void;
  select<U>(selector: (state: T) => U, fn: (next: U) => void): () => void;
}

export function createStore<T extends object>(initial: T): Store<T> {
  let state = initial;
  const subs = new Set<(next: T) => void>();

  const notify = () => subs.forEach((s) => s(state));

  return {
    get: () => state,
    set: (next) => {
      state = next;
      notify();
    },
    update: (patch) => {
      state = { ...state, ...patch(state) };
      notify();
    },
    subscribe(fn) {
      subs.add(fn);
      return () => { subs.delete(fn); };
    },
    select(selector, fn) {
      let prev = selector(state);
      const wrapper = (next: T) => {
        const v = selector(next);
        if (v !== prev) {
          prev = v;
          fn(v);
        }
      };
      subs.add(wrapper);
      return () => { subs.delete(wrapper); };
    },
  };
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 13/13 PASS (5 new + 8 from Task 4).

- [ ] **Step 5: Commit**

```bash
git add web/src/state/store.ts web/test/store.test.ts
git commit -m "feat(web): tiny observable store with select"
```

---

## Task 6: EventSource interface + Mock skeleton

**Files:**
- Create: `web/src/events/eventSource.ts`
- Create: `web/src/events/mockEventSource.ts`
- Create: `web/test/mockEventSource.test.ts`

This task only stubs the mock — full scenario emission is in Task 18.

- [ ] **Step 1: Create the interface**

Create `web/src/events/eventSource.ts`:

```ts
import type { EventName, EventHandler } from "@/types";

export interface EventSource {
  start(): Promise<void>;
  stop(): void;
  beginListening(): void;
  endListening(): void;
  sendText(text: string): void;
  interrupt(): void;
  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void;
}
```

- [ ] **Step 2: Write failing tests for the mock skeleton**

Create `web/test/mockEventSource.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import { MockEventSource } from "@/events/mockEventSource";

describe("MockEventSource skeleton", () => {
  it("emits ready after start()", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    await m.start();
    expect(ready).toHaveBeenCalledOnce();
  });

  it("on(...) returns an unsubscribe", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    const off = m.on("ready", ready);
    off();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });

  it("stop() clears subscribers", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    m.stop();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run tests, verify fail**

```bash
cd web && npm run test
```

Expected: FAIL — `@/events/mockEventSource` does not exist.

- [ ] **Step 4: Implement the skeleton**

Create `web/src/events/mockEventSource.ts`:

```ts
import type { EventSource } from "./eventSource";
import type { EventName, EventMap, EventHandler } from "@/types";

export class MockEventSource implements EventSource {
  private handlers: { [K in EventName]?: Set<EventHandler<K>> } = {};
  private started = false;

  async start(): Promise<void> {
    this.started = true;
    await Promise.resolve();
    this.emit("ready", undefined);
  }

  stop(): void {
    this.started = false;
    this.handlers = {};
  }

  beginListening(): void { /* full impl in Task 18 */ }
  endListening(): void { /* full impl in Task 18 */ }
  sendText(_text: string): void { /* full impl in Task 18 */ }
  interrupt(): void { /* full impl in Task 18 */ }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    let set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) {
      set = new Set();
      this.handlers[event] = set as never;
    }
    set.add(handler);
    return () => { set?.delete(handler); };
  }

  protected emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    if (!this.started && event !== "ready") return;
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    set?.forEach((h) => h(payload));
  }
}
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 16/16 PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/events web/test/mockEventSource.test.ts
git commit -m "feat(web): EventSource interface + mock skeleton"
```

---

## Task 7: HTML grid shell + base CSS

**Files:**
- Modify: `web/index.html`
- Replace: `web/src/style.css`
- Create: `web/src/styles/global.css`
- Create: `web/src/styles/grid.css`
- Create: `web/src/styles/panel.css`

- [ ] **Step 1: Replace `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Jarvis</title>
  </head>
  <body data-state="idle">
    <div id="app" class="hud">
      <header class="cell cell-top"      data-cell="top"></header>
      <section class="cell cell-tl"      data-cell="tl"></section>
      <section class="cell cell-tr"      data-cell="tr"></section>
      <section class="cell cell-left"    data-cell="left"></section>
      <section class="cell cell-center"  data-cell="center"></section>
      <section class="cell cell-right"   data-cell="right"></section>
      <section class="cell cell-bl"      data-cell="bl"></section>
      <footer  class="cell cell-bottom"  data-cell="bottom"></footer>
      <section class="cell cell-br"      data-cell="br"></section>
    </div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 2: Replace `web/src/style.css`**

```css
@import "./styles/global.css";
@import "./styles/grid.css";
@import "./styles/panel.css";
```

- [ ] **Step 3: Create `web/src/styles/global.css`**

```css
:root {
  --bg-0: #02060a;
  --bg-1: #03101a;
  --fg: #d6f0ff;
  --fg-dim: rgba(214, 240, 255, 0.65);
  --fg-faint: rgba(214, 240, 255, 0.45);
  --accent: #5cf0ff;
  --accent-dim: rgba(92, 240, 255, 0.35);
  --accent-faint: rgba(92, 240, 255, 0.10);
  --warn: #ffae5c;
  --grid-line: rgba(92, 240, 255, 0.08);
  color-scheme: dark;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 50% 50%, var(--bg-1) 0%, var(--bg-0) 70%),
    linear-gradient(transparent 95%, var(--grid-line) 95%) 0 0 / 100% 32px,
    linear-gradient(90deg, transparent 95%, var(--grid-line) 95%) 0 0 / 32px 100%;
  color: var(--fg);
  font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
}
```

- [ ] **Step 4: Create `web/src/styles/grid.css`**

```css
.hud {
  position: fixed;
  inset: 16px;
  display: grid;
  grid-template-columns: 240px 1fr 240px;
  grid-template-rows: auto 1fr auto;
  grid-template-areas:
    "tl  top    tr"
    "left center right"
    "bl  bottom br";
  gap: 14px;
}

.cell { min-width: 0; min-height: 0; }
.cell-top    { grid-area: top; }
.cell-tl     { grid-area: tl; }
.cell-tr     { grid-area: tr; }
.cell-left   { grid-area: left; }
.cell-center { grid-area: center; }
.cell-right  { grid-area: right; }
.cell-bl     { grid-area: bl; }
.cell-bottom { grid-area: bottom; }
.cell-br     { grid-area: br; }
```

- [ ] **Step 5: Create `web/src/styles/panel.css`**

```css
.panel {
  position: relative;
  border: 1px solid var(--accent-dim);
  background: linear-gradient(180deg, rgba(92, 240, 255, 0.04), rgba(92, 240, 255, 0.01));
  padding: 14px 16px;
  backdrop-filter: blur(2px);
  height: 100%;
}

.panel::before, .panel::after {
  content: "";
  position: absolute;
  width: 14px; height: 14px;
  border: 1px solid var(--accent);
}
.panel::before { top: -1px; left: -1px; border-right: none; border-bottom: none; }
.panel::after  { bottom: -1px; right: -1px; border-left: none; border-top: none; }

.panel h4 {
  margin: 0 0 10px;
  font-size: 10px;
  letter-spacing: 0.3em;
  color: var(--accent);
  text-transform: uppercase;
  font-weight: 500;
}

.panel .row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: var(--fg-dim);
}
.panel .row b { color: var(--fg); font-weight: 500; }

.panel .bar {
  height: 4px;
  background: var(--accent-faint);
  border: 1px solid var(--accent-dim);
  margin: 6px 0 10px;
  position: relative;
  overflow: hidden;
}
.panel .bar > i {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: var(--accent);
  box-shadow: 0 0 12px var(--accent);
}
```

- [ ] **Step 6: Verify dev server still boots and renders**

```bash
cd web && npm run dev -- --port 5173 &
sleep 3
curl -s http://localhost:5173 | grep -q 'data-cell="center"' && echo OK || echo FAIL
kill %1
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/src/style.css web/src/styles
git commit -m "feat(web): HUD grid shell and panel chrome CSS"
```

---

## Task 8: Component base class

**Files:**
- Create: `web/src/ui/Component.ts`
- Create: `web/test/component.test.ts`

- [ ] **Step 1: Write failing tests**

Create `web/test/component.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import { Component } from "@/ui/Component";

class Demo extends Component<{ value: number }> {
  rendered: number[] = [];
  override render(state: { value: number }): void {
    this.rendered.push(state.value);
    this.root.textContent = String(state.value);
  }
}

describe("Component", () => {
  it("attaches to a DOM root and renders on mount", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const c = new Demo("#x");
    c.mount({ value: 1 });
    expect(c.rendered).toEqual([1]);
    expect(document.getElementById("x")?.textContent).toBe("1");
  });

  it("destroy clears subscriptions and root", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const c = new Demo("#x");
    c.mount({ value: 1 });
    const off = vi.fn();
    c.track(off);
    c.destroy();
    expect(off).toHaveBeenCalledOnce();
    expect(document.getElementById("x")?.children.length).toBe(0);
    expect(document.getElementById("x")?.textContent).toBe("");
  });

  it("throws if root selector missing", () => {
    document.body.innerHTML = ``;
    expect(() => new Demo("#missing")).toThrow(/missing/i);
  });
});
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd web && npm run test
```

Expected: FAIL — `@/ui/Component` not found.

- [ ] **Step 3: Implement**

Create `web/src/ui/Component.ts`:

```ts
export abstract class Component<S = unknown> {
  protected root: HTMLElement;
  private unsubs: Array<() => void> = [];

  constructor(rootSelector: string) {
    const el = document.querySelector<HTMLElement>(rootSelector);
    if (!el) throw new Error(`Component root missing: ${rootSelector}`);
    this.root = el;
  }

  mount(state: S): void { this.render(state); }

  abstract render(state: S): void;

  /** Track a teardown function (e.g. store subscription) so destroy() releases it. */
  track(unsub: () => void): void { this.unsubs.push(unsub); }

  destroy(): void {
    this.unsubs.splice(0).forEach((u) => u());
    this.root.replaceChildren();
    this.root.textContent = "";
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 19/19 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/ui/Component.ts web/test/component.test.ts
git commit -m "feat(web): Component base class"
```

---

## Task 9: Header + reusable Panel renderer

**Files:**
- Create: `web/src/ui/Header.ts`
- Create: `web/src/ui/Panel.ts`

- [ ] **Step 1: Create `web/src/ui/Panel.ts`**

```ts
/** Render the standard panel chrome (title + body) into a host element. */
export function renderPanel(host: HTMLElement, title: string, body: string): void {
  host.classList.add("panel");
  host.setAttribute("role", "region");
  host.setAttribute("aria-label", title);
  host.innerHTML = `<h4>${title}</h4>${body}`;
}
```

- [ ] **Step 2: Create `web/src/ui/Header.ts`**

```ts
import { Component } from "./Component";

interface HeaderState { uptimeMs: number; }

const pad2 = (n: number) => String(n).padStart(2, "0");

export class Header extends Component<HeaderState> {
  override render(state: HeaderState): void {
    const d = new Date();
    const clock = `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
    const u = Math.floor(state.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    this.root.classList.add("panel", "header");
    this.root.innerHTML = `
      <span class="id">JARVIS // OS · v0.1</span>
      <span class="uptime">${uptime}</span>
      <span class="clock">${clock}</span>
    `;
  }
}
```

- [ ] **Step 3: Add header CSS**

Append to `web/src/styles/panel.css`:

```css
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
}
.header .id { letter-spacing: 0.35em; font-size: 11px; color: var(--accent); }
.header .uptime, .header .clock { font-variant-numeric: tabular-nums; }
.header .uptime { color: var(--fg-dim); }
```

- [ ] **Step 4: Wire Header into `web/src/main.ts` (temporary smoke wiring)**

Replace `web/src/main.ts`:

```ts
import "./style.css";
import { Header } from "@/ui/Header";

const start = Date.now();
const header = new Header('[data-cell="top"]');

function tick(): void {
  header.render({ uptimeMs: Date.now() - start });
  requestAnimationFrame(tick);
}
tick();
document.body.dataset.ready = "true";
```

- [ ] **Step 5: Visual check via dev server**

```bash
cd web && npm run dev -- --port 5173 &
sleep 3
curl -s http://localhost:5173/src/main.ts | grep -q "Header" && echo OK || echo FAIL
kill %1
```

Expected: `OK`. (Visual confirmation: open browser; header shows JARVIS ID + uptime + clock.)

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/Header.ts web/src/ui/Panel.ts web/src/styles/panel.css web/src/main.ts
git commit -m "feat(web): Header component with clock and uptime"
```

---

## Task 10: Static info panels (System, Memory, Calendar, Network, Tasks)

**Files:**
- Create: `web/src/ui/panels/SystemPanel.ts`
- Create: `web/src/ui/panels/MemoryPanel.ts`
- Create: `web/src/ui/panels/CalendarPanel.ts`
- Create: `web/src/ui/panels/NetworkPanel.ts`
- Create: `web/src/ui/panels/TasksPanel.ts`
- Create: `web/src/data/calendar.ts`

- [ ] **Step 1: Create static calendar data**

Create `web/src/data/calendar.ts`:

```ts
export interface CalendarEntry { time: string; title: string; }

export const TODAY: CalendarEntry[] = [
  { time: "09:30", title: "Standup" },
  { time: "11:00", title: "Interview · A. Roy" },
  { time: "14:00", title: "Playtest review" },
  { time: "17:30", title: "Maud · dinner" },
];
```

- [ ] **Step 2: Create `web/src/ui/panels/SystemPanel.ts`**

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface SystemState {
  uptimeMs: number;
  load: number;
  tokensPerMin: number;
  sessionId: string;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

export class SystemPanel extends Component<SystemState> {
  override render(s: SystemState): void {
    const u = Math.floor(s.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    renderPanel(this.root, "System", `
      <div class="row"><span>uptime</span><b>${uptime}</b></div>
      <div class="row"><span>load</span><b>${s.load.toFixed(2)}</b></div>
      <div class="row"><span>tokens / min</span><b>${s.tokensPerMin.toLocaleString()}</b></div>
      <div class="row"><span>session</span><b>#${s.sessionId}</b></div>
    `);
  }
}
```

- [ ] **Step 3: Create `web/src/ui/panels/MemoryPanel.ts`**

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface MemoryState {
  contextUsed: number;
  contextMax: number;
  recallPct: number;
}

export class MemoryPanel extends Component<MemoryState> {
  override render(s: MemoryState): void {
    const ctxPct = Math.min(100, (s.contextUsed / s.contextMax) * 100);
    const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n);
    renderPanel(this.root, "Memory", `
      <div class="row"><span>context</span><b>${fmt(s.contextUsed)} / ${fmt(s.contextMax)}</b></div>
      <div class="bar"><i style="width:${ctxPct.toFixed(0)}%"></i></div>
      <div class="row"><span>recall</span><b>${s.recallPct.toFixed(1)}%</b></div>
      <div class="bar"><i style="width:${s.recallPct.toFixed(0)}%"></i></div>
    `);
  }
}
```

- [ ] **Step 4: Create `web/src/ui/panels/CalendarPanel.ts`**

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { CalendarEntry } from "@/data/calendar";

export interface CalendarState { entries: CalendarEntry[]; }

export class CalendarPanel extends Component<CalendarState> {
  override render(s: CalendarState): void {
    const rows = s.entries
      .map((e) => `<div class="row"><span>${e.time}</span><b>${e.title}</b></div>`)
      .join("");
    renderPanel(this.root, "Calendar", rows);
  }
}
```

- [ ] **Step 5: Create `web/src/ui/panels/NetworkPanel.ts`**

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface NetworkState {
  endpoint: string;
  latencyMs: number;
  packets: number;
  busyPct: number;
}

export class NetworkPanel extends Component<NetworkState> {
  override render(s: NetworkState): void {
    renderPanel(this.root, "Network", `
      <div class="row"><span>endpoint</span><b>${s.endpoint}</b></div>
      <div class="row"><span>latency</span><b>${s.latencyMs} ms</b></div>
      <div class="row"><span>packets</span><b>${s.packets.toLocaleString()}</b></div>
      <div class="bar"><i style="width:${Math.min(100, s.busyPct).toFixed(0)}%"></i></div>
    `);
  }
}
```

- [ ] **Step 6: Create `web/src/ui/panels/TasksPanel.ts`**

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface TasksState { queued: number; active: number; done: number; }

export class TasksPanel extends Component<TasksState> {
  override render(s: TasksState): void {
    renderPanel(this.root, "Tasks", `
      <div class="row"><span>queued</span><b>${s.queued}</b></div>
      <div class="row"><span>active</span><b>${s.active}</b></div>
      <div class="row"><span>done</span><b>${s.done}</b></div>
    `);
  }
}
```

- [ ] **Step 7: Wire panels into main.ts**

Replace `web/src/main.ts`:

```ts
import "./style.css";
import { Header } from "@/ui/Header";
import { SystemPanel } from "@/ui/panels/SystemPanel";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";
import { TasksPanel } from "@/ui/panels/TasksPanel";
import { TODAY } from "@/data/calendar";

const start = Date.now();

const header = new Header('[data-cell="top"]');
const system = new SystemPanel('[data-cell="tl"]');
const memory = new MemoryPanel('[data-cell="tr"]');
const calendar = new CalendarPanel('[data-cell="bl"]');
const network = new NetworkPanel('[data-cell="br"]');
// Tasks panel goes inside the left cell (audio comes later in same cell)
document.querySelector('[data-cell="left"]')!.innerHTML =
  `<div class="panel-stack">
    <div data-slot="audio"></div>
    <div data-slot="tasks"></div>
  </div>`;
const tasks = new TasksPanel('[data-slot="tasks"]');

function tick(): void {
  const u = Date.now() - start;
  header.render({ uptimeMs: u });
  system.render({ uptimeMs: u, load: 0.42, tokensPerMin: 1284, sessionId: "A271" });
  memory.render({ contextUsed: 62000, contextMax: 200000, recallPct: 98.2 });
  calendar.render({ entries: TODAY });
  network.render({ endpoint: "local", latencyMs: 12, packets: 0, busyPct: 18 });
  tasks.render({ queued: 3, active: 1, done: 14 });
  requestAnimationFrame(tick);
}
tick();
document.body.dataset.ready = "true";
```

- [ ] **Step 8: Add panel-stack CSS**

Append to `web/src/styles/panel.css`:

```css
.panel-stack {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 14px;
  height: 100%;
}
.panel-stack > div { min-height: 0; }
```

- [ ] **Step 9: Lint, build, test**

```bash
cd web && npm run lint && npm run test && npm run build
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add web/src
git commit -m "feat(web): static info panels (system, memory, calendar, network, tasks)"
```

---

## Task 11: TelemetryPanel with scrolling feed

**Files:**
- Create: `web/src/ui/panels/TelemetryPanel.ts`

- [ ] **Step 1: Implement TelemetryPanel**

Create `web/src/ui/panels/TelemetryPanel.ts`:

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { TelemetryEvent } from "@/types";

export interface TelemetryState { events: TelemetryEvent[]; }

const SYMBOL: Record<TelemetryEvent["level"], string> = {
  info: "·",
  ok: "+",
  warn: "!",
  error: "x",
};

const tsStr = (ms: number): string => {
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}`;
};

const escape = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export class TelemetryPanel extends Component<TelemetryState> {
  override render(s: TelemetryState): void {
    const lines = s.events
      .slice(0, 14)
      .map((e) => `<div class="line ${e.level}">${tsStr(e.ts)}  ${SYMBOL[e.level]} ${escape(e.message)}</div>`)
      .join("");
    renderPanel(this.root, "Telemetry", `<div class="feed">${lines}</div>`);
  }
}
```

- [ ] **Step 2: Add telemetry CSS**

Append to `web/src/styles/panel.css`:

```css
.feed { font-size: 10.5px; line-height: 1.7; color: var(--fg-dim); height: 100%; overflow: hidden; }
.feed .line { white-space: nowrap; }
.feed .line.ok { color: var(--accent); }
.feed .line.warn { color: var(--warn); }
.feed .line.error { color: #ff6c6c; }
```

- [ ] **Step 3: Wire into main.ts**

Add to `web/src/main.ts` imports:

```ts
import { TelemetryPanel } from "@/ui/panels/TelemetryPanel";
import type { TelemetryEvent } from "@/types";
```

Inside the wiring section (after `tasks`):

```ts
const telemetry = new TelemetryPanel('[data-cell="right"]');

const seedEvents: TelemetryEvent[] = [
  { ts: Date.now() - 5000, level: "ok",   message: "whisper.asr ready" },
  { ts: Date.now() - 4500, level: "ok",   message: "tts.openvoice loaded" },
  { ts: Date.now() - 4000, level: "ok",   message: "llm.local connected · 7B" },
  { ts: Date.now() - 3000, level: "info", message: "kb.index synced · 24,182 docs" },
  { ts: Date.now() - 2000, level: "warn", message: "gpu.temp 71°C" },
  { ts: Date.now() - 1000, level: "ok",   message: "context.bridge open" },
];
```

Inside `tick()`:

```ts
telemetry.render({ events: seedEvents });
```

- [ ] **Step 4: Build + dev verify**

```bash
cd web && npm run build
npm run dev -- --port 5173 &
sleep 3
curl -s http://localhost:5173 | grep -q 'data-cell="right"' && echo OK || echo FAIL
kill %1
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): TelemetryPanel scrolling feed"
```

---

## Task 12: Mic capture + amplitude analyzer

**Files:**
- Create: `web/src/audio/micCapture.ts`
- Create: `web/src/audio/analyzer.ts`
- Create: `web/test/analyzer.test.ts`

Note: AudioWorklet/getUserMedia behavior cannot be unit-tested in jsdom; we test the analyzer (pure math) only. Mic capture is covered manually in Task 22.

- [ ] **Step 1: Write failing test for analyzer**

Create `web/test/analyzer.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { rms } from "@/audio/analyzer";

describe("analyzer.rms", () => {
  it("returns 0 for silence", () => {
    expect(rms(new Float32Array(128))).toBe(0);
  });

  it("returns ~1 for a max-amplitude DC signal", () => {
    const a = new Float32Array(128).fill(1);
    expect(rms(a)).toBeCloseTo(1, 3);
  });

  it("returns ~0.707 for a sine wave at unit amplitude", () => {
    const a = new Float32Array(1024);
    for (let i = 0; i < a.length; i++) a[i] = Math.sin((i / a.length) * 2 * Math.PI * 4);
    expect(rms(a)).toBeCloseTo(Math.SQRT1_2, 2);
  });
});
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd web && npm run test
```

Expected: FAIL — `@/audio/analyzer` not found.

- [ ] **Step 3: Implement analyzer**

Create `web/src/audio/analyzer.ts`:

```ts
/** Root-mean-square amplitude of a buffer of mono float samples in [-1, 1]. */
export function rms(buf: Float32Array): number {
  if (buf.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i]! * buf[i]!;
  return Math.sqrt(sum / buf.length);
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 22/22 PASS.

- [ ] **Step 5: Implement micCapture**

Create `web/src/audio/micCapture.ts`:

```ts
import { rms } from "./analyzer";

export interface MicCapture {
  start(): Promise<void>;
  stop(): void;
  /** Subscribe to amplitude (0..1) updates ~60Hz. Returns unsubscribe. */
  onAmplitude(cb: (level: number) => void): () => void;
}

export type MicError =
  | { kind: "denied" }
  | { kind: "unsupported" }
  | { kind: "device" }
  | { kind: "unknown"; cause: unknown };

export async function probeMicSupport(): Promise<true | MicError> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    return { kind: "unsupported" };
  }
  return true;
}

export function createMicCapture(): MicCapture {
  let stream: MediaStream | undefined;
  let ctx: AudioContext | undefined;
  let raf = 0;
  const subs = new Set<(level: number) => void>();

  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      const tick = () => {
        analyser.getFloatTimeDomainData(buf);
        const level = Math.min(1, rms(buf) * 4); // perceptual scaling
        subs.forEach((s) => s(level));
        raf = requestAnimationFrame(tick);
      };
      tick();
    },
    stop() {
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      stream = undefined;
      void ctx?.close();
      ctx = undefined;
      subs.clear();
    },
    onAmplitude(cb) {
      subs.add(cb);
      return () => { subs.delete(cb); };
    },
  };
}
```

- [ ] **Step 6: Lint + build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/audio web/test/analyzer.test.ts
git commit -m "feat(web): mic capture + RMS amplitude analyzer"
```

---

## Task 13: AudioPanel with mic permission UX

**Files:**
- Create: `web/src/ui/panels/AudioPanel.ts`

- [ ] **Step 1: Implement AudioPanel**

Create `web/src/ui/panels/AudioPanel.ts`:

```ts
import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export type MicStatus =
  | { kind: "unprompted" }
  | { kind: "granted" }
  | { kind: "denied" }
  | { kind: "unsupported" }
  | { kind: "error"; message: string };

export interface AudioState {
  inputDb: number;
  outputDb: number;
  inputBarPct: number;
  mic: MicStatus;
}

const banner = (mic: MicStatus): string => {
  switch (mic.kind) {
    case "unprompted":
      return `<div class="mic-banner"><span>Mic not yet enabled.</span> <button data-action="mic-request">Enable</button></div>`;
    case "granted":
      return ``;
    case "denied":
      return `<div class="mic-banner warn"><span>Mic permission denied.</span> <button data-action="mic-request">Retry</button></div>`;
    case "unsupported":
      return `<div class="mic-banner warn"><span>Voice mode unavailable in this browser.</span></div>`;
    case "error":
      return `<div class="mic-banner warn"><span>${mic.message}</span> <button data-action="mic-request">Retry</button></div>`;
  }
};

export class AudioPanel extends Component<AudioState> {
  override render(s: AudioState): void {
    renderPanel(this.root, "Audio", `
      <div class="row"><span>input</span><b>${s.inputDb.toFixed(0)} dB</b></div>
      <div class="row"><span>output</span><b>${s.outputDb.toFixed(0)} dB</b></div>
      <div class="bar"><i style="width:${Math.min(100, s.inputBarPct).toFixed(0)}%"></i></div>
      ${banner(s.mic)}
    `);
  }
}
```

- [ ] **Step 2: CSS for mic banner**

Append to `web/src/styles/panel.css`:

```css
.mic-banner {
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid var(--accent-dim);
  background: var(--accent-faint);
  font-size: 10.5px;
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}
.mic-banner.warn { border-color: rgba(255, 174, 92, 0.4); background: rgba(255, 174, 92, 0.08); color: var(--warn); }
.mic-banner button {
  appearance: none;
  background: rgba(92, 240, 255, 0.08);
  color: var(--fg);
  border: 1px solid var(--accent-dim);
  padding: 4px 10px;
  font: inherit;
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  cursor: pointer;
}
.mic-banner button:hover { background: rgba(92, 240, 255, 0.18); border-color: var(--accent); }
```

- [ ] **Step 3: Wire AudioPanel into main.ts**

Add to imports:

```ts
import { AudioPanel, type MicStatus } from "@/ui/panels/AudioPanel";
```

After other panel constructions:

```ts
const audio = new AudioPanel('[data-slot="audio"]');
let micStatus: MicStatus = { kind: "unprompted" };
```

Inside `tick()`:

```ts
audio.render({ inputDb: -72, outputDb: -31, inputBarPct: 30, mic: micStatus });
```

- [ ] **Step 4: Lint + build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): AudioPanel with mic permission UX"
```

---

## Task 14: Waveform canvas

**Files:**
- Create: `web/src/ui/Waveform.ts`

This is a render-on-demand component, not store-driven — its `render` method is called every frame with current amplitude.

- [ ] **Step 1: Create Waveform component**

Create `web/src/ui/Waveform.ts`:

```ts
import { Component } from "./Component";

export interface WaveformInput {
  amplitude: number;   // 0..1, smoothed externally
  modeHint: "idle" | "listening" | "thinking" | "speaking";
}

interface Particle { x: number; y: number; vx: number; vy: number; r: number; }

export class Waveform extends Component<WaveformInput> {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private dpr = Math.min(window.devicePixelRatio || 1, 2);
  private W = 0; private H = 0;
  private t = 0;
  private particles: Particle[] = [];
  private resizeObs: ResizeObserver | undefined;

  constructor(rootSelector: string) {
    super(rootSelector);
    this.canvas = document.createElement("canvas");
    this.canvas.classList.add("waveform-canvas");
    this.root.appendChild(this.canvas);
    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;
    this.particles = Array.from({ length: 80 }, () => ({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0004,
      vy: (Math.random() - 0.5) * 0.0004,
      r: Math.random() * 1.4 + 0.3,
    }));
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(this.root);
    this.resize();
  }

  private resize(): void {
    const rect = this.root.getBoundingClientRect();
    this.W = Math.max(1, Math.floor(rect.width  * this.dpr));
    this.H = Math.max(1, Math.floor(rect.height * this.dpr));
    this.canvas.width = this.W;
    this.canvas.height = this.H;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
  }

  override render(input: WaveformInput): void {
    this.t += 1;
    const ctx = this.ctx;
    const { W, H, dpr } = this;
    const amp = input.amplitude;

    ctx.fillStyle = "rgba(2,4,10,0.18)";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "rgba(125,249,255,0.45)";
    for (const p of this.particles) {
      p.x += p.vx + amp * 0.0002; p.y += p.vy;
      if (p.x < 0) p.x += 1; if (p.x > 1) p.x -= 1;
      if (p.y < 0) p.y += 1; if (p.y > 1) p.y -= 1;
      ctx.beginPath();
      ctx.arc(p.x * W, p.y * H, p.r * dpr, 0, Math.PI * 2);
      ctx.fill();
    }

    const cy = H * 0.5;
    const layers = [
      { hue: "rgba(125,249,255,", a: 0.85, mul: 1.0, freq: 0.012, speed: 0.05 },
      { hue: "rgba(125,249,255,", a: 0.45, mul: 0.7, freq: 0.008, speed: 0.03 },
      { hue: "rgba(168,200,255,", a: 0.30, mul: 1.4, freq: 0.020, speed: 0.07 },
    ];
    ctx.lineWidth = 2 * dpr;
    for (const L of layers) {
      ctx.beginPath();
      ctx.strokeStyle = `${L.hue}${L.a})`;
      ctx.shadowBlur = 24 * dpr;
      ctx.shadowColor = `${L.hue}0.6)`;
      for (let x = 0; x <= W; x += 4 * dpr) {
        const env = Math.sin(x * 0.001 + this.t * 0.003) * 0.5 + 0.5;
        const y = cy
          + Math.sin(x * L.freq + this.t * L.speed)         * H * 0.18 * amp * L.mul * env
          + Math.sin(x * L.freq * 2.2 + this.t * L.speed * 1.3) * H * 0.06 * amp * L.mul;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }

  override destroy(): void {
    this.resizeObs?.disconnect();
    super.destroy();
  }
}
```

- [ ] **Step 2: Add canvas CSS**

Append to `web/src/styles/panel.css`:

```css
.waveform-canvas {
  position: absolute;
  inset: 0;
  display: block;
}
```

- [ ] **Step 3: Lint + build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/ui/Waveform.ts web/src/styles/panel.css
git commit -m "feat(web): waveform canvas component"
```

---

## Task 15: Transcript renderer with streaming TDD

**Files:**
- Create: `web/src/ui/Transcript.ts`
- Create: `web/test/transcript.test.ts`

- [ ] **Step 1: Failing test**

Create `web/test/transcript.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Transcript } from "@/ui/Transcript";

describe("Transcript", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="t"></div>`;
    vi.useFakeTimers();
  });

  it("appends tokens incrementally", () => {
    const t = new Transcript("#t");
    t.mount({ text: "" });
    t.appendToken("Hello");
    t.appendToken(" world");
    expect(document.getElementById("t")?.textContent).toContain("Hello world");
  });

  it("setLine replaces and starts streaming via stream()", () => {
    const t = new Transcript("#t");
    t.mount({ text: "" });
    t.stream("Hi there", 10);
    vi.advanceTimersByTime(10 * 8 + 5);
    expect(document.getElementById("t")?.textContent).toContain("Hi there");
  });

  it("interrupt() stops in-flight streaming", () => {
    const t = new Transcript("#t");
    t.mount({ text: "" });
    t.stream("This will be interrupted", 50);
    vi.advanceTimersByTime(50);
    t.interrupt();
    const before = document.getElementById("t")?.textContent ?? "";
    vi.advanceTimersByTime(1000);
    expect(document.getElementById("t")?.textContent).toBe(before);
  });

  it("clear() empties the rendered text", () => {
    const t = new Transcript("#t");
    t.mount({ text: "anything" });
    t.clear();
    expect(document.getElementById("t")?.textContent?.trim()).toBe("");
  });
});
```

- [ ] **Step 2: Run, verify fail**

```bash
cd web && npm run test
```

Expected: FAIL.

- [ ] **Step 3: Implement Transcript**

Create `web/src/ui/Transcript.ts`:

```ts
import { Component } from "./Component";

interface TranscriptState { text: string; }

export class Transcript extends Component<TranscriptState> {
  private body!: HTMLElement;
  private caret!: HTMLElement;
  private streamTimer: ReturnType<typeof setTimeout> | undefined;

  override render(state: TranscriptState): void {
    if (!this.body) {
      this.root.classList.add("transcript");
      this.root.innerHTML = `<span class="body"></span><span class="caret"></span>`;
      this.body = this.root.querySelector(".body")!;
      this.caret = this.root.querySelector(".caret")!;
    }
    this.body.textContent = state.text;
  }

  appendToken(token: string): void {
    this.body.textContent = (this.body.textContent ?? "") + token;
  }

  stream(text: string, msPerChar: number): void {
    this.interrupt();
    this.body.textContent = "";
    let i = 0;
    const step = (): void => {
      if (i > text.length) return;
      this.body.textContent = text.slice(0, i++);
      this.streamTimer = setTimeout(step, msPerChar);
    };
    step();
  }

  interrupt(): void {
    if (this.streamTimer !== undefined) {
      clearTimeout(this.streamTimer);
      this.streamTimer = undefined;
    }
  }

  clear(): void {
    this.interrupt();
    this.body.textContent = "";
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd web && npm run test
```

Expected: 26/26 PASS.

- [ ] **Step 5: Add transcript CSS**

Append to `web/src/styles/panel.css`:

```css
.transcript {
  position: relative;
  z-index: 2;
  text-align: center;
  font-family: -apple-system, "SF Pro Text", "Inter", system-ui, sans-serif;
  font-size: clamp(15px, 1.6vw, 19px);
  line-height: 1.55;
  color: var(--fg);
  max-width: 720px;
  padding: 0 24px;
}
.transcript .caret {
  display: inline-block;
  width: 0.55ch; height: 1em;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: -0.12em;
  box-shadow: 0 0 8px var(--accent);
  animation: tcaret 1s steps(1) infinite;
}
@keyframes tcaret { 50% { opacity: 0; } }
```

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/Transcript.ts web/test/transcript.test.ts web/src/styles/panel.css
git commit -m "feat(web): streaming Transcript renderer with interrupt"
```

---

## Task 16: Centerpiece (waveform + transcript composition)

**Files:**
- Create: `web/src/ui/Centerpiece.ts`

- [ ] **Step 1: Implement Centerpiece**

Create `web/src/ui/Centerpiece.ts`:

```ts
import { Waveform } from "./Waveform";
import { Transcript } from "./Transcript";
import type { ConvState } from "@/types";

export class Centerpiece {
  private root: HTMLElement;
  private waveform: Waveform;
  private transcript: Transcript;
  private title: HTMLElement;
  private scan: HTMLElement;

  constructor(rootSelector: string) {
    const el = document.querySelector<HTMLElement>(rootSelector);
    if (!el) throw new Error(`Centerpiece root missing: ${rootSelector}`);
    this.root = el;
    this.root.classList.add("panel", "centerpiece");
    this.root.innerHTML = `
      <div class="scan"></div>
      <div data-slot="waveform" class="waveform-host"></div>
      <div class="centerpiece-content">
        <h2 class="centerpiece-title">Standing by.</h2>
        <div data-slot="transcript"></div>
      </div>
    `;
    this.waveform = new Waveform('[data-slot="waveform"]');
    this.transcript = new Transcript('[data-slot="transcript"]');
    this.transcript.mount({ text: "" });
    this.title = this.root.querySelector(".centerpiece-title")!;
    this.scan = this.root.querySelector(".scan")!;
  }

  setTitle(text: string): void { this.title.textContent = text; }
  streamReply(text: string, ms = 26): void { this.transcript.stream(text, ms); }
  appendToken(t: string): void { this.transcript.appendToken(t); }
  clearTranscript(): void { this.transcript.clear(); }
  interruptTranscript(): void { this.transcript.interrupt(); }

  setStateClass(state: ConvState): void {
    this.root.dataset.state = state;
    this.scan.dataset.state = state;
  }

  renderFrame(amplitude: number, modeHint: ConvState): void {
    this.waveform.render({ amplitude, modeHint });
  }
}
```

- [ ] **Step 2: CSS for centerpiece**

Append to `web/src/styles/panel.css`:

```css
.centerpiece {
  position: relative;
  overflow: hidden;
  padding: 0;
  display: grid;
  place-items: center;
}
.centerpiece .waveform-host {
  position: absolute;
  inset: 0;
}
.centerpiece-content {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 32px;
  max-width: 760px;
}
.centerpiece-title {
  font-family: -apple-system, "SF Pro Display", "Inter", system-ui, sans-serif;
  font-weight: 200;
  font-size: clamp(28px, 4.5vw, 56px);
  margin: 0 0 14px;
  letter-spacing: -0.02em;
  color: var(--fg);
}
.centerpiece .scan {
  position: absolute;
  left: 0; right: 0;
  height: 60px;
  pointer-events: none;
  background: linear-gradient(180deg, transparent, rgba(92,240,255,0.08), transparent);
  animation: scan 6s linear infinite;
  z-index: 1;
}
@keyframes scan { 0% { top: -60px; } 100% { top: 100%; } }
```

- [ ] **Step 3: Wire Centerpiece into main.ts**

Add to imports:

```ts
import { Centerpiece } from "@/ui/Centerpiece";
```

After other constructions:

```ts
const center = new Centerpiece('[data-cell="center"]');
let amplitude = 0.08;
```

Inside `tick()`:

```ts
center.renderFrame(amplitude, "idle");
```

- [ ] **Step 4: Lint + build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): Centerpiece composition (waveform + transcript)"
```

---

## Task 17: Controls + keyboard handlers

**Files:**
- Create: `web/src/ui/Controls.ts`
- Create: `web/src/ui/keyboard.ts`

- [ ] **Step 1: Implement Controls**

Create `web/src/ui/Controls.ts`:

```ts
import { Component } from "./Component";
import type { ConvState } from "@/types";

export interface ControlsState { state: ConvState; }

export interface ControlsActions {
  onMicDown(): void;
  onMicUp(): void;
  onInterrupt(): void;
  onRunScenario(): void;
  onIdle(): void;
}

const STATUS_LABEL: Record<ConvState, string> = {
  idle: "— idle —",
  listening: "— listening —",
  thinking: "— thinking —",
  speaking: "— speaking —",
};

export class Controls extends Component<ControlsState> {
  constructor(rootSelector: string, private actions: ControlsActions, devMode: boolean) {
    super(rootSelector);
    this.root.classList.add("panel", "controls");
    this.root.innerHTML = `
      <button data-action="mic" aria-label="Push to talk">▶ Speak</button>
      <button data-action="interrupt">◉ Interrupt</button>
      <button data-action="idle">○ Idle</button>
      ${devMode ? `<button data-action="run-scenario">Run scenario</button>` : ``}
      <span class="status" data-status>—</span>
    `;
    const mic = this.root.querySelector<HTMLButtonElement>('[data-action="mic"]')!;
    mic.addEventListener("mousedown", () => this.actions.onMicDown());
    mic.addEventListener("mouseup",   () => this.actions.onMicUp());
    mic.addEventListener("mouseleave", () => this.actions.onMicUp());
    mic.addEventListener("touchstart", (e) => { e.preventDefault(); this.actions.onMicDown(); }, { passive: false });
    mic.addEventListener("touchend",   () => this.actions.onMicUp());

    this.root.querySelector('[data-action="interrupt"]')!
      .addEventListener("click", () => this.actions.onInterrupt());
    this.root.querySelector('[data-action="idle"]')!
      .addEventListener("click", () => this.actions.onIdle());
    this.root.querySelector('[data-action="run-scenario"]')
      ?.addEventListener("click", () => this.actions.onRunScenario());
  }

  override render(s: ControlsState): void {
    const status = this.root.querySelector<HTMLElement>("[data-status]")!;
    status.textContent = STATUS_LABEL[s.state];
    this.root.dataset.state = s.state;
  }
}
```

- [ ] **Step 2: Implement keyboard handler**

Create `web/src/ui/keyboard.ts`:

```ts
export interface KeyboardActions {
  onMicDown(): void;
  onMicUp(): void;
  onInterrupt(): void;
}

export function attachKeyboard(target: Window, a: KeyboardActions): () => void {
  let micDown = false;

  const onKeyDown = (e: KeyboardEvent): void => {
    if (e.repeat) return;
    if (e.code === "Space" && !micDown && !isInputTarget(e.target)) {
      e.preventDefault();
      micDown = true;
      a.onMicDown();
    } else if (e.key === "Escape") {
      e.preventDefault();
      a.onInterrupt();
    }
  };

  const onKeyUp = (e: KeyboardEvent): void => {
    if (e.code === "Space" && micDown) {
      e.preventDefault();
      micDown = false;
      a.onMicUp();
    }
  };

  target.addEventListener("keydown", onKeyDown);
  target.addEventListener("keyup", onKeyUp);
  return (): void => {
    target.removeEventListener("keydown", onKeyDown);
    target.removeEventListener("keyup", onKeyUp);
  };
}

function isInputTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  return t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable;
}
```

- [ ] **Step 3: Add controls CSS**

Append to `web/src/styles/panel.css`:

```css
.controls {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
}
.controls button {
  appearance: none;
  background: rgba(92, 240, 255, 0.05);
  color: var(--fg);
  border: 1px solid var(--accent-dim);
  border-radius: 0;
  padding: 8px 18px;
  font: inherit;
  font-size: 11px;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  cursor: pointer;
}
.controls button:hover { background: rgba(92, 240, 255, 0.15); border-color: var(--accent); }
.controls button:active { transform: scale(0.97); }
.controls .status { margin-left: auto; color: var(--accent); letter-spacing: 0.3em; }
```

- [ ] **Step 4: Lint + build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/ui/Controls.ts web/src/ui/keyboard.ts web/src/styles/panel.css
git commit -m "feat(web): Controls component + keyboard shortcuts"
```

---

## Task 18: Mock event source full implementation + scenarios

**Files:**
- Create: `web/src/events/scenarios.ts`
- Modify: `web/src/events/mockEventSource.ts`
- Modify: `web/test/mockEventSource.test.ts`

- [ ] **Step 1: Define scenarios**

Create `web/src/events/scenarios.ts`:

```ts
export interface Scenario {
  user: string;
  reply: string;     // assistant reply, sentences end with `.` `?` or `!`
}

export const SCENARIOS: Scenario[] = [
  {
    user: "Brief me on today.",
    reply: "Two interviews on your calendar. The playtesting deck is ready for review. Three slides flagged for your attention. Otherwise, your morning is clear.",
  },
  {
    user: "Summarize yesterday's research notes.",
    reply: "Eight key insights synthesized. The strongest pattern: testers consistently abandon at the second tutorial gate. I drafted a one-paragraph summary in your inbox.",
  },
  {
    user: "What's the status of the playtest review?",
    reply: "Slides ready. Three need your review before sending. The remaining content is approved by Harsh.",
  },
  {
    user: "Cancel my eleven o'clock.",
    reply: "Done. Apologies sent. Calendar slot reopened. Your morning is now fully clear.",
  },
  {
    user: "Anything urgent in my inbox?",
    reply: "One. The grant deadline moved up by a week. I drafted a response asking for clarification. Want me to send it?",
  },
];

export function pickScenario(): Scenario {
  return SCENARIOS[Math.floor(Math.random() * SCENARIOS.length)]!;
}

export function splitSentences(text: string): string[] {
  return text.match(/[^.!?]+[.!?]+\s*/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
}
```

- [ ] **Step 2: Extend tests**

Replace `web/test/mockEventSource.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MockEventSource } from "@/events/mockEventSource";

describe("MockEventSource skeleton", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("emits ready after start()", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    await m.start();
    expect(ready).toHaveBeenCalledOnce();
  });

  it("on(...) returns an unsubscribe", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    const off = m.on("ready", ready);
    off();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });

  it("stop() clears subscribers", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    m.stop();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });
});

describe("MockEventSource conversation flow", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("emits stt.partial during listening, stt.final after endListening, then llm + tts", async () => {
    const m = new MockEventSource({ scenarioOverride: { user: "hi", reply: "ok. yes." } });
    const partial = vi.fn();
    const final = vi.fn();
    const tokens = vi.fn();
    const sentences = vi.fn();
    const llmEnd = vi.fn();
    m.on("stt.partial", partial);
    m.on("stt.final", final);
    m.on("llm.token", tokens);
    m.on("tts.sentence", sentences);
    m.on("llm.end", llmEnd);

    await m.start();
    m.beginListening();
    await vi.advanceTimersByTimeAsync(2000);
    m.endListening();
    await vi.advanceTimersByTimeAsync(5000);

    expect(partial).toHaveBeenCalled();
    expect(final).toHaveBeenCalledWith({ text: "hi" });
    expect(tokens.mock.calls.length).toBeGreaterThan(0);
    expect(sentences).toHaveBeenCalledTimes(2); // "ok." and "yes."
    expect(llmEnd).toHaveBeenCalledOnce();
  });

  it("interrupt() stops in-flight emissions", async () => {
    const m = new MockEventSource({ scenarioOverride: { user: "x", reply: "one. two. three." } });
    const sentences = vi.fn();
    m.on("tts.sentence", sentences);

    await m.start();
    m.beginListening();
    await vi.advanceTimersByTimeAsync(500);
    m.endListening();
    await vi.advanceTimersByTimeAsync(800);
    m.interrupt();
    await vi.advanceTimersByTimeAsync(5000);

    expect(sentences.mock.calls.length).toBeLessThan(3);
  });
});
```

- [ ] **Step 3: Run, verify the new tests fail**

```bash
cd web && npm run test
```

Expected: FAIL on the new flow tests (skeleton tests still pass).

- [ ] **Step 4: Implement full mock**

Replace `web/src/events/mockEventSource.ts`:

```ts
import type { EventSource } from "./eventSource";
import type { EventName, EventMap, EventHandler, TtsAudioChunk } from "@/types";
import { pickScenario, splitSentences, type Scenario } from "./scenarios";

interface Options { scenarioOverride?: Scenario; }

interface PendingTimer { id: ReturnType<typeof setTimeout>; }

export class MockEventSource implements EventSource {
  private handlers: { [K in EventName]?: Set<EventHandler<K>> } = {};
  private started = false;
  private currentUser: string | undefined;
  private currentReply: string | undefined;
  private timers = new Set<PendingTimer>();
  private cancelled = false;

  constructor(private opts: Options = {}) {}

  async start(): Promise<void> {
    this.started = true;
    this.cancelled = false;
    await Promise.resolve();
    this.emit("ready", undefined);
  }

  stop(): void {
    this.started = false;
    this.cancelAll();
    this.handlers = {};
  }

  beginListening(): void {
    if (!this.started) return;
    this.cancelled = false;
    const scenario = this.opts.scenarioOverride ?? pickScenario();
    this.currentUser = scenario.user;
    this.currentReply = scenario.reply;
    const words = scenario.user.split(" ");
    let acc = "";
    words.forEach((w, i) => {
      this.schedule(80 + i * 100, () => {
        acc = acc ? `${acc} ${w}` : w;
        this.emit("stt.partial", { text: acc });
      });
    });
  }

  endListening(): void {
    if (!this.started || this.currentUser === undefined) return;
    const user = this.currentUser;
    this.schedule(150, () => this.emit("stt.final", { text: user }));
    this.schedule(900, () => this.streamReply());
  }

  sendText(text: string): void {
    if (!this.started) return;
    this.currentReply = pickScenario().reply;
    this.schedule(0, () => this.emit("stt.final", { text }));
    this.schedule(400, () => this.streamReply());
  }

  interrupt(): void {
    this.cancelled = true;
    this.cancelAll();
    this.emit("llm.end", undefined);
  }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    let set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) {
      set = new Set();
      this.handlers[event] = set as never;
    }
    set.add(handler);
    return () => { set?.delete(handler); };
  }

  private streamReply(): void {
    if (this.cancelled || this.currentReply === undefined) return;
    const reply = this.currentReply;
    let charIdx = 0;
    const stepMs = 33;
    const tokenStep = (): void => {
      if (this.cancelled) return;
      if (charIdx >= reply.length) {
        this.emit("llm.end", undefined);
        return;
      }
      const next = Math.min(charIdx + 3 + Math.floor(Math.random() * 4), reply.length);
      const delta = reply.slice(charIdx, next);
      charIdx = next;
      this.emit("llm.token", { delta });
      this.schedule(stepMs, tokenStep);
    };
    tokenStep();

    // Emit one tts.sentence per sentence with audio chunks paced over its duration.
    const sentences = splitSentences(reply);
    let cumulative = 0;
    for (const [i, sent] of sentences.entries()) {
      const audioId = `s${i}-${Math.random().toString(36).slice(2, 7)}`;
      cumulative += 200 + sent.length * 30;
      this.schedule(cumulative, () => {
        if (this.cancelled) return;
        this.emit("tts.sentence", { text: sent, audioId });
        const totalChunks = 6;
        for (let c = 0; c < totalChunks; c++) {
          this.schedule(c * 90, () => {
            if (this.cancelled) return;
            const samples = new Float32Array(2048);
            const payload: TtsAudioChunk = { audioId, samples };
            this.emit("tts.audioChunk", payload);
          });
        }
        this.schedule(totalChunks * 90 + 80, () => {
          if (this.cancelled) return;
          this.emit("tts.end", { audioId });
        });
      });
    }
  }

  private schedule(ms: number, fn: () => void): void {
    const timer: PendingTimer = { id: setTimeout(() => {
      this.timers.delete(timer);
      if (!this.cancelled) fn();
    }, ms) };
    this.timers.add(timer);
  }

  private cancelAll(): void {
    this.timers.forEach((t) => clearTimeout(t.id));
    this.timers.clear();
  }

  protected emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    if (!this.started && event !== "ready") return;
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    set?.forEach((h) => h(payload));
  }
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd web && npm run test
```

Expected: 30/30 PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/events web/test/mockEventSource.test.ts
git commit -m "feat(web): full mock event source with conversation scenarios"
```

---

## Task 19: main.ts wiring + boot sequence

**Files:**
- Replace: `web/src/main.ts`

This task replaces all earlier scaffold wiring with the real boot sequence: store → event source → mic → state machine → all panels.

- [ ] **Step 1: Replace `web/src/main.ts`**

```ts
import "./style.css";

import type { ConvState, TelemetryEvent } from "@/types";
import { transition, canTransition } from "@/state/stateMachine";
import { createStore } from "@/state/store";

import { Header } from "@/ui/Header";
import { SystemPanel } from "@/ui/panels/SystemPanel";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";
import { TasksPanel } from "@/ui/panels/TasksPanel";
import { TelemetryPanel } from "@/ui/panels/TelemetryPanel";
import { AudioPanel, type MicStatus } from "@/ui/panels/AudioPanel";
import { Centerpiece } from "@/ui/Centerpiece";
import { Controls } from "@/ui/Controls";
import { attachKeyboard } from "@/ui/keyboard";

import { TODAY } from "@/data/calendar";
import { MockEventSource } from "@/events/mockEventSource";
import { createMicCapture, probeMicSupport } from "@/audio/micCapture";

interface AppState {
  state: ConvState;
  micAmplitude: number;
  micStatus: MicStatus;
  telemetry: TelemetryEvent[];
  centerTitle: string;
}

const start = Date.now();
const params = new URLSearchParams(location.search);
const devMode = params.get("dev") === "1";

const store = createStore<AppState>({
  state: "idle",
  micAmplitude: 0.08,
  micStatus: { kind: "unprompted" },
  telemetry: [],
  centerTitle: "Standing by.",
});

const log = (level: TelemetryEvent["level"], message: string): void => {
  store.update((d) => ({ telemetry: [{ ts: Date.now(), level, message }, ...d.telemetry].slice(0, 14) }));
};

// EventSource (mock for spec-01)
const events = new MockEventSource();

// Components
const header = new Header('[data-cell="top"]');
const system = new SystemPanel('[data-cell="tl"]');
const memory = new MemoryPanel('[data-cell="tr"]');
const calendar = new CalendarPanel('[data-cell="bl"]');
const network = new NetworkPanel('[data-cell="br"]');
document.querySelector('[data-cell="left"]')!.innerHTML =
  `<div class="panel-stack"><div data-slot="audio"></div><div data-slot="tasks"></div></div>`;
const audioPanel = new AudioPanel('[data-slot="audio"]');
const tasks = new TasksPanel('[data-slot="tasks"]');
const telemetry = new TelemetryPanel('[data-cell="right"]');
const center = new Centerpiece('[data-cell="center"]');

// Mic capture
const mic = createMicCapture();
mic.onAmplitude((level) => store.update(() => ({ micAmplitude: level })));

async function ensureMic(): Promise<boolean> {
  const status = store.get().micStatus;
  if (status.kind === "granted") return true;
  const probe = await probeMicSupport();
  if (probe !== true) {
    store.update(() => ({ micStatus: probe }));
    log("warn", `mic: ${probe.kind}`);
    return false;
  }
  try {
    await mic.start();
    store.update(() => ({ micStatus: { kind: "granted" } }));
    log("ok", "mic: granted");
    return true;
  } catch (err) {
    const denied = err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError");
    store.update(() => ({ micStatus: denied ? { kind: "denied" } : { kind: "error", message: String(err) } }));
    log("warn", denied ? "mic: denied" : `mic: error ${String(err)}`);
    return false;
  }
}

function tryTransition(event: Parameters<typeof transition>[1]): void {
  const cur = store.get().state;
  if (!canTransition(cur, event)) return;
  const next = transition(cur, event);
  store.update(() => ({ state: next }));
  document.body.dataset.state = next;
  log("info", `state: ${cur} → ${next} (${event})`);
}

// Shared actions (Controls + keyboard both call into this)
const actions = {
  onMicDown: async (): Promise<void> => {
    if (store.get().state !== "idle") return;
    const ok = await ensureMic();
    if (ok) {
      events.beginListening();
      tryTransition("startListening");
      store.update(() => ({ centerTitle: "Listening." }));
    }
  },
  onMicUp: (): void => {
    if (store.get().state !== "listening") return;
    events.endListening();
    tryTransition("stopListening");
    store.update(() => ({ centerTitle: "Thinking." }));
  },
  onInterrupt: (): void => {
    events.interrupt();
    center.interruptTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onIdle: (): void => {
    events.interrupt();
    center.clearTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onRunScenario: (): void => {
    if (store.get().state !== "idle") return;
    events.beginListening();
    tryTransition("startListening");
    store.update(() => ({ centerTitle: "Listening." }));
    setTimeout(() => {
      events.endListening();
      tryTransition("stopListening");
      store.update(() => ({ centerTitle: "Thinking." }));
    }, 1500);
  },
};

const controls = new Controls('[data-cell="bottom"]', actions, devMode);

attachKeyboard(window, {
  onMicDown: () => { void actions.onMicDown(); },
  onMicUp:     actions.onMicUp,
  onInterrupt: actions.onInterrupt,
});

// Event source wiring
events.on("stt.partial", ({ text }) => {
  if (store.get().state === "listening") center.setTitle(text || "Listening.");
});
events.on("stt.final", ({ text }) => {
  log("info", `you: ${text}`);
});
events.on("llm.token", ({ delta }) => {
  if (store.get().state === "thinking") {
    tryTransition("replyStart");
    store.update(() => ({ centerTitle: "" }));
    center.clearTranscript();
  }
  center.appendToken(delta);
});
events.on("llm.end", () => {
  // Stay in `speaking` until tts.end of the last sentence; mock fires that shortly.
});
events.on("tts.end", () => {
  // Naive: any tts.end while speaking ends the session. Real impl tracks queue.
  if (store.get().state === "speaking") {
    setTimeout(() => {
      tryTransition("replyEnd");
      store.update(() => ({ centerTitle: "Standing by." }));
    }, 200);
  }
});
events.on("error", (e) => log("error", `${e.code}: ${e.message}`));
events.on("telemetry", (t) => store.update((d) => ({ telemetry: [t, ...d.telemetry].slice(0, 14) })));

// Boot
(async () => {
  await events.start();
  log("ok", "session ready");
  document.body.dataset.ready = "true";
})();

// Render loop
function tick(): void {
  const s = store.get();
  const u = Date.now() - start;

  header.render({ uptimeMs: u });
  system.render({ uptimeMs: u, load: 0.42, tokensPerMin: 1284, sessionId: "A271" });
  memory.render({ contextUsed: 62000, contextMax: 200000, recallPct: 98.2 });
  calendar.render({ entries: TODAY });
  network.render({ endpoint: "local", latencyMs: 12, packets: 0, busyPct: 18 });
  tasks.render({ queued: 3, active: 1, done: 14 });
  telemetry.render({ events: s.telemetry });

  // Audio meter
  const meter = s.state === "listening" ? s.micAmplitude * 100 : (s.state === "speaking" ? 60 + Math.random() * 30 : 5 + Math.random() * 5);
  audioPanel.render({
    inputDb: -80 + (s.state === "listening" ? s.micAmplitude * 60 : Math.random() * 4),
    outputDb: -60 + meter * 0.4,
    inputBarPct: meter,
    mic: s.micStatus,
  });

  controls.render({ state: s.state });
  center.setStateClass(s.state);
  if (s.centerTitle) center.setTitle(s.centerTitle);

  // Synthetic amplitude when not listening
  let amp: number;
  if (s.state === "listening") amp = s.micAmplitude;
  else if (s.state === "thinking") amp = 0.18 + Math.sin(u * 0.004) * 0.05;
  else if (s.state === "speaking") amp = 0.45 + Math.random() * 0.35;
  else amp = 0.08 + Math.sin(u * 0.001) * 0.02;
  center.renderFrame(amp, s.state);

  requestAnimationFrame(tick);
}
tick();

// Mic banner button delegation
document.body.addEventListener("click", (e) => {
  const t = e.target;
  if (t instanceof HTMLElement && t.dataset.action === "mic-request") {
    void ensureMic();
  }
});
```

- [ ] **Step 2: Lint, build**

```bash
cd web && npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 3: Boot dev server, full smoke (manual)**

```bash
cd web && npm run dev -- --port 5173
```

Open `http://localhost:5173?dev=1` in Chromium. Verify:
- All 9 cells render with content.
- Click `Run scenario` → state cycles through listening → thinking → speaking → idle.
- Title changes match.
- Telemetry feed populates with state transitions and "you: …" lines.
- No console errors.

Stop the dev server.

- [ ] **Step 4: Commit**

```bash
git add web/src/main.ts
git commit -m "feat(web): wire all components into the application boot sequence"
```

---

## Task 20: Playwright smoke test

**Files:**
- Create: `web/playwright.config.ts`
- Create: `web/e2e/smoke.spec.ts`

- [ ] **Step 1: Install Chromium browser binary**

```bash
cd web && npx playwright install chromium
```

Expected: chromium downloaded.

- [ ] **Step 2: Create `web/playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
```

- [ ] **Step 3: Create `web/e2e/smoke.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

test("HUD boots, cycles through full conversation", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/?dev=1");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 5000 });

  // All 9 cells exist
  for (const cell of ["top","tl","tr","left","center","right","bl","bottom","br"]) {
    await expect(page.locator(`[data-cell="${cell}"]`)).toBeVisible();
  }

  // Run a scenario
  await page.locator('[data-action="run-scenario"]').click();

  // State should reach speaking, then return to idle
  await expect(page.locator("body")).toHaveAttribute("data-state", "speaking", { timeout: 8000 });
  await expect(page.locator("body")).toHaveAttribute("data-state", "idle", { timeout: 30000 });

  // Transcript should have content (at least one of the scenarios' replies has "ready" or "synthesized" or "approved" or "Done" or "drafted")
  const text = (await page.locator(".transcript .body").textContent()) ?? "";
  expect(text.length).toBeGreaterThan(5);

  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([]);
});
```

- [ ] **Step 4: Run smoke**

```bash
cd web && npm run test:e2e
```

Expected: 1/1 passed.

- [ ] **Step 5: Commit**

```bash
git add web/playwright.config.ts web/e2e/smoke.spec.ts
git commit -m "test(web): playwright smoke covers boot and full scenario cycle"
```

---

## Task 21: Accessibility + polish pass

**Files:**
- Modify: `web/index.html`
- Modify: `web/src/styles/global.css`
- Modify: `web/src/styles/panel.css`
- Modify: `web/src/ui/Controls.ts`

- [ ] **Step 1: Add reduced motion + focus styles**

Append to `web/src/styles/global.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}

button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

[role="region"]:focus-visible {
  outline: 1px dashed var(--accent);
  outline-offset: 2px;
}

.skip-link {
  position: absolute;
  left: -9999px;
}
.skip-link:focus {
  left: 16px; top: 16px;
  padding: 8px 12px;
  background: var(--bg-1);
  border: 1px solid var(--accent);
  z-index: 1000;
}
```

- [ ] **Step 2: Add lang/role on `<body>` and skip link**

Replace `web/index.html` body opening:

```html
<body data-state="idle">
  <a href="#center" class="skip-link">Skip to conversation</a>
  <div id="app" class="hud" role="application" aria-label="Jarvis">
    <header class="cell cell-top"      data-cell="top"></header>
    <section class="cell cell-tl"      data-cell="tl"></section>
    <section class="cell cell-tr"      data-cell="tr"></section>
    <section class="cell cell-left"    data-cell="left"></section>
    <section id="center" class="cell cell-center" data-cell="center" tabindex="-1"></section>
    <section class="cell cell-right"   data-cell="right"></section>
    <section class="cell cell-bl"      data-cell="bl"></section>
    <footer  class="cell cell-bottom"  data-cell="bottom"></footer>
    <section class="cell cell-br"      data-cell="br"></section>
  </div>
  <script type="module" src="/src/main.ts"></script>
</body>
```

- [ ] **Step 3: Improve Controls accessibility**

Modify `web/src/ui/Controls.ts` button row to set `aria-pressed` on the mic button while held. Replace the `mousedown`/`mouseup` block with:

```ts
const setPressed = (v: boolean): void => mic.setAttribute("aria-pressed", v ? "true" : "false");
mic.setAttribute("aria-pressed", "false");
mic.addEventListener("mousedown", () => { setPressed(true);  this.actions.onMicDown(); });
mic.addEventListener("mouseup",   () => { setPressed(false); this.actions.onMicUp(); });
mic.addEventListener("mouseleave", () => { setPressed(false); this.actions.onMicUp(); });
mic.addEventListener("touchstart", (e) => { e.preventDefault(); setPressed(true);  this.actions.onMicDown(); }, { passive: false });
mic.addEventListener("touchend",   () => { setPressed(false); this.actions.onMicUp(); });
```

- [ ] **Step 4: Re-run all checks**

```bash
cd web && npm run lint && npm run test && npm run build && npm run test:e2e
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/src/styles web/src/ui/Controls.ts
git commit -m "feat(web): a11y pass — reduced motion, focus styles, skip link, aria-pressed"
```

---

## Task 22: Final verification + merge prep

**Files:**
- Create: `web/README.md`

- [ ] **Step 1: Write `web/README.md`**

```markdown
# Jarvis · Frontend (web/)

Vite + TypeScript SPA implementing the Jarvis HUD with audio-reactive
waveform centerpiece. Spec-01 of the Jarvis build.

## Develop

```bash
cd web
npm install
npm run dev          # dev server on http://localhost:5173
```

Append `?dev=1` to enable the `Run scenario` button.

## Quality gates

```bash
npm run lint          # eslint
npm run test          # vitest unit tests
npm run test:e2e      # playwright smoke (chromium)
npm run build         # production build → dist/
npm run preview       # serve the production build
```

## Architecture

See `docs/superpowers/specs/2026-05-07-frontend-shell-design.md`.

The mock event source (`src/events/mockEventSource.ts`) implements the
same `EventSource` interface (`src/events/eventSource.ts`) the real
WebSocket client will provide in spec-03 — no rewiring required when
the swap happens.
```

- [ ] **Step 2: Run the full acceptance checklist (from spec §8)**

Execute and verify each:

```bash
cd web
npm install
npm run dev -- --port 5173 &
sleep 5
curl -s http://localhost:5173 | grep -q 'data-cell="center"' && echo "1: OK boot"
# Visual check (manual): all 9 panels render, scenario cycles cleanly
kill %1
npm run build
npm run preview -- --port 4173 &
sleep 3
curl -s http://localhost:4173 | grep -q 'data-cell="center"' && echo "2: OK preview"
kill %1
npm run test       && echo "3: OK unit"
npm run test:e2e   && echo "4: OK e2e"
npm run lint       && echo "5: OK lint"
```

Expected: all five OK.

- [ ] **Step 3: Update root STATUS.md**

Edit `docs/superpowers/STATUS.md` (in the worktree's view, but the file lives at the repo root and is shared via git index — use the worktree-local path):

Update the spec-01 row to all ✅ except merge. Update "Last completed action" and "Next action" to point at merging the worktree and starting spec-02 brainstorm.

- [ ] **Step 4: Commit**

```bash
git add web/README.md docs/superpowers/STATUS.md
git commit -m "docs: web README + STATUS update for spec-01 ready to merge"
```

- [ ] **Step 5: Final verify before merge**

```bash
git log --oneline main..HEAD
```

Expected: a clean linear sequence of feature commits, one per task. No "WIP", no "fix" commits without context.

- [ ] **Step 6: Hand off to merge phase**

Stop here. The Orchestrator (main session) will run the `finishing-a-development-branch` skill to merge `spec-01-frontend-shell` into `main`, then begin spec-02 brainstorm.

---

## Self-review summary (orchestrator before commit of plan)

**Spec coverage check (each spec §8 acceptance criterion → task):**

1. install + dev boots → Task 1, Task 2, Task 22
2. all 9 panels populated → Tasks 7, 9, 10, 11, 13, 16, 19
3. mic permission flow + waveform reacts → Tasks 12, 13, 14, 19
4. scenario cycles through all states → Tasks 17, 18, 19, 20
5. build + preview works → Task 22
6. test passes (Vitest) → Tasks 4, 5, 6, 8, 12, 15, 18
7. test:e2e passes (Playwright) → Task 20
8. lint clean → Task 2 + every commit
9. no console errors → Task 20 (smoke asserts)

**Spec features → tasks:**

- State machine (§4.1) → Task 4
- EventSource interface (§4.2) → Task 6 + Task 18
- Mock event source behavior (§4.3) → Task 18
- Audio reactivity (§4.4) → Tasks 12, 14, 19
- Component base (§5.1) → Task 8
- Panel composition (§5.2) → Tasks 7, 9, 10
- Centerpiece (§5.3) → Tasks 14, 15, 16
- Controls + keyboard (§5.4) → Task 17
- Telemetry feed (§5.5) → Task 11
- Error handling (§6) → Task 13 + Task 19 (mic permission paths) + global error toast deferred (acceptable: §6 says "boundary handling at micCapture, top-level handler" — micCapture errors are caught in main.ts ensureMic; uncaught render exceptions are NOT explicitly hooked, see Risk note below)

**Risk: §6 mentions a top-level `window.onerror` toast.** This is not implemented above. Acceptable for spec-01 because (a) the only realistic uncaught error path is in components, and (b) Playwright smoke asserts no console errors as a hard gate. Adding the toast adds UI surface. Deferred to a follow-up if a real error surfaces during use.

**Placeholder scan:** none — every step has concrete code or commands.

**Type consistency:** all event names, payload shapes, ConvState values, and method signatures match across `types.ts`, `eventSource.ts`, `mockEventSource.ts`, `stateMachine.ts`, store usage, and main.ts.

---
