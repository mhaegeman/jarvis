import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { Topbar } from "@/ui/compass/Topbar";

// Minimal clock stub — prevent setInterval from running indefinitely
vi.useFakeTimers();

describe("Topbar dual persona chips", () => {
  let parent: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = `<div id="topbar-parent"></div>`;
    parent = document.getElementById("topbar-parent")!;
  });

  it("renders both Jarvis and Pepper chips", () => {
    new Topbar(parent);
    const text = parent.textContent ?? "";
    expect(text.toLowerCase()).toContain("jarvis");
    expect(text.toLowerCase()).toContain("pepper");
  });

  it("marks the active chip when currentSpeaker is jarvis", () => {
    const tb = new Topbar(parent);
    tb.render({ convState: "speaking", currentSpeaker: "jarvis" });
    const chips = parent.querySelectorAll(".persona-chip");
    const active = Array.from(chips).filter((c) => c.classList.contains("active"));
    expect(active).toHaveLength(1);
    expect(active[0].textContent?.toLowerCase()).toContain("jarvis");
  });

  it("marks the active chip when currentSpeaker is pepper", () => {
    const tb = new Topbar(parent);
    tb.render({ convState: "speaking", currentSpeaker: "pepper" });
    const chips = parent.querySelectorAll(".persona-chip");
    const active = Array.from(chips).filter((c) => c.classList.contains("active"));
    expect(active).toHaveLength(1);
    expect(active[0].textContent?.toLowerCase()).toContain("pepper");
  });

  it("no chip is active when currentSpeaker is null", () => {
    const tb = new Topbar(parent);
    tb.render({ convState: "idle", currentSpeaker: null });
    const chips = parent.querySelectorAll(".persona-chip");
    const active = Array.from(chips).filter((c) => c.classList.contains("active"));
    expect(active).toHaveLength(0);
  });

  it("chips have data-speaker attribute", () => {
    new Topbar(parent);
    const jarvisChip = parent.querySelector<HTMLElement>('[data-speaker="jarvis"]');
    const pepperChip = parent.querySelector<HTMLElement>('[data-speaker="pepper"]');
    expect(jarvisChip).not.toBeNull();
    expect(pepperChip).not.toBeNull();
  });

  it("clicking a chip logs the pin intent", () => {
    const logs: string[] = [];
    const origConsole = console.log;
    console.log = (...args: unknown[]) => { logs.push(args.join(" ")); };
    const tb = new Topbar(parent);
    const jarvisChip = parent.querySelector<HTMLElement>('[data-speaker="jarvis"]');
    jarvisChip?.click();
    console.log = origConsole;
    tb.destroy();
    // Should have logged something mentioning jarvis or pin
    expect(logs.some((l) => l.toLowerCase().includes("jarvis") || l.toLowerCase().includes("pin"))).toBe(true);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });
});
