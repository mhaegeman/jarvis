import { describe, it, expect, beforeEach, vi } from "vitest";
import { Centerpiece, SPEAKER_TINT } from "@/ui/Centerpiece";

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

if (typeof ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}

describe("Centerpiece.setTint", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="c"></div>`;
  });

  it("SPEAKER_TINT exports jarvis cyan and pepper amber", () => {
    expect(SPEAKER_TINT.jarvis).toBe("#0bc5ea");
    expect(SPEAKER_TINT.pepper).toBe("#ffb86b");
  });

  it("setTint(null) clears --centerpiece-tint on root element", () => {
    const cp = new Centerpiece("#c");
    const root = document.getElementById("c")!;
    cp.setTint(null);
    expect(root.style.getPropertyValue("--centerpiece-tint")).toBe("");
  });

  it("setTint('jarvis') sets --centerpiece-tint to jarvis cyan", () => {
    const cp = new Centerpiece("#c");
    const root = document.getElementById("c")!;
    cp.setTint("jarvis");
    expect(root.style.getPropertyValue("--centerpiece-tint")).toBe(SPEAKER_TINT.jarvis);
  });

  it("setTint('pepper') sets --centerpiece-tint to pepper amber", () => {
    const cp = new Centerpiece("#c");
    const root = document.getElementById("c")!;
    cp.setTint("pepper");
    expect(root.style.getPropertyValue("--centerpiece-tint")).toBe(SPEAKER_TINT.pepper);
  });

  it("setTint transitions between speakers", () => {
    const cp = new Centerpiece("#c");
    const root = document.getElementById("c")!;
    cp.setTint("jarvis");
    expect(root.style.getPropertyValue("--centerpiece-tint")).toBe(SPEAKER_TINT.jarvis);
    cp.setTint("pepper");
    expect(root.style.getPropertyValue("--centerpiece-tint")).toBe(SPEAKER_TINT.pepper);
  });
});
