import { describe, it, expect } from "vitest";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";

describe("MemoryPanel", () => {
  it("renders context bar at proportional width", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const p = new MemoryPanel("#x");
    p.mount({ contextUsed: 50000, contextMax: 200000 });
    const html = document.getElementById("x")?.innerHTML ?? "";
    expect(html).toMatch(/width:25%/);
    expect(html).toContain("50K / 200K");
  });

  it("clamps width to 100% when used > max", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const p = new MemoryPanel("#x");
    p.mount({ contextUsed: 999999, contextMax: 200000 });
    const html = document.getElementById("x")?.innerHTML ?? "";
    expect(html).toMatch(/width:100%/);
  });

  it("does NOT render a recall row", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const p = new MemoryPanel("#x");
    p.mount({ contextUsed: 1, contextMax: 100 });
    const html = document.getElementById("x")?.innerHTML ?? "";
    expect(html).not.toContain("recall");
  });
});
