import "./style.css";

import type {
  ConvState,
  TelemetryEvent,
  PanelDataSystem,
  PanelDataMemory,
  PanelDataNetwork,
  PanelDataTasks,
  PanelDataCalendarEntry,
} from "@/types";
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

import { connect } from "@/events/connect";
import { createMicCapture, probeMicSupport } from "@/audio/micCapture";
import { analyserDb } from "@/audio/analyzer";

interface PanelData {
  system: PanelDataSystem | null;
  memory: PanelDataMemory | null;
  network: PanelDataNetwork | null;
  tasks: PanelDataTasks | null;
  calendar: { entries: PanelDataCalendarEntry[]; syncing: boolean };
}

type WsState = "live" | "demo" | "reconnecting";

interface AppState {
  state: ConvState;
  micAmplitude: number;
  micStatus: MicStatus;
  telemetry: TelemetryEvent[];
  centerTitle: string;
  panelData: PanelData;
  wsState: WsState;
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
  panelData: {
    system: null,
    memory: null,
    network: null,
    tasks: null,
    calendar: { entries: [], syncing: false },
  },
  wsState: "live",
});

const log = (level: TelemetryEvent["level"], message: string): void => {
  store.update((d) => ({
    telemetry: [{ ts: Date.now(), level, message }, ...d.telemetry].slice(0, 14),
  }));
};

// EventSource: try real WS, fall back to mock if backend is unreachable.
const audioCtx = new AudioContext({ sampleRate: 16000 });
let activeMicStream: MediaStream | null = null;
const micSource = async (): Promise<MediaStreamAudioSourceNode> => {
  if (audioCtx.state === "suspended") await audioCtx.resume();
  activeMicStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: 16000,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  return audioCtx.createMediaStreamSource(activeMicStream);
};
const stopMicStream = (): void => {
  activeMicStream?.getTracks().forEach((t) => t.stop());
  activeMicStream = null;
};
const wsUrl =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://localhost:8000/ws";
const { events, mode } = await connect({
  url: wsUrl,
  audioCtx,
  openTimeoutMs: 1000,
  micSource,
});
const liveAnalyser: AnalyserNode | null =
  mode === "live"
    ? ((events as unknown as { analyser?: AnalyserNode }).analyser ?? null)
    : null;

// Track open TTS sentences so we only return to idle after the last one and
// after the LLM has signalled the end of generation.
const openAudioIds = new Set<string>();
let llmEnded = false;

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
  if (status.kind === "granted") {
    // Permission already granted; ensure the stream is (re)started.
    // mic.start() is idempotent.
    await mic.start();
    return true;
  }
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

// micHeld: true while the button is physically down. Cleared on any release.
// micReady: true once beginListening() resolves and the worklet is streaming.
// Together they let us give immediate "Listening." feedback while still
// preventing a quick tap from triggering "thinking" before any audio lands.
let micHeld = false;
let micReady = false;

