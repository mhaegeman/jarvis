import type { ConvState } from "@/types";

/** State-driven ribbon below the orrery. Handles transcript streaming. */
export class UnderCore {
  private readonly el: HTMLElement;
  private streamInterval: ReturnType<typeof setInterval> | null = null;
  private streamTarget = "";
  private streamCurrent = "";
  private lastState: ConvState = "idle";

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "under-core";
    this.el.setAttribute("aria-live", "polite");
    parent.appendChild(this.el);
  }

  render(state: ConvState, text: string): void {
    if (state !== this.lastState) {
      this.stopStream();
      this.lastState = state;
    }

    if (state === "idle" || state === "thinking") {
      this.el.innerHTML = `<div style="font-family:var(--serif);font-style:italic;font-size:16px;font-weight:300;color:var(--ink-3);">
        ${state === "thinking" ? "thinking…" : "hold Space to speak · Ctrl K command"}
      </div>`;
      return;
    }

    if (state === "listening") {
      this.el.innerHTML = `<div style="font-family:var(--serif);font-style:italic;font-size:16px;font-weight:300;color:var(--accent);">listening…</div>`;
      return;
    }

    if (state === "speaking") {
      if (text !== this.streamTarget) {
        this.streamTarget = text;
        const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (prefersReduced) {
          this.streamCurrent = text;
          this.renderSpeaking();
        } else if (!this.streamInterval) {
          this.startStream();
        }
      }
    }
  }

  private startStream(): void {
    this.streamInterval = setInterval(() => {
      if (this.streamCurrent.length >= this.streamTarget.length) {
        this.stopStream();
        return;
      }
      this.streamCurrent = this.streamTarget.slice(0, this.streamCurrent.length + 2);
      this.renderSpeaking();
    }, 28);
  }

  private stopStream(): void {
    if (this.streamInterval !== null) {
      clearInterval(this.streamInterval);
      this.streamInterval = null;
    }
    this.streamCurrent = "";
  }

  private renderSpeaking(): void {
    const bars = Array.from({ length: 22 }, (_, i) => {
      const h = 4 + Math.abs(Math.sin(Date.now() / 300 + i * 0.6)) * 18;
      return `<span style="height:${h.toFixed(1)}px"></span>`;
    }).join("");

    this.el.innerHTML = `
      <div class="wave-bars">${bars}</div>
      <div class="transcript">${escapeHtml(this.streamCurrent)}<span class="caret"></span></div>`;
  }

  destroy(): void {
    this.stopStream();
    this.el.remove();
  }
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
