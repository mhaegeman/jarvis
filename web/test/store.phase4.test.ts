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
