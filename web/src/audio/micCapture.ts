import { rms } from "./analyzer";

export interface MicCapture {
  start(): Promise<void>;
  stop(): void;
  /** Subscribe to amplitude (0..1) updates ~60Hz. Returns unsubscribe. */
  onAmplitude(cb: (level: number) => void): () => void;
}

export type MicError =
  | { kind: "denied" }
  | { kind: "unsupported" }
  | { kind: "device" }
  | { kind: "unknown"; cause: unknown };

export async function probeMicSupport(): Promise<true | MicError> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    return { kind: "unsupported" };
  }
  return true;
}

export function createMicCapture(): MicCapture {
  let stream: MediaStream | undefined;
  let ctx: AudioContext | undefined;
  let raf = 0;
  const subs = new Set<(level: number) => void>();

  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      const tick = (): void => {
        analyser.getFloatTimeDomainData(buf);
        const level = Math.min(1, rms(buf) * 4); // perceptual scaling
        subs.forEach((s) => s(level));
        raf = requestAnimationFrame(tick);
      };
      tick();
    },
    stop() {
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      stream = undefined;
      void ctx?.close();
      ctx = undefined;
      subs.clear();
    },
    onAmplitude(cb) {
      subs.add(cb);
      return () => {
        subs.delete(cb);
      };
    },
  };
}
