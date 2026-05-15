import type { Speaker } from "@/types";

const STORAGE_KEY = "jarvis_recent_commands";
const MAX_ENTRIES = 8;

export interface CommandEntry {
  text: string;
  speaker?: Speaker;
}

function load(): CommandEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((e): CommandEntry | null => {
        if (typeof e === "string") return { text: e };
        if (e && typeof (e as Record<string, unknown>).text === "string") {
          const entry: CommandEntry = { text: (e as { text: string }).text };
          const spk = (e as { speaker?: unknown }).speaker;
          if (spk === "jarvis" || spk === "pepper") entry.speaker = spk;
          return entry;
        }
        return null;
      })
      .filter((e): e is CommandEntry => e !== null && e.text.length > 0);
  } catch {
    return [];
  }
}

function save(entries: CommandEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // localStorage full or unavailable — silently skip
  }
}

export const CommandHistory = {
  /** Returns recent command entries (newest-first). */
  recentEntries(): CommandEntry[] {
    return load();
  },

  /** Returns recent command text strings (newest-first). Back-compat API. */
  recent(): string[] {
    return load().map((e) => e.text);
  },

  push(text: string, speaker?: Speaker): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    const entries = load().filter((e) => e.text !== trimmed);
    const entry: CommandEntry = { text: trimmed };
    if (speaker) entry.speaker = speaker;
    entries.unshift(entry);
    save(entries.slice(0, MAX_ENTRIES));
  },
};
