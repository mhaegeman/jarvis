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
