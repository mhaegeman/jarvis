import "./style.css";

import type {
  ConvState,
  TelemetryEvent,
  PanelDataSystem,
  PanelDataMemory,
  PanelDataNetwork,
  PanelDataTasks,
  PanelDataCalendarEntry,
  Speaker,
  DispatchPlan,
} from "@/types";
import { transition, canTransition } from "@/state/stateMachine";
import { createStore } from "@/state/store";
import type { MicStatus } from "@/ui/panels/AudioPanel";
import { connect } from "@/events/connect";
import { createMicCapture, probeMicSupport } from "@/audio/micCapture";

import { mount } from "@/router";
import { createLoginPage } from "@/ui/login/LoginPage";
import { createCompassApp } from "@/ui/compass/CompassApp";
import { CommandHistory } from "@/ui/compass/commandHistory";

interface PanelData {
  system: PanelDataSystem | null;
  memory: PanelDataMemory | null;
  network: PanelDataNetwork | null;
  tasks: PanelDataTasks | null;
  calendar: { entries: PanelDataCalendarEntry[]; syncing: boolean };
}

type WsState = "live" | "demo" | "reconnecting";

export interface AppState {
  state: ConvState;
  micAmplitude: number;
  micStatus: MicStatus;
  telemetry: TelemetryEvent[];
  centerTitle: string;
  panelData: PanelData;
  wsState: WsState;
  // ─── Phase 4 additions ───
  currentSpeaker: Speaker | null;
  lastPlan: DispatchPlan | null;
  activeAgentRun: { runId: string; task: string; speaker: Speaker } | null;
}

export const store = createStore<AppState>({
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
  currentSpeaker: null,
  lastPlan: null,
  activeAgentRun: null,
});

export const log = (level: TelemetryEvent["level"], message: string): void => {
  store.update((d) => ({
    telemetry: [{ ts: Date.now(), level, message }, ...d.telemetry].slice(0, 14),
  }));
};

// Audio / WS setup — shared across surfaces
const audioCtx = new AudioContext({ sampleRate: 16000 });
let activeMicStream: MediaStream | null = null;
const micSource = async (): Promise<MediaStreamAudioSourceNode> => {
  if (audioCtx.state === "suspended") await audioCtx.resume();
  activeMicStream = await navigator.mediaDevices.getUserMedia({
    audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  return audioCtx.createMediaStreamSource(activeMicStream);
};
export const stopMicStream = (): void => {
  activeMicStream?.getTracks().forEach((t) => t.stop());
  activeMicStream = null;
};

const wsUrl = (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://localhost:8000/ws";
export const { events, mode } = await connect({ url: wsUrl, audioCtx, openTimeoutMs: 1000, micSource });

export const liveAnalyser: AnalyserNode | null =
  mode === "live" ? ((events as unknown as { analyser?: AnalyserNode }).analyser ?? null) : null;

const openAudioIds = new Set<string>();
let llmEnded = false;

export const mic = createMicCapture();
mic.onAmplitude((level) => store.update(() => ({ micAmplitude: level })));

export async function ensureMic(): Promise<boolean> {
  const status = store.get().micStatus;
  if (status.kind === "granted") { await mic.start(); return true; }
  const probe = await probeMicSupport();
  if (probe !== true) {
    const s: MicStatus =
      probe.kind === "denied" || probe.kind === "unsupported"
        ? probe
        : { kind: "error", message: `mic.${probe.kind}` };
    store.update(() => ({ micStatus: s }));
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

export function tryTransition(event: Parameters<typeof transition>[1]): void {
  const cur = store.get().state;
  if (!canTransition(cur, event)) return;
  const next = transition(cur, event);
  store.update(() => ({ state: next }));
  log("info", `state: ${cur} → ${next} (${event})`);
}

// Wire WS events into store
events.on("stt.partial", ({ text }) => {
  store.update(() => ({ centerTitle: text || "Listening." }));
});
events.on("stt.final", ({ text }) => {
  log("info", `you: ${text}`);
  CommandHistory.push(text);
  openAudioIds.clear();
  llmEnded = false;
});
events.on("llm.token", ({ delta, speaker }) => {
  if (store.get().state === "thinking") {
    tryTransition("replyStart");
    store.update(() => ({ centerTitle: "" }));
  }
  store.update((d) => ({
    centerTitle: d.centerTitle + delta,
    currentSpeaker: speaker ?? d.currentSpeaker,
  }));
});
events.on("llm.segment_end", () => {
  // No-op for now: next llm.token's speaker field flips the centerpiece tint.
});
events.on("dispatch.plan", (plan) => {
  store.update(() => ({ lastPlan: plan }));
});
events.on("agent.start", ({ runId, task, speaker }) => {
  store.update(() => ({ activeAgentRun: { runId, task, speaker } }));
});
events.on("agent.end", () => {
  store.update(() => ({ activeAgentRun: null }));
});
events.on("llm.end", () => { llmEnded = true; maybeFinishSpeaking(); });
events.on("tts.sentence", ({ audioId }) => { openAudioIds.add(audioId); });
events.on("tts.end", ({ audioId }) => {
  openAudioIds.delete(audioId);
  maybeFinishSpeaking();
});
events.on("error", (e) => log("error", `${e.code}: ${e.message}`));
events.on("telemetry", (t) => {
  store.update((d) => ({ telemetry: [t, ...d.telemetry].slice(0, 14) }));
  if (mode === "live") {
    if (t.message.startsWith("reconnecting")) store.update(() => ({ wsState: "reconnecting" }));
    else if (t.message === "reconnected") store.update(() => ({ wsState: "live" }));
  }
});
events.on("state.snapshot", (snap) =>
  store.update((d) => ({
    panelData: { ...d.panelData, system: snap.system, memory: snap.memory, network: snap.network, tasks: snap.tasks },
  })),
);
events.on("calendar.update", ({ entries }) =>
  store.update((d) => ({ panelData: { ...d.panelData, calendar: { entries, syncing: false } } })),
);

function maybeFinishSpeaking(): void {
  if (store.get().state !== "speaking") return;
  if (!llmEnded || openAudioIds.size > 0) return;
  setTimeout(() => {
    if (store.get().state !== "speaking") return;
    tryTransition("replyEnd");
    store.update(() => ({ centerTitle: "Standing by." }));
  }, 200);
}

// Boot
store.update(() => ({ wsState: mode === "demo" ? "demo" : "live" }));
log("ok", `session ready (${mode})`);
if (mode === "demo") log("warn", "backend offline — demo mode");

// Mount login first; on success swap to compass
mount(() => createLoginPage(() => {
  mount(() => createCompassApp());
}));
