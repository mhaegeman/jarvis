import { Waveform } from "./Waveform";
import { Transcript } from "./Transcript";
import type { ConvState, Speaker } from "@/types";

export const SPEAKER_TINT: Record<Speaker, string> = {
  jarvis: "#0bc5ea",
  pepper: "#ffb86b",
};

export class Centerpiece {
  private root: HTMLElement;
  private waveform: Waveform;
  private transcript: Transcript;
  private title: HTMLElement;
  private scan: HTMLElement;

  constructor(rootSelector: string) {
    const el = document.querySelector<HTMLElement>(rootSelector);
    if (!el) throw new Error(`Centerpiece root missing: ${rootSelector}`);
    this.root = el;
    this.root.classList.add("panel", "centerpiece");
    this.root.innerHTML = `
      <div class="scan"></div>
      <div data-slot="waveform" class="waveform-host"></div>
      <div class="centerpiece-content">
        <h2 class="centerpiece-title">Standing by.</h2>
        <div data-slot="transcript"></div>
      </div>
    `;
    this.waveform = new Waveform('[data-slot="waveform"]');
    this.transcript = new Transcript('[data-slot="transcript"]');
    this.transcript.mount({ text: "" });
    this.title = this.root.querySelector(".centerpiece-title") as HTMLElement;
    this.scan = this.root.querySelector(".scan") as HTMLElement;
  }

  setTitle(text: string): void {
    this.title.textContent = text;
  }
  streamReply(text: string, ms = 26): void {
    this.transcript.stream(text, ms);
  }
  appendToken(t: string): void {
    this.transcript.appendToken(t);
  }
  clearTranscript(): void {
    this.transcript.clear();
  }
  interruptTranscript(): void {
    this.transcript.interrupt();
  }

  setStateClass(state: ConvState): void {
    this.root.dataset.state = state;
    this.scan.dataset.state = state;
  }

  /**
   * Set the centerpiece tint colour based on the currently-speaking persona.
   * Passes `null` to clear the tint (revert to the default ink colour).
   * The CSS transition on `--centerpiece-tint` handles the 120ms crossfade.
   */
  setTint(speaker: Speaker | null): void {
    if (speaker === null) {
      this.root.style.removeProperty("--centerpiece-tint");
    } else {
      this.root.style.setProperty("--centerpiece-tint", SPEAKER_TINT[speaker]);
    }
  }

  renderFrame(amplitude: number, modeHint: ConvState): void {
    this.waveform.render({ amplitude, modeHint });
  }
}
