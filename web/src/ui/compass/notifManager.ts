/**
 * NotifManager — derives live notification chips from the panel data store.
 *
 * Replaces the static STUB_NOTIFS in CompassApp. Three sources are watched:
 *   1. Calendar: an entry whose start is within `CAL_LEAD_MIN` minutes ahead.
 *   2. Tasks:    state transitions queue→run (firing a "task started" chip)
 *                and run→done (firing a "task done" chip).
 *   3. System:   context budget usage > `CONTEXT_WARN_PCT` of contextMax.
 *
 * Chips are deduped by stable id, capped at `MAX_CHIPS`, and chips whose
 * source condition has resolved (event passed, task moved on, context dropped)
 * are removed automatically.
 *
 * Angle stability: chips claim a ring slot the first time they appear and
 * keep it until they leave. Slot positions are filled in display order
 * (newest-first among first-seen chips), so a freshly arriving chip lands
 * in the lowest available slot — established chips never shuffle. Removes
 * the per-tick angle reshuffle the original review flagged as P2.2.
 *
 * Known limitation (P2.3): a task that starts AND finishes inside one
 * tick only emits the "done" chip — we never see the queue→run edge
 * because porcelain only gives us before/after counts. Acceptable for
 * the current usage; switch to a per-task event stream if we ever need
 * the "started" chip in that case.
 *
 * The manager is pure logic over a `NotifInputs` snapshot. The caller is
 * expected to invoke `update(inputs)` once per render tick; `snapshot()`
 * returns the current chips, sorted by recency (most recent first).
 */

import type { CompassNotif } from "@/compass/types";
import type {
  PanelDataCalendarEntry,
  PanelDataMemory,
  PanelDataTasks,
} from "@/types";

export interface NotifInputs {
  calendar: PanelDataCalendarEntry[];
  tasks: PanelDataTasks | null;
  memory: PanelDataMemory | null;
  /** epoch ms; injectable for testing */
  now: number;
}

/** Hand-tuned ring angles (degrees) for chip placement — mirrors the prior stub layout. */
const CHIP_ANGLES = [-52, -38, 42, 58, 138, -138] as const;

const CAL_LEAD_MIN = 5;
const CONTEXT_WARN_PCT = 0.80;
const MAX_CHIPS = 6;
/** Auto-expire transient chips (task done / task started) after this long. */
const TRANSIENT_TTL_MS = 5 * 60_000;

interface ChipMeta extends CompassNotif {
  /** epoch ms when the chip was first surfaced; used for sort + expiry. */
  createdAt: number;
  /** If true, chip remains until TTL elapses even after source condition clears. */
  transient: boolean;
}

export class NotifManager {
  private chips: Map<string, ChipMeta> = new Map();
  /** Previous task counts to detect queue→run and run→done transitions. */
  private prevTasks: { queued: number; active: number; done: number } | null = null;
  /** Counter to give each task transition a unique id. */
  private taskSeq = 0;
  /**
   * Stable slot map: chip id → angle. Once a chip claims a slot it keeps
   * it for its lifetime; removed chips free their slot for new arrivals.
   * Solves the P2.2 jitter where every tick re-sorted by createdAt and
   * re-assigned angles, making chips visibly shuffle.
   */
  private slotByChipId: Map<string, number> = new Map();

  /** Reset internal state (test helper / hot-reload). */
  reset(): void {
    this.chips.clear();
    this.prevTasks = null;
    this.taskSeq = 0;
    this.slotByChipId.clear();
  }

  /** Snapshot of current chips, sorted by recency, capped at MAX_CHIPS. */
  snapshot(): CompassNotif[] {
    const out: ChipMeta[] = [...this.chips.values()];
    out.sort((a, b) => b.createdAt - a.createdAt);
    return out.slice(0, MAX_CHIPS).map(({ createdAt: _c, transient: _t, ...rest }) => rest);
  }

