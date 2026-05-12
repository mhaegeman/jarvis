import { describe, it, expect } from "vitest";
import { mapCalendarEntries } from "@/compass/types";
import type { PanelDataCalendarEntry } from "@/types";

describe("mapCalendarEntries with attendees/room", () => {
  it("passes attendees and room through from backend entry", () => {
    const entry: PanelDataCalendarEntry = {
      time: "14:00",
      title: "Design Review",
      durationMin: 60,
      attendees: ["Alice", "bob@example.com"],
      room: "Room 42",
    };
    const result = mapCalendarEntries([entry]);
    expect(result[0].attendees).toEqual(["Alice", "bob@example.com"]);
    expect(result[0].room).toBe("Room 42");
  });

  it("defaults attendees to [] and room to null when absent", () => {
    const entry: PanelDataCalendarEntry = {
      time: "09:00",
      title: "Solo",
      durationMin: 30,
      attendees: [],
      room: null,
    };
    const result = mapCalendarEntries([entry]);
    expect(result[0].attendees).toEqual([]);
    expect(result[0].room).toBeNull();
  });
});
