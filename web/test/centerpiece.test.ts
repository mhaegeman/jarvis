import { describe, it, expect, beforeEach, vi } from "vitest";
import { Centerpiece } from "@/ui/Centerpiece";

// Stub canvas 2D context so Waveform doesn't throw in JSDOM
const ctx2dStub = {
  clearRect: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  stroke: vi.fn(),
  fillRect: vi.fn(),
  fillStyle: "",
  strokeStyle: "",
  lineWidth: 0,
  shadowBlur: 0,
  shadowColor: "",
  arc: vi.fn(),
  fill: vi.fn(),
};
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(HTMLCanvasElement.prototype as any).getContext = () => ctx2dStub;

// Stub ResizeObserver (not available in JSDOM by default)
if (typeof ResizeObserver === "undefined") {
  // @ts-expect-error — JSDOM shim
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

describe("Centerpiece", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="c"></div>`;
  });

  it("mounts the standard structure", () => {
    new Centerpiece("#c");
    expect(document.querySelector("#c .scan")).not.toBeNull();
    expect(document.querySelector("#c [data-slot=waveform]")).not.toBeNull();
    expect(document.querySelector("#c [data-slot=transcript]")).not.toBeNull();
    expect(document.querySelector("#c .centerpiece-title")).not.toBeNull();
  });

  it("setTitle updates the title element text", () => {
    const cp = new Centerpiece("#c");
    cp.setTitle("Listening.");
    const title = document.querySelector("#c .centerpiece-title");
    expect(title?.textContent).toBe("Listening.");
  });

  it("setStateClass sets data-state on root and .scan", () => {
    const cp = new Centerpiece("#c");
    cp.setStateClass("listening");
    const root = document.querySelector<HTMLElement>("#c");
    const scan = document.querySelector<HTMLElement>("#c .scan");
    expect(root?.dataset.state).toBe("listening");
    expect(scan?.dataset.state).toBe("listening");
  });

  it("appendToken followed by interruptTranscript doesn't throw and transcript element still exists", () => {
    const cp = new Centerpiece("#c");
    expect(() => {
      cp.appendToken("Hello");
      cp.appendToken(" world");
      cp.interruptTranscript();
    }).not.toThrow();
    expect(document.querySelector("#c [data-slot=transcript]")).not.toBeNull();
  });
});
