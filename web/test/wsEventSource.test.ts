import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { WSEventSource } from "@/events/wsEventSource";
import { KIND_SERVER_TTS } from "@/audio/wsCodec";
import { FakeWebSocket, FakeAudioContext } from "./_fakes";

function freshSrc(): { src: WSEventSource; ctx: FakeAudioContext } {
  const ctx = new FakeAudioContext();
  const src = new WSEventSource({
    url: "ws://x",
    audioCtx: ctx as unknown as AudioContext,
  });
  return { src, ctx };
}

describe("WSEventSource — reconnect", () => {
  let restore: () => void;
  beforeEach(() => {
    vi.useFakeTimers();
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => {
    vi.useRealTimers();
    restore();
  });

  it("walks backoff [1,2,4] on repeated failures and emits telemetry", async () => {
    const tele = vi.fn();
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
    });
    src.on("telemetry", tele);
    void src.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveText(JSON.stringify({ type: "ready" }));
    await Promise.resolve();

    FakeWebSocket.instances[0].close();
    expect(tele).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining("reconnecting"),
      }),
    );

    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances.length).toBe(2);
    FakeWebSocket.instances[1].close();

    await vi.advanceTimersByTimeAsync(2000);
    expect(FakeWebSocket.instances.length).toBe(3);
    FakeWebSocket.instances[2].close();

    await vi.advanceTimersByTimeAsync(4000);
    expect(FakeWebSocket.instances.length).toBe(4);
  });

  it("emits 'reconnected' telemetry on successful reconnect", async () => {
    const tele = vi.fn();
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
    });
    src.on("telemetry", tele);
    void src.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveText(JSON.stringify({ type: "ready" }));
    await Promise.resolve();
    FakeWebSocket.instances[0].close();

    await vi.advanceTimersByTimeAsync(1000);
    FakeWebSocket.instances[1].open();
    expect(tele).toHaveBeenCalledWith(
      expect.objectContaining({ message: "reconnected" }),
    );
  });

  it("stop() cancels pending reconnect", async () => {
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
    });
    void src.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].close();
    src.stop();
    await vi.advanceTimersByTimeAsync(60000);
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});

