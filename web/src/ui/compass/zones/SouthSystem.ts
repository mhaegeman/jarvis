import type { CompassSystem } from "@/compass/types";
import type { PanelDataSystemPersonas } from "@/types";

export class SouthSystem {
  private readonly el: HTMLElement;
  private onClickCb: (() => void) | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "zone south";
    this.el.setAttribute("role", "region");
    this.el.setAttribute("aria-label", "System status");
    parent.appendChild(this.el);
    this.el.addEventListener("click", () => this.onClickCb?.());
  }

  onClick(cb: () => void): void {
    this.onClickCb = cb;
  }

  render(sys: CompassSystem): void {
    const ctxPct = sys.contextMax > 0 ? Math.round((sys.contextUsed / sys.contextMax) * 100) : 0;

    this.el.innerHTML = `
      <div class="zone-head">
        <span class="label-tag">South · System</span>
        <span class="title">All quiet · local</span>
        <span class="meta">${sys.model}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;margin-bottom:10px;">
        <div class="zone-row" style="border:none;padding:2px 0;">
          <span class="when">uptime</span>
          <span class="what">${escHtml(sys.uptime)}</span>
        </div>
        <div class="zone-row" style="border:none;padding:2px 0;">
          <span class="when">load</span>
          <span class="what">${escHtml(sys.load)}</span>
        </div>
        <div class="zone-row" style="border:none;padding:2px 0;">
          <span class="when">tok/m</span>
          <span class="what">${escHtml(sys.tokens)}</span>
        </div>
        <div class="zone-row" style="border:none;padding:2px 0;">
          <span class="when">model</span>
          <span class="what" style="font-size:10px;">${escHtml(sys.model)}</span>
        </div>
      </div>
      <div style="margin-top:6px;">
        <div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--ink-3);margin-bottom:4px;">
          <span>context · ${sys.contextUsed}K / ${sys.contextMax}K</span>
          <span>${ctxPct}%</span>
        </div>
        <div class="meter${ctxPct > 80 ? " warm" : ""}">
          <i style="width:${ctxPct}%"></i>
        </div>
      </div>
      ${sys.personas ? renderPersonaRows(sys.personas) : ""}
      <div class="peek">Click to open system details</div>`;
  }

  destroy(): void {
    this.el.remove();
  }
}

function renderPersonaRows(personas: PanelDataSystemPersonas): string {
  const rows: string[] = [];
  const entries: [string, { model: string; tier: string } | undefined][] = [
    ["jarvis", personas.jarvis],
    ["pepper", personas.pepper],
  ];
  for (const [id, p] of entries) {
    if (p) {
      rows.push(
        `<div class="zone-row" style="border:none;padding:2px 0;">
          <span class="when">${escHtml(id)}</span>
          <span class="what" style="font-size:10px;">${escHtml(p.model)}</span>
          <span class="meta">${escHtml(p.tier)}</span>
        </div>`,
      );
    }
  }
  if (rows.length === 0) return "";
  return `<div style="margin-top:6px;border-top:1px solid var(--paper-2);padding-top:6px;">${rows.join("")}</div>`;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
