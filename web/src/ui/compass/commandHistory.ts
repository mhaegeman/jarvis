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

  /**
   * Tag the most-recent entry with a speaker. Called when `dispatch.plan`
   * arrives AFTER the matching `stt.final` — the speaker for the current
   * turn isn't known until then. No-op when the entry already has a
   * speaker (later same-turn plans don't overwrite) or when the entry
   * text has drifted (different command in the meantime).
   */
  tagLastSpeaker(text: string, speaker: Speaker): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    const entries = load();
    if (entries.length === 0 || entries[0].text !== trimmed) return;
    if (entries[0].speaker !== undefined) return;
    entries[0] = { ...entries[0], speaker };
    save(entries);
  },
};
