import type { CompassCalendarEntry } from "@/compass/types";

export class NorthCalendar {
  private readonly el: HTMLElement;
  private onClickCb: (() => void) | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "zone north";
    this.el.setAttribute("role", "region");
    this.el.setAttribute("aria-label", "Calendar");
    parent.appendChild(this.el);
    this.el.addEventListener("click", () => this.onClickCb?.());
  }

  onClick(cb: () => void): void {
    this.onClickCb = cb;
  }

  render(entries: CompassCalendarEntry[]): void {
    const today = new Date();
    const dateStr = today.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

    const rows = entries
      .slice(0, 4)
      .map(
        (e) => `
        <div class="zone-row ${e.state}">
          <span class="when">${escHtml(e.time)}</span>
          <span class="what">${escHtml(e.title)}</span>
          <span class="meta">${escHtml(e.dur)}</span>
        </div>`,
      )
      .join("");

    const emptyMsg =
      entries.length === 0
        ? `<div style="font-family:var(--mono);font-size:10.5px;color:var(--ink-3);padding:6px 0;">no events today</div>`
        : "";

    this.el.innerHTML = `
      <div class="zone-head">
        <span class="label-tag">North · Calendar</span>
        <span class="title">${escHtml(dateStr)}</span>
        <span class="meta">${entries.length} events</span>
      </div>
      ${rows}${emptyMsg}
      <div class="peek">Click to open full calendar view</div>`;
  }

  destroy(): void {
    this.el.remove();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
