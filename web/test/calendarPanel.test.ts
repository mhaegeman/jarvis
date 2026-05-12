import { describe, it, expect, vi } from "vitest";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";

const mount = (state: Parameters<CalendarPanel["mount"]>[0]) => {
  document.body.innerHTML = `<div id="x"></div>`;
  const p = new CalendarPanel("#x");
  p.mount(state);
  return document.getElementById("x")!;
};

describe("CalendarPanel", () => {
  it("shows empty state when entries is empty", () => {
    const root = mount({ entries: [], syncing: false, onSync: () => {} });
    expect(root.textContent).toContain("Click Sync");
  });

  it("calls onSync when the button is clicked", () => {
    const onSync = vi.fn();
    const root = mount({ entries: [], syncing: false, onSync });
    root.querySelector<HTMLButtonElement>(".sync-btn")?.click();
    expect(onSync).toHaveBeenCalledOnce();
  });

  it("disables the button while syncing", () => {
    const onSync = vi.fn();
    const root = mount({ entries: [], syncing: true, onSync });
    const btn = root.querySelector<HTMLButtonElement>(".sync-btn");
    expect(btn?.disabled).toBe(true);
    btn?.click();
    expect(onSync).not.toHaveBeenCalled();
  });

  it("renders a single entry with duration", () => {
    const root = mount({
      entries: [{ time: "09:00", title: "Standup", durationMin: 30, attendees: [], room: null }],
      syncing: false,
      onSync: () => {},
    });
    expect(root.textContent).toContain("09:00");
    expect(root.textContent).toContain("Standup");
    expect(root.textContent).toContain("(30m)");
  });

  it("renders 5 entries", () => {
    const entries = Array.from({ length: 5 }, (_, i) => ({
      time: `${String(8 + i).padStart(2, "0")}:00`,
      title: `Event ${i}`,
      durationMin: 30,
      attendees: [] as string[],
      room: null as string | null,
    }));
    const root = mount({ entries, syncing: false, onSync: () => {} });
    expect(root.querySelectorAll(".row").length).toBe(5);
  });

  it("escapes HTML in entry titles to prevent XSS (regression: PR#7 P1)", () => {
    const root = mount({
      entries: [
        {
          time: "09:00",
          title: `<img src=x onerror="alert(1)">`,
          durationMin: 30,
          attendees: [],
          room: null,
        },
      ],
      syncing: false,
      onSync: () => {},
    });
    // The raw markup must not appear in innerHTML — only its escaped form.
    expect(root.innerHTML).not.toContain("<img src=x");
    expect(root.innerHTML).toContain("&lt;img src=x");
    // Also confirm no real <img> element was created.
    expect(root.querySelector("img")).toBeNull();
  });
});
