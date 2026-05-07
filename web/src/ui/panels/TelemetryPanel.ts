import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { TelemetryEvent } from "@/types";

export interface TelemetryState {
  events: TelemetryEvent[];
}

const SYMBOL: Record<TelemetryEvent["level"], string> = {
  info: "·",
  ok: "+",
  warn: "!",
  error: "x",
};

const tsStr = (ms: number): string => {
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
};

const escape = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export class TelemetryPanel extends Component<TelemetryState> {
  override render(s: TelemetryState): void {
    const lines = s.events
      .slice(0, 14)
      .map(
        (e) =>
          `<div class="line ${e.level}">${tsStr(e.ts)}  ${SYMBOL[e.level]} ${escape(e.message)}</div>`,
      )
      .join("");
    renderPanel(this.root, "Telemetry", `<div class="feed">${lines}</div>`);
  }
}
