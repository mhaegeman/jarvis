import type { CompassNotif } from "@/compass/types";

/**
 * Six notification chips placed at hand-tuned angles around the compass ring rim.
 * Each chip is positioned by converting its angle to Cartesian coords relative
 * to the compass disc centre, then placed absolutely on the #app element so it
 * sits in viewport space rather than inside the scaled disc.
 *
 * Hover expand and dismiss (.dismissing → remove after 380ms) are CSS-driven.
 */
export class NotifRing {
  private readonly parent: HTMLElement;
  private chips: Map<string, HTMLElement> = new Map();

  /** Outer radius of the ring in the 820px reference frame (matches CSS .ring-svg) */
  private static readonly RING_R = 390;

  constructor(parent: HTMLElement) {
    this.parent = parent;
  }

  render(notifs: CompassNotif[]): void {
    const discEl = document.querySelector<HTMLElement>("#compass-disc");
    if (!discEl) return;

    const rect = discEl.getBoundingClientRect();
    const cx = rect.left + rect.width  / 2;
    const cy = rect.top  + rect.height / 2;
    const scale = rect.width / 820;

    const seen = new Set<string>();

    for (const n of notifs) {
      seen.add(n.id);
      if (this.chips.has(n.id)) continue;

      const chip = this.buildChip(n);
      this.parent.appendChild(chip);
      this.chips.set(n.id, chip);
    }

    // Position all active chips
    for (const [id, chip] of this.chips) {
      if (!seen.has(id)) continue;
      const notif = notifs.find((n) => n.id === id);
      if (!notif) continue;

      const rad = (notif.angle - 90) * (Math.PI / 180);
      const r = NotifRing.RING_R * scale;
      const x = cx + r * Math.cos(rad);
      const y = cy + r * Math.sin(rad);

      chip.style.left = `${x}px`;
      chip.style.top  = `${y}px`;
    }
  }

  private buildChip(n: CompassNotif): HTMLElement {
    const el = document.createElement("div");
    el.className = `notif${n.warm ? " warm" : ""}`;
    el.setAttribute("role", "status");
    el.setAttribute("aria-label", n.text);
    el.innerHTML = `
      <span class="dot"></span>
      <span class="ntext">${escHtml(n.text)}</span>
      <span class="kbd">${escHtml(n.kbd)}</span>
      <span class="preview"><span class="when">${escHtml(n.when)}</span>${escHtml(n.preview)}</span>`;

    el.addEventListener("click", () => this.dismiss(n.id));
    return el;
  }

  private dismiss(id: string): void {
    const chip = this.chips.get(id);
    if (!chip) return;
    chip.classList.add("dismissing");
    setTimeout(() => {
      chip.remove();
      this.chips.delete(id);
    }, 380);
  }

  destroy(): void {
    for (const chip of this.chips.values()) chip.remove();
    this.chips.clear();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
