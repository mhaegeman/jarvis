import { describe, it, expect, beforeEach } from "vitest";
import { VoiceDock } from "@/ui/compass/VoiceDock";
import { CommandHistory } from "@/ui/compass/commandHistory";
import type { Speaker } from "@/types";

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

describe("VoiceDock speaker dots", () => {
  it("renders a cyan dot for a jarvis command", () => {
    CommandHistory.push("jarvis command", "jarvis" as Speaker);
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    const html = document.getElementById("parent")?.innerHTML ?? "";
    // Dot should carry the cyan colour
    expect(html).toContain("speaker-dot");
    expect(html.toLowerCase()).toContain("#48d1cc");
    dock.destroy();
  });

  it("renders an amber dot for a pepper command", () => {
    CommandHistory.push("pepper command", "pepper" as Speaker);
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    const html = document.getElementById("parent")?.innerHTML ?? "";
    expect(html).toContain("speaker-dot");
    expect(html.toLowerCase()).toContain("#ffb86b");
    dock.destroy();
  });

  it("renders no dot when command has no speaker", () => {
    CommandHistory.push("plain command");
    document.body.innerHTML = `<div id="parent"></div>`;
    const dock = new VoiceDock(document.getElementById("parent")!);
    dock.show();
    const html = document.getElementById("parent")?.innerHTML ?? "";
    expect(html).not.toContain("speaker-dot");
    dock.destroy();
  });
});
