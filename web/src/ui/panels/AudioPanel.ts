import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export type MicStatus =
  | { kind: "unprompted" }
  | { kind: "granted" }
  | { kind: "denied" }
  | { kind: "unsupported" }
  | { kind: "error"; message: string };

export interface AudioState {
  inputDb: number;
  outputDb: number;
  inputBarPct: number;
  mic: MicStatus;
}

const escapeHtml = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const banner = (mic: MicStatus): string => {
  switch (mic.kind) {
    case "unprompted":
      return `<div class="mic-banner"><span>Mic not yet enabled.</span> <button data-action="mic-request">Enable</button></div>`;
    case "granted":
      return ``;
    case "denied":
      return `<div class="mic-banner warn"><span>Mic permission denied.</span> <button data-action="mic-request">Retry</button></div>`;
    case "unsupported":
      return `<div class="mic-banner warn"><span>Voice mode unavailable in this browser.</span></div>`;
    case "error":
      return `<div class="mic-banner warn"><span>${escapeHtml(mic.message)}</span> <button data-action="mic-request">Retry</button></div>`;
  }
};

export class AudioPanel extends Component<AudioState> {
  override render(s: AudioState): void {
    renderPanel(
      this.root,
      "Audio",
      `
      <div class="row"><span>input</span><b>${s.inputDb.toFixed(0)} dB</b></div>
      <div class="row"><span>output</span><b>${s.outputDb.toFixed(0)} dB</b></div>
      <div class="bar"><i style="width:${Math.min(100, s.inputBarPct).toFixed(0)}%"></i></div>
      ${banner(s.mic)}
    `,
    );
  }
}
