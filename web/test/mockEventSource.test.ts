import { describe, it, expect, vi } from "vitest";
import { MockEventSource } from "@/events/mockEventSource";

describe("MockEventSource skeleton", () => {
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
