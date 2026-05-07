import { Component } from "./Component";

export interface WaveformInput {
  amplitude: number; // 0..1, smoothed externally
  modeHint: "idle" | "listening" | "thinking" | "speaking";
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
}

export class Waveform extends Component<WaveformInput> {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private dpr = Math.min(window.devicePixelRatio || 1, 2);
  private W = 0;
  private H = 0;
  private t = 0;
  private particles: Particle[] = [];
  private resizeObs: ResizeObserver | undefined;

  constructor(rootSelector: string) {
    super(rootSelector);
    this.canvas = document.createElement("canvas");
    this.canvas.classList.add("waveform-canvas");
    this.root.appendChild(this.canvas);
    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;
    this.particles = Array.from({ length: 80 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0004,
      vy: (Math.random() - 0.5) * 0.0004,
      r: Math.random() * 1.4 + 0.3,
    }));
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(this.root);
    this.resize();
  }

  private resize(): void {
    const rect = this.root.getBoundingClientRect();
    this.W = Math.max(1, Math.floor(rect.width * this.dpr));
    this.H = Math.max(1, Math.floor(rect.height * this.dpr));
    this.canvas.width = this.W;
    this.canvas.height = this.H;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
  }

  override render(input: WaveformInput): void {
    this.t += 1;
    const ctx = this.ctx;
    const { W, H, dpr } = this;
    const amp = input.amplitude;

    ctx.fillStyle = "rgba(2,4,10,0.18)";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "rgba(125,249,255,0.45)";
    for (const p of this.particles) {
      p.x += p.vx + amp * 0.0002;
      p.y += p.vy;
      if (p.x < 0) p.x += 1;
      if (p.x > 1) p.x -= 1;
      if (p.y < 0) p.y += 1;
      if (p.y > 1) p.y -= 1;
      ctx.beginPath();
      ctx.arc(p.x * W, p.y * H, p.r * dpr, 0, Math.PI * 2);
      ctx.fill();
    }

    const cy = H * 0.5;
    const layers = [
      { hue: "rgba(125,249,255,", a: 0.85, mul: 1.0, freq: 0.012, speed: 0.05 },
      { hue: "rgba(125,249,255,", a: 0.45, mul: 0.7, freq: 0.008, speed: 0.03 },
      { hue: "rgba(168,200,255,", a: 0.3, mul: 1.4, freq: 0.02, speed: 0.07 },
    ];
    ctx.lineWidth = 2 * dpr;
    for (const L of layers) {
      ctx.beginPath();
      ctx.strokeStyle = `${L.hue}${L.a})`;
      ctx.shadowBlur = 24 * dpr;
      ctx.shadowColor = `${L.hue}0.6)`;
      for (let x = 0; x <= W; x += 4 * dpr) {
        const env = Math.sin(x * 0.001 + this.t * 0.003) * 0.5 + 0.5;
        const y =
          cy +
          Math.sin(x * L.freq + this.t * L.speed) * H * 0.18 * amp * L.mul * env +
          Math.sin(x * L.freq * 2.2 + this.t * L.speed * 1.3) * H * 0.06 * amp * L.mul;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }

  override destroy(): void {
    this.resizeObs?.disconnect();
    super.destroy();
  }
}
