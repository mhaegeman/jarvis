import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { connect } from "@/events/connect";
import { FakeWebSocket, FakeAudioContext } from "./_fakes";

describe("connect", () => {
  let restore: () => void;
  beforeEach(() => {
    vi.useFakeTimers();
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => {
    vi.useRealTimers();
    restore();
  });

  it("returns live mode when WS opens within timeout", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await Promise.resolve();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveText(JSON.stringify({ type: "ready" }));
    const result = await promise;
    expect(result.mode).toBe("live");
  });

  it("falls back to demo when WS open times out", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await vi.advanceTimersByTimeAsync(1000);
    const result = await promise;
    expect(result.mode).toBe("demo");
  });

  it("falls back to demo when WS errors immediately", async () => {
    const audioCtx = new FakeAudioContext() as unknown as AudioContext;
    const promise = connect({ url: "ws://x", audioCtx, openTimeoutMs: 1000 });
    await Promise.resolve();
    FakeWebSocket.instances[0].fail();
    await vi.advanceTimersByTimeAsync(1000);
    const result = await promise;
    expect(result.mode).toBe("demo");
  });
});
