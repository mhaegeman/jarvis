import { Component } from "./Component";

interface TranscriptState {
  text: string;
}

export class Transcript extends Component<TranscriptState> {
  private body: HTMLElement | undefined;
  private caret: HTMLElement | undefined;
  private streamTimer: ReturnType<typeof setTimeout> | undefined;

  override render(state: TranscriptState): void {
    if (!this.body) {
      this.root.classList.add("transcript");
      this.root.innerHTML = `<span class="body"></span><span class="caret"></span>`;
      this.body = this.root.querySelector(".body") as HTMLElement;
      this.caret = this.root.querySelector(".caret") as HTMLElement;
    }
    this.body.textContent = state.text;
  }

  appendToken(token: string): void {
    if (!this.body) return;
    this.body.textContent = (this.body.textContent ?? "") + token;
  }

  stream(text: string, msPerChar: number): void {
    if (!this.body) return;
    this.interrupt();
    this.body.textContent = "";
    let i = 0;
    const body = this.body;
    const step = (): void => {
      if (i > text.length) return;
      body.textContent = text.slice(0, i++);
      this.streamTimer = setTimeout(step, msPerChar);
    };
    step();
  }

  interrupt(): void {
    if (this.streamTimer !== undefined) {
      clearTimeout(this.streamTimer);
      this.streamTimer = undefined;
    }
  }

  clear(): void {
    this.interrupt();
    if (this.body) this.body.textContent = "";
  }
}
