export const KIND_CLIENT_MIC = 0x01;
export const KIND_SERVER_TTS = 0x02;

export function encodeMicFrame(int16: Int16Array): ArrayBuffer {
  const out = new Uint8Array(2 + int16.byteLength);
  out[0] = KIND_CLIENT_MIC;
  out[1] = 0;
  out.set(new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength), 2);
  return out.buffer;
}

export interface DecodedAudioFrame {
  kind: number;
  audioId: string;
  samples: Int16Array;
}

export function decodeAudioFrame(buf: ArrayBuffer): DecodedAudioFrame {
  const view = new Uint8Array(buf);
  if (view.byteLength < 2) throw new Error("frame too short");
  const kind = view[0];
  const idLen = view[1];
  if (view.byteLength < 2 + idLen) throw new Error("frame truncated (id)");
  const audioId = new TextDecoder().decode(view.subarray(2, 2 + idLen));
  const payloadOffset = 2 + idLen;
  const payloadLen = view.byteLength - payloadOffset;
  if (payloadLen % 2 !== 0) throw new Error("payload not Int16-aligned");
  const samples = new Int16Array(buf.slice(payloadOffset));
  return { kind, audioId, samples };
}
