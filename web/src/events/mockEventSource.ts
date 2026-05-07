import type { EventSource } from "./eventSource";
import type { EventName, EventMap, EventHandler, TtsAudioChunk } from "@/types";
import { pickScenario, splitSentences, type Scenario } from "./scenarios";

interface Options {
  scenarioOverride?: Scenario;
}

interface PendingTimer {
  id: ReturnType<typeof setTimeout>;
}

export class MockEventSource implements EventSource {
  private handlers: { [K in EventName]?: Set<EventHandler<K>> } = {};
  private started = false;
  private currentUser: string | undefined;
  private currentReply: string | undefined;
  private timers = new Set<PendingTimer>();
  private cancelled = false;

  constructor(private opts: Options = {}) {}

  async start(): Promise<void> {
    this.started = true;
    this.cancelled = false;
    await Promise.resolve();
    this.emit("ready", undefined);
  }

  stop(): void {
    this.started = false;
    this.cancelAll();
    this.handlers = {};
  }

  beginListening(): void {
    if (!this.started) return;
    this.cancelled = false;
    const scenario = this.opts.scenarioOverride ?? pickScenario();
    this.currentUser = scenario.user;
    this.currentReply = scenario.reply;
    const words = scenario.user.split(" ");
    let acc = "";
    words.forEach((w, i) => {
      this.schedule(80 + i * 100, () => {
        acc = acc ? `${acc} ${w}` : w;
        this.emit("stt.partial", { text: acc });
      });
    });
  }

  endListening(): void {
    if (!this.started || this.currentUser === undefined) return;
    const user = this.currentUser;
    this.schedule(150, () => this.emit("stt.final", { text: user }));
    this.schedule(900, () => this.streamReply());
  }

  sendText(text: string): void {
    if (!this.started) return;
    this.currentReply = pickScenario().reply;
    this.schedule(0, () => this.emit("stt.final", { text }));
    this.schedule(400, () => this.streamReply());
  }

  interrupt(): void {
    this.cancelled = true;
    this.cancelAll();
    this.emit("llm.end", undefined);
  }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    let set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) {
      set = new Set();
      this.handlers[event] = set as never;
    }
    set.add(handler);
    return () => {
      set?.delete(handler);
    };
  }

  private streamReply(): void {
    if (this.cancelled || this.currentReply === undefined) return;
    const reply = this.currentReply;
    let charIdx = 0;
    const stepMs = 33;
    const tokenStep = (): void => {
      if (this.cancelled) return;
      if (charIdx >= reply.length) {
        this.emit("llm.end", undefined);
        return;
      }
      const next = Math.min(charIdx + 3 + Math.floor(Math.random() * 4), reply.length);
      const delta = reply.slice(charIdx, next);
      charIdx = next;
      this.emit("llm.token", { delta });
      this.schedule(stepMs, tokenStep);
    };
    tokenStep();

    const sentences = splitSentences(reply);
    let cumulative = 0;
    for (const [i, sent] of sentences.entries()) {
      const audioId = `s${i}-${Math.random().toString(36).slice(2, 7)}`;
      cumulative += 200 + sent.length * 30;
      this.schedule(cumulative, () => {
        if (this.cancelled) return;
        this.emit("tts.sentence", { text: sent, audioId });
        const totalChunks = 6;
        for (let c = 0; c < totalChunks; c++) {
          this.schedule(c * 90, () => {
            if (this.cancelled) return;
            const samples = new Float32Array(2048);
            const payload: TtsAudioChunk = { audioId, samples };
            this.emit("tts.audioChunk", payload);
          });
        }
        this.schedule(totalChunks * 90 + 80, () => {
          if (this.cancelled) return;
          this.emit("tts.end", { audioId });
        });
      });
    }
  }

  private schedule(ms: number, fn: () => void): void {
    const timer: PendingTimer = {
      id: setTimeout(() => {
        this.timers.delete(timer);
        if (!this.cancelled) fn();
      }, ms),
    };
    this.timers.add(timer);
  }

  private cancelAll(): void {
    this.timers.forEach((t) => clearTimeout(t.id));
    this.timers.clear();
  }

  protected emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    if (!this.started && event !== "ready") return;
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    set?.forEach((h) => h(payload));
  }
}
