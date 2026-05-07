import { describe, it, expect, vi } from "vitest";
import { Component } from "@/ui/Component";

class Demo extends Component<{ value: number }> {
  rendered: number[] = [];
  override render(state: { value: number }): void {
    this.rendered.push(state.value);
    this.root.textContent = String(state.value);
  }
}

describe("Component", () => {
  it("attaches to a DOM root and renders on mount", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const c = new Demo("#x");
    c.mount({ value: 1 });
    expect(c.rendered).toEqual([1]);
    expect(document.getElementById("x")?.textContent).toBe("1");
  });

  it("destroy clears subscriptions and root", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const c = new Demo("#x");
    c.mount({ value: 1 });
    const off = vi.fn();
    c.track(off);
    c.destroy();
    expect(off).toHaveBeenCalledOnce();
    expect(document.getElementById("x")?.children.length).toBe(0);
    expect(document.getElementById("x")?.textContent).toBe("");
  });

  it("throws if root selector missing", () => {
    document.body.innerHTML = ``;
    expect(() => new Demo("#missing")).toThrow(/missing/i);
  });
});
