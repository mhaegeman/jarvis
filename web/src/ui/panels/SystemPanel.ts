import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface SystemState {
  uptimeMs: number;
  load: number;
  tokensPerMin: number;
  sessionId: string;
}

const pad2 = (n: number): string => String(n).padStart(2, "0");

export class SystemPanel extends Component<SystemState> {
  override render(s: SystemState): void {
    const u = Math.floor(s.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    renderPanel(
      this.root,
      "System",
      `
      <div class="row"><span>uptime</span><b>${uptime}</b></div>
      <div class="row"><span>load</span><b>${s.load.toFixed(2)}</b></div>
      <div class="row"><span>tokens / min</span><b>${s.tokensPerMin.toLocaleString()}</b></div>
      <div class="row"><span>session</span><b>#${s.sessionId}</b></div>
    `,
    );
  }
}
