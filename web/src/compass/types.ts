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
  kbd: string;           // "⌘1"
  warm: boolean;
  when: string;          // "2m ago"
  preview: string;
}

// ── Mappers ──────────────────────────────────────────────────────────────────

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

// TODO: wire CompassNotif[] from unified notification inbox (calendar, tasks, system, CI).
// Initial angles hand-tuned to diagonal alleys; production should assign by source quadrant + jitter.
export const STUB_NOTIFS: CompassNotif[] = [
  { id: "n1", angle: -52, text: "build #482 ✓", kbd: "Ctrl 1", warm: false, when: "2m ago", preview: "all green · 14.2s · main · ready to deploy" },
  { id: "n2", angle: -38, text: "design review in 14m", kbd: "Ctrl 2", warm: true,  when: "14m",    preview: "w/ Harsh, Karoline, Fabio · room not booked" },
  { id: "n3", angle:  42, text: "immer migration done", kbd: "Ctrl 3", warm: false, when: "8m ago", preview: "store.ts migrated · 4 tests added · ready to review" },
  { id: "n4", angle:  58, text: "context 87%", kbd: "Ctrl 4", warm: true,  when: "now",    preview: "87K / 200K tokens used — consider compacting" },
  { id: "n5", angle: 138, text: "cpu load 0.42", kbd: "Ctrl 5", warm: false, when: "live",   preview: "load avg 0.42 · 1 core · 14.1GB free RAM" },
  { id: "n6", angle:-138, text: "stt latency 380ms", kbd: "Ctrl 6", warm: false, when: "live", preview: "avg 380ms · p95 640ms · last 5 turns" },
];
