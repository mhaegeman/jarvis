export interface BottombarState {
  tokensPerMin: number;
  load: number;
  uptimeMs: number;
}

function fmtUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export class Bottombar {
  private readonly el: HTMLElement;
  private statsEl: HTMLElement | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "bottombar";
    this.el.innerHTML = `
      <div class="left">
        <span class="pill"><span class="k">⌘</span> space speak</span>
        <span class="pill"><span class="k">⌘ K</span> command</span>
        <span class="pill"><span class="k">⌘ E</span> code</span>
        <span class="pill"><span class="k">esc</span> close</span>
      </div>
      <div class="right" id="bottombar-stats"></div>`;
    parent.appendChild(this.el);
    this.statsEl = this.el.querySelector("#bottombar-stats");
  }

  render(state: BottombarState): void {
    if (!this.statsEl) return;
    this.statsEl.textContent =
      `${state.tokensPerMin} tok/m · load ${state.load.toFixed(2)} · up ${fmtUptime(state.uptimeMs)}`;
  }

  destroy(): void {
    this.el.remove();
  }
}
