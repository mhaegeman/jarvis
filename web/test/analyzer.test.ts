import { describe, it, expect } from "vitest";
import { rms } from "@/audio/analyzer";

describe("analyzer.rms", () => {
  it("returns 0 for silence", () => {
    expect(rms(new Float32Array(128))).toBe(0);
  });

  it("returns ~1 for a max-amplitude DC signal", () => {
    const a = new Float32Array(128).fill(1);
    expect(rms(a)).toBeCloseTo(1, 3);
  });

  it("returns ~0.707 for a sine wave at unit amplitude", () => {
    const a = new Float32Array(1024);
    for (let i = 0; i < a.length; i++) a[i] = Math.sin((i / a.length) * 2 * Math.PI * 4);
    expect(rms(a)).toBeCloseTo(Math.SQRT1_2, 2);
  });
});
