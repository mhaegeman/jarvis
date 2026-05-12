import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NotifRing } from "@/ui/compass/NotifRing";
import type { CompassNotif } from "@/compass/types";

/**
 * NotifRing renders chips to absolute viewport positions relative to the
 * #compass-disc element. Tests mount a small DOM scaffold, then inspect
 * the rendered chips directly — we care about real text/className/DOM
 * mutations, not the manager's array shape.
 */

const chip = (overrides: Partial<CompassNotif> = {}): CompassNotif => ({
  id: "x",
  angle: 0,
  text: "hello",
  warm: false,
  when: "now",
  preview: "p",
  ...overrides,
});

let host: HTMLElement;
let ring: NotifRing;

beforeEach(() => {
  document.body.innerHTML = `<div id="app"></div><div id="compass-disc"></div>`;
  host = document.getElementById("app")!;
  // jsdom returns zeroed rects by default; that's fine — we test
  // existence + content, not pixel positions.
  ring = new NotifRing(host);
});

afterEach(() => {
  ring.destroy();
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("NotifRing — reconciliation", () => {
  it("creates a chip on first render of a new id", () => {
    ring.render([chip({ id: "a", text: "first" })]);
    const el = host.querySelector(".notif");
    expect(el).not.toBeNull();
    expect(el!.querySelector(".ntext")!.textContent).toBe("first");
  });

  it("updates chip text in place across renders without rebuilding the node", () => {
    ring.render([chip({ id: "a", text: "in 3m" })]);
    const before = host.querySelector(".notif") as HTMLElement;
    ring.render([chip({ id: "a", text: "in 2m" })]);
    const after = host.querySelector(".notif") as HTMLElement;
    // Same DOM node → CSS transitions stay intact (P1.1).
    expect(after).toBe(before);
    expect(after.querySelector(".ntext")!.textContent).toBe("in 2m");
  });

  it("refreshes the warm modifier when the chip flips state", () => {
    ring.render([chip({ id: "a", warm: false })]);
    expect(host.querySelector(".notif")!.classList.contains("warm")).toBe(false);
    ring.render([chip({ id: "a", warm: true })]);
    expect(host.querySelector(".notif")!.classList.contains("warm")).toBe(true);
  });

  it("refreshes preview text in place", () => {
    ring.render([chip({ id: "a", preview: "v1" })]);
    ring.render([chip({ id: "a", preview: "v2" })]);
    const preview = host.querySelector(".preview")!;
    // .preview = .when + text node body
    expect(preview.textContent).toContain("v2");
    expect(preview.textContent).not.toContain("v1");
  });

  it("removes a chip when its id leaves the input (zombie cleanup P1.1)", () => {
    vi.useFakeTimers();
    ring.render([chip({ id: "a" })]);
    expect(host.querySelectorAll(".notif").length).toBe(1);
    ring.render([]);
    // Chip is marked dismissing immediately, then removed after the fade.
    expect(host.querySelector(".notif")!.classList.contains("dismissing")).toBe(true);
    vi.advanceTimersByTime(400);
    expect(host.querySelectorAll(".notif").length).toBe(0);
  });
});

describe("NotifRing — dismissal (P1.2)", () => {
  it("dismissed chips stay gone on subsequent renders with the same input", () => {
    vi.useFakeTimers();
    ring.render([chip({ id: "a", text: "go away" })]);
    const el = host.querySelector(".notif") as HTMLElement;
    el.click();
    vi.advanceTimersByTime(400);
    // Manager re-supplies the same id (e.g. countdown still in window).
    ring.render([chip({ id: "a", text: "go away" })]);
    expect(host.querySelectorAll(".notif").length).toBe(0);
  });

  it("forgets the dismissal once the source condition clears so the id can re-appear", () => {
    vi.useFakeTimers();
    ring.render([chip({ id: "a" })]);
    (host.querySelector(".notif") as HTMLElement).click();
    vi.advanceTimersByTime(400);
    // Source resolved — id no longer in input.
    ring.render([]);
    vi.advanceTimersByTime(400);
    // Same id re-arrives later (new qualifying event).
    ring.render([chip({ id: "a", text: "round two" })]);
    const el = host.querySelector(".notif");
    expect(el).not.toBeNull();
    expect(el!.querySelector(".ntext")!.textContent).toBe("round two");
  });

  it("dismissing one chip doesn't affect other chips' visibility", () => {
    vi.useFakeTimers();
    ring.render([chip({ id: "a", text: "A" }), chip({ id: "b", text: "B" })]);
    const aEl = Array.from(host.querySelectorAll(".notif")).find(
      (c) => c.querySelector(".ntext")?.textContent === "A",
    ) as HTMLElement;
    aEl.click();
    vi.advanceTimersByTime(400);
    ring.render([chip({ id: "a", text: "A" }), chip({ id: "b", text: "B" })]);
    const labels = Array.from(host.querySelectorAll(".ntext")).map(
      (n) => n.textContent,
    );
    expect(labels).toEqual(["B"]);
  });
});

describe("NotifRing — countdown ticks (regression for P1.1)", () => {
  it("updates calendar countdown text on each render, not just on first surface", () => {
    ring.render([chip({ id: "cal:1", text: "1:1 in 3m" })]);
    ring.render([chip({ id: "cal:1", text: "1:1 in 2m" })]);
    ring.render([chip({ id: "cal:1", text: "1:1 in 1m" })]);
    expect(host.querySelector(".ntext")!.textContent).toBe("1:1 in 1m");
  });

  it("updates context% chip text on each render", () => {
    ring.render([chip({ id: "sys:context", text: "context 85%" })]);
    ring.render([chip({ id: "sys:context", text: "context 93%" })]);
    expect(host.querySelector(".ntext")!.textContent).toBe("context 93%");
  });
});
