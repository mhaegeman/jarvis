import type { CompassCalendarEntry } from "@/compass/types";

export function buildCalendarTakeover(
  entries: CompassCalendarEntry[],
  onClose: () => void,
): HTMLElement {
  const overlay = document.createElement("div");
  overlay.className = "overlay";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) onClose(); });

  // Pick the most relevant event: "now" > nearest "next" > first entry
  const current =
    entries.find((e) => e.state === "now") ??
    entries.find((e) => e.state === "next") ??
    entries[0];

  if (!current) {
    overlay.innerHTML = `<div class="takeover-card">
      <button class="close" style="position:absolute;top:14px;right:18px;font-family:var(--mono);font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-3);background:none;border:none;cursor:pointer;">esc · close</button>
      <div class="now-eyebrow" style="margin-bottom:16px;">no upcoming events</div>
    </div>`;
    overlay.querySelector(".close")?.addEventListener("click", onClose);
    return overlay;
  }

  const eyebrow = current.state === "now"
    ? `now · ${current.time}`
    : `in ${current.dur} · ${current.time}`;

  // TODO: wire attendee and room info from calendar source (e.g. macOS EventKit / Google Calendar API)
  // Interface: CalendarEvent { title, time, durationMin, attendees: string[], room: string | null }
  overlay.innerHTML = `
    <div class="takeover-card">
      <button class="close" style="position:absolute;top:14px;right:18px;font-family:var(--mono);font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-3);background:none;border:none;cursor:pointer;" aria-label="Close">esc · close</button>
      <div class="now-eyebrow">${escHtml(eyebrow)}</div>
      <div class="what">${escHtml(current.title)}</div>
      <div class="who">
        <!-- TODO: wire attendees from calendar source -->
        ${current.dur} · details not yet available
      </div>
      <div class="actions">
        <button class="f-btn">snooze 5m</button>
        <button class="f-btn">prep notes</button>
        <button class="f-btn solid">ok, ready</button>
      </div>
    </div>`;

  overlay.querySelector(".close")?.addEventListener("click", onClose);
  overlay.querySelectorAll(".f-btn").forEach((btn) => btn.addEventListener("click", onClose));

  return overlay;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
