import type { ConvState } from "@/types";

export interface TopbarState {
  convState: ConvState;
}

export class Topbar {
  private readonly el: HTMLElement;
  private clockInterval: ReturnType<typeof setInterval> | null = null;
  private clockEl: HTMLElement | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "topbar";
    this.el.innerHTML = `
      <div class="brand">
        Jarvis
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
  }

  destroy(): void {
    if (this.clockInterval !== null) clearInterval(this.clockInterval);
    this.el.remove();
  }
}