  /**
   * Reconcile chips against a fresh input snapshot. Returns the new chip list.
   * Idempotent: calling repeatedly with the same inputs at the same `now` yields
   * the same set of chips.
   */
  update(inputs: NotifInputs): CompassNotif[] {
    const { calendar, tasks, memory, now } = inputs;

    // --- 1. Calendar: keep one chip per upcoming entry within CAL_LEAD_MIN.
    const activeCalIds = new Set<string>();
    for (const entry of calendar) {
      const startMs = parseEntryStart(entry, now);
      if (startMs === null) continue;
      const minutesUntil = (startMs - now) / 60_000;
      if (minutesUntil < 0 || minutesUntil > CAL_LEAD_MIN) continue;

      const id = calId(entry);
      activeCalIds.add(id);
      if (!this.chips.has(id)) {
        this.chips.set(id, {
          id,
          angle: 0,
          text: `${entry.title} in ${Math.max(0, Math.round(minutesUntil))}m`,
          warm: true,
          when: entry.time,
          preview: this.calPreview(entry),
          createdAt: now,
          transient: false,
        });
      } else {
        // Refresh countdown text in-place; don't bump createdAt.
        const chip = this.chips.get(id)!;
        chip.text = `${entry.title} in ${Math.max(0, Math.round(minutesUntil))}m`;
      }
    }
    // Drop calendar chips whose condition no longer holds.
    for (const id of [...this.chips.keys()]) {
      if (id.startsWith("cal:") && !activeCalIds.has(id)) {
        this.chips.delete(id);
      }
    }

    // --- 2. Tasks: detect queue→run and run→done transitions vs previous snapshot.
    if (tasks) {
      const prev = this.prevTasks;
      if (prev) {
        // Counter reset (e.g. new session): `done` going down means the
        // tracked totals were restarted. Skip transition diffing this tick
        // and re-baseline so the next diff is against the new floor —
        // otherwise the next tick would interpret the rebound as a wave
        // of "task started"/"task done" events.
        if (tasks.done < prev.done) {
          this.prevTasks = { queued: tasks.queued, active: tasks.active, done: tasks.done };
        } else {
          // Active count rising = at least that many queue→run transitions
          // this tick. We deliberately can't detect tasks that start AND
          // finish in the same tick — that limitation is documented at the
          // top of this file.
          const startedCount = Math.max(0, tasks.active - prev.active);
          const doneCount = Math.max(0, tasks.done - prev.done);
          for (let i = 0; i < startedCount; i++) {
            const id = `task-start:${++this.taskSeq}`;
            this.chips.set(id, {
              id,
              angle: 0,
              text: "task started",
              warm: false,
              when: "now",
              preview: `${tasks.active} active · ${tasks.queued} queued`,
              createdAt: now,
              transient: true,
            });
          }
          for (let i = 0; i < doneCount; i++) {
            const id = `task-done:${++this.taskSeq}`;
            this.chips.set(id, {
              id,
              angle: 0,
              text: "task done",
              warm: false,
              when: "now",
              preview: `${tasks.done} completed total`,
              createdAt: now,
              transient: true,
            });
          }
          this.prevTasks = { queued: tasks.queued, active: tasks.active, done: tasks.done };
        }
      } else {
        this.prevTasks = { queued: tasks.queued, active: tasks.active, done: tasks.done };
      }
    }

    // --- 3. System: context budget over CONTEXT_WARN_PCT.
    const ctxId = "sys:context";
    if (memory && memory.contextMax > 0) {
      const pct = memory.contextUsed / memory.contextMax;
      if (pct > CONTEXT_WARN_PCT) {
        const text = `context ${Math.round(pct * 100)}%`;
        const preview = `${Math.round(memory.contextUsed / 1000)}K / ${Math.round(memory.contextMax / 1000)}K tokens used`;
        const existing = this.chips.get(ctxId);
        if (!existing) {
          this.chips.set(ctxId, {
            id: ctxId,
            angle: 0,
            text,
            warm: true,
            when: "live",
            preview,
            createdAt: now,
            transient: false,
          });
        } else {
          existing.text = text;
          existing.preview = preview;
        }
      } else if (this.chips.has(ctxId)) {
        this.chips.delete(ctxId);
      }
    } else if (this.chips.has(ctxId)) {
      this.chips.delete(ctxId);
    }

    // --- Expire transient chips past their TTL.
    for (const [id, chip] of [...this.chips.entries()]) {
      if (chip.transient && now - chip.createdAt > TRANSIENT_TTL_MS) {
        this.chips.delete(id);
      }
    }

    // --- Free slot reservations for chips that no longer exist. New
    // chips fill freed slots from lowest index up (stable placement).
    for (const id of [...this.slotByChipId.keys()]) {
      if (!this.chips.has(id)) this.slotByChipId.delete(id);
    }

    // Assign stable angles via the slot map.
    const display = this.snapshot();
    const usedSlots = new Set(this.slotByChipId.values());
    let nextSlot = 0;
    const allocSlot = (): number => {
      while (usedSlots.has(nextSlot) && nextSlot < CHIP_ANGLES.length) nextSlot++;
      const slot = nextSlot < CHIP_ANGLES.length ? nextSlot : 0;
      usedSlots.add(slot);
      nextSlot++;
      return slot;
    };
    return display.map((chip) => {
      let slot = this.slotByChipId.get(chip.id);
      if (slot === undefined) {
        slot = allocSlot();
        this.slotByChipId.set(chip.id, slot);
      }
      return { ...chip, angle: CHIP_ANGLES[slot % CHIP_ANGLES.length] };
    });
  }

  private calPreview(entry: PanelDataCalendarEntry): string {
    const parts: string[] = [];
    if (entry.attendees.length > 0) parts.push(`w/ ${entry.attendees.join(", ")}`);
    if (entry.room) parts.push(entry.room);
    parts.push(`${entry.durationMin}m`);
    return parts.join(" · ");
  }
}

function calId(entry: PanelDataCalendarEntry): string {
  return `cal:${entry.time}:${entry.title}`;
}

/**
 * Parse a "HH:MM" calendar entry start into epoch ms anchored to today.
 * Returns null when the format is unexpected. Times that already passed
 * earlier today still resolve to today's epoch — the caller filters by
 * elapsed minutes.
 */
function parseEntryStart(entry: PanelDataCalendarEntry, now: number): number | null {
  const [hStr, mStr] = entry.time.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  const d = new Date(now);
  d.setHours(h, m, 0, 0);
  return d.getTime();
}
