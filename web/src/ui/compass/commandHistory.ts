const STORAGE_KEY = "jarvis_recent_commands";
const MAX_ENTRIES = 8;

function load(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function save(entries: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // localStorage full or unavailable — silently skip
  }
}

export const CommandHistory = {
  recent(): string[] {
    return load();
  },

  push(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    const entries = load().filter((e) => e !== trimmed);
    entries.unshift(trimmed);
    save(entries.slice(0, MAX_ENTRIES));
  },
};
