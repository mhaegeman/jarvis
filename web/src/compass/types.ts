/**
 * Compass-specific view types. These are richer than the runtime PanelData* types
 * and are adapted at the view layer to keep the backend protocol stable.
 */

import type { PanelDataCalendarEntry, PanelDataSystem, PanelDataMemory, PanelDataTasks } from "@/types";

export interface CompassCalendarEntry {
  time: string;          // "14:30"
  title: string;
  dur: string;           // "30m"
  state: "past" | "now" | "next";
  attendees: string[];
  room: string | null;
}

export interface CompassTask {
  id: string;
  state: "run" | "queue" | "done";
  label: string;
  meta: string;          // "step 4 / 7" — TODO: wire from agent runtime
  pct: number;           // progress 0-100 — TODO: wire from agent runtime
}

export interface CompassCodeFile {
  group: "modified" | "added" | "deleted";
  name: string;
  delta: string;         // "+58 / −22"
  active: boolean;
}

export interface CompassSystem {
  uptime: string;        // "02:14:08"
  load: string;          // "0.42"
  tokens: string;        // "1,240 tok/m"
  model: string;
  contextUsed: number;   // K tokens
  contextMax: number;    // K tokens
}

export interface CompassNotif {
  id: string;
  angle: number;         // degrees, hand-tuned to diagonal alleys
  text: string;
  warm: boolean;
  when: string;          // "2m ago"
  preview: string;
}

// ── Mappers ──────────────────────────────────────

export function mapCalendarEntries(
  entries: PanelDataCalendarEntry[],
): CompassCalendarEntry[] {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  return entries.map((e) => {
    const [hStr, mStr] = e.time.split(":");
    const entryMinutes = Number(hStr) * 60 + Number(mStr);
    const diffMin = entryMinutes - currentMinutes;

    let state: CompassCalendarEntry["state"];
    if (diffMin < -e.durationMin) state = "past";
    else if (diffMin <= 0) state = "now";
    else state = "next";

    return {
      time: e.time,
      title: e.title,
      dur: `${e.durationMin}m`,
      state,
      attendees: e.attendees,
      room: e.room,
    };
  });
}

export function mapSystem(
  system: PanelDataSystem | null,
  memory: PanelDataMemory | null,
  uptimeMs: number,
): CompassSystem {
  const s = Math.floor(uptimeMs / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const uptime = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;

  return {
    uptime,
    load: system?.load?.toFixed(2) ?? "—",
    tokens: system ? `${system.tokensPerMin.toLocaleString()} tok/m` : "—",
    model: system?.modelName ?? "—",
    contextUsed: memory ? Math.round(memory.contextUsed / 1000) : 0,
    contextMax: memory ? Math.round(memory.contextMax / 1000) : 200,
  };
}

export function mapTasks(
  tasks: PanelDataTasks | null,
): CompassTask[] {
  // TODO: wire individual task details from agent runtime (Temporal, BullMQ, custom).
  // PanelDataTasks only provides counts; detailed CompassTask rows need a richer source.
  // Interface: TaskDetail { id, label, state, step, totalSteps, pct }
  if (!tasks) return [];
  const rows: CompassTask[] = [];
  for (let i = 0; i < tasks.active; i++) {
    rows.push({ id: `run-${i}`, state: "run", label: "agent task running", meta: "step — / —", pct: 50 });
  }
  for (let i = 0; i < tasks.queued; i++) {
    rows.push({ id: `q-${i}`, state: "queue", label: "queued", meta: "", pct: 0 });
  }
  for (let i = 0; i < Math.min(tasks.done, 2); i++) {
    rows.push({ id: `done-${i}`, state: "done", label: "completed", meta: "", pct: 100 });
  }
  return rows;
}

// CompassCodeFile[] now comes from the live `/git/status` endpoint via
// `@/api/gitStatus` and is fetched by CompassApp on a poll. The stub array
// has been removed.

// CompassNotif[] is now produced live by `NotifManager` (see ui/compass/notifManager.ts)
// from calendar entries, tasks state transitions, and context budget.
// Build/CI source intentionally deferred — needs an external poller.
