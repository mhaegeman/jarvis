import { describe, it, expect } from "vitest";
import { buildCalendarTakeover } from "@/ui/compass/overlays/CalendarTakeover";
import type { CompassCalendarEntry } from "@/compass/types";

const makeEntry = (overrides: Partial<CompassCalendarEntry> = {}): CompassCalendarEntry => ({
  time: "14:00",
  title: "Design Review",
  dur: "60m",
  state: "now",
  attendees: [],
  room: null,
  ...overrides,
});

describe("CalendarTakeover", () => {
  it("renders attendees when provided", () => {
    const el = buildCalendarTakeover(
      [makeEntry({ attendees: ["Alice", "Bob"], room: null })],
      () => {},
    );
    expect(el.textContent).toContain("Alice");
    expect(el.textContent).toContain("Bob");
  });

  it("renders room when provided", () => {
    const el = buildCalendarTakeover(
      [makeEntry({ attendees: [], room: "Room 42" })],
      () => {},
    );
    expect(el.textContent).toContain("Room 42");
  });

  it("shows 'no details' when attendees empty and no room", () => {
    const el = buildCalendarTakeover([makeEntry()], () => {});
    expect(el.textContent).toContain("no details");
  });

  it("escapes XSS in attendee names", () => {
    const el = buildCalendarTakeover(
      [makeEntry({ attendees: ['<script>alert(1)</script>'], room: null })],
      () => {},
    );
    expect(el.innerHTML).not.toContain("<script>");
  });

  it("escapes XSS in room", () => {
    const el = buildCalendarTakeover(
      [makeEntry({ room: '<img src=x onerror="alert(1)">' })],
      () => {},
    );
    expect(el.innerHTML).not.toContain("<img src=x");
  });
});
