/** 48-bar rAF waveform rendered around the orrery when state === "listening". */
export class ListeningRim {
  private readonly el: HTMLElement;
  private readonly bars: SVGLineElement[] = [];
  private rafId: number | null = null;
  private startTime = performance.now();
  private visible = false;

  private static readonly BAR_COUNT = 48;
  private static readonly CENTER = 120; // viewBox center
  private static readonly RADIUS = 90;  // px from center

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "mic-rim";
    this.el.setAttribute("aria-hidden", "true");

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const size = ListeningRim.CENTER * 2;
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");

    for (let i = 0; i < ListeningRim.BAR_COUNT; i++) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.classList.add("bar");
      svg.appendChild(line);
      this.bars.push(line);
    }

    this.el.appendChild(svg);
    parent.appendChild(this.el);
    this.el.style.display = "none";
  }

  show(): void {
    if (this.visible) return;
    this.visible = true;
    this.el.style.display = "";
    this.startTime = performance.now();
    this.loop();
  }

  hide(): void {
    if (!this.visible) return;
    this.visible = false;
    this.el.style.display = "none";
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  private loop(): void {
    if (!this.visible) return;
    const t = (performance.now() - this.startTime) / 1000;
    const n = ListeningRim.BAR_COUNT;
    const cx = ListeningRim.CENTER;
    const cy = ListeningRim.CENTER;
    const r = ListeningRim.RADIUS;

    for (let i = 0; i < n; i++) {
      const angle = (i / n) * 2 * Math.PI - Math.PI / 2;
      const amp = 4 + Math.sin(t + i * 0.6) * 3 + Math.sin(t * 1.7 + i * 0.2) * 2.5;
      const x1 = cx + r * Math.cos(angle);
      const y1 = cy + r * Math.sin(angle);
      const x2 = cx + (r + amp) * Math.cos(angle);
      const y2 = cy + (r + amp) * Math.sin(angle);
      const bar = this.bars[i];
      bar.setAttribute("x1", x1.toFixed(2));
      bar.setAttribute("y1", y1.toFixed(2));
      bar.setAttribute("x2", x2.toFixed(2));
      bar.setAttribute("y2", y2.toFixed(2));
    }

    this.rafId = requestAnimationFrame(() => this.loop());
  }

  destroy(): void {
    this.hide();
    this.el.remove();
  }
}
