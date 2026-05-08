export function float32ToInt16(f32: Float32Array): Int16Array {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const v = Math.max(-1, Math.min(1, f32[i]));
    out[i] = v < 0 ? Math.round(v * 32768) : Math.round(v * 32767);
  }
  return out;
}

export interface MicWorkletHandle {
  stop(): void;
}

export async function startMicWorklet(
  ctx: AudioContext,
  source: MediaStreamAudioSourceNode,
  onFrame: (int16: Int16Array) => void,
): Promise<MicWorkletHandle> {
  await ctx.audioWorklet.addModule("/mic-processor.js");
  const node = new AudioWorkletNode(ctx, "mic-processor");
  node.port.onmessage = (ev: MessageEvent<Float32Array>): void => {
    onFrame(float32ToInt16(ev.data));
  };
  source.connect(node);
  return {
    stop(): void {
      try {
        source.disconnect(node);
      } catch {
        // already disconnected
      }
      node.port.close();
    },
  };
}
