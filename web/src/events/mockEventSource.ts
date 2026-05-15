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
  private llmEnded = false;

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
    this.llmEnded = false;
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
    this.currentUser = undefined;
    this.currentReply = undefined;
    if (!this.llmEnded) {
      this.llmEnded = true;
      this.emit("llm.end", undefined);
    }
  }

  syncCalendar(): void {
    // Demo mode: emit a small canned set so the panel shows something on click.
    this.emit("calendar.update", {
      entries: [
        { time: "09:00", title: "(demo) Standup", durationMin: 30, attendees: [], room: null },
        { time: "11:00", title: "(demo) Deep work", durationMin: 90, attendees: [], room: null },
        { time: "15:00", title: "(demo) Review", durationMin: 45, attendees: [], room: null },
      ],
    });
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

  sendAgentApprove(_runId: string, _choice: string): void {
    // Demo mode: no-op (agent approval not wired to backend in demo).
  }

  sendAgentCancel(_runId: string): void {
    // Demo mode: no-op.
  }

  private streamReply(): void {
    if (this.cancelled || this.currentReply === undefined) return;
    const reply = this.currentReply;

    // Emit a synthetic 2-segment dispatch.plan before tokens.
    const turnId = `t-demo-${Math.random().toString(36).slice(2, 7)}`;
    this.emit("dispatch.plan", {
      turnId,
      segments: [
        { speaker: "jarvis", tier: "balanced", mode: "chat", intent: "design" },
        { speaker: "pepper", tier: "deep", mode: "chat", intent: "implement" },
      ],
      rationale: "demo: jarvis designs, pepper implements",
    });

    // Split reply into two halves for two segments.
    const midpoint = Math.ceil(reply.length / 2);
    const seg0Text = reply.slice(0, midpoint);

    let charIdx = 0;
    const stepMs = 33;
    let segmentEmitted = false;

    const tokenStep = (): void => {
      if (this.cancelled) return;
      if (charIdx >= reply.length) {
        if (!this.llmEnded) {
          this.llmEnded = true;
          this.emit("llm.end", undefined);
        }
        return;
      }
      const next = Math.min(charIdx + 3 + Math.floor(Math.random() * 4), reply.length);
      const delta = reply.slice(charIdx, next);

      // Determine which segment we're in and emit segment_end at boundary.
      const wasInSeg0 = charIdx < midpoint;
      charIdx = next;
      const nowInSeg1 = charIdx >= midpoint;

      if (wasInSeg0 && nowInSeg1 && !segmentEmitted) {
        segmentEmitted = true;
        this.emit("llm.token", { delta: seg0Text.slice(seg0Text.length - (next - midpoint)), speaker: "jarvis", segmentIdx: 0 });
        this.emit("llm.segment_end", { speaker: "jarvis", segmentIdx: 0 });
        const remainder = reply.slice(charIdx);
        if (remainder.length > 0) {
          this.emit("llm.token", { delta: remainder.slice(0, Math.min(3, remainder.length)), speaker: "pepper", segmentIdx: 1 });
        }
      } else if (charIdx <= midpoint) {
        this.emit("llm.token", { delta, speaker: "jarvis", segmentIdx: 0 });
      } else {
        this.emit("llm.token", { delta, speaker: "pepper", segmentIdx: 1 });
      }

      this.schedule(stepMs, tokenStep);
    };
    tokenStep();

    // Mark end of second segment before llm.end.
    const seg1EndMs = Math.ceil(reply.length / 3) * stepMs + 100;
    this.schedule(seg1EndMs, () => {
      if (this.cancelled) return;
      this.emit("llm.segment_end", { speaker: "pepper", segmentIdx: 1 });
    });

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
