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
// ─── Phase 2/3 additions ────────────────────────────────────────────────

export type Speaker = "jarvis" | "pepper";
export type Tier = "fast" | "balanced" | "deep";
export type SegmentMode = "chat" | "codex_agent";
export type HandoffStyle = "flat" | "soft";

export interface LlmToken {
  delta: string;
  speaker?: Speaker;
  segmentIdx?: number;
}
export interface TtsSentence {
  text: string;
  audioId: string;
  speaker?: Speaker;
}

export interface LlmSegmentEnd {
  speaker: Speaker;
  segmentIdx: number;
}

export interface PlanSegment {
  speaker: Speaker;
  tier: Tier;
  mode: SegmentMode;
  intent: string;
  handoff_style?: HandoffStyle | null;
}

export interface DispatchPlan {
  turnId: string;
  segments: PlanSegment[];
  rationale: string;
}

export interface AgentStart {
  speaker: Speaker;
  task: string;
  runId: string;
}

export interface AgentStep {
  runId: string;
  kind: "thinking" | "file_edit" | "shell" | "tool" | string;
  summary: string;
  detail?: Record<string, unknown>;
}

export interface AgentApproval {
  runId: string;
  prompt: string;
  choices: string[];
}

export interface AgentProgress {
  runId: string;
  phase: string;
  percent?: number;
}

export interface AgentEnd {
  runId: string;
  status: "ok" | "failed" | "cancelled";
  summary: string;
}

export interface PersonaStatus {
  model: string;
  tier: Tier;
  status: "idle" | "thinking" | "speaking" | "agent";
}

export interface PanelDataSystemPersonas {
  jarvis?: PersonaStatus;
  pepper?: PersonaStatus;
  lastDispatch?: { turnId: string; segments: PlanSegment[] } | null;
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
  personas?: PanelDataSystemPersonas;
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
  "llm.segment_end": LlmSegmentEnd;
  "llm.end": void;
  "tts.sentence": TtsSentence;
  "tts.audioChunk": TtsAudioChunk;
  "tts.end": TtsEnd;
  "dispatch.plan": DispatchPlan;
  "agent.start": AgentStart;
  "agent.step": AgentStep;
  "agent.approval": AgentApproval;
  "agent.progress": AgentProgress;
  "agent.end": AgentEnd;
  error: ProtocolError;
  telemetry: TelemetryEvent;
  "state.snapshot": StateSnapshot;
  "calendar.update": CalendarUpdate;
};

export type EventName = keyof EventMap;
export type EventHandler<E extends EventName> = (payload: EventMap[E]) => void;
