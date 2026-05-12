import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { connect, withAuthToken } from "@/events/connect";
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

describe("withAuthToken", () => {
  afterEach(() => {
    sessionStorage.removeItem("jarvis_token");
  });

  it("appends ?token= when sessionStorage has a token", () => {
    sessionStorage.setItem("jarvis_token", "abc123");
    expect(withAuthToken("ws://x/ws")).toBe("ws://x/ws?token=abc123");
  });

  it("appends &token= when URL already has a query string", () => {
    sessionStorage.setItem("jarvis_token", "abc");
    expect(withAuthToken("ws://x/ws?foo=1")).toBe(
      "ws://x/ws?foo=1&token=abc",
    );
  });

  it("returns the URL unchanged when no token is cached", () => {
    sessionStorage.removeItem("jarvis_token");
    expect(withAuthToken("ws://x/ws")).toBe("ws://x/ws");
  });

  it("url-encodes the token (defense against weird storage)", () => {
    sessionStorage.setItem("jarvis_token", "a b/c");
    expect(withAuthToken("ws://x/ws")).toBe("ws://x/ws?token=a%20b%2Fc");
  });
});