// Shared actions (Controls + keyboard both call into this)
const actions = {
  onMicDown: async (): Promise<void> => {
    if (store.get().state !== "idle") return;
    micHeld = true;
    micReady = false;
    const ok = await ensureMic();
    if (!ok) {
      micHeld = false;
      return;
    }
    // Show "Listening." immediately so the user knows to start speaking,
    // even though the worklet is still starting up.
    tryTransition("startListening");
    store.update(() => ({ centerTitle: "Listening." }));
    try {
      await events.beginListening();
    } catch (err) {
      log("warn", `mic start failed: ${String(err)}`);
      events.endListening();
      stopMicStream();
      micHeld = false;
      tryTransition("interrupt");
      store.update(() => ({ centerTitle: "Standing by." }));
      return;
    }
    micReady = true;
    if (!micHeld) {
      // Released while worklet was starting — worklet is up but user is gone.
      // Send audio.end so the server isn't left hanging, then cancel.
      events.endListening();
      mic.stop();
      stopMicStream();
      tryTransition("cancelListening");
      store.update(() => ({ centerTitle: "Standing by." }));
    }
  },
  onMicUp: (): void => {
    micHeld = false;
    if (store.get().state !== "listening") {
      // Released before startListening transition — abort in-flight setup.
      events.endListening();
      mic.stop();
      stopMicStream();
      return;
    }
    if (!micReady) {
      // Worklet still starting — abort it and let the user retry.
      // endListening() fires listenAbort so beginListening() exits early.
      events.endListening();
      mic.stop();
      stopMicStream();
      tryTransition("cancelListening");
      store.update(() => ({ centerTitle: "Standing by." }));
      return;
    }
    events.endListening();
    mic.stop();
    stopMicStream();
    tryTransition("stopListening");
    store.update(() => ({ centerTitle: "Thinking." }));
  },
  onInterrupt: (): void => {
    micHeld = false;
    micReady = false;
    events.interrupt();
    mic.stop();
    stopMicStream();
    center.interruptTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onIdle: (): void => {
    micHeld = false;
    micReady = false;
    events.interrupt();
    mic.stop();
    stopMicStream();
    center.clearTranscript();
    tryTransition("interrupt");
    store.update(() => ({ centerTitle: "Standing by." }));
  },
  onRunScenario: (): void => {
    if (store.get().state !== "idle") return;
    void Promise.resolve(events.beginListening()).then(() => {
      tryTransition("startListening");
      store.update(() => ({ centerTitle: "Listening." }));
      setTimeout(() => {
        events.endListening();
        tryTransition("stopListening");
        store.update(() => ({ centerTitle: "Thinking." }));
      }, 1500);
    });
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
  // Reset reply tracking for the new turn.
  openAudioIds.clear();
  llmEnded = false;
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
  llmEnded = true;
  maybeFinishSpeaking();
});
events.on("tts.sentence", ({ audioId }) => {
  openAudioIds.add(audioId);
});
events.on("tts.end", ({ audioId }) => {
  openAudioIds.delete(audioId);
  maybeFinishSpeaking();
});

function maybeFinishSpeaking(): void {
  if (store.get().state !== "speaking") return;
  if (!llmEnded || openAudioIds.size > 0) return;
  setTimeout(() => {
    if (store.get().state !== "speaking") return;
    tryTransition("replyEnd");
    store.update(() => ({ centerTitle: "Standing by." }));
  }, 200);
}
events.on("error", (e) => log("error", `${e.code}: ${e.message}`));
events.on("telemetry", (t) => {
  store.update((d) => ({ telemetry: [t, ...d.telemetry].slice(0, 14) }));
  if (mode === "live") {
    if (t.message.startsWith("reconnecting")) {
      store.update(() => ({ wsState: "reconnecting" }));
    } else if (t.message === "reconnected") {
      store.update(() => ({ wsState: "live" }));
    }
  }
});
events.on("state.snapshot", (snap) =>
  store.update((d) => ({
    panelData: {
      ...d.panelData,
      system: snap.system,
      memory: snap.memory,
      network: snap.network,
      tasks: snap.tasks,
    },
  })),
);
events.on("calendar.update", ({ entries }) =>
  store.update((d) => ({
    panelData: { ...d.panelData, calendar: { entries, syncing: false } },
  })),
);

// Boot — connect() already awaited events.start() for both live and demo modes.
store.update(() => ({ wsState: mode === "demo" ? "demo" : "live" }));
log("ok", `session ready (${mode})`);
if (mode === "demo") {
  log("warn", "backend offline — demo mode");
}
document.body.dataset.ready = "true";

// Render loop
function tick(): void {
  const s = store.get();
  const u = Date.now() - start;

  const pd = s.panelData;
  header.render({ uptimeMs: u, wsState: s.wsState });
  system.render({
    uptimeMs: u,
    load: pd.system?.load ?? 0,
    tokensPerMin: pd.system?.tokensPerMin ?? 0,
    sessionId: pd.system?.sessionId ?? "----",
    modelName: pd.system?.modelName ?? "—",
  });
  memory.render({
    contextUsed: pd.memory?.contextUsed ?? 0,
    contextMax: pd.memory?.contextMax ?? 200000,
  });
  calendar.render({
    entries: pd.calendar.entries,
    syncing: pd.calendar.syncing,
    onSync: () => {
      store.update((d) => ({
        panelData: {
          ...d.panelData,
          calendar: { ...d.panelData.calendar, syncing: true },
        },
      }));
      events.syncCalendar();
    },
  });
  network.render({
    endpoint: pd.network?.endpoint ?? (mode === "demo" ? "demo" : "local"),
    latencyMs: pd.network?.latencyMs ?? null,
    packets: pd.network?.packets ?? 0,
    sendQueueDepth: pd.network?.sendQueueDepth ?? 0,
    sendQueueMax: pd.network?.sendQueueMax ?? 256,
  });
  tasks.render({
    queued: pd.tasks?.queued ?? 0,
    active: pd.tasks?.active ?? 0,
    done: pd.tasks?.done ?? 0,
  });
  telemetry.render({ events: s.telemetry });

  // Audio meter
  const meter =
    s.state === "listening"
      ? s.micAmplitude * 100
      : s.state === "speaking"
        ? 60 + Math.random() * 30
        : 5 + Math.random() * 5;
  // outputDb: real RMS of the playback analyser when in live mode + speaking;
  // synthetic fallback otherwise (silence/idle reports the analyser noise floor as -∞).
  let outputDb: number;
  if (mode === "live" && liveAnalyser && s.state === "speaking") {
    const db = analyserDb(liveAnalyser);
    outputDb = db === -Infinity ? -80 : db;
  } else {
    outputDb = -60 + meter * 0.4;
  }
  audioPanel.render({
    inputDb: -80 + (s.state === "listening" ? s.micAmplitude * 60 : Math.random() * 4),
    outputDb,
    inputBarPct: meter,
    mic: s.micStatus,
  });

  controls.render({ state: s.state });
  center.setStateClass(s.state);
  if (s.centerTitle) center.setTitle(s.centerTitle);

  // Centerpiece amplitude: prefer live signals (mic in, TTS analyser out) over synthetic.
  let amp: number;
  if (s.state === "listening") {
    amp = s.micAmplitude;
  } else if (s.state === "speaking" && liveAnalyser) {
    const data = new Float32Array(liveAnalyser.fftSize);
    liveAnalyser.getFloatTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    amp = Math.min(1, Math.sqrt(sum / data.length) * 4);
  } else if (s.state === "thinking") {
    amp = 0.18 + Math.sin(u * 0.004) * 0.05;
  } else if (s.state === "speaking") {
    amp = 0.45 + Math.random() * 0.35;
  } else {
    amp = 0.08 + Math.sin(u * 0.001) * 0.02;
  }
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
