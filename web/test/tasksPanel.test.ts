import { describe, it, expect } from "vitest";
import { TasksPanel } from "@/ui/panels/TasksPanel";

describe("TasksPanel", () => {
  it("renders zeroes when state is all zero", () => {
    document.body.innerHTML = `<div id="x"></div>`;
    const p = new TasksPanel("#x");
    p.mount({ queued: 0, active: 0, done: 0 });
    const rows = document.querySelectorAll("#x .row");
    expect(rows.length).toBe(3);
    rows.forEach((r) => expect(r.querySelector("b")?.textContent).toBe("0"));
  });

  it("renders mixed state correctly", () => {
    document.body.innerHTML = `<div id="y"></div>`;
    const p = new TasksPanel("#y");
    p.mount({ queued: 1, active: 2, done: 5 });
    const rows = document.querySelectorAll("#y .row");
    expect(rows.length).toBe(3);
    expect(rows[0].querySelector("b")?.textContent).toBe("1");
    expect(rows[1].querySelector("b")?.textContent).toBe("2");
    expect(rows[2].querySelector("b")?.textContent).toBe("5");
  });

  it("renders high-volume done count verbatim without thousands separator", () => {
    document.body.innerHTML = `<div id="z"></div>`;
    const p = new TasksPanel("#z");
    p.mount({ queued: 0, active: 0, done: 1234 });
    const rows = document.querySelectorAll("#z .row");
    expect(rows.length).toBe(3);
    // done is the third row — no comma formatting, just the raw number
    expect(rows[2].querySelector("b")?.textContent).toBe("1234");
  });
});
