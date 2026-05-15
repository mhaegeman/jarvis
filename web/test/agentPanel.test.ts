import { describe, it, expect, vi, beforeEach } from "vitest";

// ─── Minimal fakes ──────────────────────────────────────────────────────────

type Handler = (payload: unknown) => void;

class FakeEvents {
  private handlers: Map<string, Set<Handler>> = new Map();
  sent: { method: string; args: unknown[] }[] = [];

  on(event: string, handler: Handler): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
    return () => { this.handlers.get(event)?.delete(handler); };
  }

  emit(event: string, payload: unknown): void {
    this.handlers.get(event)?.forEach((h) => h(payload));
  }

  sendAgentApprove(runId: string, choice: string): void {
    this.sent.push({ method: "sendAgentApprove", args: [runId, choice] });
  }

  sendAgentCancel(runId: string): void {
    this.sent.push({ method: "sendAgentCancel", args: [runId] });
  }
}

function makeStore(initial: { activeAgentRun: { runId: string; task: string; speaker: string } | null }) {
  let state = initial;
  const subs = new Set<(s: typeof initial) => void>();
  return {
    get: () => state,
    update: (fn: (s: typeof initial) => Partial<typeof initial>) => {
      state = { ...state, ...fn(state) };
      subs.forEach((s) => s(state));
    },
    subscribe: (fn: (s: typeof initial) => void) => {
      subs.add(fn);
      return () => { subs.delete(fn); };
    },
  };
}

// ─── Import under test ──────────────────────────────────────────────────────

import { mountAgentPanel } from "@/ui/compass/AgentPanel";

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("AgentPanel", () => {
  let container: HTMLElement;
  let fakeEvents: FakeEvents;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    fakeEvents = new FakeEvents();
  });

  it("renders nothing (hidden) when activeAgentRun is null", () => {
    const store = makeStore({ activeAgentRun: null });
    mountAgentPanel(container, store as never, fakeEvents as never);
    // Panel should be hidden or empty
    const panel = container.querySelector(".agent-panel");
    expect(panel === null || (panel as HTMLElement).style.display === "none" || panel.textContent?.trim() === "").toBe(true);
  });

  it("renders task line when activeAgentRun is set", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "rename all the things", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);
    expect(container.textContent).toContain("rename all the things");
  });

  it("appends a row for each agent.step event", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "do stuff", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    fakeEvents.emit("agent.step", { runId: "r1", kind: "file_edit", summary: "edited x.py +3 -1" });
    fakeEvents.emit("agent.step", { runId: "r1", kind: "shell", summary: "ran npm install" });

    expect(container.textContent).toContain("edited x.py +3 -1");
    expect(container.textContent).toContain("ran npm install");
  });

  it("renders approval card with one button per choice", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    fakeEvents.emit("agent.approval", {
      runId: "r1",
      prompt: "Allow file write?",
      choices: ["approve", "deny", "approve_session"],
    });

    expect(container.textContent).toContain("Allow file write?");
    const buttons = container.querySelectorAll("button");
    const buttonTexts = Array.from(buttons).map((b) => b.textContent?.trim());
    expect(buttonTexts).toContain("approve");
    expect(buttonTexts).toContain("deny");
    expect(buttonTexts).toContain("approve_session");
  });

  it("approval button calls sendAgentApprove with the right choice", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    fakeEvents.emit("agent.approval", {
      runId: "r1",
      prompt: "OK?",
      choices: ["approve", "deny"],
    });

    const approveBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "approve",
    );
    expect(approveBtn).toBeDefined();
    approveBtn!.click();

    expect(fakeEvents.sent).toContainEqual({ method: "sendAgentApprove", args: ["r1", "approve"] });
  });

  it("cancel button calls sendAgentCancel with the runId", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    const cancelBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.toLowerCase().includes("cancel"),
    );
    expect(cancelBtn).toBeDefined();
    cancelBtn!.click();

    expect(fakeEvents.sent).toContainEqual({ method: "sendAgentCancel", args: ["r1"] });
  });

  it("hides the panel when activeAgentRun becomes null", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    // Initially visible
    const panel = container.querySelector(".agent-panel") as HTMLElement | null;
    expect(panel).not.toBeNull();

    // Clear run
    store.update(() => ({ activeAgentRun: null }));

    const panelAfter = container.querySelector(".agent-panel") as HTMLElement | null;
    expect(
      panelAfter === null || panelAfter.style.display === "none" || panelAfter.textContent?.trim() === "",
    ).toBe(true);
  });

  it("renders a progress indicator when agent.progress is emitted", () => {
    const store = makeStore({ activeAgentRun: { runId: "r1", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    fakeEvents.emit("agent.progress", { runId: "r1", phase: "editing", percent: 0.5 });

    expect(container.textContent).toContain("editing");
  });

  it("spy: approve and cancel are called via the events interface", () => {
    const approveSpy = vi.spyOn(fakeEvents, "sendAgentApprove");
    const cancelSpy = vi.spyOn(fakeEvents, "sendAgentCancel");

    const store = makeStore({ activeAgentRun: { runId: "r99", task: "task", speaker: "pepper" } });
    mountAgentPanel(container, store as never, fakeEvents as never);

    fakeEvents.emit("agent.approval", { runId: "r99", prompt: "q?", choices: ["approve"] });
    const approveBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "approve",
    )!;
    approveBtn.click();
    expect(approveSpy).toHaveBeenCalledWith("r99", "approve");

    const cancelBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.toLowerCase().includes("cancel"),
    )!;
    cancelBtn.click();
    expect(cancelSpy).toHaveBeenCalledWith("r99");
  });
});
