# Voice Dock Command History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static `RECENT_COMMANDS` array in `VoiceDock` with a `localStorage`-backed command history that persists and surfaces the last 8 voice commands across page reloads.

**Architecture:** A small `CommandHistory` module in `web/src/ui/compass/commandHistory.ts` manages read/write to `localStorage` under the key `jarvis_recent_commands`. `VoiceDock` reads from it on every `show()`. `main.ts` calls `CommandHistory.push(text)` on each `stt.final` event so recognized voice commands are persisted. No backend changes needed.

**Tech Stack:** TypeScript, `localStorage`, vitest

**Branch:** `feat/voice-dock-history` (branch off `main`)

---

### Environment setup

```bash
cd /home/user/jarvis
git fetch origin main
git checkout -b feat/voice-dock-history origin/main
```

Frontend baseline:
```bash
cd web && npm run test -- --run 2>&1 | tail -5
```
Must be green before touching code.

---

### Task 1: Create `CommandHistory` module

**Files:**
- Create: `web/src/ui/compass/commandHistory.ts`
- Create: `web/test/commandHistory.test.ts`

Contract:
- `CommandHistory.push(text: string): void` — prepends `text`, deduplicates (removes earlier occurrence of same string), trims to 8 entries, persists to `localStorage`.
- `CommandHistory.recent(): string[]` — returns the stored list (up to 8), or `[]` if nothing stored yet.

- [ ] **Step 1: Write the failing tests**

Create `web/test/commandHistory.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { CommandHistory } from "@/ui/compass/commandHistory";

beforeEach(() => localStorage.clear());

describe("CommandHistory.recent()", () => {
  it("returns empty array when nothing stored", () => {
    expect(CommandHistory.recent()).toEqual([]);
  });

  it("returns previously pushed commands newest-first", () => {
    CommandHistory.push("first command");
    CommandHistory.push("second command");
    expect(CommandHistory.recent()).toEqual(["second command", "first command"]);
  });
});

describe("CommandHistory.push()", () => {
  it("deduplicates: pushes existing entry to front instead of duplicating", () => {
    CommandHistory.push("hello");
    CommandHistory.push("world");
    CommandHistory.push("hello");
    expect(CommandHistory.recent()).toEqual(["hello", "world"]);
  });

  it("trims to 8 entries", () => {
    for (let i = 0; i < 12; i++) CommandHistory.push(`command ${i}`);
    expect(CommandHistory.recent().length).toBe(8);
  });

  it("persists across module calls (simulating page reload via fresh read)", () => {
    CommandHistory.push("persistent command");
    // Simulate fresh read from localStorage
    const raw = localStorage.getItem("jarvis_recent_commands");
    const parsed: string[] = raw ? JSON.parse(raw) : [];
    expect(parsed).toContain("persistent command");
  });

  it("ignores blank strings", () => {
    CommandHistory.push("");
    CommandHistory.push("   ");
    expect(CommandHistory.recent()).toEqual([]);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/web
npm run test -- commandHistory --run 2>&1 | tail -20
```
Expected: FAIL (cannot find module `@/ui/compass/commandHistory`)

- [ ] **Step 3: Implement `commandHistory.ts`**

Create `web/src/ui/compass/commandHistory.ts`:

```typescript
const STORAGE_KEY = "jarvis_recent_commands";
const MAX_ENTRIES = 8;

function load(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function save(entries: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // localStorage full or unavailable — silently skip
  }
}

export const CommandHistory = {
  recent(): string[] {
    return load();
  },

  push(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    const entries = load().filter((e) => e !== trimmed);
    entries.unshift(trimmed);
    save(entries.slice(0, MAX_ENTRIES));
  },
};
```

- [ ] **Step 4: Run tests — expect green**

```bash
npm run test -- commandHistory --run 2>&1 | tail -20
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/jarvis
git add web/src/ui/compass/commandHistory.ts web/test/commandHistory.test.ts
git commit -m "feat(voice-dock): CommandHistory module with localStorage persistence"
```

---

### Task 2: Wire `VoiceDock` to read from `CommandHistory`

**Files:**
- Modify: `web/src/ui/compass/VoiceDock.ts`

- [ ] **Step 1: Write the failing test**

