import { describe, it, expect } from "vitest";
import { float32ToInt16 } from "@/audio/micWorklet";

describe("float32ToInt16", () => {
  it("clamps and scales", () => {
    const out = float32ToInt16(new Float32Array([0, 0.5, -0.5, 1, -1, 2, -2]));
    expect(Array.from(out)).toEqual([0, 16384, -16384, 32767, -32768, 32767, -32768]);
  });

  it("preserves length", () => {
    const out = float32ToInt16(new Float32Array(1600));
    expect(out.length).toBe(1600);
  });
});
