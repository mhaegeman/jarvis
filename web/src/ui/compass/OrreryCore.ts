import type { ConvState, Speaker } from "@/types";
import { SPEAKER_TINT } from "@/ui/Centerpiece";

/** Four-ring animated SVG orrery. State drives CSS class → animation swap. */
export class OrreryCore {
  private readonly el: HTMLElement;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "core";
    this.el.setAttribute("aria-hidden", "true");

    const svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgEl.setAttribute("viewBox", "-100 -100 200 200");
    svgEl.innerHTML = `
      <circle class="r r1" r="78" />
      <circle class="r r2" r="58" />
      <circle class="r r3" r="38" />
      <circle class="r r4" r="22" />
      <circle class="center-dot" r="3.2" />
      <circle class="orbit-dot" r="1.6" cx="78" cy="0">
        <animateTransform attributeName="transform" type="rotate"
          from="0" to="360" dur="12s" repeatCount="indefinite" />
      </circle>`;
    this.el.appendChild(svgEl);
    parent.appendChild(this.el);
  }

  render(state: ConvState): void {
    this.el.classList.remove("warm", "listening");
    if (state === "speaking") this.el.classList.add("warm");
    if (state === "listening") this.el.classList.add("listening");
  }

  /**
   * Set the speaker tint on the orrery core.
   * Null clears the tint (fallback to accent colour).
   * The CSS transition on --centerpiece-tint handles the 120ms crossfade.
   */
  setTint(speaker: Speaker | null): void {
    if (speaker === null) {
      this.el.style.removeProperty("--centerpiece-tint");
    } else {
      this.el.style.setProperty("--centerpiece-tint", SPEAKER_TINT[speaker]);
    }
  }

  destroy(): void {
    this.el.remove();
  }
}