describe("WSEventSource — handshake + dispatch", () => {
  let restore: () => void;
  beforeEach(() => {
    ({ restore } = FakeWebSocket.install());
  });
  afterEach(() => restore());

  it("opens WS, sends hello, resolves start() on ready", async () => {
    const { src } = freshSrc();
    const startPromise = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    expect(ws.sent[0]).toBe(
      JSON.stringify({ type: "hello", clientVersion: "spec-03" }),
    );
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await startPromise;
  });

  it("dispatches stt.partial / stt.final / llm.token / llm.end / tts.sentence / tts.end / telemetry / error", async () => {
    const { src } = freshSrc();
    const partial = vi.fn();
    const final = vi.fn();
    const token = vi.fn();
    const llmEnd = vi.fn();
    const sentence = vi.fn();
    const ttsEnd = vi.fn();
    const tele = vi.fn();
    const err = vi.fn();
    src.on("stt.partial", partial);
    src.on("stt.final", final);
    src.on("llm.token", token);
    src.on("llm.end", llmEnd);
    src.on("tts.sentence", sentence);
    src.on("tts.end", ttsEnd);
    src.on("telemetry", tele);
    src.on("error", err);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText(JSON.stringify({ type: "stt.partial", text: "hi" }));
    ws.receiveText(JSON.stringify({ type: "stt.final", text: "hello world" }));
    ws.receiveText(JSON.stringify({ type: "llm.token", delta: "yo" }));
    ws.receiveText(JSON.stringify({ type: "llm.end" }));
    ws.receiveText(
      JSON.stringify({ type: "tts.sentence", text: "Sup.", audioId: "s0" }),
    );
    ws.receiveText(JSON.stringify({ type: "tts.end", audioId: "s0" }));
    ws.receiveText(
      JSON.stringify({ type: "telemetry", level: "info", message: "heartbeat" }),
    );
    ws.receiveText(JSON.stringify({ type: "error", code: "x", message: "y" }));
    expect(partial).toHaveBeenCalledWith({ text: "hi" });
    expect(final).toHaveBeenCalledWith({ text: "hello world" });
    expect(token).toHaveBeenCalledWith({ delta: "yo" });
    expect(llmEnd).toHaveBeenCalledWith(undefined);
    expect(sentence).toHaveBeenCalledWith({ text: "Sup.", audioId: "s0" });
    expect(ttsEnd).toHaveBeenCalledWith({ audioId: "s0" });
    expect(tele).toHaveBeenCalledWith(
      expect.objectContaining({ level: "info", message: "heartbeat" }),
    );
    expect(err).toHaveBeenCalledWith({ code: "x", message: "y" });
  });

  it("sendText forwards a JSON text frame", async () => {
    const { src } = freshSrc();
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    src.sendText("brief me on today");
    const found = ws.sent.find(
      (m): m is string => typeof m === "string" && m.includes("brief me"),
    );
    expect(found).toBe(
      JSON.stringify({ type: "text", content: "brief me on today" }),
    );
  });

  it("malformed JSON emits error event", async () => {
    const { src } = freshSrc();
    const err = vi.fn();
    src.on("error", err);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText("{not json");
    expect(err).toHaveBeenCalledWith(
      expect.objectContaining({ code: "client.bad_message" }),
    );
  });

  it("on() returns an unsubscribe fn", async () => {
    const { src } = freshSrc();
    const fn = vi.fn();
    const off = src.on("telemetry", fn);
    off();
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText(JSON.stringify({ type: "telemetry", level: "info", message: "x" }));
    expect(fn).not.toHaveBeenCalled();
  });

  it("decodes a TTS binary frame, emits tts.audioChunk, and enqueues to playback", async () => {
    const { src, ctx } = freshSrc();
    const chunkSpy = vi.fn();
    src.on("tts.audioChunk", chunkSpy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    const samples = new Int16Array([0, 100, -100]);
    const audioId = "s0-aaa";
    const idBytes = new TextEncoder().encode(audioId);
    const frame = new Uint8Array(2 + idBytes.byteLength + samples.byteLength);
    frame[0] = KIND_SERVER_TTS;
    frame[1] = idBytes.byteLength;
    frame.set(idBytes, 2);
    frame.set(new Uint8Array(samples.buffer), 2 + idBytes.byteLength);
    ws.receiveBinary(frame.buffer);

    expect(chunkSpy).toHaveBeenCalledTimes(1);
    expect(chunkSpy.mock.calls[0][0].audioId).toBe("s0-aaa");
    expect(ctx.sources.length).toBe(1);
  });

  it("malformed binary frame emits client.bad_frame", async () => {
    const { src } = freshSrc();
    const errSpy = vi.fn();
    src.on("error", errSpy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveBinary(new Uint8Array([0x02]).buffer);
    expect(errSpy).toHaveBeenCalledWith(
      expect.objectContaining({ code: "client.bad_frame" }),
    );
  });

  it("rejects unexpected binary frame kind (mic kind from server)", async () => {
    const { src } = freshSrc();
    const errSpy = vi.fn();
    src.on("error", errSpy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    const samples = new Int16Array([0, 0]);
    const frame = new Uint8Array(2 + samples.byteLength);
    frame[0] = 0x01;
    frame[1] = 0;
    frame.set(new Uint8Array(samples.buffer), 2);
    ws.receiveBinary(frame.buffer);
    expect(errSpy).toHaveBeenCalledWith(
      expect.objectContaining({ code: "client.bad_frame" }),
    );
  });

  it("beginListening sends audio.start; mic frames go out as binary; endListening sends audio.end", async () => {
    const ctx = new FakeAudioContext();
    let onFrame: ((s: Int16Array) => void) | null = null;
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
      micFactory: async (_ctx, cb) => {
        onFrame = cb;
        return {
          stop(): void {
            onFrame = null;
          },
        };
      },
    });
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    await src.beginListening();
    const startMsg = ws.sent.find(
      (m): m is string => typeof m === "string" && m.includes("audio.start"),
    );
    expect(startMsg).toBeTruthy();
    expect(onFrame).toBeTruthy();

    onFrame!(new Int16Array([1, 2, 3]));
    const binSent = ws.sent.find((m) => m instanceof ArrayBuffer);
    expect(binSent).toBeTruthy();

    src.endListening();
    const endMsg = ws.sent.find(
      (m): m is string => typeof m === "string" && m.includes("audio.end"),
    );
    expect(endMsg).toBeTruthy();
    expect(onFrame).toBeNull();
  });

  it("audio.start is sent only AFTER mic setup resolves (regression: P1)", async () => {
    const ctx = new FakeAudioContext();
    let resolveMic: ((h: { stop: () => void }) => void) | null = null;
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
      micFactory: (_ctx, _cb) =>
        new Promise<{ stop: () => void }>((r) => {
          resolveMic = r;
        }),
    });
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    const begin = src.beginListening();
    // Mic factory pending — audio.start MUST NOT be sent yet.
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.start"),
      ),
    ).toBe(false);

    resolveMic!({ stop: () => {} });
    await begin;
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.start"),
      ),
    ).toBe(true);
  });

  it("mic factory failure leaves no audio.start on the wire (regression: P1)", async () => {
    const ctx = new FakeAudioContext();
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
      micFactory: () => Promise.reject(new Error("worklet load failed")),
    });
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    await expect(src.beginListening()).rejects.toThrow("worklet load failed");
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.start"),
      ),
    ).toBe(false);
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.end"),
      ),
    ).toBe(false);
  });

  it("endListening during in-flight beginListening cancels with no audio.start/end (regression: P1)", async () => {
    const ctx = new FakeAudioContext();
    let resolveMic: ((h: { stop: () => void }) => void) | null = null;
    let stopCalled = false;
    const src = new WSEventSource({
      url: "ws://x",
      audioCtx: ctx as unknown as AudioContext,
      micFactory: (_ctx, _cb) =>
        new Promise<{ stop: () => void }>((r) => {
          resolveMic = r;
        }),
    });
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    const begin = src.beginListening();
    src.endListening(); // user releases push-to-talk before mic is ready
    resolveMic!({
      stop: () => {
        stopCalled = true;
      },
    });
    await begin;

    expect(stopCalled).toBe(true);
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.start"),
      ),
    ).toBe(false);
    expect(
      ws.sent.some(
        (m) => typeof m === "string" && m.includes("audio.end"),
      ),
    ).toBe(false);
  });

  it("dispatches state.snapshot to handlers (regression: panels-v2)", async () => {
    const { src } = freshSrc();
    const spy = vi.fn();
    src.on("state.snapshot", spy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText(
      JSON.stringify({
        type: "state.snapshot",
        system: {
          load: 12,
          tokensPerMin: 100,
          sessionId: "abc",
          modelName: "m",
        },
        memory: { contextUsed: 1, contextMax: 200000 },
        network: {
          endpoint: "ws://x",
          latencyMs: 4,
          packets: 5,
          sendQueueDepth: 0,
          sendQueueMax: 256,
        },
        tasks: { queued: 0, active: 0, done: 0 },
      }),
    );
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].system.sessionId).toBe("abc");
  });

  it("dispatches calendar.update to handlers (regression: panels-v2)", async () => {
    const { src } = freshSrc();
    const spy = vi.fn();
    src.on("calendar.update", spy);
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.receiveText(
      JSON.stringify({
        type: "calendar.update",
        entries: [{ time: "09:00", title: "Standup", durationMin: 30 }],
      }),
    );
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].entries[0].title).toBe("Standup");
  });

  it("auto-replies to server ping with pong of the same seq (regression: panels-v2)", async () => {
    const { src } = freshSrc();
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    ws.sent.length = 0;
    ws.receiveText(JSON.stringify({ type: "ping", seq: 42 }));
    const sent = ws.sent.find((m) => typeof m === "string" && m.includes("pong"));
    expect(sent).toBe(JSON.stringify({ type: "pong", seq: 42 }));
  });

  it("syncCalendar() sends calendar.sync over the wire (regression: panels-v2)", async () => {
    const { src } = freshSrc();
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;
    src.syncCalendar();
    const sent = ws.sent.find(
      (m) => typeof m === "string" && m.includes("calendar.sync"),
    );
    expect(sent).toBe(JSON.stringify({ type: "calendar.sync" }));
  });

  it("interrupt() stops local playback synchronously and sends interrupt msg", async () => {
    const { src, ctx } = freshSrc();
    const p = src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.receiveText(JSON.stringify({ type: "ready" }));
    await p;

    const samples = new Int16Array(2400);
    const idBytes = new TextEncoder().encode("a");
    const frame = new Uint8Array(2 + 1 + samples.byteLength);
    frame[0] = 0x02;
    frame[1] = 1;
    frame.set(idBytes, 2);
    frame.set(new Uint8Array(samples.buffer), 3);
    ws.receiveBinary(frame.buffer);
    expect(ctx.sources[0].stopCalls.length).toBe(0);

    src.interrupt();
    expect(ctx.sources[0].stopCalls.length).toBe(1);
    const sent = ws.sent.find(
      (m): m is string => typeof m === "string" && m.includes("interrupt"),
    );
    expect(sent).toBe(JSON.stringify({ type: "interrupt" }));
  });

  it("stop() closes the socket and prevents reconnect", () => {
    const { src } = freshSrc();
    void src.start();
    const ws = FakeWebSocket.instances[0];
    ws.open();
    src.stop();
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED);
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
