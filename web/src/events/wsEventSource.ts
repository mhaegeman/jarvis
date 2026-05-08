import type { EventSource as IEventSource } from "@/events/eventSource";
import type {
  EventName,
  EventHandler,
  EventMap,
  TelemetryEvent,
} from "@/types";
import { decodeAudioFrame, KIND_SERVER_TTS } from "@/audio/wsCodec";
import { PlaybackQueue } from "@/audio/playbackQueue";

export interface WSEventSourceOpts {
  url: string;
  audioCtx?: AudioContext;
  clientVersion?: string;
}

type Handlers = { [K in EventName]?: Set<EventHandler<K>> };

export class WSEventSource implements IEventSource {
  private ws: WebSocket | null = null;
  private handlers: Handlers = {};
  private readyResolve: (() => void) | null = null;
  private readyReject: ((err: Error) => void) | null = null;
  private readyPromise: Promise<void> | null = null;
  private closedByUser = false;
  private playback: PlaybackQueue | null = null;

  constructor(private opts: WSEventSourceOpts) {
    if (opts.audioCtx) this.playback = new PlaybackQueue(opts.audioCtx);
  }

  get analyser(): AnalyserNode | null {
    return this.playback?.analyser ?? null;
  }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    const set = (this.handlers[event] ??= new Set()) as Set<EventHandler<E>>;
    set.add(handler);
    return (): void => {
      set.delete(handler);
    };
  }

  private emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) return;
    for (const fn of set) fn(payload);
  }

  start(): Promise<void> {
    if (this.readyPromise) return this.readyPromise;
    this.readyPromise = new Promise<void>((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
    });
    this.openSocket();
    return this.readyPromise;
  }

  stop(): void {
    this.closedByUser = true;
    this.ws?.close();
    this.ws = null;
  }

  beginListening(): void {
    /* implemented in Task 7 */
  }

  endListening(): void {
    /* implemented in Task 7 */
  }

  sendText(content: string): void {
    this.ws?.send(JSON.stringify({ type: "text", content }));
  }

  interrupt(): void {
    /* implemented in Task 8 */
  }

  private openSocket(): void {
    const ws = new WebSocket(this.opts.url);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.addEventListener("open", () => {
      ws.send(
        JSON.stringify({
          type: "hello",
          clientVersion: this.opts.clientVersion ?? "spec-03",
        }),
      );
    });
    ws.addEventListener("message", (ev) => {
      const data = (ev as MessageEvent).data;
      if (typeof data === "string") this.handleJson(data);
      else this.handleBinary(data as ArrayBuffer);
    });
    ws.addEventListener("close", () => {
      /* reconnect added in Task 9 */
    });
    ws.addEventListener("error", () => {
      if (this.readyReject && !this.closedByUser) {
        this.readyReject(new Error("ws error"));
        this.readyReject = null;
        this.readyResolve = null;
      }
    });
  }

  private handleJson(raw: string): void {
    let msg: { type?: string } & Record<string, unknown>;
    try {
      msg = JSON.parse(raw) as { type?: string } & Record<string, unknown>;
    } catch {
      this.emit("error", {
        code: "client.bad_message",
        message: raw.slice(0, 80),
      });
      return;
    }
    switch (msg.type) {
      case "ready":
        this.readyResolve?.();
        this.readyResolve = null;
        this.readyReject = null;
        return;
      case "stt.partial":
        this.emit("stt.partial", { text: String(msg.text ?? "") });
        return;
      case "stt.final":
        this.emit("stt.final", { text: String(msg.text ?? "") });
        return;
      case "llm.token":
        this.emit("llm.token", { delta: String(msg.delta ?? "") });
        return;
      case "llm.end":
        this.emit("llm.end", undefined);
        return;
      case "tts.sentence":
        this.emit("tts.sentence", {
          text: String(msg.text ?? ""),
          audioId: String(msg.audioId ?? ""),
        });
        return;
      case "tts.end":
        this.emit("tts.end", { audioId: String(msg.audioId ?? "") });
        return;
      case "telemetry": {
        const t: TelemetryEvent = {
          ts: Date.now(),
          level: (msg.level as TelemetryEvent["level"]) ?? "info",
          message: String(msg.message ?? ""),
        };
        this.emit("telemetry", t);
        return;
      }
      case "error":
        this.emit("error", {
          code: String(msg.code ?? "unknown"),
          message: String(msg.message ?? ""),
        });
        return;
      default:
        this.emit("telemetry", {
          ts: Date.now(),
          level: "warn",
          message: `unknown msg ${String(msg.type)}`,
        });
    }
  }

  private handleBinary(buf: ArrayBuffer): void {
    let frame;
    try {
      frame = decodeAudioFrame(buf);
    } catch (e) {
      this.emit("error", { code: "client.bad_frame", message: String(e) });
      return;
    }
    if (frame.kind !== KIND_SERVER_TTS) {
      this.emit("error", {
        code: "client.bad_frame",
        message: `unexpected kind ${frame.kind}`,
      });
      return;
    }
    const f32 = new Float32Array(frame.samples.length);
    for (let i = 0; i < frame.samples.length; i++)
      f32[i] = frame.samples[i] / 32768;
    this.emit("tts.audioChunk", { audioId: frame.audioId, samples: f32 });
    this.playback?.enqueue(frame.audioId, frame.samples);
  }
}
