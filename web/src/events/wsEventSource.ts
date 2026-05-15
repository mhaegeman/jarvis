import type { EventSource as IEventSource } from "@/events/eventSource";
import type {
  EventName,
  EventHandler,
  EventMap,
  TelemetryEvent,
  StateSnapshot,
  CalendarUpdate,
  Speaker,
} from "@/types";
import {
  decodeAudioFrame,
  encodeMicFrame,
  KIND_SERVER_TTS,
} from "@/audio/wsCodec";
import { PlaybackQueue } from "@/audio/playbackQueue";
import {
  startMicWorklet,
  type MicWorkletHandle,
} from "@/audio/micWorklet";

export interface WSEventSourceOpts {
  url: string;
  audioCtx?: AudioContext;
  clientVersion?: string;
  micFactory?: (
    ctx: AudioContext,
    onFrame: (int16: Int16Array) => void,
  ) => Promise<MicWorkletHandle>;
  micSource?: () => Promise<MediaStreamAudioSourceNode>;
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
  private mic: MicWorkletHandle | null = null;
  private listenAbort: AbortController | null = null;
  private audioStartSent = false;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private sentenceEndTimes = new Map<string, number>();
  private ttsEndTimers = new Set<ReturnType<typeof setTimeout>>();
  private static BACKOFF_S = [1, 2, 4, 8, 16, 30];

  constructor(private opts: WSEventSourceOpts) {
    if (opts.audioCtx) this.playback = new PlaybackQueue(opts.audioCtx);
  }

