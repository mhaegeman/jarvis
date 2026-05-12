import { CommandHistory } from "./commandHistory";

export class VoiceDock {
  private readonly el: HTMLElement;
  private visible = false;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "voice-dock";
    this.el.setAttribute("aria-label", "Voice command dock");
    parent.appendChild(this.el);
    this.renderContent();
  }

  private renderContent(): void {
    const cmds = CommandHistory.recent();
    const cmdRows =
      cmds.length > 0
        ? cmds.map((cmd) => `<div class="cmd">${escHtml(cmd)}</div>`).join("")
        : `<div class="cmd empty">no recent commands</div>`;

    this.el.innerHTML = `
      <div class="head">
        <span class="invite">listening…</span>
        <span class="hold-hint">hold Space</span>
      </div>
      <div class="recents">
        <div class="rlabel">recent</div>
        ${cmdRows}
      </div>`;
  }

  show(): void {
    if (this.visible) return;
    this.visible = true;
    // Re-render to restart stagger animations and pick up latest history
    this.renderContent();
    this.el.classList.add("open");
  }

  hide(): void {
    if (!this.visible) return;
    this.visible = false;
    this.el.classList.remove("open");
  }

  destroy(): void {
    this.el.remove();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
