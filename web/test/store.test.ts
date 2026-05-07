import { describe, it, expect, vi } from "vitest";
import { createStore } from "@/state/store";

interface Shape {
  count: number;
  name: string;
}

describe("store", () => {
  it("returns initial state", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    expect(s.get()).toEqual({ count: 0, name: "a" });
  });

  it("set updates state and notifies subscribers", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    s.subscribe(sub);
    s.set({ count: 1, name: "b" });
    expect(s.get()).toEqual({ count: 1, name: "b" });
    expect(sub).toHaveBeenCalledOnce();
    expect(sub).toHaveBeenCalledWith({ count: 1, name: "b" });
  });

  it("update applies a partial patch", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    s.update((d) => ({ count: d.count + 1 }));
    expect(s.get()).toEqual({ count: 1, name: "a" });
  });

  it("subscribe returns an unsubscribe", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    const off = s.subscribe(sub);
    off();
    s.update(() => ({ count: 99 }));
    expect(sub).not.toHaveBeenCalled();
  });

  it("select notifies only when the selected slice changes (===)", () => {
    const s = createStore<Shape>({ count: 0, name: "a" });
    const sub = vi.fn();
    s.select((d) => d.count, sub);
    s.update(() => ({ name: "b" })); // count unchanged
    expect(sub).not.toHaveBeenCalled();
    s.update(() => ({ count: 1 }));
    expect(sub).toHaveBeenCalledOnce();
    expect(sub).toHaveBeenCalledWith(1);
  });
});
