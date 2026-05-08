import { describe, it, expect } from "vitest";
import { analyserDb } from "@/audio/analyzer";

class FakeAnalyser {
  fftSize = 128;
  constructor(private fill: number) {}
  getFloatTimeDomainData(buf: Float32Array): void {
    buf.fill(this.fill);
  }
}

describe("analyserDb", () => {
  it("returns -Infinity for silence", () => {
    expect(analyserDb(new FakeAnalyser(0) as unknown as AnalyserNode)).toBe(-Infinity);
  });

  it("returns ≈ 0 dB for full scale", () => {
    expect(analyserDb(new FakeAnalyser(1) as unknown as AnalyserNode)).toBeCloseTo(0, 1);
  });

  it("returns ≈ -6 dB for half scale", () => {
    expect(analyserDb(new FakeAnalyser(0.5) as unknown as AnalyserNode)).toBeCloseTo(-6, 0);
  });

  it("clamps tiny values to -80 dB", () => {
    expect(analyserDb(new FakeAnalyser(0.00001) as unknown as AnalyserNode)).toBe(-80);
  });
});
