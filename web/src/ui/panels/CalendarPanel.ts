import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { PanelDataCalendarEntry } from "@/types";

export interface CalendarState {
  entries: PanelDataCalendarEntry[];
  syncing: boolean;
  onSync: () => void;
}

export class CalendarPanel extends Component<CalendarState> {
  override render(s: CalendarState): void {
    const body =
      s.entries.length === 0
        ? `<div class="row empty">Click Sync to load today's calendar</div>`
        : s.entries
            .map((e) => {
              const duration = e.durationMin > 0 ? ` (${e.durationMin}m)` : "";
              return `<div class="row"><span>${e.time}</span><b>${e.title}${duration}</b></div>`;
            })
            .join("");

    renderPanel(this.root, "Calendar", body);

    // Add sync button as a sibling to the title inside h4
    const h4 = this.root.querySelector("h4");
    if (h4) {
      const btn = document.createElement("button");
      btn.className = "sync-btn";
      btn.dataset.action = "calendar-sync";
      if (s.syncing) {
        btn.disabled = true;
        btn.dataset.syncing = "true";
        btn.textContent = "Syncing…";
      } else {
        btn.textContent = "Sync";
      }
      h4.appendChild(btn);
    }

    // Attach click listener (idempotent — replaces on each render via innerHTML)
    const btn = this.root.querySelector<HTMLButtonElement>(".sync-btn");
    if (btn) {
      btn.addEventListener("click", () => {
        if (!s.syncing) {
          s.onSync();
        }
      });
    }
  }
}
