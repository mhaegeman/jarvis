import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface MemoryState {
  contextUsed: number;
  contextMax: number;
  recallPct: number;
}

const fmt = (n: number): string => (n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n));

export class MemoryPanel extends Component<MemoryState> {
  override render(s: MemoryState): void {
    const ctxPct = Math.min(100, (s.contextUsed / s.contextMax) * 100);
    renderPanel(
      this.root,
      "Memory",
      `
      <div class="row"><span>context</span><b>${fmt(s.contextUsed)} / ${fmt(s.contextMax)}</b></div>
      <div class="bar"><i style="width:${ctxPct.toFixed(0)}%"></i></div>
      <div class="row"><span>recall</span><b>${s.recallPct.toFixed(1)}%</b></div>
      <div class="bar"><i style="width:${s.recallPct.toFixed(0)}%"></i></div>
    `,
    );
  }
}
