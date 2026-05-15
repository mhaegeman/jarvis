import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { PanelDataSystemPersonas } from "@/types";

export interface SystemState {
  uptimeMs: number;
  load: number;
  tokensPerMin: number;
  sessionId: string;
  modelName: string;
  personas?: PanelDataSystemPersonas;
}

const pad2 = (n: number): string => String(n).padStart(2, "0");

function renderPersonaRows(personas: PanelDataSystemPersonas): string {
  const rows: string[] = [];
  const entries: [string, { model: string; tier: string } | undefined][] = [
    ["jarvis", personas.jarvis],
    ["pepper", personas.pepper],
  ];
  for (const [id, p] of entries) {
    if (p) {
      rows.push(
        `<div class="row persona-row"><span>${id}</span><b>${p.model}</b><span class="meta">${p.tier}</span></div>`,
      );
    }
  }
  return rows.join("");
}

export class SystemPanel extends Component<SystemState> {
  override render(s: SystemState): void {
    const u = Math.floor(s.uptimeMs / 1000);
    const uptime = `${pad2(Math.floor(u / 3600))}:${pad2(Math.floor((u % 3600) / 60))}:${pad2(u % 60)}`;
    const personasHtml = s.personas ? renderPersonaRows(s.personas) : "";
    renderPanel(
      this.root,
      "System",
      `
      <div class="row"><span>uptime</span><b>${uptime}</b></div>
      <div class="row"><span>load</span><b>${s.load.toFixed(2)}</b></div>
      <div class="row"><span>tokens / min</span><b>${s.tokensPerMin.toLocaleString()}</b></div>
      <div class="row"><span>session</span><b>#${s.sessionId}</b></div>
      <div class="row"><span>model</span><b>${s.modelName}</b></div>
      ${personasHtml}
    `,
    );
  }
}
