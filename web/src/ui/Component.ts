export abstract class Component<S = unknown> {
  protected root: HTMLElement;
  private unsubs: Array<() => void> = [];

  constructor(rootSelector: string) {
    const el = document.querySelector<HTMLElement>(rootSelector);
    if (!el) throw new Error(`Component root missing: ${rootSelector}`);
    this.root = el;
  }

  mount(state: S): void {
    this.render(state);
  }

  abstract render(state: S): void;

  /** Track a teardown function (e.g. store subscription) so destroy() releases it. */
  track(unsub: () => void): void {
    this.unsubs.push(unsub);
  }

  destroy(): void {
    this.unsubs.splice(0).forEach((u) => u());
    this.root.replaceChildren();
    this.root.textContent = "";
  }
}
