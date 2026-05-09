import type { ConvState } from "@/types";

/** 24-hour tick ring SVG. Positioned as absolute overlay on the compass disc. */
export class Ring {
  private readonly el: SVGSVGElement;

  constructor(parent: HTMLElement) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.classList.add("ring-svg");
    svg.setAttribute("aria-hidden", "true");

    const center = { x: 50, y: 50 };
    const r = 45; // radius for tick positioning

    // Track circles
    svg.innerHTML += `
      <circle class="ring-track" cx="50" cy="50" r="46" />
      <circle class="ring-track" cx="50" cy="50" r="44"
        stroke-dasharray="0.4 1.6" stroke-dashoffset="0" />`;

    // Cardinal crosshairs
    svg.innerHTML += `
      <line class="axis" x1="50" y1="4"  x2="50" y2="14" />
      <line class="axis" x1="50" y1="86" x2="50" y2="96" />
      <line class="axis" x1="4"  y1="50" x2="14" y2="50" />
      <line class="axis" x1="86" y1="50" x2="96" y2="50" />`;

    // 24 hour ticks
    for (let h = 0; h < 24; h++) {
      const angle = (h / 24) * 2 * Math.PI - Math.PI / 2;
      const major = h % 6 === 0;
      const len = major ? 4 : 2.5;
      const x1 = center.x + (r - len) * Math.cos(angle);
      const y1 = center.y + (r - len) * Math.sin(angle);
      const x2 = center.x + r * Math.cos(angle);
      const y2 = center.y + r * Math.sin(angle);
      const cls = major ? "ring-tick-maj" : "ring-tick";
      svg.innerHTML += `<line class="${cls}" x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" />`;
    }

    // Now tick (will be updated by render)
    const nowTick = document.createElementNS("http://www.w3.org/2000/svg", "line");
    nowTick.classList.add("now-tick");
    svg.appendChild(nowTick);

    // Speaking pulses (two animated circles, hidden by default)
    const pulse1 = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    pulse1.setAttribute("cx", "50");
    pulse1.setAttribute("cy", "50");
    pulse1.classList.add("pulse");
    pulse1.innerHTML = `
      <animate attributeName="r" values="30;38;30" dur="3.2s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.55;0.05;0.55" dur="3.2s" repeatCount="indefinite" />`;

    const pulse2 = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    pulse2.setAttribute("cx", "50");
    pulse2.setAttribute("cy", "50");
    pulse2.classList.add("pulse");
    pulse2.innerHTML = `
      <animate attributeName="r" values="38;48;38" dur="4s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.3;0;0.3" dur="4s" repeatCount="indefinite" />`;

    svg.appendChild(pulse1);
    svg.appendChild(pulse2);

    this.el = svg;
    parent.appendChild(svg);

    // Store refs for render
    (this as unknown as { nowTick: SVGLineElement; pulse1: SVGCircleElement; pulse2: SVGCircleElement;
      center: { x: number; y: number }; r: number; labelR: number }).nowTick = nowTick;
    (this as unknown as { pulse1: SVGCircleElement }).pulse1 = pulse1;
    (this as unknown as { pulse2: SVGCircleElement }).pulse2 = pulse2;
    (this as unknown as { _center: { x: number; y: number }; _r: number }).
      _center = center;
    (this as unknown as { _r: number })._r = r;
  }

  render(state: ConvState): void {
    const self = this as unknown as {
      nowTick: SVGLineElement;
      pulse1: SVGCircleElement;
      pulse2: SVGCircleElement;
      _center: { x: number; y: number };
      _r: number;
    };
    const now = new Date();
    const hour = now.getHours() + now.getMinutes() / 60;
    const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
    const c = self._center;
    const r = self._r;
    const len = 5;
    self.nowTick.setAttribute("x1", (c.x + (r - len) * Math.cos(angle)).toFixed(2));
    self.nowTick.setAttribute("y1", (c.y + (r - len) * Math.sin(angle)).toFixed(2));
    self.nowTick.setAttribute("x2", (c.x + r * Math.cos(angle)).toFixed(2));
    self.nowTick.setAttribute("y2", (c.y + r * Math.sin(angle)).toFixed(2));

    const speaking = state === "speaking";
    self.pulse1.style.display = speaking ? "" : "none";
    self.pulse2.style.display = speaking ? "" : "none";
  }

  destroy(): void {
    this.el.remove();
  }
}
