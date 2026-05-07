import "./style.css";

import type { ConvState, TelemetryEvent } from "@/types";
import { transition, canTransition } from "@/state/stateMachine";
import { createStore } from "@/state/store";

import { Header } from "@/ui/Header";
import { SystemPanel } from "@/ui/panels/SystemPanel";
import { MemoryPanel } from "@/ui/panels/MemoryPanel";
import { CalendarPanel } from "@/ui/panels/CalendarPanel";
import { NetworkPanel } from "@/ui/panels/NetworkPanel";
import { TasksPanel } from "@/ui/panels/TasksPanel";
import { TelemetryPanel } from "@/ui/panels/TelemetryPanel";
import { AudioPanel, type MicStatus } from "@/ui/panels/AudioPanel";
import { Centerpiece } from "@/ui/Centerpiece";
import { Controls } from "@/ui/Controls";
import { attachKeyboard } from "@/ui/keyboard";

import { TODAY } from "@/data/calendar";
import { MockEventSource } from "@/events/mockEventSource";
import { createMicCapture, probeMicSupport } from "@/audio/micCapture";

interface AppState {
  state: ConvState;
  micAmplitude: number;
  micStatus: MicStatus;
  telemetry: TelemetryEvent[];
  centerTitle: string;
}

const start = Date.now();
const params = new URLSearchParams(location.search);
const devMode = params.get("dev") === "1";

const store = createStore<AppState>({
  state: "idle",
  micAmplitude: 0.08,
  micStatus: { kind: "unprompted" },
  telemetry: [],
  centerTitle: "Standing by.",
});

const log = (level: TelemetryEvent["level"], message: string): void => {
  store.update((d) => ({
    telemetry: [{ ts: Date.now(), level, message }, ...d.telemetry].slice(0, 14),
  }));
};

// EventSource (mock for spec-01)
const events = new MockEventSource();

// Components
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
const audioPanel = new AudioPanel('[data-slot="audio"]');
const tasks = new TasksPanel('[data-slot="tasks"]');
const telemetry = new TelemetryPanel('[data-cell="right"]');
const center = new Centerpiece('[data-cell="center"]');

// Mic capture
const mic = createMicCapture();
mic.onAmplitude((level) => store.update(() => ({ micAmplitude: level })));

async function ensureMic(): Promise<boolean> {
  const status = store.get().micStatus;
  if (status.kind === "granted") return true;
  const probe = await probeMicSupport();
  if (probe !== true) {
    const status: MicStatus =
      probe.kind === "denied" || probe.kind === "unsupported"
        ? probe
        : { kind: "error", message: `mic.${probe.kind}` };
    store.update(() => ({ micStatus: status }));
    log("warn", `mic: ${probe.kind}`);
    return false;
  }
  try {
    await mic.start();
    store.update(() => ({ micStatus: { kind: "granted" } }));
    log("ok", "mic: granted");
    return true;
  } catch (err) {
    const denied =
      err instanceof DOMException &&
      (err.name === "NotAllowedError" || err.name === "PermissionDeniedError");
    store.update(() => ({
      micStatus: denied ? { kind: "denied" } : { kind: "error", message: String(err) },
    }));
    log("warn", denied ? "mic: denied" : `mic: error ${String(err)}`);
    return false;
  }
}

function tryTransition(event: Parameters<typeof transition>[1]): void {
  const cur = store.get().state;
  if (!canTransition(cur, event)) return;
  const next = transition(cur, event);
  store.update(() => ({ state: next }));
  document.body.dataset.state = next;
  log("info", `state: ${cur} → ${next} (${event})`);
}

