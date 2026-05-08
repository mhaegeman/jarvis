import { Component } from "./Component";

interface HeaderState {
  uptimeMs: number;
  wsState: "live" | "demo" | "reconnecting";
}

const pad2 = (n: number): string => String(n).padStart(2, "0");

const WS_LABELS: Record<HeaderState["wsState"], string> = {
  live: "LIVE",
  demo: "DEMO",
  reconnecting: "RECONNECT…",
};

export class Header extends Component<HeaderState> {
  override render(state: HeaderState): void {
    const d = new Date();
    const clock = `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
    const u = Math.floor(state.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    const wsLabel = WS_LABELS[state.wsState];
    this.root.classList.add("panel", "header");
    this.root.innerHTML = `
      <span class="id">JARVIS // OS · v0.1</span>
      <span class="ws-badge" data-ws-state="${state.wsState}">${wsLabel}</span>
      <span class="uptime">${uptime}</span>
      <span class="clock">${clock}</span>
    `;
  }
}
