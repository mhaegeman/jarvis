import { describe, it, expect } from "vitest";
import { TelemetryPanel } from "@/ui/panels/TelemetryPanel";
import type { TelemetryEvent } from "@/types";

const mount = (events: TelemetryEvent[]) => {
  document.body.innerHTML = `<div id="x"></div>`;
  const p = new TelemetryPanel("#x");
  p.mount({ events });
  return document.getElementById("x")!;
};

describe("TelemetryPanel", () => {
  it("renders empty when events is []", () => {
    const root = mount([]);
    expect(root.querySelectorAll(".line").length).toBe(0);
  });

  it("renders one .line per event with correct level class", () => {
    const events: TelemetryEvent[] = [
      { ts: 0, level: "info", message: "info msg" },
      { ts: 0, level: "ok", message: "ok msg" },
      { ts: 0, level: "warn", message: "warn msg" },
    ];
    const root = mount(events);
    const lines = root.querySelectorAll(".line");
    expect(lines.length).toBe(3);
    expect(lines[0].classList.contains("info")).toBe(true);
    expect(lines[1].classList.contains("ok")).toBe(true);
    expect(lines[2].classList.contains("warn")).toBe(true);
  });

  it("renders HH:MM:SS timestamp prefix matching the event ts", () => {
    // 2000-01-01T13:05:09Z = 946728309000 ms (UTC)
    // Use a fixed timestamp and derive expected string in UTC
    const ts = new Date("2000-01-01T13:05:09").getTime();
    const d = new Date(ts);
    const expected = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
    const root = mount([{ ts, level: "info", message: "hello" }]);
    expect(root.querySelector(".line")!.textContent).toContain(expected);
  });

  it("escapes HTML in messages", () => {
    const root = mount([{ ts: 0, level: "info", message: "<script>x</script>" }]);
    expect(root.innerHTML).not.toContain("<script>");
    expect(root.innerHTML).toContain("&lt;script&gt;");
  });

  it("caps at 14 events when given 20", () => {
    const events: TelemetryEvent[] = Array.from({ length: 20 }, (_, i) => ({
      ts: i,
      level: "info" as const,
      message: `event ${i}`,
    }));
    const root = mount(events);
    expect(root.querySelectorAll(".line").length).toBe(14);
  });
});
