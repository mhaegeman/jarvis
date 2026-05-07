import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface NetworkState {
  endpoint: string;
  latencyMs: number;
  packets: number;
  busyPct: number;
}

export class NetworkPanel extends Component<NetworkState> {
  override render(s: NetworkState): void {
    renderPanel(
      this.root,
      "Network",
      `
      <div class="row"><span>endpoint</span><b>${s.endpoint}</b></div>
      <div class="row"><span>latency</span><b>${s.latencyMs} ms</b></div>
      <div class="row"><span>packets</span><b>${s.packets.toLocaleString()}</b></div>
      <div class="bar"><i style="width:${Math.min(100, s.busyPct).toFixed(0)}%"></i></div>
    `,
    );
  }
}
