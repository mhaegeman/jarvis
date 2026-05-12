export type ConvState = "idle" | "listening" | "thinking" | "speaking";

export interface TelemetryEvent {
  ts: number; // epoch ms
  level: "info" | "ok" | "warn" | "error";
  message: string;
}

export interface SttPartial {
  text: string;
}
export interface SttFinal {
  text: string;
}
export interface LlmToken {
  delta: string;
}
export interface TtsSentence {
  text: string;
  audioId: string;
}
export interface TtsAudioChunk {
  audioId: string;
  samples: Float32Array;
}
export interface TtsEnd {
  audioId: string;
}
export interface ProtocolError {
  code: string;
  message: string;
}

export interface PanelDataSystem {
  load: number;
  tokensPerMin: number;
  sessionId: string;
  modelName: string;
}
export interface PanelDataMemory {
  contextUsed: number;
  contextMax: number;
}
export interface PanelDataNetwork {
  endpoint: string;
  latencyMs: number | null;
  packets: number;
  sendQueueDepth: number;
  sendQueueMax: number;
}
export interface PanelDataTasks {
  queued: number;
  active: number;
  done: number;
}
export interface PanelDataCalendarEntry {
  time: string;
  title: string;
  durationMin: number;
  attendees: string[];
  room: string | null;
}
export interface StateSnapshot {
  system: PanelDataSystem;
  memory: PanelDataMemory;
  network: PanelDataNetwork;
  tasks: PanelDataTasks;
}
export interface CalendarUpdate {
  entries: PanelDataCalendarEntry[];
}

export type EventMap = {
  ready: void;
  "stt.partial": SttPartial;
  "stt.final": SttFinal;
  "llm.token": LlmToken;
  "llm.end": void;
  "tts.sentence": TtsSentence;
  "tts.audioChunk": TtsAudioChunk;
  "tts.end": TtsEnd;
  error: ProtocolError;
  telemetry: TelemetryEvent;
  "state.snapshot": StateSnapshot;
  "calendar.update": CalendarUpdate;
};

export type EventName = keyof EventMap;
export type EventHandler<E extends EventName> = (payload: EventMap[E]) => void;