Create `web/test/voiceDock.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { VoiceDock } from "@/ui/compass/VoiceDock";
import { CommandHistory } from "@/ui/compass/commandHistory";

beforeEach(() => localStorage.clear());

describe("VoiceDock", () => {
  it("renders 'no recent commands' when history is empty", () => {
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    expect(document.body.textContent).toContain("no recent commands");
    dock.destroy();
  });

  it("renders stored commands from CommandHistory on show()", () => {
    CommandHistory.push("What's on my calendar?");
    CommandHistory.push("Set a timer for 5 minutes");
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    expect(document.body.textContent).toContain("Set a timer for 5 minutes");
    expect(document.body.textContent).toContain("What's on my calendar?");
    dock.destroy();
  });

  it("re-renders on each show() to pick up new history", () => {
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    dock.hide();
    CommandHistory.push("new command after hide");
    dock.show();
    expect(document.body.textContent).toContain("new command after hide");
    dock.destroy();
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/web
npm run test -- voiceDock --run 2>&1 | tail -20
```
Expected: FAIL (renders static RECENT_COMMANDS, not from CommandHistory)

- [ ] **Step 3: Update `VoiceDock.ts`**

Replace the contents of `web/src/ui/compass/VoiceDock.ts` entirely:

```typescript
import { CommandHistory } from "./commandHistory";

export class VoiceDock {
  private readonly el: HTMLElement;
  private visible = false;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "voice-dock";
    this.el.setAttribute("aria-label", "Voice command dock");
    parent.appendChild(this.el);
    this.renderContent();
  }

  private renderContent(): void {
    const cmds = CommandHistory.recent();
    const cmdRows =
      cmds.length > 0
        ? cmds.map((cmd) => `<div class="cmd">${escHtml(cmd)}</div>`).join("")
        : `<div class="cmd empty">no recent commands</div>`;

    this.el.innerHTML = `
      <div class="head">
        <span class="invite">listening…</span>
        <span class="hold-hint">hold Space</span>
      </div>
      <div class="recents">
        <div class="rlabel">recent</div>
        ${cmdRows}
      </div>`;
  }

  show(): void {
    if (this.visible) return;
    this.visible = true;
    // Re-render to restart stagger animations and pick up latest history
    this.renderContent();
    this.el.classList.add("open");
  }

  hide(): void {
    if (!this.visible) return;
    this.visible = false;
    this.el.classList.remove("open");
  }

  destroy(): void {
    this.el.remove();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
```

- [ ] **Step 4: Run tests — expect green**

```bash
npm run test -- voiceDock --run 2>&1 | tail -20
```
Expected: all 3 tests PASS

- [ ] **Step 5: Run full suite**

```bash
npm run test -- --run 2>&1 | tail -10
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/compass/VoiceDock.ts web/test/voiceDock.test.ts
git commit -m "feat(voice-dock): read recent commands from CommandHistory instead of static stub"
```

---

### Task 3: Push commands from `stt.final` in `main.ts`

**Files:**
- Modify: `web/src/main.ts`

- [ ] **Step 1: Write a test for the integration**

Append to `web/test/commandHistory.test.ts`:

```typescript
describe("CommandHistory integrates with stt.final (unit check)", () => {
  it("push + recent round-trip works for a real voice command string", () => {
    const cmd = "Brief me on today's agenda";
    CommandHistory.push(cmd);
    expect(CommandHistory.recent()[0]).toBe(cmd);
  });
});
```

This test is already covered by the module tests above; it documents the integration expectation.

- [ ] **Step 2: Run — expect green immediately**

```bash
npm run test -- commandHistory --run 2>&1 | tail -10
```
Expected: PASS (the module already handles this)

- [ ] **Step 3: Wire into `main.ts`**

In `web/src/main.ts`, add the import at the top (after the other imports, before the AudioContext setup):

```typescript
import { CommandHistory } from "@/ui/compass/commandHistory";
```

Then find the `stt.final` handler (currently):
```typescript
events.on("stt.final", ({ text }) => {
  log("info", `you: ${text}`);
  openAudioIds.clear();
  llmEnded = false;
});
```

Add the `CommandHistory.push` call:
```typescript
events.on("stt.final", ({ text }) => {
  log("info", `you: ${text}`);
  CommandHistory.push(text);
  openAudioIds.clear();
  llmEnded = false;
});
```

- [ ] **Step 4: Type-check and build**

```bash
cd /home/user/jarvis/web
npm run build 2>&1 | tail -10
```
Expected: clean build

- [ ] **Step 5: Run full suite**

```bash
npm run test -- --run 2>&1 | tail -10
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
cd /home/user/jarvis
git add web/src/main.ts
git commit -m "feat(voice-dock): persist recognized commands to CommandHistory on stt.final"
```

---

### Task 4: Push branch

```bash
git push -u origin feat/voice-dock-history
```

**Merge order note:** Merge this branch first (frontend-only, no dependencies on the other two branches).
