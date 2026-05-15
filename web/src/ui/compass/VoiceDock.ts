import { CommandHistory } from "./commandHistory";

const SPEAKER_COLOR: Record<string, string> = {
  jarvis: "var(--cyan, #48d1cc)",
  pepper: "var(--amber, #ffb86b)",
};

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
    const entries = CommandHistory.recentEntries();
    const cmdRows =
      entries.length > 0
        ? entries
            .map((entry) => {
              const dot =
                entry.speaker && SPEAKER_COLOR[entry.speaker]
                  ? `<span class="speaker-dot" aria-hidden="true" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${SPEAKER_COLOR[entry.speaker]};margin-right:6px;vertical-align:middle;flex-shrink:0;"></span>`
                  : "";
              return `<div class="cmd">${dot}${escHtml(entry.text)}</div>`;
            })
            .join("")
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