  get analyser(): AnalyserNode | null {
    return this.playback?.analyser ?? null;
  }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    let set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) {
      set = new Set<EventHandler<E>>();
      (this.handlers as Record<string, Set<EventHandler<EventName>>>)[event] =
        set as unknown as Set<EventHandler<EventName>>;
    }
    set.add(handler);
    const target = set;
    return (): void => {
      target.delete(handler);
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
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    for (const t of this.ttsEndTimers) clearTimeout(t);
    this.ttsEndTimers.clear();
    this.sentenceEndTimes.clear();
    this.ws?.close();
    this.ws = null;
  }

  async beginListening(): Promise<void> {
    if (!this.opts.audioCtx) throw new Error("audioCtx required for listening");
    // Defer `audio.start` until the mic is actually capturing — if mic setup
    // fails or is cancelled, the server is never told we're recording.
    this.listenAbort?.abort();
    const abort = new AbortController();
    this.listenAbort = abort;
    const onFrame = (int16: Int16Array): void => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(encodeMicFrame(int16));
      }
    };
    let handle: MicWorkletHandle;
    if (this.opts.micFactory) {
      handle = await this.opts.micFactory(this.opts.audioCtx, onFrame);
    } else {
      if (!this.opts.micSource) {
        throw new Error("micSource required when micFactory absent");
      }
      const source = await this.opts.micSource();
      handle = await startMicWorklet(this.opts.audioCtx, source, onFrame);
    }
    if (abort.signal.aborted) {
      // endListening() ran while we were awaiting mic setup — discard.
      handle.stop();
      return;
    }
    this.mic = handle;
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "audio.start",
          sampleRate: 16000,
          format: "pcm_s16le",
        }),
      );
      this.audioStartSent = true;
    }
  }

  endListening(): void {
    // Cancel any in-flight beginListening so a quick press/release pair
    // never leaves the server in a half-started state.
    this.listenAbort?.abort();
    this.listenAbort = null;
    this.mic?.stop();
    this.mic = null;
    if (this.audioStartSent && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "audio.end" }));
    }
    this.audioStartSent = false;
  }

  sendText(content: string): void {
    this.ws?.send(JSON.stringify({ type: "text", content }));
  }

  interrupt(): void {
    this.playback?.interrupt();
    for (const t of this.ttsEndTimers) clearTimeout(t);
    this.ttsEndTimers.clear();
    this.sentenceEndTimes.clear();
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "interrupt" }));
    }
  }

  syncCalendar(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "calendar.sync" }));
    }
  }

  sendAgentApprove(runId: string, choice: "approve" | "deny" | "approve_session"): void {
    this.ws?.send(JSON.stringify({ type: "agent.approve", runId, choice }));
  }

  sendAgentCancel(runId: string): void {
    this.ws?.send(JSON.stringify({ type: "agent.cancel", runId }));
  }

  currentSpeaker(): Speaker | null {
    return this.playback?.currentSpeaker() ?? null;
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
      if (this.reconnectAttempt > 0) {
        this.emit("telemetry", {
          ts: Date.now(),
          level: "ok",
          message: "reconnected",
        });
        this.reconnectAttempt = 0;
      }
    });
    ws.addEventListener("message", (ev) => {
      const data = (ev as MessageEvent).data;
      if (typeof data === "string") this.handleJson(data);
      else this.handleBinary(data as ArrayBuffer);
    });
    ws.addEventListener("close", () => {
      if (this.closedByUser) return;
      this.playback?.interrupt();
      this.mic?.stop();
      this.mic = null;
      for (const t of this.ttsEndTimers) clearTimeout(t);
      this.ttsEndTimers.clear();
      this.sentenceEndTimes.clear();
      this.scheduleReconnect();
    });
    ws.addEventListener("error", () => {
      if (this.readyReject && !this.closedByUser) {
        this.readyReject(new Error("ws error"));
        this.readyReject = null;
        this.readyResolve = null;
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.closedByUser) return;
    if (this.reconnectTimer) return;
    const idx = Math.min(
      this.reconnectAttempt,
      WSEventSource.BACKOFF_S.length - 1,
    );
    const delayMs = WSEventSource.BACKOFF_S[idx] * 1000;
    this.reconnectAttempt++;
    this.emit("telemetry", {
      ts: Date.now(),
      level: "warn",
      message: `reconnecting (attempt ${this.reconnectAttempt})…`,
    });
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.openSocket();
    }, delayMs);
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
      case "llm.token": {
        const tokenPayload: EventMap["llm.token"] = { delta: String(msg.delta ?? "") };
        if (msg.speaker !== undefined) tokenPayload.speaker = msg.speaker as Speaker;
        if (msg.segmentIdx !== undefined) tokenPayload.segmentIdx = Number(msg.segmentIdx);
        this.emit("llm.token", tokenPayload);
        return;
      }
      case "llm.segment_end":
        this.emit("llm.segment_end", {
          speaker: msg.speaker as Speaker,
          segmentIdx: Number(msg.segmentIdx),
        });
        return;
      case "llm.end":
        this.emit("llm.end", undefined);
        return;
      case "tts.sentence": {
        const sentPayload: EventMap["tts.sentence"] = {
          text: String(msg.text ?? ""),
          audioId: String(msg.audioId ?? ""),
        };
        if (msg.speaker !== undefined) sentPayload.speaker = msg.speaker as Speaker;
        // Register speaker for the playback queue so currentSpeaker() tracks audio.
        if (sentPayload.speaker !== undefined && this.playback) {
          this.playback.enqueueSentence(sentPayload.audioId, sentPayload.speaker);
        }
        this.emit("tts.sentence", sentPayload);
        return;
      }
      case "dispatch.plan":
        this.emit("dispatch.plan", msg as unknown as EventMap["dispatch.plan"]);
        return;
      case "agent.start":
        this.emit("agent.start", msg as unknown as EventMap["agent.start"]);
        return;
      case "agent.step":
        this.emit("agent.step", msg as unknown as EventMap["agent.step"]);
        return;
      case "agent.approval":
        this.emit("agent.approval", msg as unknown as EventMap["agent.approval"]);
        return;
      case "agent.progress":
        this.emit("agent.progress", msg as unknown as EventMap["agent.progress"]);
        return;
      case "agent.end":
        this.emit("agent.end", msg as unknown as EventMap["agent.end"]);
        return;
      case "tts.end": {
        const audioId = String(msg.audioId ?? "");
        const scheduledEnd = this.sentenceEndTimes.get(audioId) ?? 0;
        this.sentenceEndTimes.delete(audioId);
        const remainingMs =
          scheduledEnd > 0
            ? Math.max(
                0,
                (scheduledEnd - (this.opts.audioCtx?.currentTime ?? 0)) * 1000,
              )
            : 0;
        if (remainingMs === 0) {
          this.emit("tts.end", { audioId });
        } else {
          const timer = setTimeout(() => {
            this.ttsEndTimers.delete(timer);
            this.emit("tts.end", { audioId });
          }, remainingMs);
          this.ttsEndTimers.add(timer);
        }
        return;
      }
      case "telemetry": {
        const t: TelemetryEvent = {
          ts: Date.now(),
          level: (msg.level as TelemetryEvent["level"]) ?? "info",
          message: String(msg.message ?? ""),
        };
        this.emit("telemetry", t);
        return;
      }
      case "state.snapshot":
        this.emit(
          "state.snapshot",
          msg as unknown as StateSnapshot,
        );
        return;
      case "calendar.update":
        this.emit(
          "calendar.update",
          msg as unknown as CalendarUpdate,
        );
        return;
      case "ping":
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: "pong", seq: msg.seq }));
        }
        return;
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
    this.playback?.markChunkPlaying(frame.audioId);
    const scheduledEnd = this.playback?.enqueue(frame.audioId, frame.samples);
    if (scheduledEnd !== undefined) {
      this.sentenceEndTimes.set(frame.audioId, scheduledEnd);
    }
  }
}
