# Calendar Attendees & Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forward `attendees` and `room` from the Google Calendar API response through the backend `project_events` function, the WebSocket `calendar.update` protocol, the frontend types, and into the CalendarTakeover overlay's "who" line (replacing the "details not yet available" stub).

**Architecture:** The Google Calendar API already returns `attendees[]` (each with a `displayName` or `email`) and `location` on each event object. `project_events` in `calendar_client.py` currently discards these. We add them to the projected dict; the `calendar_update` server message already sends raw dicts so no protocol change is needed. On the frontend, `PanelDataCalendarEntry` and `CompassCalendarEntry` grow `attendees: string[]` and `room: string | null`; the `mapCalendarEntries` mapper passes them through; `CalendarTakeover` renders them in the `.who` div.

**Tech Stack:** Python (calendar_client.py), TypeScript (types.ts, compass/types.ts, CalendarTakeover.ts)

**Branch:** `feat/calendar-attendees` (branch off `main`)

---

### Environment setup

```bash
cd /home/user/jarvis
git fetch origin main
git checkout -b feat/calendar-attendees origin/main
```

Backend baseline:
```bash
cd server && uv run --extra dev pytest -q
```

Frontend baseline:
```bash
cd /home/user/jarvis/web && npm run test -- --run 2>&1 | tail -5
```

Both must be green before touching code.

---

### Task 1: Extend `project_events` to include attendees and room

**Files:**
- Modify: `server/server/calendar_client.py`
- Modify: `server/tests/test_calendar_client.py`

The Google Calendar API returns attendees as:
```json
"attendees": [{"displayName": "Alice", "email": "alice@example.com"}, ...]
```
and room/location as:
```json
"location": "Room 42"
```

We project `attendees` as a list of display names (falling back to email when `displayName` is absent), and `room` as the `location` string or `null` when absent.

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_calendar_client.py`:

```python
def test_project_events_includes_attendees_and_room() -> None:
    raw = [
        {
            "summary": "Design Review",
            "start": {"dateTime": "2026-05-08T14:00:00+00:00"},
            "end": {"dateTime": "2026-05-08T15:00:00+00:00"},
            "attendees": [
                {"displayName": "Alice", "email": "alice@example.com"},
                {"email": "bob@example.com"},
            ],
            "location": "Room 42",
        }
    ]
    out = project_events(raw)
    assert out[0]["attendees"] == ["Alice", "bob@example.com"]
    assert out[0]["room"] == "Room 42"


def test_project_events_attendees_defaults_to_empty() -> None:
    raw = [_evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "Solo")]
    out = project_events(raw)
    assert out[0]["attendees"] == []
    assert out[0]["room"] is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/server
