import type { CompassTask } from "@/compass/types";

export class WestTasks {
  private readonly el: HTMLElement;
  private onClickCb: (() => void) | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "zone west";
    this.el.setAttribute("role", "region");
    this.el.setAttribute("aria-label", "Agent tasks");
    parent.appendChild(this.el);
    this.el.addEventListener("click", () => this.onClickCb?.());
  }

  onClick(cb: () => void): void {
    this.onClickCb = cb;
  }

  render(tasks: CompassTask[]): void {
    const running = tasks.filter((t) => t.state === "run").length;
    const queued  = tasks.filter((t) => t.state === "queue").length;
    const done    = tasks.filter((t) => t.state === "done").length;
    const active  = tasks.find((t) => t.state === "run");

    const rows = tasks
      .slice(0, 4)
      .map(
        (t) => `
        <div class="zone-row ${t.state}">
          <span class="dotmark"></span>
          <span class="what">${escHtml(t.label)}</span>
          <span class="meta">${escHtml(t.meta)}</span>
        </div>`,
      )
      .join("");

    const meter = active
      ? `<div style="margin-top:8px;">
          <div class="meter warm"><i style="width:${active.pct}%"></i></div>
          <div style="font-family:var(--mono);font-size:9.5px;color:var(--ink-3);margin-top:4px;">${escHtml(active.meta)} · running</div>
        </div>`
      : "";

    this.el.innerHTML = `
      <div class="zone-head">
        <span class="label-tag">West · Tasks</span>
        <span class="title">${running} running</span>
        <span class="meta">${queued} queued · ${done} done</span>
      </div>
      ${rows}
      ${meter}
      <div class="peek">Click to open task details</div>`;
  }

  destroy(): void {
    this.el.remove();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
