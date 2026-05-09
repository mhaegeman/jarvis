export type LockState = "idle" | "error" | "unlocking";

/** Three-ring SVG orrery for the login screen. */
export class LoginOrrery {
  private readonly el: HTMLElement;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "lock";
    this.el.setAttribute("aria-hidden", "true");
    this.el.innerHTML = `
      <svg viewBox="-100 -100 200 200">
        <circle class="ring r1" r="78" />
        <circle class="ring r2" r="58" />
        <circle class="ring r3" r="38" />
        <circle class="center" r="3.2" />
      </svg>`;
    parent.appendChild(this.el);
  }

  setState(state: LockState): void {
    this.el.classList.remove("unlocking", "error");
    if (state === "unlocking") this.el.classList.add("unlocking");
    if (state === "error") this.el.classList.add("error");
  }

  destroy(): void {
    this.el.remove();
  }
}
