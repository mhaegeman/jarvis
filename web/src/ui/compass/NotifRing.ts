import type { CompassNotif } from "@/compass/types";

/**
 * Six notification chips placed at hand-tuned angles around the compass ring rim.
 * Each chip is positioned by converting its angle to Cartesian coords relative
 * to the compass disc centre, then placed absolutely on the #app element so it
 * sits in viewport space rather than inside the scaled disc.
 *
 * Reconciliation: every `render(input)` pass updates the text/preview/warm
 * state of chips that already exist, creates chips for new ids, and removes
 * chips whose id has dropped out of the input. The full-rebuild path is
 * avoided to keep CSS transitions intact (no flicker when a countdown
 * ticks "in 3m" → "in 2m").
 *
 * Dismissal: clicking a chip fades it out (CSS `.dismissing`) and adds its
 * id to a local `dismissed` set so the next `render()` filters it back out
 * even if NotifManager still surfaces it. The dismissed mark is dropped
 * the moment the source condition resolves (id naturally leaves the
 * input), so the same chip can re-appear on the *next* qualifying event.
 */
export class NotifRing {
  private readonly parent: HTMLElement;
  private chips: Map<string, HTMLElement> = new Map();
  /**
   * Chips the user dismissed by click. Stays in this set until the source
   * condition resolves (id stops appearing in the input). Without this,
   * NotifManager keeps re-supplying the same id and the chip springs back
   * on the next tick — dismissal would be decorative.
   */
  private dismissed: Set<string> = new Set();
  /** Last set of ids seen in `render()` input — needed to compute the diff that frees dismissals. */
  private lastInputIds: Set<string> = new Set();

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

    // Clear dismissals for ids that have left the input (P1.2 cleanup):
    // when the source condition resolves, the same id can return as a new
    // notification on a future tick — but only after a real gap.
    const currentInputIds = new Set(notifs.map((n) => n.id));
    for (const id of [...this.dismissed]) {
      const wasPresent = this.lastInputIds.has(id);
      const stillPresent = currentInputIds.has(id);
      if (wasPresent && !stillPresent) this.dismissed.delete(id);
    }
    this.lastInputIds = currentInputIds;

    // Filter out dismissed chips so they aren't re-created.
    const visible = notifs.filter((n) => !this.dismissed.has(n.id));
    const visibleIds = new Set(visible.map((n) => n.id));

    // Reconcile: create missing chips, update existing ones in-place.
    for (const n of visible) {
      const existing = this.chips.get(n.id);
      if (existing) {
        this.updateChip(existing, n);
      } else {
        const chip = this.buildChip(n);
        this.parent.appendChild(chip);
        this.chips.set(n.id, chip);
      }
    }

    // Remove chips whose id has dropped out of the input set (zombie cleanup).
    for (const [id, chip] of [...this.chips]) {
      if (visibleIds.has(id)) continue;
      this.removeChip(id, chip);
    }

    // Position visible chips. We iterate `visible` (not `this.chips`) so
    // freshly-removed chips mid-fade-out don't get repositioned.
    for (const n of visible) {
      const chip = this.chips.get(n.id);
      if (!chip) continue;
      const rad = (n.angle - 90) * (Math.PI / 180);
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
      <span class="preview"><span class="when">${escHtml(n.when)}</span>${escHtml(n.preview)}</span>`;

    el.addEventListener("click", () => this.dismiss(n.id));
    return el;
  }

  /** Update an existing chip's surface in place — no full rebuild. */
  private updateChip(el: HTMLElement, n: CompassNotif): void {
    el.classList.toggle("warm", n.warm);
    el.setAttribute("aria-label", n.text);
    const ntext = el.querySelector<HTMLElement>(".ntext");
    if (ntext && ntext.textContent !== n.text) ntext.textContent = n.text;
    const when = el.querySelector<HTMLElement>(".when");
    if (when && when.textContent !== n.when) when.textContent = n.when;
    const preview = el.querySelector<HTMLElement>(".preview");
    if (preview) {
      // Preview wraps a `.when` span + the preview text. Update text node
      // after the `.when` child without rebuilding the wrapper.
      const expected = n.preview;
      // The text node directly after .when carries the preview body.
      const textNode = preview.childNodes[1];
      if (textNode && textNode.nodeType === Node.TEXT_NODE) {
        if (textNode.textContent !== expected) textNode.textContent = expected;
      } else {
        preview.appendChild(document.createTextNode(expected));
      }
    }
  }

  /** Animate a chip away, then drop it from the DOM and the map. */
  private removeChip(id: string, chip: HTMLElement): void {
    chip.classList.add("dismissing");
    this.chips.delete(id);
    setTimeout(() => chip.remove(), 380);
  }

  private dismiss(id: string): void {
    const chip = this.chips.get(id);
    if (!chip) return;
    this.dismissed.add(id);
    this.removeChip(id, chip);
  }

  destroy(): void {
    for (const chip of this.chips.values()) chip.remove();
    this.chips.clear();
    this.dismissed.clear();
    this.lastInputIds.clear();
  }
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
