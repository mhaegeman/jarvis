import "./style.css";
import { Header } from "@/ui/Header";
import { SystemPanel } from "@/ui/panels/SystemPanel";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";
import { TasksPanel } from "@/ui/panels/TasksPanel";
import { TODAY } from "@/data/calendar";

const start = Date.now();

const header = new Header('[data-cell="top"]');
const system = new SystemPanel('[data-cell="tl"]');
const memory = new MemoryPanel('[data-cell="tr"]');
const calendar = new CalendarPanel('[data-cell="bl"]');
const network = new NetworkPanel('[data-cell="br"]');

document.querySelector('[data-cell="left"]')!.innerHTML = `
  <div class="panel-stack">
    <div data-slot="audio"></div>
    <div data-slot="tasks"></div>
  </div>`;
const tasks = new TasksPanel('[data-slot="tasks"]');

function tick(): void {
  const u = Date.now() - start;
  header.render({ uptimeMs: u });
  system.render({ uptimeMs: u, load: 0.42, tokensPerMin: 1284, sessionId: "A271" });
  memory.render({ contextUsed: 62000, contextMax: 200000, recallPct: 98.2 });
  calendar.render({ entries: TODAY });
  network.render({ endpoint: "local", latencyMs: 12, packets: 0, busyPct: 18 });
  tasks.render({ queued: 3, active: 1, done: 14 });
  requestAnimationFrame(tick);
}
tick();
document.body.dataset.ready = "true";
