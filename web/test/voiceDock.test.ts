import { describe, it, expect, beforeEach } from "vitest";
import { VoiceDock } from "@/ui/compass/VoiceDock";
import { CommandHistory } from "@/ui/compass/commandHistory";

beforeEach(() => localStorage.clear());

describe("VoiceDock", () => {
  it("renders 'no recent commands' when history is empty", () => {
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    expect(document.body.textContent).toContain("no recent commands");
    dock.destroy();
  });

  it("renders stored commands from CommandHistory on show()", () => {
    CommandHistory.push("What's on my calendar?");
    CommandHistory.push("Set a timer for 5 minutes");
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    expect(document.body.textContent).toContain("Set a timer for 5 minutes");
    expect(document.body.textContent).toContain("What's on my calendar?");
    dock.destroy();
  });

  it("re-renders on each show() to pick up new history", () => {
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    dock.hide();
    CommandHistory.push("new command after hide");
    dock.show();
    expect(document.body.textContent).toContain("new command after hide");
    dock.destroy();
  });
});
