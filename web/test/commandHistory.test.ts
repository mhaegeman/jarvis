import { describe, it, expect, beforeEach } from "vitest";
import { CommandHistory } from "@/ui/compass/commandHistory";

beforeEach(() => localStorage.clear());

describe("CommandHistory.recent()", () => {
  it("returns empty array when nothing stored", () => {
    expect(CommandHistory.recent()).toEqual([]);
  });

  it("returns previously pushed commands newest-first", () => {
    CommandHistory.push("first command");
    CommandHistory.push("second command");
    expect(CommandHistory.recent()).toEqual(["second command", "first command"]);
  });
});

describe("CommandHistory.push()", () => {
  it("deduplicates: pushes existing entry to front instead of duplicating", () => {
    CommandHistory.push("hello");
    CommandHistory.push("world");
    CommandHistory.push("hello");
    expect(CommandHistory.recent()).toEqual(["hello", "world"]);
  });

  it("trims to 8 entries", () => {
    for (let i = 0; i < 12; i++) CommandHistory.push(`command ${i}`);
    expect(CommandHistory.recent().length).toBe(8);
  });

  it("persists across module calls (simulating page reload via fresh read)", () => {
    CommandHistory.push("persistent command");
    // Storage format is now CommandEntry[]; verify round-trip via the public API.
    expect(CommandHistory.recent()).toContain("persistent command");
  });

  it("ignores blank strings", () => {
    CommandHistory.push("");
    CommandHistory.push("   ");
    expect(CommandHistory.recent()).toEqual([]);
  });
});

describe("CommandHistory integrates with stt.final (unit check)", () => {
  it("push + recent round-trip works for a real voice command string", () => {
    const cmd = "Brief me on today's agenda";
    CommandHistory.push(cmd);
    expect(CommandHistory.recent()[0]).toBe(cmd);
  });
});

describe("CommandHistory tolerates corrupted localStorage", () => {
  it("returns [] when stored value is a JSON object (not array)", () => {
    localStorage.setItem("jarvis_recent_commands", JSON.stringify({ foo: "bar" }));
    expect(CommandHistory.recent()).toEqual([]);
  });

  it("returns [] when stored value is a JSON string (not array)", () => {
    localStorage.setItem("jarvis_recent_commands", JSON.stringify("legacy data"));
    expect(CommandHistory.recent()).toEqual([]);
  });

  it("filters out non-string elements from a mixed array", () => {
    localStorage.setItem(
      "jarvis_recent_commands",
      JSON.stringify(["valid", 42, null, "also valid", { x: 1 }]),
    );
    expect(CommandHistory.recent()).toEqual(["valid", "also valid"]);
  });

  it("push() works after recovering from a non-array stored value", () => {
    localStorage.setItem("jarvis_recent_commands", JSON.stringify({ foo: "bar" }));
    CommandHistory.push("new command");
    expect(CommandHistory.recent()).toEqual(["new command"]);
  });
});
