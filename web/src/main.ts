import "./style.css";
import { Header } from "@/ui/Header";
import { SystemPanel } from "@/ui/panels/SystemPanel";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";
import { TasksPanel } from "@/ui/panels/TasksPanel";
import { AudioPanel, type MicStatus } from "@/ui/panels/AudioPanel";
import { Centerpiece } from "@/ui/Centerpiece";
import { TelemetryPanel } from "@/ui/panels/TelemetryPanel";
import type { TelemetryEvent } from "@/types";
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
const telemetry = new TelemetryPanel('[data-cell="right"]');
const audio = new AudioPanel('[data-slot="audio"]');
const micStatus: MicStatus = { kind: "unprompted" };
const center = new Centerpiece('[data-cell="center"]');
const ambientAmp = 0.08;

const seedEvents: TelemetryEvent[] = [
  { ts: Date.now() - 5000, level: "ok", message: "whisper.asr ready" },
  { ts: Date.now() - 4500, level: "ok", message: "tts.openvoice loaded" },
  { ts: Date.now() - 4000, level: "ok", message: "llm.local connected · 7B" },
  { ts: Date.now() - 3000, level: "info", message: "kb.index synced · 24,182 docs" },
  { ts: Date.now() - 2000, level: "warn", message: "gpu.temp 71°C" },
  { ts: Date.now() - 1000, level: "ok", message: "context.bridge open" },
];

function tick(): void {
  const u = Date.now() - start;
  header.render({ uptimeMs: u });
  system.render({ uptimeMs: u, load: 0.42, tokensPerMin: 1284, sessionId: "A271" });
  memory.render({ contextUsed: 62000, contextMax: 200000, recallPct: 98.2 });
  calendar.render({ entries: TODAY });
  network.render({ endpoint: "local", latencyMs: 12, packets: 0, busyPct: 18 });
  tasks.render({ queued: 3, active: 1, done: 14 });
  telemetry.render({ events: seedEvents });
  audio.render({ inputDb: -72, outputDb: -31, inputBarPct: 30, mic: micStatus });
  center.renderFrame(ambientAmp + Math.sin(u * 0.001) * 0.02, "idle");
  requestAnimationFrame(tick);
}
tick();
document.body.dataset.ready = "true";
