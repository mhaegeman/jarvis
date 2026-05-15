import type { ConvState, Speaker } from "@/types";
import { SPEAKER_TINT } from "@/ui/Centerpiece";

export interface TopbarState {
  convState: ConvState;
  currentSpeaker?: Speaker | null;
}

export class Topbar {
  private readonly el: HTMLElement;
  private clockInterval: ReturnType<typeof setInterval> | null = null;
  private clockEl: HTMLElement | null = null;
  private jarvisChip: HTMLElement | null = null;
  private pepperChip: HTMLElement | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "topbar";
    this.el.innerHTML = `
      <div class="brand">
        <div class="persona-chips">
          <button class="persona-chip" data-speaker="jarvis" style="border-color:${SPEAKER_TINT.jarvis}">
            Jarvis
          </button>
          <button class="persona-chip" data-speaker="pepper" style="border-color:${SPEAKER_TINT.pepper}">
            Pepper
          </button>
        </div>
        <span class="v">v0.4</span>
      </div>
      <div class="meta">
        <div class="statepill" id="compass-statepill">
          <span class="dot"></span>
          <span class="label-text">idle</span>
        </div>
        <div class="clock" id="compass-clock"></div>
      </div>`;
    parent.appendChild(this.el);
    this.clockEl = this.el.querySelector("#compass-clock");
    this.jarvisChip = this.el.querySelector('[data-speaker="jarvis"]');
    this.pepperChip = this.el.querySelector('[data-speaker="pepper"]');

    // Click handlers — stub: log the pin intent (full "pin next turn" is a follow-up)
    this.jarvisChip?.addEventListener("click", () => {
      console.log("pin: jarvis");
    });
    this.pepperChip?.addEventListener("click", () => {
      console.log("pin: pepper");
    });

    this.startClock();
  }

  private startClock(): void {
    const tick = (): void => {
      if (!this.clockEl) return;
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      const s = String(now.getSeconds()).padStart(2, "0");
      this.clockEl.textContent = `${h}:${m}:${s}`;
    };
    tick();
    this.clockInterval = setInterval(tick, 1000);
  }

  render(state: TopbarState): void {
    const pill = this.el.querySelector(".statepill")!;
    const labelEl = this.el.querySelector(".label-text")!;
    const live = state.convState === "listening" || state.convState === "speaking";
    pill.classList.toggle("live", live);
    labelEl.textContent = state.convState;

    // Update persona chips: pulse the active speaker
    const speaker = state.currentSpeaker ?? null;
    this.jarvisChip?.classList.toggle("active", speaker === "jarvis");
    this.pepperChip?.classList.toggle("active", speaker === "pepper");
  }

  destroy(): void {
    if (this.clockInterval !== null) clearInterval(this.clockInterval);
    this.el.remove();
  }
}
