/** Five absolute-positioned mono labels on the 24h ring (00, 06, 12, 18, now). */
export class HourLabels {
  private readonly labels: HTMLElement[] = [];
  private readonly parent: HTMLElement;

  constructor(parent: HTMLElement) {
    this.parent = parent;
    const size = 820; // reference size; CSS scales via min(82vmin, 820px)
    const center = size / 2;
    const r = size * 0.42; // 41% of size matches the ring track at r=41 in 0-100 viewBox

    const positions = [
      { h: 0,  label: "00" },
      { h: 6,  label: "06" },
      { h: 12, label: "12" },
      { h: 18, label: "18" },
    ];

    for (const { h, label } of positions) {
      const angle = (h / 24) * 2 * Math.PI - Math.PI / 2;
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      const pct = (v: number): string => `${((v / size) * 100).toFixed(3)}%`;

      const el = document.createElement("div");
      el.className = "hour-label";
      el.textContent = label;
      el.style.left = pct(x);
      el.style.top = pct(y);
      parent.appendChild(el);
      this.labels.push(el);
    }

    // "now" label — updated by render()
    const nowEl = document.createElement("div");
    nowEl.className = "hour-label now";
    nowEl.id = "hour-label-now";
    parent.appendChild(nowEl);
    this.labels.push(nowEl);
  }

  render(): void {
    const nowEl = this.parent.querySelector<HTMLElement>("#hour-label-now");
    if (!nowEl) return;
    const now = new Date();
    const hour = now.getHours();
    const size = 820;
    const center = size / 2;
    const r = size * 0.42;
    const frac = now.getHours() + now.getMinutes() / 60;
    const angle = (frac / 24) * 2 * Math.PI - Math.PI / 2;
    const x = center + r * Math.cos(angle);
    const y = center + r * Math.sin(angle);
    const pct = (v: number): string => `${((v / size) * 100).toFixed(3)}%`;
    nowEl.style.left = pct(x);
    nowEl.style.top = pct(y);
    nowEl.textContent = String(hour).padStart(2, "0");
  }

  destroy(): void {
    this.labels.forEach((l) => l.remove());
  }
}
