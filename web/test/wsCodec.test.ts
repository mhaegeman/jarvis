import { describe, it, expect } from "vitest";
import {
  KIND_CLIENT_MIC,
  KIND_SERVER_TTS,
  encodeMicFrame,
  decodeAudioFrame,
} from "@/audio/wsCodec";

describe("wsCodec", () => {
  it("encodes mic frame with empty audioId", () => {
    const samples = new Int16Array([0, 1, -1, 32767, -32768]);
    const buf = new Uint8Array(encodeMicFrame(samples));
    expect(buf[0]).toBe(KIND_CLIENT_MIC);
    expect(buf[1]).toBe(0);
    expect(buf.byteLength).toBe(2 + samples.byteLength);
  });

  it("round-trips a TTS frame with audioId", () => {
    const samples = new Int16Array([100, -200, 300]);
    const audioId = "s0-abcdef";
    const idBytes = new TextEncoder().encode(audioId);
    const out = new Uint8Array(2 + idBytes.byteLength + samples.byteLength);
    out[0] = KIND_SERVER_TTS;
    out[1] = idBytes.byteLength;
    out.set(idBytes, 2);
    out.set(new Uint8Array(samples.buffer), 2 + idBytes.byteLength);
    const decoded = decodeAudioFrame(out.buffer);
    expect(decoded.kind).toBe(KIND_SERVER_TTS);
    expect(decoded.audioId).toBe(audioId);
    expect(Array.from(decoded.samples)).toEqual([100, -200, 300]);
  });

  it("rejects truncated frames", () => {
    expect(() => decodeAudioFrame(new Uint8Array([0x02]).buffer)).toThrow();
    const short = new Uint8Array([0x02, 5, 0x61]);
    expect(() => decodeAudioFrame(short.buffer)).toThrow();
  });

  it("rejects payload not aligned to Int16", () => {
    const odd = new Uint8Array([0x01, 0, 0x00, 0x01, 0x02]);
    expect(() => decodeAudioFrame(odd.buffer)).toThrow();
  });
});
