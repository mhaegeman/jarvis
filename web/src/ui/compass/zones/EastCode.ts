import type { CompassCodeFile } from "@/compass/types";

export interface EastCodeProps {
  branch: string;
  files: CompassCodeFile[];
  buildStatus: "ok" | "fail" | "running" | null;
}

const BUILD_GLYPH: Record<"ok" | "fail" | "running", string> = {
  ok: "✓",
  fail: "✗",
  running: "…",
};

export class EastCode {
  private readonly el: HTMLElement;
  private onClickCb: (() => void) | null = null;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "zone east";
    this.el.setAttribute("role", "region");
    this.el.setAttribute("aria-label", "Code changes");
    parent.appendChild(this.el);
    this.el.addEventListener("click", () => this.onClickCb?.());
  }

  onClick(cb: () => void): void {
    this.onClickCb = cb;
  }

  render(props: EastCodeProps): void {
    const { branch, files, buildStatus } = props;
    const modified = files.filter((f) => f.group === "modified").length;
    const added    = files.filter((f) => f.group === "added").length;
    const deleted  = files.filter((f) => f.group === "deleted").length;
    const totalDelta = `+${modified + added} / −${deleted}`;
    const buildLabel = buildStatus ? `build ${BUILD_GLYPH[buildStatus]}` : "build —";

    const active = files.find((f) => f.active) ?? files[0];
    const peekHtml = active
      ? `<div class="diff">
          <span class="hunk">@@ ${escHtml(active.name)} @@</span>
          <span class="ctx">  ${escHtml(active.delta)}</span>
        </div>`
      : `<div class="diff"><span class="ctx">  no changes</span></div>`;

    this.el.innerHTML = `
      <div class="zone-head">
        <span class="label-tag">East · Code</span>
        <span class="title">${escHtml(branch)}</span>
        <span class="meta">${files.length} files · ${buildLabel}</span>
      </div>
      <div class="zone-row">
        <span class="when">mod</span>
        <span class="what">${modified} modified · ${added} added · ${deleted} deleted</span>
        <span class="meta">${totalDelta}</span>
      </div>
      ${peekHtml}
      <div class="peek">Ctrl E · open full diff</div>`;
  }

  destroy(): void {
    this.el.remove();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
