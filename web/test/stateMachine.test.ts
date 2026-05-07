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
