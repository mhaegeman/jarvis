import { describe, it, expect } from "vitest";
import { SystemPanel } from "@/ui/panels/SystemPanel";

describe("SystemPanel", () => {
  it("renders all five rows from state", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const p = new SystemPanel("#x");
    p.mount({
      uptimeMs: 3661000,
      load: 12.5,
      tokensPerMin: 1234,
      sessionId: "abc",
      modelName: "mock",
    });
    const html = document.getElementById("x")?.innerHTML ?? "";
    expect(html).toContain("01:01:01");
    expect(html).toContain("12.50");
    expect(html).toContain("1,234");
    expect(html).toContain("abc");
    expect(html).toContain("mock");
  });

  it("renders tokens/min with comma separator when > 1000", () => {
    document.body.innerHTML = `<div id="y"></div>`;
    const p = new SystemPanel("#y");
    p.mount({
      uptimeMs: 0,
      load: 0,
      tokensPerMin: 5678,
      sessionId: "s1",
      modelName: "m1",
    });
    const html = document.getElementById("y")?.innerHTML ?? "";
    expect(html).toContain("5,678");
  });

  it("renders modelName row", () => {
    document.body.innerHTML = `<div id="z"></div>`;
    const p = new SystemPanel("#z");
    p.mount({
      uptimeMs: 0,
      load: 0,
      tokensPerMin: 0,
      sessionId: "s2",
      modelName: "claude-sonnet-4-6",
    });
    const html = document.getElementById("z")?.innerHTML ?? "";
    expect(html).toContain("model");
    expect(html).toContain("claude-sonnet-4-6");
  });
});
