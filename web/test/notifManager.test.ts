import { describe, it, expect, beforeEach } from "vitest";
import { NotifManager, type NotifInputs } from "@/ui/compass/notifManager";
import type {
  PanelDataCalendarEntry,
  PanelDataMemory,
  PanelDataTasks,
} from "@/types";

/** 2026-05-12T14:00:00Z — fixed clock used across tests. */
const T0 = new Date("2026-05-12T14:00:00Z").getTime();

const cal = (
  time: string,
  title: string,
  overrides: Partial<PanelDataCalendarEntry> = {},
): PanelDataCalendarEntry => ({
  time,
  title,
  durationMin: 30,
  attendees: [],
  room: null,
  ...overrides,
});

const minuteOffset = (mins: number): string => {
  const d = new Date(T0);
  d.setMinutes(d.getMinutes() + mins);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const baseInputs = (overrides: Partial<NotifInputs> = {}): NotifInputs => ({
  calendar: [],
  tasks: null,
  memory: null,
  now: T0,
  ...overrides,
});

describe("NotifManager — calendar source", () => {
  let mgr: NotifManager;
  beforeEach(() => {
    mgr = new NotifManager();
  });

  it("emits a chip for an event starting within the 5-minute lead window", () => {
    const entry = cal(minuteOffset(3), "design review");
    const chips = mgr.update(baseInputs({ calendar: [entry] }));
    expect(chips).toHaveLength(1);
    expect(chips[0].text).toMatch(/design review/);
    expect(chips[0].text).toMatch(/3m/);
    expect(chips[0].warm).toBe(true);
  });

  it("does not emit a chip for an event further out than the lead window", () => {
    const entry = cal(minuteOffset(20), "later");
    const chips = mgr.update(baseInputs({ calendar: [entry] }));
    expect(chips).toHaveLength(0);
  });

  it("does not emit a chip for an event already past", () => {
    const entry = cal(minuteOffset(-10), "done");
    const chips = mgr.update(baseInputs({ calendar: [entry] }));
    expect(chips).toHaveLength(0);
  });

  it("dedups across repeated updates for the same event", () => {
    const entry = cal(minuteOffset(2), "1:1");
    mgr.update(baseInputs({ calendar: [entry] }));
    mgr.update(baseInputs({ calendar: [entry] }));
    const chips = mgr.update(baseInputs({ calendar: [entry] }));
    expect(chips).toHaveLength(1);
  });

  it("clears the chip once the event passes out of the lead window", () => {
    const entry = cal(minuteOffset(2), "1:1");
    let chips = mgr.update(baseInputs({ calendar: [entry], now: T0 }));
    expect(chips).toHaveLength(1);
    // 10 minutes later the event is in the past — chip should be gone.
    chips = mgr.update(baseInputs({ calendar: [entry], now: T0 + 10 * 60_000 }));
    expect(chips).toHaveLength(0);
  });
});

describe("NotifManager — tasks source", () => {
  let mgr: NotifManager;
  beforeEach(() => {
    mgr = new NotifManager();
  });

  const tasks = (queued: number, active: number, done: number): PanelDataTasks => ({
    queued,
    active,
    done,
  });

  it("emits no chips on first observation (no baseline to diff against)", () => {
    const chips = mgr.update(baseInputs({ tasks: tasks(2, 1, 3) }));
    expect(chips).toHaveLength(0);
  });

  it("emits a chip when active count rises (queue->run)", () => {
    mgr.update(baseInputs({ tasks: tasks(2, 1, 0) }));
    const chips = mgr.update(baseInputs({ tasks: tasks(1, 2, 0) }));
    expect(chips.some((c) => /task started/.test(c.text))).toBe(true);
  });

  it("emits a chip when done count rises (run->done)", () => {
    mgr.update(baseInputs({ tasks: tasks(0, 1, 0) }));
    const chips = mgr.update(baseInputs({ tasks: tasks(0, 0, 1) }));
    expect(chips.some((c) => /task done/.test(c.text))).toBe(true);
  });

  it("does not re-emit on identical task state", () => {
    mgr.update(baseInputs({ tasks: tasks(0, 1, 0) }));
    mgr.update(baseInputs({ tasks: tasks(0, 0, 1) }));
    const chips = mgr.update(baseInputs({ tasks: tasks(0, 0, 1) }));
    // The previously emitted "task done" chip remains (transient) but no new one fires.
    expect(chips.filter((c) => /task done/.test(c.text))).toHaveLength(1);
  });

  it("expires transient task chips past their TTL", () => {
    mgr.update(baseInputs({ tasks: tasks(0, 1, 0), now: T0 }));
    let chips = mgr.update(baseInputs({ tasks: tasks(0, 0, 1), now: T0 }));
    expect(chips.some((c) => /task done/.test(c.text))).toBe(true);
    // Six minutes later the transient chip is gone.
    chips = mgr.update(
      baseInputs({ tasks: tasks(0, 0, 1), now: T0 + 6 * 60_000 }),
    );
    expect(chips.some((c) => /task done/.test(c.text))).toBe(false);
  });
});

describe("NotifManager — system context source", () => {
  let mgr: NotifManager;
  beforeEach(() => {
    mgr = new NotifManager();
  });

  const mem = (used: number, max = 200_000): PanelDataMemory => ({
    contextUsed: used,
    contextMax: max,
  });

  it("emits a chip when context usage exceeds 80%", () => {
    const chips = mgr.update(baseInputs({ memory: mem(170_000) }));
    expect(chips).toHaveLength(1);
    expect(chips[0].text).toMatch(/context 85%/);
  });

  it("does not emit a chip below threshold", () => {
    const chips = mgr.update(baseInputs({ memory: mem(80_000) }));
    expect(chips).toHaveLength(0);
  });

  it("clears the chip when usage drops back below threshold", () => {
    let chips = mgr.update(baseInputs({ memory: mem(180_000) }));
    expect(chips).toHaveLength(1);
    chips = mgr.update(baseInputs({ memory: mem(60_000) }));
    expect(chips).toHaveLength(0);
  });

  it("updates the chip text in place as the percentage moves", () => {
    let chips = mgr.update(baseInputs({ memory: mem(170_000) }));
    expect(chips[0].text).toMatch(/85%/);
    chips = mgr.update(baseInputs({ memory: mem(186_000) }));
    expect(chips[0].text).toMatch(/93%/);
  });
});

describe("NotifManager — display contract", () => {
  it("caps visible chips at 6", () => {
    const mgr = new NotifManager();
    const calendar = Array.from({ length: 10 }, (_, i) =>
      cal(minuteOffset(i % 5), `evt-${i}`),
    );
    const chips = mgr.update(baseInputs({ calendar }));
    expect(chips.length).toBeLessThanOrEqual(6);
  });

  it("assigns a non-empty angle and Ctrl-N kbd to each visible chip", () => {
    const mgr = new NotifManager();
    const entry = cal(minuteOffset(2), "1:1");
    const chips = mgr.update(baseInputs({ calendar: [entry] }));
    expect(chips[0].kbd).toBe("Ctrl 1");
    expect(typeof chips[0].angle).toBe("number");
  });

  it("reset() clears all internal state", () => {
    const mgr = new NotifManager();
    mgr.update(
      baseInputs({
        calendar: [cal(minuteOffset(2), "evt")],
        memory: { contextUsed: 170_000, contextMax: 200_000 },
      }),
    );
    mgr.reset();
    expect(mgr.snapshot()).toEqual([]);
  });
});
