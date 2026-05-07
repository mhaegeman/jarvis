import { Component } from "./Component";
import type { ConvState } from "@/types";

export interface ControlsState {
  state: ConvState;
}

export interface ControlsActions {
  onMicDown(): void;
  onMicUp(): void;
  onInterrupt(): void;
  onRunScenario(): void;
  onIdle(): void;
}

const STATUS_LABEL: Record<ConvState, string> = {
  idle: "— idle —",
  listening: "— listening —",
  thinking: "— thinking —",
  speaking: "— speaking —",
};

export class Controls extends Component<ControlsState> {
  constructor(
    rootSelector: string,
    private actions: ControlsActions,
    devMode: boolean,
  ) {
    super(rootSelector);
    this.root.classList.add("panel", "controls");
    this.root.innerHTML = `
      <button data-action="mic" aria-label="Push to talk" aria-pressed="false">▶ Speak</button>
      <button data-action="interrupt">◉ Interrupt</button>
      <button data-action="idle">○ Idle</button>
      ${devMode ? `<button data-action="run-scenario">Run scenario</button>` : ``}
      <span class="status" data-status>—</span>
    `;
    const mic = this.root.querySelector<HTMLButtonElement>('[data-action="mic"]')!;
    const setPressed = (v: boolean): void => mic.setAttribute("aria-pressed", v ? "true" : "false");
    mic.addEventListener("mousedown", () => {
      setPressed(true);
      this.actions.onMicDown();
    });
    mic.addEventListener("mouseup", () => {
      setPressed(false);
      this.actions.onMicUp();
    });
    mic.addEventListener("mouseleave", () => {
      setPressed(false);
      this.actions.onMicUp();
    });
    mic.addEventListener(
      "touchstart",
      (e) => {
        e.preventDefault();
        setPressed(true);
        this.actions.onMicDown();
      },
      { passive: false },
    );
    mic.addEventListener("touchend", () => {
      setPressed(false);
      this.actions.onMicUp();
    });

    this.root
      .querySelector('[data-action="interrupt"]')!
      .addEventListener("click", () => this.actions.onInterrupt());
    this.root
      .querySelector('[data-action="idle"]')!
      .addEventListener("click", () => this.actions.onIdle());
    this.root
      .querySelector('[data-action="run-scenario"]')
      ?.addEventListener("click", () => this.actions.onRunScenario());
  }

  override render(s: ControlsState): void {
    const status = this.root.querySelector<HTMLElement>("[data-status]")!;
    status.textContent = STATUS_LABEL[s.state];
    this.root.dataset.state = s.state;
  }
}
