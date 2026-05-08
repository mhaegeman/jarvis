import { describe, it, expect } from "vitest";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";

const mount = (state: Parameters<NetworkPanel["mount"]>[0]) => {
  document.body.innerHTML = `<div id="x"></div>`;
  const p = new NetworkPanel("#x");
  p.mount(state);
  return document.getElementById("x")!;
};

describe("NetworkPanel", () => {
  it("renders endpoint, latency, packets, and busy bar", () => {
    const root = mount({
      endpoint: "ws://localhost:8000/ws",
      latencyMs: 4.2,
      packets: 1234,
      sendQueueDepth: 64,
      sendQueueMax: 256,
    });
    const html = root.innerHTML;
    expect(html).toContain("ws://localhost:8000/ws");
    expect(html).toContain("4.2");
    expect(html).toContain("1,234");
    expect(html).toMatch(/width:25%/);
  });

  it("shows -- ms when latency is null", () => {
    const root = mount({
      endpoint: "x",
      latencyMs: null,
      packets: 0,
      sendQueueDepth: 0,
      sendQueueMax: 256,
    });
    expect(root.textContent).toContain("-- ms");
  });

  it("clamps bar width to 100% when queue exceeds max", () => {
    const root = mount({
      endpoint: "x",
      latencyMs: null,
      packets: 0,
      sendQueueDepth: 512,
      sendQueueMax: 256,
    });
    expect(root.innerHTML).toMatch(/width:100%/);
  });

  it("formats packets with comma thousands separator", () => {
    const root = mount({
      endpoint: "x",
      latencyMs: 1.0,
      packets: 1000000,
      sendQueueDepth: 0,
      sendQueueMax: 256,
    });
    expect(root.textContent).toContain("1,000,000");
  });
});
