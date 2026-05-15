import type { AgentStep, AgentApproval, AgentProgress } from "@/types";

// Minimal interface for the events object the panel needs.
interface AgentEvents {
  on(event: "agent.step", handler: (payload: AgentStep) => void): () => void;
  on(event: "agent.approval", handler: (payload: AgentApproval) => void): () => void;
  on(event: "agent.progress", handler: (payload: AgentProgress) => void): () => void;
  sendAgentApprove(runId: string, choice: string): void;
  sendAgentCancel(runId: string): void;
}

// Minimal store shape the panel reads.
interface AgentStore {
  get(): { activeAgentRun: { runId: string; task: string; speaker: string } | null };
  subscribe(fn: (state: { activeAgentRun: { runId: string; task: string; speaker: string } | null }) => void): () => void;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function kindIcon(kind: string): string {
  switch (kind) {
    case "file_edit": return "✎";
    case "shell":     return "$";
    case "thinking":  return "…";
    case "tool":      return "⚙";
    default:          return "·";
  }
}

/**
 * Mounts the agent panel into `container`. Subscribes to `activeAgentRun` in
 * the store and to `agent.step` / `agent.approval` / `agent.progress` events.
 * Returns an unsubscribe / cleanup function.
 */
export function mountAgentPanel(
  container: HTMLElement,
  store: AgentStore,
  events: AgentEvents,
): () => void {
  // Internal state
  let steps: AgentStep[] = [];
  let approval: AgentApproval | null = null;
  let progress: AgentProgress | null = null;

  function render(): void {
    const run = store.get().activeAgentRun;

    if (!run) {
      // Remove or hide the panel when no agent is running.
      const existing = container.querySelector(".agent-panel") as HTMLElement | null;
      if (existing) existing.style.display = "none";
      return;
    }

    // Find or create the panel element.
    let panel = container.querySelector(".agent-panel") as HTMLElement | null;
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "agent-panel";
      container.appendChild(panel);
    }
    panel.style.display = "";

    // Progress bar HTML.
    const progressHtml = progress
      ? `<div class="agent-progress">
           <span class="agent-progress-phase">${escHtml(progress.phase)}</span>
           ${progress.percent !== undefined
             ? `<div class="agent-progress-bar"><i style="width:${Math.round(progress.percent * 100)}%"></i></div>`
             : ""}
         </div>`
      : "";

    // Steps log HTML.
    const stepsHtml = steps.length > 0
      ? `<div class="agent-steps">${steps
          .map((s) => `<div class="agent-step-row">
              <span class="agent-step-icon">${kindIcon(s.kind)}</span>
              <span class="agent-step-summary">${escHtml(s.summary)}</span>
            </div>`)
          .join("")}
         </div>`
      : "";

    // Approval card HTML.
    const approvalHtml = approval
      ? `<div class="agent-approval">
           <div class="agent-approval-prompt">${escHtml(approval.prompt)}</div>
           <div class="agent-approval-buttons">
             ${approval.choices
               .map(
                 (c) =>
                   `<button class="agent-choice-btn" data-choice="${escHtml(c)}">${escHtml(c)}</button>`,
               )
               .join("")}
           </div>
         </div>`
      : "";

    panel.innerHTML = `
      <div class="agent-panel-head">
        <span class="label-tag">Agent · Pepper</span>
        <span class="agent-task">${escHtml(run.task)}</span>
        <button class="agent-cancel-btn">cancel</button>
      </div>
      ${progressHtml}
      ${stepsHtml}
      ${approvalHtml}`;

    // Wire approval buttons.
    const choiceBtns = panel.querySelectorAll<HTMLButtonElement>(".agent-choice-btn");
    for (const btn of choiceBtns) {
      btn.addEventListener("click", () => {
        const choice = btn.dataset["choice"] ?? "";
        events.sendAgentApprove(run.runId, choice);
      });
    }

    // Wire cancel button.
    const cancelBtn = panel.querySelector<HTMLButtonElement>(".agent-cancel-btn");
    cancelBtn?.addEventListener("click", () => {
      events.sendAgentCancel(run.runId);
    });
  }

  // Subscribe to store changes (mainly to react to activeAgentRun toggling).
  const unsubStore = store.subscribe(() => {
    // Reset per-run state when run changes or clears.
    const run = store.get().activeAgentRun;
    if (!run) {
      steps = [];
      approval = null;
      progress = null;
    }
    render();
  });

  // Subscribe to agent events.
  const unsubStep = events.on("agent.step", (payload) => {
    const run = store.get().activeAgentRun;
    if (!run || payload.runId !== run.runId) return;
    steps.push(payload);
    render();
  });

  const unsubApproval = events.on("agent.approval", (payload) => {
    const run = store.get().activeAgentRun;
    if (!run || payload.runId !== run.runId) return;
    approval = payload;
    render();
  });

  const unsubProgress = events.on("agent.progress", (payload) => {
    const run = store.get().activeAgentRun;
    if (!run || payload.runId !== run.runId) return;
    progress = payload;
    render();
  });

  // Initial render.
  render();

  return () => {
    unsubStore();
    unsubStep();
    unsubApproval();
    unsubProgress();
    container.querySelector(".agent-panel")?.remove();
  };
}