uv run --extra dev pytest tests/test_calendar_client.py::test_project_events_includes_attendees_and_room tests/test_calendar_client.py::test_project_events_attendees_defaults_to_empty -v
```
Expected: both FAIL (KeyError or AssertionError — `attendees` not in projected dict)

- [ ] **Step 3: Update `project_events`**

In `server/server/calendar_client.py`, replace the `project_events` function body. The key change is adding attendee/room extraction before appending to `out`:

```python
def project_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map raw `events.list` items to panel entries; drop all-day events."""
    out: list[tuple[dt.datetime, dict[str, Any]]] = []
    for ev in items:
        start_obj = ev.get("start") or {}
        end_obj = ev.get("end") or {}
        start_dt = start_obj.get("dateTime")
        end_dt = end_obj.get("dateTime")
        if not start_dt or not end_dt:
            continue
        start = dt.datetime.fromisoformat(start_dt)
        end = dt.datetime.fromisoformat(end_dt)
        title = (ev.get("summary") or "").strip() or "(no title)"
        duration_min = max(0, int((end - start).total_seconds() // 60))
        raw_attendees: list[dict[str, Any]] = ev.get("attendees") or []
        attendees = [
            a.get("displayName") or a.get("email") or ""
            for a in raw_attendees
            if a.get("displayName") or a.get("email")
        ]
        room: str | None = ev.get("location") or None
        out.append(
            (
                start,
                {
                    "time": start.strftime("%H:%M"),
                    "title": title,
                    "durationMin": duration_min,
                    "attendees": attendees,
                    "room": room,
                },
            )
        )
    out.sort(key=lambda x: x[0])
    return [entry for _, entry in out]
```

- [ ] **Step 4: Run new tests — expect green**

```bash
uv run --extra dev pytest tests/test_calendar_client.py -v
```
Expected: all tests PASS (including existing ones — the new fields are additive)

- [ ] **Step 5: Full backend suite + lint**

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check server/
uv run --extra dev mypy --strict server/
```
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add server/server/calendar_client.py server/tests/test_calendar_client.py
git commit -m "feat(calendar): forward attendees and room from Google Calendar API"
```

---

### Task 2: Extend frontend types

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/compass/types.ts`

- [ ] **Step 1: Write the failing test**

Create `web/test/calendarTypes.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/web
npm run test -- calendarTypes --run 2>&1 | tail -20
```
Expected: FAIL (type error — `attendees` not on `PanelDataCalendarEntry`)

- [ ] **Step 3: Extend `PanelDataCalendarEntry` in `web/src/types.ts`**

Find `PanelDataCalendarEntry` (currently lines 56–60) and add the two new fields:

```typescript
export interface PanelDataCalendarEntry {
  time: string;
  title: string;
  durationMin: number;
  attendees: string[];
  room: string | null;
}
```

- [ ] **Step 4: Extend `CompassCalendarEntry` in `web/src/compass/types.ts`**

Find `CompassCalendarEntry` (currently lines 8–13) and add:

```typescript
export interface CompassCalendarEntry {
  time: string;
  title: string;
  dur: string;
  state: "past" | "now" | "next";
  attendees: string[];
  room: string | null;
}
```

Then update `mapCalendarEntries` to pass the new fields through. Find the `return { time, title, dur, state }` object in the `.map()` and add the two fields:

```typescript
    return {
      time: e.time,
      title: e.title,
      dur: `${e.durationMin}m`,
      state,
      attendees: e.attendees,
      room: e.room,
    };
```

- [ ] **Step 5: Run the new test — expect green**

```bash
npm run test -- calendarTypes --run 2>&1 | tail -20
```
Expected: 2 tests PASS

- [ ] **Step 6: Run full frontend suite**

```bash
npm run test -- --run 2>&1 | tail -10
```
Expected: all tests PASS

- [ ] **Step 7: Type-check**

```bash
npm run build 2>&1 | tail -10
```
Expected: clean build

- [ ] **Step 8: Commit**

```bash
git add web/src/types.ts web/src/compass/types.ts web/test/calendarTypes.test.ts
git commit -m "feat(calendar): add attendees and room to frontend types and mapper"
```

---

### Task 3: Render attendees and room in `CalendarTakeover`

**Files:**
- Modify: `web/src/ui/compass/overlays/CalendarTakeover.ts`
- Create: `web/test/calendarTakeover.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/test/calendarTakeover.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/web
npm run test -- calendarTakeover --run 2>&1 | tail -20
```
Expected: FAIL (type errors or "details not yet available" text mismatch)

- [ ] **Step 3: Update `CalendarTakeover.ts`**

Replace the `.who` div content in `buildCalendarTakeover`. Find the `<div class="who">` block and replace it:

```typescript
  // Build the "who" line: attendees list + room, or "no details"
  const whoLines: string[] = [];
  if (current.attendees.length > 0) {
    whoLines.push(current.attendees.map(escHtml).join(" · "));
  }
  if (current.room) {
    whoLines.push(escHtml(current.room));
  }
  const whoText = whoLines.length > 0 ? whoLines.join(" · ") : "no details";
```

Then in the `.innerHTML` template, replace the `<div class="who">` block with:

```typescript
      <div class="who">
        ${current.dur} · ${whoText}
      </div>
```

The full updated `overlay.innerHTML` template's `.who` line becomes:
```
      <div class="who">
        ${current.dur} · ${whoText}
      </div>
```

Make sure `whoText` is computed before the `overlay.innerHTML = \`...\`` assignment.

- [ ] **Step 4: Run tests — expect green**

```bash
npm run test -- calendarTakeover --run 2>&1 | tail -20
```
Expected: 5 tests PASS

- [ ] **Step 5: Full suite + type check**

```bash
npm run test -- --run 2>&1 | tail -10
npm run build 2>&1 | tail -10
```
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/compass/overlays/CalendarTakeover.ts web/test/calendarTakeover.test.ts
git commit -m "feat(calendar): render attendees and room in CalendarTakeover overlay"
```

---

### Task 4: Push branch

```bash
git push -u origin feat/calendar-attendees
```

**Merge order note:** Merge this branch third (after `feat/voice-dock-history` and `feat/auth-login`).
