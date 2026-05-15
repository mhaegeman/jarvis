import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WSEventSource } from "@/events/wsEventSource";
import { FakeWebSocket, FakeAudioContext } from "./_fakes";

function freshSrc(): { src: WSEventSource } {
  const ctx = new FakeAudioContext();
  const src = new WSEventSource({
    url: "ws://x",
    audioCtx: ctx as unknown as AudioContext,
  });
  return { src };
}

describe("WSEventSource — Phase 4", () => {
  let restore: () => void;
  beforeEach(() => {
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => restore());

  async function openSrc(src: WSEventSource): Promise<FakeWebSocket> {
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    return ws;
  }

  it("forwards llm.token with speaker + segmentIdx", async () => {
    const { src } = freshSrc();
    const handler = vi.fn();
    src.on("llm.token", handler);
    const ws = await openSrc(src);
    ws.receiveText(JSON.stringify({ type: "llm.token", delta: "hi", speaker: "pepper", segmentIdx: 1 }));
    expect(handler).toHaveBeenCalledWith({ delta: "hi", speaker: "pepper", segmentIdx: 1 });
  });

  it("forwards llm.segment_end", async () => {
    const { src } = freshSrc();
    const handler = vi.fn();
    src.on("llm.segment_end", handler);
    const ws = await openSrc(src);
    ws.receiveText(JSON.stringify({ type: "llm.segment_end", speaker: "jarvis", segmentIdx: 0 }));
    expect(handler).toHaveBeenCalledWith({ speaker: "jarvis", segmentIdx: 0 });
  });

  it("forwards dispatch.plan", async () => {
    const { src } = freshSrc();
    const handler = vi.fn();
    src.on("dispatch.plan", handler);
    const ws = await openSrc(src);
    ws.receiveText(JSON.stringify({
      type: "dispatch.plan",
      turnId: "t-1",
      segments: [
        { speaker: "jarvis", tier: "fast", mode: "chat", intent: "hi" },
      ],
      rationale: "trivial",
    }));
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({
      turnId: "t-1", rationale: "trivial",
    }));
  });

  it("forwards each agent.* event", async () => {
    const { src } = freshSrc();
    const starts = vi.fn(); src.on("agent.start", starts);
    const steps = vi.fn(); src.on("agent.step", steps);
    const approvals = vi.fn(); src.on("agent.approval", approvals);
    const progress = vi.fn(); src.on("agent.progress", progress);
    const ends = vi.fn(); src.on("agent.end", ends);
    const ws = await openSrc(src);

    ws.receiveText(JSON.stringify({ type: "agent.start", speaker: "pepper", task: "x", runId: "r1" }));
    ws.receiveText(JSON.stringify({ type: "agent.step", runId: "r1", kind: "file_edit", summary: "x.py +3 -1" }));
    ws.receiveText(JSON.stringify({ type: "agent.approval", runId: "r1", prompt: "ok?", choices: ["approve", "deny"] }));
    ws.receiveText(JSON.stringify({ type: "agent.progress", runId: "r1", phase: "editing", percent: 0.5 }));
    ws.receiveText(JSON.stringify({ type: "agent.end", runId: "r1", status: "ok", summary: "done." }));

    expect(starts).toHaveBeenCalled();
    expect(steps).toHaveBeenCalled();
    expect(approvals).toHaveBeenCalled();
    expect(progress).toHaveBeenCalled();
    expect(ends).toHaveBeenCalled();
  });

  it("sendAgentApprove writes the right WS payload", async () => {
    const { src } = freshSrc();
    const ws = await openSrc(src);
    ws.sent.length = 0;
    src.sendAgentApprove("r1", "approve");
    const found = ws.sent.find((m): m is string => typeof m === "string" && m.includes("agent.approve"));
    expect(found).toBeDefined();
    expect(JSON.parse(found!)).toEqual({
      type: "agent.approve", runId: "r1", choice: "approve",
    });
  });

  it("sendAgentCancel writes the right WS payload", async () => {
    const { src } = freshSrc();
    const ws = await openSrc(src);
    ws.sent.length = 0;
    src.sendAgentCancel("r1");
    const found = ws.sent.find((m): m is string => typeof m === "string" && m.includes("agent.cancel"));
    expect(found).toBeDefined();
    expect(JSON.parse(found!)).toEqual({
      type: "agent.cancel", runId: "r1",
    });
  });
});
