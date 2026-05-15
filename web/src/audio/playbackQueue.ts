import type { Speaker } from "@/types";

export interface PlaybackQueueOptions {
  sampleRate?: number;
}

export class PlaybackQueue {
  readonly analyser: AnalyserNode;
  private nextStart = 0;
  private active: AudioBufferSourceNode[] = [];
  private readonly inputRate: number;
  private speakerMap = new Map<string, Speaker>();
  private _currentSpeaker: Speaker | null = null;

  constructor(
    private ctx: AudioContext,
    opts?: PlaybackQueueOptions,
  ) {
    this.inputRate = opts?.sampleRate ?? 24000;
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.connect(ctx.destination);
  }

  /** Register the speaker for a given audioId before chunks arrive. */
  enqueueSentence(audioId: string, speaker: Speaker): void {
    this.speakerMap.set(audioId, speaker);
  }

  /** Called when chunks for a given audioId start playing; updates currentSpeaker. */
  markChunkPlaying(audioId: string): void {
    const speaker = this.speakerMap.get(audioId);
    if (speaker !== undefined) {
      this._currentSpeaker = speaker;
    }
  }

  /** Returns the speaker of the currently-playing chunk, or null when idle. */
  currentSpeaker(): Speaker | null {
    return this._currentSpeaker;
  }

  enqueue(_audioId: string, int16: Int16Array): number {
    if (int16.length === 0) return this.nextStart;
    const buf = this.ctx.createBuffer(1, int16.length, this.inputRate);
    const out = buf.getChannelData(0);
    for (let i = 0; i < int16.length; i++) out[i] = int16[i] / 32768;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.analyser);
    const start = Math.max(this.nextStart, this.ctx.currentTime);
    src.start(start);
    this.nextStart = start + buf.duration;
    this.active.push(src);
    src.onended = (): void => {
      const i = this.active.indexOf(src);
      if (i >= 0) this.active.splice(i, 1);
    };
    return this.nextStart;
  }

  endSentence(_audioId: string): void {
    // Reserved for future per-sentence bookkeeping; WS preserves order so no-op for now.
  }

  interrupt(): void {
    for (const s of this.active) {
      try {
        s.stop();
      } catch {
        // already ended
      }
    }
    this.active = [];
    this.nextStart = this.ctx.currentTime;
    this.speakerMap.clear();
    this._currentSpeaker = null;
  }

  destroy(): void {
    this.interrupt();
  }
}
