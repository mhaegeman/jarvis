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

  it("renders 3-segment plan with two arrows", () => {
    const html = renderDispatchRibbon({
      turnId: "t2",
      segments: [
        { speaker: "jarvis", tier: "fast", mode: "chat", intent: "plan" },
        { speaker: "pepper", tier: "deep", mode: "codex_agent", intent: "implement" },
        { speaker: "jarvis", tier: "balanced", mode: "chat", intent: "review" },
      ],
      rationale: "plan → implement → review",
    });
    expect(html).toContain("Jarvis");
    expect(html).toContain("Pepper");
    // Two arrows for three segments
    expect((html.match(/→/g) ?? []).length).toBe(2);
  });

  it("capitalises speaker names correctly", () => {
    const html = renderDispatchRibbon({
      turnId: "t1",
      segments: [{ speaker: "pepper", tier: "deep", mode: "codex_agent", intent: "build" }],
      rationale: "",
    });
    expect(html).toContain("Pepper");
    expect(html).not.toContain("pepper"); // lowercase should not appear in visible text
  });

  it("includes a mode hint in the output", () => {
    const html = renderDispatchRibbon({
      turnId: "t1",
      segments: [
        { speaker: "jarvis", tier: "fast", mode: "chat", intent: "answer" },
      ],
      rationale: "",
    });
    // mode "chat" should appear as some human label
    expect(html.toLowerCase()).toMatch(/chat|planning|answer/);
  });
});
