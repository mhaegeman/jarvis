import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface NetworkState {
  endpoint: string;
  latencyMs: number | null;
  packets: number;
  sendQueueDepth: number;
  sendQueueMax: number;
}

export class NetworkPanel extends Component<NetworkState> {
  override render(s: NetworkState): void {
    const latency = s.latencyMs === null ? "-- ms" : `${s.latencyMs.toFixed(1)} ms`;
    const pct = Math.min(100, (s.sendQueueDepth / s.sendQueueMax) * 100).toFixed(0);
    renderPanel(
      this.root,
      "Network",
      `
      <div class="row"><span>endpoint</span><b>${s.endpoint}</b></div>
      <div class="row"><span>latency</span><b>${latency}</b></div>
      <div class="row"><span>packets</span><b>${s.packets.toLocaleString()}</b></div>
      <div class="bar"><i style="width:${pct}%"></i></div>
    `,
    );
  }
}
