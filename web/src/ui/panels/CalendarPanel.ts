import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";
import type { CalendarEntry } from "@/data/calendar";

export interface CalendarState {
  entries: CalendarEntry[];
}

export class CalendarPanel extends Component<CalendarState> {
  override render(s: CalendarState): void {
    const rows = s.entries
      .map((e) => `<div class="row"><span>${e.time}</span><b>${e.title}</b></div>`)
      .join("");
    renderPanel(this.root, "Calendar", rows);
  }
}
