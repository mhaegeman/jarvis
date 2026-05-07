import { Component } from "@/ui/Component";
import { renderPanel } from "@/ui/Panel";

export interface TasksState {
  queued: number;
  active: number;
  done: number;
}

export class TasksPanel extends Component<TasksState> {
  override render(s: TasksState): void {
    renderPanel(
      this.root,
      "Tasks",
      `
      <div class="row"><span>queued</span><b>${s.queued}</b></div>
      <div class="row"><span>active</span><b>${s.active}</b></div>
      <div class="row"><span>done</span><b>${s.done}</b></div>
    `,
    );
  }
}
