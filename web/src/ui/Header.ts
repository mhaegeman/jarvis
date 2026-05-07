import { Component } from "./Component";

interface HeaderState {
  uptimeMs: number;
}

const pad2 = (n: number): string => String(n).padStart(2, "0");

export class Header extends Component<HeaderState> {
  override render(state: HeaderState): void {
    const d = new Date();
    const clock = `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
    const u = Math.floor(state.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    this.root.classList.add("panel", "header");
    this.root.innerHTML = `
      <span class="id">JARVIS // OS · v0.1</span>
      <span class="uptime">${uptime}</span>
      <span class="clock">${clock}</span>
    `;
  }
}