// Shared actions (Controls + keyboard both call into this)
const actions = {
  onMicDown: async (): Promise<void> => {
    if (store.get().state !== "idle") return;
    const ok = await ensureMic();
    if (ok) {
      events.beginListening();
      tryTransition("startListening");
      store.update(() => ({ centerTitle: "Listening." }));
    }
  },
  onMicUp: (): void => {
    if (store.get().state !== "listening") return;
    events.endListening();
    tryTransition("stopListening");
    store.update(() => ({ centerTitle: "Thinking." }));
  },
  onInterrupt: (): void => {
    events.interrupt();
    center.interruptTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onIdle: (): void => {
    events.interrupt();
    center.clearTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onRunScenario: (): void => {
    if (store.get().state !== "idle") return;
    events.beginListening();
    tryTransition("startListening");
    store.update(() => ({ centerTitle: "Listening." }));
    setTimeout(() => {
      events.endListening();
      tryTransition("stopListening");
      store.update(() => ({ centerTitle: "Thinking." }));
    }, 1500);
  },
};

const controls = new Controls('[data-cell="bottom"]', actions, devMode);

attachKeyboard(window, {
  onMicDown: () => {
    void actions.onMicDown();
  },
  onMicUp: actions.onMicUp,
  onInterrupt: actions.onInterrupt,
});

// Event source wiring
events.on("stt.partial", ({ text }) => {
  if (store.get().state === "listening") center.setTitle(text || "Listening.");
});
events.on("stt.final", ({ text }) => {
  log("info", `you: ${text}`);
});
events.on("llm.token", ({ delta }) => {
  if (store.get().state === "thinking") {
    tryTransition("replyStart");
    store.update(() => ({ centerTitle: "" }));
    center.clearTranscript();
  }
  center.appendToken(delta);
});
events.on("llm.end", () => {
  // Stay in `speaking` until tts.end of the last sentence; mock fires that shortly.
});
events.on("tts.end", () => {
  // Naive: any tts.end while speaking ends the session. Real impl tracks queue.
  if (store.get().state === "speaking") {
    setTimeout(() => {
      tryTransition("replyEnd");
      store.update(() => ({ centerTitle: "Standing by." }));
    }, 200);
  }
});
events.on("error", (e) => log("error", `${e.code}: ${e.message}`));
events.on("telemetry", (t) =>
  store.update((d) => ({ telemetry: [t, ...d.telemetry].slice(0, 14) })),
);

// Boot
void (async () => {
  await events.start();
  log("ok", "session ready");
  document.body.dataset.ready = "true";
})();

// Render loop
function tick(): void {
  const s = store.get();
  const u = Date.now() - start;

  header.render({ uptimeMs: u });
  system.render({ uptimeMs: u, load: 0.42, tokensPerMin: 1284, sessionId: "A271" });
  memory.render({ contextUsed: 62000, contextMax: 200000, recallPct: 98.2 });
  calendar.render({ entries: TODAY });
  network.render({ endpoint: "local", latencyMs: 12, packets: 0, busyPct: 18 });
  tasks.render({ queued: 3, active: 1, done: 14 });
  telemetry.render({ events: s.telemetry });

  // Audio meter
  const meter =
    s.state === "listening"
      ? s.micAmplitude * 100
      : s.state === "speaking"
        ? 60 + Math.random() * 30
        : 5 + Math.random() * 5;
  audioPanel.render({
    inputDb: -80 + (s.state === "listening" ? s.micAmplitude * 60 : Math.random() * 4),
    outputDb: -60 + meter * 0.4,
    inputBarPct: meter,
    mic: s.micStatus,
  });

  controls.render({ state: s.state });
  center.setStateClass(s.state);
  if (s.centerTitle) center.setTitle(s.centerTitle);

  // Synthetic amplitude when not listening
  let amp: number;
  if (s.state === "listening") amp = s.micAmplitude;
  else if (s.state === "thinking") amp = 0.18 + Math.sin(u * 0.004) * 0.05;
  else if (s.state === "speaking") amp = 0.45 + Math.random() * 0.35;
  else amp = 0.08 + Math.sin(u * 0.001) * 0.02;
  center.renderFrame(amp, s.state);

  requestAnimationFrame(tick);
}
tick();

// Mic banner button delegation
document.body.addEventListener("click", (e) => {
  const t = e.target;
  if (t instanceof HTMLElement && t.dataset.action === "mic-request") {
    void ensureMic();
  }
});
