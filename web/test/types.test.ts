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
    // Compile-time check: assign to void-typed variables to satisfy noUnusedLocals.
    const _plan: EventMap["dispatch.plan"] = undefined as unknown as EventMap["dispatch.plan"];
    const _seg: EventMap["llm.segment_end"] = undefined as unknown as EventMap["llm.segment_end"];
    const _as: EventMap["agent.start"] = undefined as unknown as EventMap["agent.start"];
    const _ae: EventMap["agent.end"] = undefined as unknown as EventMap["agent.end"];
    expect([_plan, _seg, _as, _ae]).toBeDefined();
  });

  it("Speaker is a string literal union", () => {
    const j: Speaker = "jarvis";
    const p: Speaker = "pepper";
    expect([j, p]).toEqual(["jarvis", "pepper"]);
  });

  // Silence unused type warnings
  it("AgentApproval and AgentProgress are defined", () => {
    const a: AgentApproval = { runId: "r1", prompt: "ok?", choices: ["approve", "deny"] };
    const pr: AgentProgress = { runId: "r1", phase: "editing", percent: 0.5 };
    const as: AgentStart = { speaker: "pepper", task: "rename X", runId: "r1" };
    expect(a.choices).toHaveLength(2);
    expect(pr.phase).toBe("editing");
    expect(as.runId).toBe("r1");
  });
});
