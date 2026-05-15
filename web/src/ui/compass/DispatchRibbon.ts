import type { DispatchPlan, PlanSegment } from "@/types";
import type { AppState } from "@/main";
import type { Store } from "@/state/store";

/** Human-readable label for a segment mode. */
function modeLabel(segment: PlanSegment): string {
  switch (segment.mode) {
    case "codex_agent": return "code";
    case "chat":        return "chat";
    default:            return segment.mode;
  }
}

/** Capitalise the first letter of a speaker name. */
function capitaliseSpeaker(speaker: string): string {
  return speaker.charAt(0).toUpperCase() + speaker.slice(1);
}

/**
 * Pure function: returns the HTML string for the dispatch ribbon.
 * Returns an empty string when `plan` is null (ribbon is hidden).
 */
export function renderDispatchRibbon(plan: DispatchPlan | null): string {
  if (plan === null || plan.segments.length === 0) return "";

  const segments = plan.segments;

  if (segments.length === 1) {
    const seg = segments[0];
    const label = `${capitaliseSpeaker(seg.speaker)} (${modeLabel(seg)})`;
    return `<div class="dispatch-ribbon">${escHtml(label)}</div>`;
  }

  // 2 or 3 segments: render as "A → B (mode)" or "A → B (mode) → C (mode)"
  const parts = segments.map((seg, i) => {
    const name = capitaliseSpeaker(seg.speaker);
    // For the last segment, always show the mode; for earlier segments only
    // show the mode if it differs from "chat" (to keep the ribbon terse).
    const showMode = i === segments.length - 1 || seg.mode !== "chat";
    return showMode ? `${name} (${modeLabel(seg)})` : name;
  });

  const ribbon = parts.join(" → ");
  return `<div class="dispatch-ribbon">${escHtml(ribbon)}</div>`;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Mount the dispatch ribbon into `container`.
 * Subscribes to `lastPlan` in the store; re-renders whenever it changes.
 */
export function mountDispatchRibbon(
  container: HTMLElement,
  store: Store<AppState>,
): () => void {
  function render(state: AppState): void {
    const html = renderDispatchRibbon(state.lastPlan);
    container.innerHTML = html;
    container.style.display = html === "" ? "none" : "";
  }

  // Initial render
  render(store.get());

  // Subscribe to store changes
  return store.subscribe(render);
}
