import { describe, it, expect, beforeEach } from "vitest";
import { PlaybackQueue } from "@/audio/playbackQueue";
import { FakeAudioContext } from "./_fakes";

describe("PlaybackQueue.currentSpeaker", () => {
  let ctx: FakeAudioContext;
  let q: PlaybackQueue;

  beforeEach(() => {
    ctx = new FakeAudioContext();
    q = new PlaybackQueue(ctx as unknown as AudioContext);
  });

  it("returns null when nothing has played", () => {
    expect(q.currentSpeaker()).toBeNull();
  });

  it("returns null after construction even if chunks are enqueueable", () => {
    // No enqueueSentence called yet
    expect(q.currentSpeaker()).toBeNull();
  });

  it("returns the speaker after markChunkPlaying is called", () => {
    q.enqueueSentence("a1", "jarvis");
    q.markChunkPlaying("a1");
    expect(q.currentSpeaker()).toBe("jarvis");
  });

  it("updates speaker when a later audioId starts playing", () => {
    q.enqueueSentence("a1", "jarvis");
    q.enqueueSentence("a2", "pepper");
    q.markChunkPlaying("a1");
    expect(q.currentSpeaker()).toBe("jarvis");
    q.markChunkPlaying("a2");
    expect(q.currentSpeaker()).toBe("pepper");
  });

  it("returns null after interrupt clears state", () => {
    q.enqueueSentence("a1", "jarvis");
    q.markChunkPlaying("a1");
    expect(q.currentSpeaker()).toBe("jarvis");
    q.interrupt();
    expect(q.currentSpeaker()).toBeNull();
  });

  it("returns null for unknown audioId in markChunkPlaying", () => {
    q.markChunkPlaying("unknown");
    expect(q.currentSpeaker()).toBeNull();
  });

  it("clears when active queue empties naturally (no interrupt)", () => {
    // Regression: previously the speaker persisted past the end of playback,
    // so the tint stayed amber/cyan into the idle state.
    q.enqueueSentence("a1", "pepper");
    q.enqueue("a1", new Int16Array([1, 2, 3, 4]));
    q.markChunkPlaying("a1");
    expect(q.currentSpeaker()).toBe("pepper");
    // Fire onended on every active source — simulates natural playback end.
    for (const src of ctx.sources) src.onended?.();
    expect(q.currentSpeaker()).toBeNull();
  });
});
