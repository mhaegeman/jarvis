import { describe, it, expect, beforeEach } from "vitest";
import { PlaybackQueue } from "@/audio/playbackQueue";
import { FakeAudioContext } from "./_fakes";

describe("PlaybackQueue", () => {
  let ctx: FakeAudioContext;
  let q: PlaybackQueue;
  beforeEach(() => {
    ctx = new FakeAudioContext();
    q = new PlaybackQueue(ctx as unknown as AudioContext);
  });

  it("schedules each enqueued chunk after the previous one", () => {
    const a = new Int16Array(2400);
    const b = new Int16Array(2400);
    q.enqueue("s0", a);
    q.enqueue("s0", b);
    expect(ctx.sources.length).toBe(2);
    const [s1, s2] = ctx.sources;
    expect(s1.startCalls[0]).toBe(0);
    expect(s2.startCalls[0]).toBeCloseTo(0.1, 5);
  });

  it("interrupt cancels all pending sources and resets cursor to currentTime", () => {
    q.enqueue("s0", new Int16Array(2400));
    q.enqueue("s0", new Int16Array(2400));
    q.interrupt();
    for (const s of ctx.sources) expect(s.stopCalls.length).toBe(1);
    ctx.currentTime = 5;
    q.enqueue("s1", new Int16Array(2400));
    expect(ctx.sources[ctx.sources.length - 1].startCalls[0]).toBe(5);
  });

  it("exposes the AnalyserNode in the audio graph", () => {
    expect(q.analyser).toBe(ctx.analyser);
  });

  it("ignores empty chunks", () => {
    q.enqueue("s0", new Int16Array(0));
    expect(ctx.sources.length).toBe(0);
  });
});
