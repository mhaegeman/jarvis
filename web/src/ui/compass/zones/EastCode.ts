import type { CompassCodeFile } from "@/compass/types";

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

  render(files: CompassCodeFile[]): void {
    const modified = files.filter((f) => f.group === "modified").length;
    const added    = files.filter((f) => f.group === "added").length;
    const deleted  = files.filter((f) => f.group === "deleted").length;
    const totalDelta = `+${modified + added} / −${deleted}`;

    // 6-line diff snippet using the active file
    const active = files.find((f) => f.active) ?? files[0];
    const diffHtml = active
      ? `<div class="diff">
          <span class="hunk">@@ src/ui/compass/CompassApp.ts @@</span>
          <span class="ctx">  import { store, events, mic } from "@/main";</span>
          <span class="add">+ import { createCompassApp } from "./CompassApp";</span>
          <span class="rem">- import { Centerpiece } from "@/ui/Centerpiece";</span>
          <span class="ctx">  // Mount sub-components</span>
          <span class="add">+ const rim = new ListeningRim(disc);</span>
        </div>`
      : "";

    this.el.innerHTML = `
      <div class="zone-head">
        <span class="label-tag">East · Code</span>
        <span class="title">feat/compass-ui</span>
        <span class="meta">${files.length} files · build ✓</span>
      </div>
      <div class="zone-row">
        <span class="when">mod</span>
        <span class="what">${modified} modified · ${added} added · ${deleted} deleted</span>
        <span class="meta">${totalDelta}</span>
      </div>
      ${diffHtml}
      <div class="peek">⌘ E · open full diff</div>`;
  }

  destroy(): void {
    this.el.remove();
  }
}
