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
