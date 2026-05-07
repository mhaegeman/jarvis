import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MockEventSource } from "@/events/mockEventSource";

describe("MockEventSource skeleton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("emits ready after start()", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    await m.start();
    expect(ready).toHaveBeenCalledOnce();
  });

  it("on(...) returns an unsubscribe", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    const off = m.on("ready", ready);
    off();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });

  it("stop() clears subscribers", async () => {
    const m = new MockEventSource();
    const ready = vi.fn();
    m.on("ready", ready);
    m.stop();
    await m.start();
    expect(ready).not.toHaveBeenCalled();
  });
});

describe("MockEventSource conversation flow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("emits stt.partial during listening, stt.final after endListening, then llm + tts", async () => {
    const m = new MockEventSource({ scenarioOverride: { user: "hi", reply: "ok. yes." } });
    const partial = vi.fn();
    const final = vi.fn();
    const tokens = vi.fn();
    const sentences = vi.fn();
    const llmEnd = vi.fn();
    m.on("stt.partial", partial);
    m.on("stt.final", final);
    m.on("llm.token", tokens);
    m.on("tts.sentence", sentences);
    m.on("llm.end", llmEnd);

    await m.start();
    m.beginListening();
    await vi.advanceTimersByTimeAsync(2000);
    m.endListening();
    await vi.advanceTimersByTimeAsync(5000);

    expect(partial).toHaveBeenCalled();
    expect(final).toHaveBeenCalledWith({ text: "hi" });
    expect(tokens.mock.calls.length).toBeGreaterThan(0);
    expect(sentences).toHaveBeenCalledTimes(2);
    expect(llmEnd).toHaveBeenCalledOnce();
  });

  it("interrupt() stops in-flight emissions", async () => {
    const m = new MockEventSource({
      scenarioOverride: { user: "x", reply: "one. two. three." },
    });
    const sentences = vi.fn();
    m.on("tts.sentence", sentences);

    await m.start();
    m.beginListening();
    await vi.advanceTimersByTimeAsync(500);
    m.endListening();
    await vi.advanceTimersByTimeAsync(800);
    m.interrupt();
    await vi.advanceTimersByTimeAsync(5000);

    expect(sentences.mock.calls.length).toBeLessThan(3);
  });

  it("llm.end fires exactly once even if interrupt() is called after natural end", async () => {
    const m = new MockEventSource({ scenarioOverride: { user: "hi", reply: "ok." } });
    const llmEnd = vi.fn();
    m.on("llm.end", llmEnd);

    await m.start();
    m.beginListening();
    await vi.advanceTimersByTimeAsync(500);
    m.endListening();
    await vi.advanceTimersByTimeAsync(5000);
    m.interrupt(); // late interrupt after natural completion
    await vi.advanceTimersByTimeAsync(1000);

    expect(llmEnd).toHaveBeenCalledOnce();
  });
});
