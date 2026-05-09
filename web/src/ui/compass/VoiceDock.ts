/**
 * Voice dock — appears while Space is held.
 * Shows a serif "listening…" invite and a stagger-rise list of recent commands.
 * VoiceDock owns its DOM element but delegates show/hide to CompassApp which
 * already handles the Space keydown/keyup lifecycle.
 *
 * TODO: wire recentCmds from command history store instead of static stub.
 * Interface: CommandHistory { recent(): string[] }
 */

// TODO: replace with real command history source
const RECENT_COMMANDS: string[] = [
  "What's on my calendar this afternoon?",
  "Summarise the last stand-up notes",
  "Open the PR for the compass branch",
  "Set a timer for fifteen minutes",
];

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
    const cmdRows = RECENT_COMMANDS.map(
      (cmd) => `<div class="cmd">${escHtml(cmd)}</div>`,
    ).join("");

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
    // Re-render to restart stagger animations
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
